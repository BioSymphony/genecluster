#!/usr/bin/env python3
"""Regression tests for the public-surface checker."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_public_surface
from check_public_surface import format_findings, scan_tree


class PublicSurfaceTests(unittest.TestCase):
    def test_svg_binary_and_all_home_path_forms_are_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "nested" / "diagram.svg").parent.mkdir(parents=True)
            slash = chr(92)
            home_values = [
                "/" + "Users/operator/work",
                "/" + "home/operator/work",
                "C:" + slash + "Users" + slash + "operator" + slash + "work",
                "https://example.invalid/file?sig=" + "a" * 20,
            ]
            (root / "nested" / "diagram.svg").write_text("\n".join(home_values), encoding="utf-8")
            marker = "g" + "hp_" + "x" * 24
            fine_marker = "github" + "_pat_" + "x" * 24
            aws_marker = "A" + "SIA" + "A" * 16
            (root / "nested" / "image.bin").write_bytes(
                b"PNG\0"
                + marker.encode()
                + b"\n"
                + fine_marker.encode()
                + b"\n"
                + aws_marker.encode()
            )
            findings = scan_tree(root)
        rules = {item.rule for item in findings}
        self.assertTrue(
            {
                "home_path",
                "github_token",
                "github_fine_grained_token",
                "aws_session_key",
                "signed_url_credential",
            }
            <= rules
        )
        self.assertGreaterEqual(sum(item.rule == "home_path" for item in findings), 3)

    def test_nested_internal_folder_and_ignored_environment_file_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            internal = root / "nested" / "references" / "internal"
            internal.mkdir(parents=True)
            (root / ".git").mkdir()
            (root / "nested" / ".git").mkdir()
            (internal / ("writing" + "-style.md")).write_text("fixture", encoding="utf-8")
            (root / "public.md").write_text(
                "See "
                + "writing"
                + "-style.md\n"
                + "internal"
                + "-only\n"
                + "write"
                + "-better/SKILL.md",
                encoding="utf-8",
            )
            env = root / "nested" / "deep" / ".env.local"
            env.parent.mkdir(parents=True)
            env.write_text("NAME=value", encoding="utf-8")
            findings = scan_tree(root)
        rules = {item.rule for item in findings}
        self.assertTrue(
            {
                "forbidden_directory",
                "nested_git_directory",
                "environment_file",
                "internal_style_reference",
                "internal_only_marker",
                "writing_skill_reference",
            }
            <= rules
        )
        self.assertNotIn((".git", "nested_git_directory"), {(item.path, item.rule) for item in findings})

    def test_nested_data_and_symlink_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nested = root / "nested" / "data"
            nested.mkdir(parents=True)
            (nested / "fixture.faa").write_bytes(b">synthetic\n" + b"M" * 4090)
            (nested / "small.fa").write_text(">synthetic\nMA\n", encoding="utf-8")
            (nested / "small.faa.gz").write_bytes(b"compressed fixture")
            (nested / "tiny.weights").write_bytes(b"x")
            (nested / "tiny.zip").write_bytes(b"x")
            allowed = root / "skills" / "biosymphony" / "examples" / "genecluster-coptis-bia-public-v0" / "fixtures"
            allowed.mkdir(parents=True)
            (allowed / "fixture-proteome.faa").write_text(">synthetic\nMA\n", encoding="utf-8")
            target = nested / "target.txt"
            target.write_text("safe", encoding="utf-8")
            link = nested / "linked.txt"
            link.symlink_to(target)
            findings = scan_tree(root)
        raw_paths = {item.path for item in findings if item.rule == "raw_data_artifact"}
        blocked_paths = {item.path for item in findings if item.rule == "blocked_artifact"}
        self.assertTrue(
            {"nested/data/fixture.faa", "nested/data/small.fa", "nested/data/small.faa.gz"}
            <= raw_paths
        )
        self.assertNotIn(
            "skills/biosymphony/examples/genecluster-coptis-bia-public-v0/fixtures/fixture-proteome.faa",
            raw_paths,
        )
        self.assertTrue({"nested/data/tiny.weights", "nested/data/tiny.zip"} <= blocked_paths)
        self.assertIn("symlink", {item.rule for item in findings})

    def test_placeholders_pass_and_output_redacts_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "safe.sh").write_text(
                "Authorization: Bearer ${RUNPOD_API_KEY}\n"
                "https://example.invalid/?sig=<signature>\n",
                encoding="utf-8",
            )
            safe = scan_tree(root)
            marker = "g" + "hp_" + "x" * 24
            (root / "bad.txt").write_text(marker, encoding="utf-8")
            findings = scan_tree(root)
            rendered = format_findings(findings)
        self.assertEqual([], safe)
        self.assertIn("github_token", rendered)
        self.assertNotIn(marker, rendered)
        self.assertTrue(all(len(item.__dict__) == 3 for item in findings))

    def test_large_artifact_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "nested").mkdir()
            (root / "nested" / "large.bin").write_bytes(b"x" * 33)
            (root / "nested" / "large.weights").write_bytes(b"x" * 33)
            (root / "nested" / "small-a.txt").write_bytes(b"a" * 20)
            (root / "nested" / "small-b.txt").write_bytes(b"b" * 20)
            findings = scan_tree(root, max_file_bytes=32, max_tree_bytes=32)
        pairs = {(item.path, item.rule) for item in findings}
        self.assertIn(("nested/large.bin", "large_artifact"), pairs)
        self.assertIn(("nested/large.weights", "blocked_artifact"), pairs)
        self.assertIn((".", "tree_size_limit"), pairs)

    def test_invalid_roots_and_walk_errors_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            missing = scan_tree(base / "missing")
            file_root = base / "file.txt"
            file_root.write_text("fixture", encoding="utf-8")
            non_directory = scan_tree(file_root)
            root = base / "tree"
            root.mkdir()

            def failing_walk(*_args, **kwargs):
                kwargs["onerror"](OSError(13, "denied", str(root / "blocked")))
                return iter(())

            with patch.object(check_public_surface.os, "walk", failing_walk):
                unreadable = scan_tree(root)
        for expected, result in (
            ("invalid_root", missing),
            ("invalid_root", non_directory),
            ("unreadable_directory", unreadable),
        ):
            self.assertEqual([expected], [item.rule for item in result])

    def test_cli_never_echoes_matched_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            marker = "g" + "hp_" + "y" * 24
            (root / "notes.txt").write_text(marker, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "tools/check_public_surface.py", "--root", str(root)],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertNotEqual(0, result.returncode)
        self.assertIn("notes.txt:1:github_token", result.stdout)
        self.assertNotIn(marker, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
