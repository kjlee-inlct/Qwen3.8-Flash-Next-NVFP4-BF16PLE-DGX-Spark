"""Offline guardrails for the Preview-native Qwen marker patch (no live vLLM)."""
from __future__ import annotations

import ast
import hashlib
import unittest
from pathlib import Path

from src import preview_p1_native_marker_verify as native
from src.preview_p1_tool_responses_stage import StageBlocked


class PreviewNativeMarkerTests(unittest.TestCase):
    def test_native_patch_exact_integrity_and_scope(self):
        data = native.PATCH.read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), native.PATCH_SHA256)
        paths = [line[6:] for line in data.decode().splitlines()
                 if line.startswith("+++ b/")]
        self.assertEqual(set(paths), set(native.PINNED))
        self.assertEqual(len(paths), 4)
        self.assertNotIn("vllm/entrypoints/openai/responses/serving.py", paths)

    def test_archive_snapshot_pins_are_full_digest(self):
        self.assertEqual(len(native.PINNED), 4)
        for name, sha in native.PINNED.items():
            self.assertTrue(name.startswith("vllm/parser/"))
            self.assertRegex(sha, r"^[0-9a-f]{64}$")

    def test_real_method_harness_rejects_missing_engine(self):
        with self.assertRaisesRegex(StageBlocked, "NATIVE_CLASS_NOT_FOUND"):
            native.verify_native_methods(b"class Unrelated: pass\n")

    def test_executable_source_parse_and_explicit_run_only(self):
        ast.parse(Path(native.__file__).read_bytes())
        self.assertEqual(native.main([]), 2)


if __name__ == "__main__":
    unittest.main()
