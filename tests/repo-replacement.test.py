#!/usr/bin/env python3
"""Tests for scripts/replace-linked-repo.py using isolated mock Git clones."""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "replace-linked-repo.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("replace_linked_repo", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TOOL = load_tool()


def run_tool(target: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args, str(target)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def tree_snapshot(root: Path) -> dict[str, tuple[str, str]]:
    """Capture regular-file bytes and symlink targets without following links."""
    snapshot: dict[str, tuple[str, str]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            snapshot[relative] = ("symlink", os.readlink(path))
        elif path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            snapshot[relative] = ("file", digest)
        elif path.is_dir():
            snapshot[relative] = ("dir", "")
    return snapshot


class RepoReplacementTests(unittest.TestCase):
    def make_clone(self, root: Path) -> Path:
        clone = root / "clone"
        (clone / ".git").mkdir(parents=True)
        (clone / ".git" / "config").write_text("mock git metadata\n", encoding="utf-8")
        return clone

    def test_source_files_enumerates_complete_source_without_mutating_source(self):
        before = tree_snapshot(ROOT)
        files = list(TOOL.source_files())
        after = tree_snapshot(ROOT)

        self.assertEqual(before, after)
        relative = {path.relative_to(ROOT) for path, _ in files}
        self.assertIn(Path("README.md"), relative)
        self.assertIn(Path("scripts/replace-linked-repo.py"), relative)
        self.assertIn(Path(".github/workflows/android-apk.yml"), relative)
        self.assertNotIn(Path(".git"), {part for path in relative for part in path.parts})
        self.assertNotIn(Path(".env"), relative)
        self.assertTrue(all(source_path.is_file() for source_path, _ in files))

    def test_preview_does_not_change_mock_clone(self):
        with tempfile.TemporaryDirectory() as temporary:
            clone = self.make_clone(Path(temporary))
            workflow_dir = clone / ".github" / "workflows"
            workflow_dir.mkdir(parents=True)
            (workflow_dir / "legacy-arbitrary-name.yaml").write_text(
                "name: Build Android Java APK\njobs: {}\n", encoding="utf-8"
            )
            (workflow_dir / "tests.yml").write_text("name: tests\n", encoding="utf-8")
            (clone / ".env").write_text("PRIVATE=value\n", encoding="utf-8")
            (clone / "unrelated.txt").write_text("leave me\n", encoding="utf-8")
            before = tree_snapshot(clone)

            result = run_tool(clone)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("PREVIEW ONLY", result.stdout)
            self.assertEqual(before, tree_snapshot(clone))
            self.assertFalse((clone / ".engx-workflow-backups").exists())

    def test_apply_preserves_private_git_and_unrelated_files_and_replaces_android_workflow(self):
        with tempfile.TemporaryDirectory() as temporary:
            clone = self.make_clone(Path(temporary))
            workflow_dir = clone / ".github" / "workflows"
            workflow_dir.mkdir(parents=True)
            old_workflow = workflow_dir / "old-build-name.yml"
            old_workflow.write_text(
                "name: Build Android Java APK\njobs:\n  build: {}\n", encoding="utf-8"
            )
            unrelated_workflow = workflow_dir / "tests-unrelated.yml"
            unrelated_workflow.write_text("name: tests\njobs: {}\n", encoding="utf-8")
            (clone / ".env").write_text("SECRET=do-not-copy-over\n", encoding="utf-8")
            (clone / "unrelated.txt").write_text("retained application data\n", encoding="utf-8")
            git_config = clone / ".git" / "config"
            git_before = git_config.read_bytes()
            new_workflow = (ROOT / ".github/workflows/android-apk.yml").read_bytes()

            result = run_tool(clone, "--apply")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(git_config.read_bytes(), git_before)
            self.assertTrue((clone / ".git").is_dir())
            self.assertEqual((clone / ".env").read_text(encoding="utf-8"), "SECRET=do-not-copy-over\n")
            self.assertEqual((clone / "unrelated.txt").read_text(encoding="utf-8"), "retained application data\n")
            self.assertEqual((workflow_dir / "tests-unrelated.yml").read_text(encoding="utf-8"), "name: tests\njobs: {}\n")
            self.assertEqual((workflow_dir / "android-apk.yml").read_bytes(), new_workflow)
            self.assertFalse(old_workflow.exists())

            backups = list((clone / ".engx-workflow-backups").iterdir())
            self.assertEqual(len(backups), 1)
            self.assertEqual((backups[0] / old_workflow.name).read_text(encoding="utf-8"), "name: Build Android Java APK\njobs:\n  build: {}\n")
            self.assertNotEqual((backups[0] / old_workflow.name).resolve(), old_workflow.resolve())

    def test_rejects_same_and_nested_source_targets(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary) / "parent"
            parent.mkdir()
            same = run_tool(ROOT)
            nested = run_tool(ROOT / "nested-target")
            outside_parent = run_tool(ROOT.parent)

            for result in (same, nested, outside_parent):
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Source and target must be separate, non-nested directories", result.stderr)

    def test_rejects_destination_symlink_without_overwriting_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            clone = self.make_clone(base)
            outside = base / "outside.txt"
            outside.write_text("must remain untouched\n", encoding="utf-8")
            destination = clone / "README.md"
            destination.symlink_to(outside)
            before = tree_snapshot(clone)

            result = run_tool(clone, "--apply")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Destination symlink is not allowed", result.stderr)
            self.assertEqual(outside.read_text(encoding="utf-8"), "must remain untouched\n")
            self.assertTrue(destination.is_symlink())
            self.assertEqual(before, tree_snapshot(clone))


if __name__ == "__main__":
    unittest.main(verbosity=2)
