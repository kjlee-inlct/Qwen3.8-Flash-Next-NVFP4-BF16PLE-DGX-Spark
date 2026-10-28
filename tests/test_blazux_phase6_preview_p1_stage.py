"""Source-integrity/safety tests for the real four-patch Preview staging tool.

No vLLM import, no GNU patch invocation, no model, no GPU or filesystem
writes outside an ephemeral test fixture. Runtime correctness is NOT claimed.
"""
from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import preview_p1_tool_responses_stage as stage


class P1PreviewToolStageTests(unittest.TestCase):
    def test_upstream_four_patch_blob_identities_and_scope(self):
        payloads, touched = stage.read_patch_bundle()
        self.assertEqual(len(payloads), 4)
        self.assertEqual(set(stage.PINNED_PREIMAGES).issubset(touched), True)
        self.assertEqual(stage.NEW_FILE in touched, True)
        self.assertTrue(touched.issubset(stage.ALLOWED_FILES))
        self.assertNotIn("vllm/v1/core/sched/scheduler.py", touched)

    def test_forbid_path_traversal(self):
        injected = b"--- a/vllm/../../etc/passwd\n+++ b/vllm/../../etc/passwd\n@@ -1 +1 @@\n-a\n+b\n"
        with self.assertRaises(stage.StageBlocked):
            stage.parse_patch_files(injected)

    def test_forbid_binary_and_rename(self):
        for payload in (b"GIT binary patch\n", b"rename from a\n",
                        b"diff --git a/a b/a\n"):
            with self.subTest(payload=payload), self.assertRaises(stage.StageBlocked):
                stage.parse_patch_files(payload)

    def test_forbid_new_file_overwrite(self):
        sample = b"--- /dev/null\n+++ b/vllm/parser/qwen3.py\n@@ -0,0 +1 @@\n+oops\n"
        with self.assertRaises(stage.StageBlocked):
            stage.parse_patch_files(sample)

    def test_incorrect_patch_blob_must_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, _ in stage.PATCHES:
                (Path(tmp) / name).write_bytes(b"--- a/vllm/parser/qwen3.py\n")
            with self.assertRaisesRegex(stage.StageBlocked, "PATCH_BLOB_DRIFT"):
                stage.read_patch_bundle(Path(tmp))

    def test_preview_preimage_drift_fails_without_modification(self):
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp)
            # Fake files are acceptable here only for verifying failure paths.
            for name in stage.ALLOWED_FILES:
                if name != stage.NEW_FILE:
                    p = site / name
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text("class Fake:\n    pass\n")
            before = (site / "vllm/parser/qwen3.py").read_bytes()
            with self.assertRaisesRegex(stage.StageBlocked, "PREVIEW_SHA_DRIFT"):
                stage.read_preview_sources(site, set(stage.ALLOWED_FILES))
            self.assertEqual(before, (site / "vllm/parser/qwen3.py").read_bytes())

    def test_refuse_any_installed_new_argument_validation_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp)
            p = site / stage.NEW_FILE
            p.parent.mkdir(parents=True)
            p.write_text("def untouched(): pass\n")
            with self.assertRaisesRegex(stage.StageBlocked, "NEW_FILE_ALREADY_EXISTS"):
                stage.read_preview_sources(site, {stage.NEW_FILE})

    def test_refuse_symlink_as_patched_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp)
            p = site / "vllm/parser/qwen3.py"
            p.parent.mkdir(parents=True)
            p.symlink_to("/etc/passwd")
            with self.assertRaisesRegex(stage.StageBlocked, "SOURCE_SYMLINK"):
                stage.read_preview_sources(site, {"vllm/parser/qwen3.py"})

    def test_required_hook_signatures_are_explicit(self):
        self.assertIn("PREVIEW_PATCH_1_CONTEXT_MISMATCH",
                      str(stage.StageBlocked("PREVIEW_PATCH_1_CONTEXT_MISMATCH")))
        self.assertNotIn("exec(", stage.stage_preview_bundle.__doc__ or "")
        self.assertEqual(stage.main([]), 2)

    def test_python_source_is_parseable(self):
        source = Path(stage.__file__).read_text()
        ast.parse(source)
        self.assertEqual(len(stage.PINNED_PREIMAGES), 6)


if __name__ == "__main__":
    unittest.main()
