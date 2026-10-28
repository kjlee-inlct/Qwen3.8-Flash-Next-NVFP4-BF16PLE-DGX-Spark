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

    def test_no_implicit_execution_or_model_gpu_network_commands(self):
        content = Path(m.__file__).read_text()
        self.assertIn('args != ["--verify-installed"]', content)
        self.assertIn('importlib.util.spec_from_file_location', content)
        self.assertNotIn('requests.post(', content)
        self.assertNotIn('torch.cuda.', content)
        self.assertNotIn('docker exec', content)

if __name__ == "__main__":
    unittest.main()
