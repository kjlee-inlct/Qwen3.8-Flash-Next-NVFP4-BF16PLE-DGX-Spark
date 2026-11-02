"""P2 source transform tests: no vLLM, GPU, Docker, API or model."""
import ast
import hashlib
import unittest
from unittest.mock import patch

from src import p2_numeric_sampler_witness as witness


def fixture():
    return (
        "import torch\n"
        "class Sampler:\n"
        "    def forward(self, logits, sampling_metadata, logprobs_mode):\n"
        + witness.INIT
        + "        if num_logprobs is not None:\n"
        + witness.RAW
        + "        sampled, processed_logprobs = self.sample(logits, sampling_metadata)\n"
        + "        if processed_logprobs is not None:\n"
        + "            raw_logprobs = processed_logprobs\n"
        + witness.SAMPLED
        + "        return sampled\n"
    ).encode()


class TransformTests(unittest.TestCase):
    def test_exact_anchored_instrumentation(self):
        raw = fixture()
        with patch.object(witness, "SOURCE_SHA256", hashlib.sha256(raw).hexdigest()):
            patched = witness.transform(raw)
        ast.parse(patched)
        self.assertEqual(patched.count(witness.MARKER.encode()), 1)
        self.assertIn(b'VLLM_P2_NUMERIC_WITNESS", "0"', patched)
        self.assertIn(b'_p2_witness_capture(logits, raw_logprobs)', patched)
        self.assertIn(b'_p2_witness_emit(_p2_witness_record', patched)
        self.assertIn(b'logprobs[0, token].item()', patched)
        self.assertIn(b'processed is not None', patched)
        self.assertIn(b'O_NOFOLLOW', patched)
        self.assertNotIn(b'docker ', patched)

    def test_wrong_sha_fails_closed(self):
        with self.assertRaisesRegex(witness.Blocked, "SHA_DRIFT"):
            witness.transform(fixture())

    def test_anchor_missing_fails_closed(self):
        raw = fixture().replace(witness.SAMPLED.encode(), b'')
        with patch.object(witness, "SOURCE_SHA256", hashlib.sha256(raw).hexdigest()):
            with self.assertRaisesRegex(witness.Blocked, "ANCHOR_DRIFT"):
                witness.transform(raw)

    def test_reapplication_fails_sha(self):
        raw = fixture()
        with patch.object(witness, "SOURCE_SHA256", hashlib.sha256(raw).hexdigest()):
            patched = witness.transform(raw)
        with patch.object(witness, "SOURCE_SHA256", hashlib.sha256(patched).hexdigest()):
            with self.assertRaisesRegex(witness.Blocked, "ALREADY_PATCHED"):
                witness.transform(patched)


if __name__ == "__main__":
    unittest.main()
