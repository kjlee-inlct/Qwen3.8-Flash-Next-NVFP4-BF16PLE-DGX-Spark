"""Source-only invariants for P1 native Responses terminal patch."""
import ast
import hashlib
import unittest
from pathlib import Path
from src import preview_p1_native_responses_verify as responses
from src.preview_p1_tool_responses_stage import StageBlocked

class NativeResponsesTests(unittest.TestCase):
    def test_exact_patch_scope_and_digest(self):
        data = responses.RESPONSES_PATCH.read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), responses.RESPONSES_SHA256)
        files = [line[6:] for line in data.decode().splitlines() if line.startswith('+++ b/')]
        self.assertEqual(set(files), {responses.SERVING, responses.PROTOCOL})
        self.assertEqual(len(files), 2)
        self.assertIn(b'| ResponseFunctionCallArgumentsDeltaEvent', data)
        self.assertIn(b'| ResponseFunctionCallArgumentsDoneEvent', data)

    def test_source_syntax_and_explicit_guard(self):
        ast.parse(Path(responses.__file__).read_bytes())
        self.assertEqual(responses.main([]), 2)

    def test_behavior_extractor_rejects_unrelated_class(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / 'module.py'
            source.write_text('class Other: pass\n')
            with self.assertRaisesRegex(StageBlocked, 'RESPONSES_CLASS_MISSING'):
                responses.actual_methods(source, 'OpenAIServingResponses', {'responses_stream_generator'})

    def test_expected_targets_are_source_only(self):
        self.assertIn(responses.SERVING, responses.TARGETS)
        self.assertIn(responses.PROTOCOL, responses.TARGETS)
        self.assertNotIn('vllm/v1/core/sched/scheduler.py', responses.TARGETS)

if __name__ == '__main__':
    unittest.main()
