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


    def test_phase_without_valid_git_is_not_archive_candidate(self):
        self.mkdir("blazux-phase1-source-compare")
        with patch.object(mod, "git_metadata", return_value={
                "git_repo": False, "branch": None, "tracked_change": "UNKNOWN",
                "untracked_change": "UNKNOWN", "linked_worktree": False,
                "additional_worktrees": "UNKNOWN", "origin_is_expected_fork": None}):
            entry = mod.inventory(self.root, "AVAILABLE", [])["entries"][0]
        self.assertEqual(entry["classification"], "HOLD_REFERENCE")
        self.assertEqual(entry["reason"], "OLD_PHASE_NOT_GIT_VERIFIED")

    def test_phase_git_unknown_status_does_not_pass(self):
        self.mkdir("blazux-phase2-offline-fixtures")
        with patch.object(mod, "git_metadata", return_value={
                "git_repo": True, "branch": "x", "tracked_change": "UNKNOWN",
                "untracked_change": False, "linked_worktree": False,
                "additional_worktrees": False, "origin_is_expected_fork": True}):
            entry = mod.inventory(self.root, "AVAILABLE", [])["entries"][0]
        self.assertEqual(entry["classification"], "HOLD_REFERENCE")
        self.assertEqual(entry["reason"], "OLD_PHASE_GIT_STATUS_UNKNOWN")

    def test_reference_audit_counts_scripts_and_docs(self):
        self.mkdir("blazux-phase3-ple-duplicate-shard-guard")
        root = self.mkdir("blazux-phase6-gates")
        (root / "worker.py").write_text("path='blazux-phase3-ple-duplicate-shard-guard'", encoding="utf-8")
        (root / "notes.md").write_text("blazux-phase3-ple-duplicate-shard-guard", encoding="utf-8")
        entries = [{"name": "blazux-phase3-ple-duplicate-shard-guard"}]
        audit = mod.reference_audit(self.root, entries)
        self.assertEqual(audit["status"], "COMPLETE_SCOPED_SCAN")
        detail = audit["targets"][entries[0]["name"]]
        self.assertEqual(detail["total_matches"], 2)
        self.assertEqual({v["kind"] for v in detail["matches"]},
                         {"DOCUMENT_REFERENCE", "SCRIPT_OR_CONFIG_REFERENCE"})
        self.assertTrue(audit["no_cross_reference_found_is_not_safe_to_move"])

    def test_reference_scan_does_not_follow_link(self):
        self.mkdir("blazux-phase4-ple-cpu-bundle")
        app = self.mkdir("blazux-phase6-gates")
        outside = self.mkdir("outside")
        (outside / "reference.py").write_text("blazux-phase4-ple-cpu-bundle")
        (app / "link.py").symlink_to(outside / "reference.py")
        audit = mod.reference_audit(self.root, [{"name": "blazux-phase4-ple-cpu-bundle"}])
        self.assertEqual(audit["targets"]["blazux-phase4-ple-cpu-bundle"]["total_matches"], 0)
        self.assertEqual(audit["symlinks_skipped"], 1)

    def test_reference_scan_budget_is_reported_partial(self):
        self.mkdir("blazux-phase5-correctness-mtp-offline")
        app = self.mkdir("blazux-phase6-gates")
        (app / "a.py").write_text("nothing")
        (app / "b.py").write_text("blazux-phase5-correctness-mtp-offline")
        with patch.object(mod, "MAX_REFERENCE_FILES", 1):
            audit = mod.reference_audit(self.root, [{"name": "blazux-phase5-correctness-mtp-offline"}])
        self.assertEqual(audit["status"], "PARTIAL_SCOPED_SCAN")
        self.assertEqual(audit["files_scanned"], 1)

    def test_reference_scan_large_files_are_not_claimed_complete(self):
        self.mkdir("blazux-phase1-source-compare")
        app = self.mkdir("blazux-phase6-gates")
        (app / "huge.py").write_text("x" * 100)
        with patch.object(mod, "MAX_REFERENCE_BYTES", 10):
            audit = mod.reference_audit(self.root, [{"name": "blazux-phase1-source-compare"}])
        self.assertEqual(audit["status"], "PARTIAL_SCOPED_SCAN")
        self.assertEqual(audit["large_files_skipped"], 1)


if __name__ == "__main__":
    unittest.main()
