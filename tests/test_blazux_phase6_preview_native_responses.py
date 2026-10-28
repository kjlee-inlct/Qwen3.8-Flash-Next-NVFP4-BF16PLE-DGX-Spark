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
        # Preserve the exact upstream-compatible original hunk context.
        self.assertIn(b'@@ -843,7 +856,11 @@', data)

    def test_union_hunk_applies_with_exact_fuzz_zero(self):
        import shutil
        import subprocess
        import tempfile

        patch_data = responses.RESPONSES_PATCH.read_bytes()
        header = b"@@ -843,7 +856,11 @@\\n"
        self.assertEqual(patch_data.count(header), 1)
        hunk = patch_data.split(header, 1)[1].split(
            b"--- a/vllm/entrypoints/openai/responses/serving.py\\n", 1
        )[0]
        # GNU patch needs the original three trailing context lines.
        self.assertTrue(hunk.endswith(
            b"     | ResponseInProgressEvent\\n"
            b"     | ResponseCompletedEvent\\n"
            b"     | ResponseOutputItemAddedEvent\\n"
        ))
        preimage = b"".join(
            line[1:] + b"\\n"
            for line in hunk.splitlines()
            if line.startswith((b" ", b"-"))
        )
        self.assertIsNotNone(shutil.which("patch"))
        with tempfile.TemporaryDirectory(prefix="p1-union-hunk-") as tmp:
            root = Path(tmp)
            target = root / "protocol.py"
            target.write_bytes(
                b"# synthetic source line\\n" * 842 + preimage
                + b"     | ResponseOutputItemDoneEvent\\n"
            )
            command_patch = (
                b"--- a/protocol.py\\n+++ b/protocol.py\\n"
                + header + hunk
            )
            proc = subprocess.run(
                ["patch", "--batch", "--forward", "--fuzz=0", "-p1",
                 "--no-backup-if-mismatch"],
                input=command_patch, cwd=root, capture_output=True,
                check=False, timeout=10,
            )
            self.assertEqual(proc.returncode, 0,
                             "exact hunk rejected against synthetic preimage")
            result = target.read_text()
            self.assertIn("    | ResponseFunctionCallArgumentsDeltaEvent\\n", result)
            self.assertIn("    | ResponseFunctionCallArgumentsDoneEvent\\n", result)

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
