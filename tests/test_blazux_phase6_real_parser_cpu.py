"""P1 pinned Preview real parser CPU integration source-only guardrails."""
import ast
import hashlib
import unittest
from pathlib import Path

from src import preview_p1_real_parser_cpu as m


class RealParserCPUPlanTests(unittest.TestCase):
    def test_source_is_parseable(self):
        ast.parse(Path(m.__file__).read_bytes())

    def test_all_overlay_imports_are_allowlisted(self):
        self.assertEqual(len(m.OVERLAY_MODULES), len(m.TARGETS) + 1)
        self.assertIn("vllm.parser.qwen3", m.OVERLAY_MODULES)
        self.assertIn("vllm.parser.engine.argument_validation", m.OVERLAY_MODULES)
        self.assertNotIn("vllm.v1.worker.gpu_model_runner", m.OVERLAY_MODULES)
        self.assertNotIn("vllm.model_executor.models.qwen3", m.OVERLAY_MODULES)

    def test_pins_are_complete_and_strong(self):
        for path in m.TARGETS:
            self.assertRegex(m.SOURCE_PINS[path], r"^[0-9a-f]{64}$")
        self.assertRegex(m.RESPONSES_SHA256, r"^[0-9a-f]{64}$")

    def test_typed_responses_patch_failure_is_sanitized(self):
        fn = m._responses_patch_failure_code
        self.assertEqual(
            fn(b"patching file vllm/entrypoints/openai/responses/protocol.py\\n"
               b"Hunk #4 FAILED at 843.\\n", b"secret input or reject context"),
            "PREVIEW_RESPONSES_PATCH_PROTOCOL_HUNK_4_FAILED")
        self.assertEqual(
            fn(b"patching file vllm/entrypoints/openai/responses/serving.py\\n"
               b"Hunk #8 FAILED at 1573.\\n", b""),
            "PREVIEW_RESPONSES_PATCH_SERVING_HUNK_8_FAILED")
        self.assertEqual(
            fn(b"", b"patch: **** malformed patch at line 53: PRIVATE"),
            "PREVIEW_RESPONSES_PATCH_MALFORMED_LINE_53")
        self.assertEqual(
            fn(b"", b"patch: **** unexpected end of file in patch"),
            "PREVIEW_RESPONSES_PATCH_TRUNCATED")
        self.assertEqual(
            fn(b"secret payload\\n", b"token=PRIVATE"),
            "PREVIEW_RESPONSES_PATCH_NOT_APPLICABLE")
        self.assertNotIn("PRIVATE", fn(b"", b"patch: **** malformed patch at line 53: PRIVATE"))

    def test_no_implicit_execution_or_model_gpu_network_commands(self):
        content = Path(m.__file__).read_text()
        self.assertIn('args != ["--verify-installed"]', content)
        self.assertIn('importlib.util.spec_from_file_location', content)
        self.assertNotIn('requests.post(', content)
        self.assertNotIn('torch.cuda.', content)
        self.assertNotIn('docker exec', content)

if __name__ == "__main__":
    unittest.main()
