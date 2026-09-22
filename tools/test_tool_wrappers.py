#!/usr/bin/env python3
"""Lightweight contract tests for the public MMseqs2 wrapper.

The tests use a temporary fake ``mmseqs`` executable.  They exercise argument
and path handling without installing MMseqs2 or searching biological data.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "skills/genecluster-superpowers/scripts/run-mmseqs2.sh"
TEMPLATE_A = ROOT / "tools/recommended/mmseqs2/iterative-profile.sh.template"
TEMPLATE_B = ROOT / "skills/genecluster-superpowers/tools/recommended/mmseqs2/iterative-profile.sh.template"
FORMAT_OUTPUT = "query,target,evalue,bits,qaln,taln"


FAKE_MMSEQS = """\
#!{python}
import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
if not args:
    raise SystemExit(2)
command = args[0]
log_path = Path(os.environ["MMSEQS_FAKE_LOG"])
with log_path.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(args) + "\\n")

if os.environ.get("MMSEQS_FAKE_FAIL") == command:
    raise SystemExit(23)

if command == "createdb":
    output = Path(args[2])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.touch()
elif command == "search":
    output = Path(args[3])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.touch()
elif command == "convertalis" and os.environ.get("MMSEQS_FAKE_NO_OUTPUT") != "1":
    output = Path(args[4])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("q\\tt\\t1e-3\\t42\\tQA\\tTA\\n", encoding="utf-8")
elif command not in {"convertalis", "createdb", "search"}:
    raise SystemExit(2)
