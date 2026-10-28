"""Host-stdlib source integrity checks; runtime behavior runs in isolated CPU image."""
from __future__ import annotations

import ast
import hashlib
import unittest
from pathlib import Path

from src import preview_p1_native_schema_verify as schema
from src.preview_p1_tool_responses_stage import StageBlocked


class PreviewNativeSchemaTests(unittest.TestCase):
    def test_exact_patch_sha_and_scope(self):
        data = schema.SCHEMA_PATCH.read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), schema.SCHEMA_SHA256)
        paths = [line[6:] for line in data.decode().splitlines()
                 if line.startswith("+++ b/")]
        self.assertEqual(set(paths), {
            "vllm/parser/engine/argument_validation.py",
            "vllm/parser/engine/parser_engine.py",
            "vllm/parser/qwen3.py",
            "vllm/parser/abstract_parser.py",
            "vllm/parser/engine/adapters.py",
            "vllm/entrypoints/openai/responses/serving.py",
        })
        self.assertEqual(len(paths), 6)
        self.assertNotIn("vllm/v1/core/sched/scheduler.py", paths)

    def test_schema_depends_on_marker_and_is_not_operational(self):
        self.assertTrue(schema.MARKER_PATCH.is_file())
        self.assertEqual(len(schema.MARKER_SHA), 64)
        self.assertFalse(schema.SCHEMA_PATCH.is_symlink())
        self.assertNotIn("vllm/v1", str(schema.TARGETS))

    def test_stage_is_fully_explicit(self):
        self.assertEqual(schema.main([]), 2)
        with self.assertRaisesRegex(StageBlocked, "PATCH_MISSING_OR_SYMLINK"):
            schema._sha(Path("/nonexistent/p1-schema.patch"), "0" * 64)

    def test_syntax_and_isolation_attributes(self):
        code = Path(schema.__file__).read_bytes()
        ast.parse(code)
        self.assertIn(b"TemporaryDirectory", code)
        self.assertIn(b'--fuzz=0', code)
        self.assertIn(b"parser_api_compatibility_certified", code)
        self.assertNotIn(b"docker exec", code)
        self.assertFalse((schema.SCHEMA_PATCH.parent / "argument_validation.py").exists())


if __name__ == "__main__":
    unittest.main()
