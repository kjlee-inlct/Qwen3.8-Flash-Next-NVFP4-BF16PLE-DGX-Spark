# publication-audit: allow-test-fixture
"""Offline regression: source SHA verification works on feature and merged main.

Creates only a disposable Git fixture in TemporaryDirectory; no Docker, HF,
live repository, network, or real deployment resources are changed.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify-source-state.py"
spec = importlib.util.spec_from_file_location("wizard_source_state_verifier", VERIFIER)
assert spec is not None and spec.loader is not None
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


class ReleaseBranchSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "checkout"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Unit Test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("remote", "add", "origin",
                 "https://github.com/kjlee-inlct/"
                 "Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark.git")
        (self.repo / "README.md").write_text("reference snapshot\n", encoding="utf-8")
        manifest_dir = self.repo / "scripts"
        manifest_dir.mkdir()
        content = {
            "schema_version": 1,
            "manifest_id": verifier.EXPECTED_ID,
            "repository": verifier.EXPECTED_REPO,
            "branch": verifier.RELEASE_BRANCHES[0],
            "allowed_branches": list(verifier.RELEASE_BRANCHES),
            "validation_at_creation": {
                "host_runtime": "NOT_OBSERVED", "tests": "NOT_RUN",
            },
            "source_creation_parent_commit": "0" * 40,
            "files": [{
                "path": "README.md",
                "mode": "100644",
                "blob_sha": verifier.git_blob(self.repo / "README.md"),
            }],
        }
        (manifest_dir / "source-state-manifest.json").write_text(
            json.dumps(content, indent=2) + "\n", encoding="utf-8")
        self.git("add", "--", "README.md", "scripts/source-state-manifest.json")
        self.git("commit", "-q", "-m", "fixture")
        self.root_patch = patch.object(verifier, "ROOT", self.repo)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.repo), *args],
                       check=True, capture_output=True, text=True)

    def test_approved_main_passes_with_strict(self):
        result = verifier.source_report(strict=True)
        self.assertEqual(result["result"], "PASS_SOURCE_ONLY", result["errors"])
        self.assertEqual(result["checked_source_files"], 1)

    def test_approved_feature_branch_passes_with_strict(self):
        self.git("switch", "-q", "-c", verifier.RELEASE_BRANCHES[0])
        result = verifier.source_report(strict=True)
        self.assertEqual(result["result"], "PASS_SOURCE_ONLY", result["errors"])

    def test_detached_pr_head_allows_inventory_not_strict(self):
        """Detached PR checkout verifies hashes; release strict remains fail-closed."""
        self.git("switch", "--detach", "-q", "HEAD")
        result = verifier.source_report(strict=False)
        self.assertEqual(result["result"], "PASS_SOURCE_ONLY", result["errors"])
        self.assertEqual(result["branch"], "(detached)")
        strict = verifier.source_report(strict=True)
        self.assertEqual(strict["result"], "FAIL")
        self.assertTrue(any("wrong branch" in e for e in strict["errors"]))

    def test_unknown_branch_rejected_with_strict(self):
        self.git("switch", "-q", "-c", "unexpected-release")
        result = verifier.source_report(strict=True)
        self.assertEqual(result["result"], "FAIL")
        self.assertTrue(any("wrong branch" in value for value in result["errors"]))

    def test_main_new_commit_same_tree_still_passes(self):
        self.git("commit", "-q", "--allow-empty", "-m", "simulate merge-commit sha")
        result = verifier.source_report(strict=True)
        self.assertEqual(result["result"], "PASS_SOURCE_ONLY", result["errors"])

    def test_main_tampered_source_fails(self):
        (self.repo / "README.md").write_text("TAMPERED\n", encoding="utf-8")
        result = verifier.source_report(strict=True)
        self.assertEqual(result["result"], "FAIL")
        self.assertTrue(any("working-tree blob differs" in e for e in result["errors"]))

    def test_manifest_cannot_add_other_release_branch(self):
        data = {"branch": verifier.RELEASE_BRANCHES[0],
                "allowed_branches": list(verifier.RELEASE_BRANCHES) + ["unapproved"]}
        with self.assertRaisesRegex(ValueError, "allowlist"):
            verifier.verification_branches(data)

    def test_manifest_must_preserve_original_source_branch(self):
        data = {"branch": "main",
                "allowed_branches": list(verifier.RELEASE_BRANCHES)}
        with self.assertRaisesRegex(ValueError, "provenance"):
            verifier.verification_branches(data)


if __name__ == "__main__":
    unittest.main()
