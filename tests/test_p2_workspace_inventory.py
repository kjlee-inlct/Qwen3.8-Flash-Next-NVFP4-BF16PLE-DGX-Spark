"""Source-only tests. No real Docker / Git commands or filesystem mutations."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "p2-workspace-inventory.py"
spec = importlib.util.spec_from_file_location("p2_workspace_inventory", SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def mkdir(self, name):
        p = self.root / name
        p.mkdir()
        return p

    def item(self, name, status="AVAILABLE", mounts=None):
        with patch.object(mod, "git_metadata", return_value={
            "git_repo": True, "branch": "old", "tracked_change": False,
            "untracked_change": False, "linked_worktree": False,
            "additional_worktrees": False, "origin_is_expected_fork": True}):
            return next(x for x in mod.inventory(self.root, status, mounts or [])["entries"]
                        if x["name"] == name)

    def test_active_and_original_protected(self):
        self.mkdir("blazux-phase6-gates")
        self.mkdir("yslab-qwen38-bf16ple-dgx-spark")
        self.assertEqual(self.item("blazux-phase6-gates")["classification"], "RETAIN_PROTECTED")
        self.assertEqual(self.item("yslab-qwen38-bf16ple-dgx-spark")["classification"], "RETAIN_PROTECTED")

    def test_old_phase_review_not_delete(self):
        self.mkdir("blazux-phase3-ple-duplicate-shard-guard")
        item = self.item("blazux-phase3-ple-duplicate-shard-guard")
        self.assertEqual(item["classification"], "REVIEW_FOR_ARCHIVE")
        self.assertIn("NOT_PROVEN_UNUSED", item["reason"])

    def test_docker_mount_protects_checkout_and_parent(self):
        p = self.mkdir("blazux-phase2-offline-fixtures")
        self.assertEqual(self.item(p.name, mounts=[p / "cache"])["classification"], "RETAIN_PROTECTED")
        self.assertTrue(mod.overlaps(p / "cache", p))

    def test_no_docker_availability_restricts_classification(self):
        self.mkdir("blazux-phase4-ple-cpu-bundle")
        self.assertIn("DOCKER_MOUNTS_UNVERIFIED", self.item("blazux-phase4-ple-cpu-bundle", "UNAVAILABLE")["reason"])

    def test_dirty_git_holds_even_old_phase(self):
        self.mkdir("blazux-phase5-correctness-mtp-offline")
        with patch.object(mod, "git_metadata", return_value={
            "git_repo": True, "branch": "x", "tracked_change": True,
            "untracked_change": False, "linked_worktree": False,
            "additional_worktrees": False, "origin_is_expected_fork": True}):
            entry = mod.inventory(self.root, "AVAILABLE", [])["entries"][0]
        self.assertEqual(entry["classification"], "HOLD_REFERENCE")

    def test_symlink_not_followed(self):
        target = self.mkdir("blazux-phase1-source-compare")
        (self.root / "alias").symlink_to(target, target_is_directory=True)
        entry = self.item("alias")
        self.assertEqual(entry["classification"], "HOLD_REFERENCE")
        self.assertEqual(entry["kind"], "SYMLINK")

    def test_unknown_benchmark_kept(self):
        self.mkdir("llama-benchy")
        self.assertEqual(self.item("llama-benchy")["classification"], "HOLD_REFERENCE")

    def test_docker_response_invalid_not_trusted(self):
        with patch.object(mod, "call", return_value=(False, "")):
            self.assertEqual(mod.docker_mount_sources(), ("UNAVAILABLE", []))
        with patch.object(mod, "call", side_effect=[(True, "id"), (True, "not json")]):
            self.assertEqual(mod.docker_mount_sources(), ("UNAVAILABLE", []))

    def test_no_mutating_commands_in_source(self):
        code = SOURCE.read_text()
        self.assertNotIn('os.remove(', code)
        self.assertNotIn('.rename(', code)
        self.assertNotIn('shutil.move(', code)
        self.assertNotIn('docker", "run', code)
        self.assertNotIn('git", "clean', code)


if __name__ == "__main__":
    unittest.main()