"""


class MMseqsWrapperTests(unittest.TestCase):
    def make_fake_environment(self, tmp: Path) -> tuple[dict[str, str], Path]:
        bin_dir = tmp / "bin"
        bin_dir.mkdir()
        fake = bin_dir / "mmseqs"
        fake.write_text(FAKE_MMSEQS.replace("{python}", sys.executable), encoding="utf-8")
        fake.chmod(0o755)
        log = tmp / "mmseqs-calls.jsonl"
        env = os.environ.copy()
        env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
        env["MMSEQS_FAKE_LOG"] = str(log)
        for name in (
            "MMSEQS_QUERY_FASTA",
            "MMSEQS_PROTEOME",
            "MMSEQS_TARGET_FASTA",
            "MMSEQS_OUTPUT_DIR",
            "MMSEQS_THREADS",
            "MMSEQS_SENSITIVITY",
            "THREADS",
            "SENSITIVITY",
        ):
            env.pop(name, None)
        return env, log

    @staticmethod
    def run_wrapper(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["/bin/bash", str(WRAPPER), *args],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    @staticmethod
    def read_calls(log: Path) -> list[list[str]]:
        return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]

    def test_help_runs_before_optional_tool_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            env = os.environ.copy()
            env["PATH"] = f"{tmp}{os.pathsep}/usr/bin{os.pathsep}/bin"
            result = self.run_wrapper(["--help"], env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Usage:", result.stdout)
        self.assertIn("--output-dir", result.stdout)
        self.assertNotIn("not installed", result.stdout + result.stderr)

    def test_legacy_positionals_and_explicit_paths_reach_fake_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            env, log = self.make_fake_environment(tmp)
            query = tmp / "query with spaces.faa"
            target = tmp / "target with spaces.faa"
            output = tmp / "output with spaces"
            query.write_text(">query\nMA\n", encoding="utf-8")
            target.write_text(">target\nMA\n", encoding="utf-8")

            result = self.run_wrapper(
                [
                    "generic-species.v1",
                    str(query),
                    "--target",
                    str(target),
                    "--out-dir",
                    str(output),
                    "--threads",
                    "2",
                    "-s",
                    "6.5",
                ],
                env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            calls = self.read_calls(log)
            createdb = [call for call in calls if call[0] == "createdb"]
            self.assertEqual([call[1] for call in createdb], [str(query), str(target)])

            search = next(call for call in calls if call[0] == "search")
            self.assertEqual(search[1:5], [
                str(output / "queries.db"),
                str(output / "target.db"),
                str(output / "queries-vs-target.result"),
                str(output / "tmp"),
            ])
            self.assertEqual(search[search.index("--num-iterations") + 1], "3")
            self.assertIn("-a", search)
            self.assertEqual(search[search.index("-s") + 1], "6.5")
            self.assertEqual(search[search.index("--threads") + 1], "2")

            convert = next(call for call in calls if call[0] == "convertalis")
            self.assertEqual(convert[4], str(output / "queries-vs-target.outfmt6"))
            self.assertEqual(
                convert[convert.index("--format-output") + 1],
                FORMAT_OUTPUT,
            )
            self.assertEqual(
                (output / "queries-vs-target.schema.txt").read_text(encoding="utf-8"),
                FORMAT_OUTPUT + "\n",
            )
            self.assertNotIn("Sensitivity gain", result.stdout)

    def test_environment_overrides_and_safe_generic_slug(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            env, log = self.make_fake_environment(tmp)
            query = tmp / "env-query.faa"
            target = tmp / "env-target.faa"
            output = tmp / "env-output"
            query.write_text(">query\nMA\n", encoding="utf-8")
            target.write_text(">target\nMA\n", encoding="utf-8")
            env.update(
                {
                    "MMSEQS_QUERY_FASTA": str(query),
                    "MMSEQS_TARGET_FASTA": str(target),
                    "MMSEQS_OUTPUT_DIR": str(output),
                    "MMSEQS_THREADS": "3",
                    "MMSEQS_SENSITIVITY": "7.0",
                }
            )

            result = self.run_wrapper(["--species", "plant.dataset_2"], env)
            self.assertEqual(result.returncode, 0, result.stderr)
            calls = self.read_calls(log)
            search = next(call for call in calls if call[0] == "search")
            self.assertEqual(search[search.index("--threads") + 1], "3")
            self.assertEqual(search[search.index("-s") + 1], "7.0")
            self.assertTrue((output / "queries-vs-target.outfmt6").is_file())

    def test_unsafe_slug_is_rejected_before_tool_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            env = os.environ.copy()
            env["PATH"] = f"{tmp}{os.pathsep}/usr/bin{os.pathsep}/bin"
            result = self.run_wrapper(["../escape"], env)
        self.assertEqual(result.returncode, 64)
        self.assertIn("unsafe species slug", result.stderr)

    def test_missing_output_from_cli_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            env, _log = self.make_fake_environment(tmp)
            query = tmp / "query.faa"
            target = tmp / "target.faa"
            query.write_text(">query\nMA\n", encoding="utf-8")
            target.write_text(">target\nMA\n", encoding="utf-8")
            env["MMSEQS_FAKE_NO_OUTPUT"] = "1"
            result = self.run_wrapper(
                [
                    "plant",
                    "--query",
                    str(query),
                    "--target",
                    str(target),
                    "--out-dir",
                    str(tmp / "output"),
                ],
                env,
            )
        self.assertEqual(result.returncode, 64)
        self.assertIn("did not create the expected output", result.stderr)

    def test_nonempty_output_dir_is_rejected_without_cli_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            env, log = self.make_fake_environment(tmp)
            query = tmp / "query.faa"
            target = tmp / "target.faa"
            output = tmp / "output"
            query.write_text(">query\nMA\n", encoding="utf-8")
            target.write_text(">target\nMA\n", encoding="utf-8")
            output.mkdir()
            sentinel = output / ".stale-result"
            sentinel.write_text("preserve me\n", encoding="utf-8")

            result = self.run_wrapper(
                [
                    "plant",
                    "--query",
                    str(query),
                    "--target",
                    str(target),
                    "--out-dir",
                    str(output),
                ],
                env,
            )

            self.assertEqual(result.returncode, 64)
            self.assertIn("must be new or empty", result.stderr)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve me\n")
            self.assertFalse(log.exists())
            self.assertFalse((output / "tmp").exists())

    def test_mmseqs_failure_is_propagated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            env, _log = self.make_fake_environment(tmp)
            query = tmp / "query.faa"
            target = tmp / "target.faa"
            query.write_text(">query\nMA\n", encoding="utf-8")
            target.write_text(">target\nMA\n", encoding="utf-8")
            env["MMSEQS_FAKE_FAIL"] = "search"
            result = self.run_wrapper(
                [
                    "plant",
                    "--query",
                    str(query),
                    "--target",
                    str(target),
                    "--out-dir",
                    str(tmp / "output"),
                ],
                env,
            )
        self.assertEqual(result.returncode, 23)
        self.assertNotIn("DONE:", result.stdout)

    def test_mirrored_templates_keep_the_same_contract(self) -> None:
        template_a = TEMPLATE_A.read_text(encoding="utf-8")
        template_b = TEMPLATE_B.read_text(encoding="utf-8")
        self.assertEqual(template_a, template_b)
        self.assertIn("-s \"${SENSITIVITY}\"", template_a)
        self.assertIn("  -a \\\n", template_a)
        self.assertIn("--format-output \"${FORMAT_OUTPUT}\"", template_a)
        self.assertIn("must be new or empty", template_a)
        self.assertIn(FORMAT_OUTPUT, template_a)
        self.assertNotIn("+10-15%", template_a)


if __name__ == "__main__":
    unittest.main()
