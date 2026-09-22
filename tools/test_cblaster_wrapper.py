#!/usr/bin/env python3
"""Contract tests for the cblaster wrapper; no biological search is performed."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "skills/genecluster-superpowers/scripts/run-cblaster.sh"
TEMPLATE = ROOT / "tools/recommended/cblaster/query-cluster.sh.template"
MIRROR_TEMPLATE = ROOT / "skills/genecluster-superpowers/tools/recommended/cblaster/query-cluster.sh.template"


FAKE_CBLASTER = r'''#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

args = sys.argv[1:]
log = Path(os.environ["FAKE_CBLASTER_LOG"])
with log.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(args) + "\n")

def value(flag):
    index = args.index(flag)
    return args[index + 1]

command = args[0]
if command == "makedb":
    source = Path(args[1])
    if source.suffix not in {".gbk", ".gb", ".genbank", ".gff", ".gff3", ".gtf"}:
        raise SystemExit("makedb received a non-annotated input")
    prefix = Path(value("--name"))
    prefix.with_suffix(".dmnd").touch()
    prefix.with_suffix(".sqlite3").touch()
elif command == "search":
    Path(value("--session_file")).write_text("{}", encoding="utf-8")
    Path(value("--output")).write_text("summary\n", encoding="utf-8")
    Path(value("--plot")).write_text("plot\n", encoding="utf-8")
elif command == "extract_clusters":
    if not args[1].endswith(".json"):
        raise SystemExit("extract_clusters requires a JSON session")
    output = Path(value("--output"))
    output.mkdir(parents=True, exist_ok=True)
    (output / "cluster1.gbk").write_text("LOCUS synthetic\n", encoding="utf-8")
else:
    raise SystemExit(f"unexpected cblaster command: {command}")
'''


FAKE_CLINKER = r'''#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

args = sys.argv[1:]
with Path(os.environ["FAKE_CLINKER_LOG"]).open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(args) + "\n")
Path(args[args.index("--plot") + 1]).write_text("plot\n", encoding="utf-8")
'''


def write_executable(directory: Path, name: str, body: str) -> None:
    path = directory / name
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


class CblasterWrapperTests(unittest.TestCase):
    def fake_environment(self, root: Path) -> dict[str, str]:
        bin_dir = root / "bin"
        bin_dir.mkdir(exist_ok=True)
        write_executable(bin_dir, "cblaster", FAKE_CBLASTER)
        write_executable(bin_dir, "clinker", FAKE_CLINKER)
        write_executable(bin_dir, "diamond", "#!/usr/bin/env bash\nexit 0\n")
        env = os.environ.copy()
        env["PATH"] = f"{bin_dir}:{env['PATH']}"
        env["FAKE_CBLASTER_LOG"] = str(root / "cblaster.log")
        env["FAKE_CLINKER_LOG"] = str(root / "clinker.log")
        return env

    def run_wrapper(self, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(WRAPPER), *args],
            cwd=ROOT,
            env=self.fake_environment(root),
            check=False,
            capture_output=True,
            text=True,
        )

    @staticmethod
    def read_calls(path: Path) -> list[list[str]]:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def test_annotated_genome_uses_session_json_and_genbank_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            query = root / "query.faa"
            genome = root / "annotated.gbk"
            output = root / "out"
            query.write_text(">query\nMA\n", encoding="utf-8")
            genome.write_text("LOCUS synthetic\n", encoding="utf-8")
            result = self.run_wrapper(
                root,
                "--organism",
                "sample-organism",
                "--query",
                str(query),
                "--genbank",
                str(genome),
                "--out-dir",
                str(output),
            )
            cblaster_calls = self.read_calls(root / "cblaster.log")
            clinker_calls = self.read_calls(root / "clinker.log")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("makedb", cblaster_calls[0][0])
        self.assertIn(str(genome), cblaster_calls[0])
        self.assertIn("--name", cblaster_calls[0])
        search = next(call for call in cblaster_calls if call[0] == "search")
        self.assertIn("--session_file", search)
        self.assertIn("--gap", search)
        self.assertNotIn("--max_distance", search)
        extract = next(call for call in cblaster_calls if call[0] == "extract_clusters")
        self.assertTrue(extract[1].endswith("search-session.json"))
        self.assertIn("--format", extract)
        self.assertEqual("genbank", extract[extract.index("--format") + 1])
        self.assertEqual("--plot", clinker_calls[0][-2])
        self.assertTrue(clinker_calls[0][0].endswith("cluster1.gbk"))
        self.assertNotIn("--output_html", clinker_calls[0])
        self.assertNotIn("--output_svg", clinker_calls[0])

    def test_prepared_database_skips_makedb_and_missing_inputs_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            query = root / "query.faa"
            prefix = root / "prepared" / "sample"
            output = root / "out"
            query.write_text(">query\nMA\n", encoding="utf-8")
            prefix.parent.mkdir()
            prefix.with_suffix(".dmnd").touch()
            prefix.with_suffix(".sqlite3").touch()
            result = self.run_wrapper(
                root,
                "--organism",
                "sample",
                "--query",
                str(query),
                "--database",
                str(prefix.with_suffix(".dmnd")),
                "--out-dir",
                str(output),
            )
            calls = self.read_calls(root / "cblaster.log")
            missing = self.run_wrapper(root, "--organism", "sample", "--query", str(query))
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotIn("makedb", [call[0] for call in calls])
        self.assertIn("search", [call[0] for call in calls])
        self.assertNotEqual(0, missing.returncode)
        self.assertIn("provide --genbank", missing.stderr)

    def test_fresh_output_and_numeric_limits_are_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            query = root / "query.faa"
            genome = root / "annotated.gbk"
            stale_output = root / "stale-out"
            query.write_text(">query\nMA\n", encoding="utf-8")
            genome.write_text("LOCUS synthetic\n", encoding="utf-8")
            stale_output.mkdir()
            (stale_output / "clusters.tsv").write_text("old\n", encoding="utf-8")
            stale = self.run_wrapper(
                root,
                "--organism",
                "sample",
                "--query",
                str(query),
                "--genbank",
                str(genome),
                "--out-dir",
                str(stale_output),
            )
            invalid_gap = self.run_wrapper(
                root,
                "--organism",
                "sample",
                "--query",
                str(query),
                "--genbank",
                str(genome),
                "--out-dir",
                str(root / "gap-out"),
                "--gap",
                "-1",
            )
            invalid_hits = self.run_wrapper(
                root,
                "--organism",
                "sample",
                "--query",
                str(query),
                "--genbank",
                str(genome),
                "--out-dir",
                str(root / "hits-out"),
                "--min-hits",
                "0",
            )
        self.assertNotEqual(0, stale.returncode)
        self.assertIn("fresh --out-dir", stale.stderr)
        self.assertNotEqual(0, invalid_gap.returncode)
        self.assertIn("--gap must be", invalid_gap.stderr)
        self.assertNotEqual(0, invalid_hits.returncode)
        self.assertIn("--min-hits must be", invalid_hits.stderr)

    def test_template_copies_are_identical_and_use_current_chain(self) -> None:
        template = TEMPLATE.read_text(encoding="utf-8")
        self.assertEqual(template, MIRROR_TEMPLATE.read_text(encoding="utf-8"))
        self.assertIn("--session_file", template)
        self.assertIn("extract_clusters", template)
        self.assertIn("--format genbank", template)
        self.assertNotIn("cblaster extract \\", template)
        self.assertNotIn("--max_distance", template)
        self.assertNotIn("--output_html", template)
        self.assertNotIn("--output_svg", template)
        self.assertIn("--gap must be", template)
        self.assertIn("fresh output directory", template)


if __name__ == "__main__":
    unittest.main()
