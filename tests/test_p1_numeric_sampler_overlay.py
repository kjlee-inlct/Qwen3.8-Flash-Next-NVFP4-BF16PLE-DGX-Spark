"""Synthetic CPU tests of the SHA-pinned candidate-only sampler patch."""
from __future__ import annotations

import ast
import hashlib
import unittest
from unittest.mock import patch

from src import p1_numeric_sampler_overlay as tap


def sample() -> bytes:
    return (
        "import torch\n"
        "class Sampler:\n"
        "    def forward(self, logits, sampling_metadata, logprobs_mode):\n"
        + tap.INIT
        + "        if num_logprobs is not None:\n"
        + tap.RAW
        + "            else:\n"
        + "                raw_logprobs = None\n"
        + "        sampled, processed_logprobs = self.sample(logits, sampling_metadata)\n"
        + tap.OVERRIDE
        + "        return raw_logprobs\n"
    ).encode()


class SamplerTapTests(unittest.TestCase):
    def test_patch_changes_only_pinned_anchors_and_is_valid_python(self):
        original = sample()
        with patch.object(tap, "SAMPLER_SHA256", hashlib.sha256(original).hexdigest()):
            patched = tap.transform(original)
        ast.parse(patched)
        self.assertEqual(patched.count(tap.HELPER_MARKER.encode()), 1)
        self.assertIn(b'raw_logits.shape[0] != 1', patched)
        self.assertIn(b'sampler_logprobs_overridden', patched)
        self.assertIn(b'pre_sampling_logits_sha256', patched)
        self.assertIn(b'pre_gather_logprobs_sha256', patched)

    def test_exact_sha_mismatch_is_blocked(self):
        with self.assertRaisesRegex(tap.Blocked, "SHA_DRIFT"):
            tap.transform(sample())

    def test_missing_anchor_is_blocked(self):
        original = sample().replace(tap.OVERRIDE.encode(), b"")
        with patch.object(tap, "SAMPLER_SHA256", hashlib.sha256(original).hexdigest()):
            with self.assertRaisesRegex(tap.Blocked, "ANCHOR_MISMATCH"):
                tap.transform(original)

    def test_double_application_is_blocked(self):
        original = sample()
        with patch.object(tap, "SAMPLER_SHA256", hashlib.sha256(original).hexdigest()):
            patched = tap.transform(original)
        with patch.object(tap, "SAMPLER_SHA256", hashlib.sha256(patched).hexdigest()):
            with self.assertRaisesRegex(tap.Blocked, "ALREADY_PATCHED"):
                tap.transform(patched)

    def test_dockerfile_defaults_off_and_pins_parent(self):
        df = tap.dockerfile()
        self.assertTrue(df.startswith("FROM " + tap.INTEGRATED_IMAGE_ID))
        self.assertEqual(df.count("COPY "), 1)
        self.assertIn("ENV VLLM_P1_NUMERIC_TAP=0", df)
        self.assertNotIn("RUN ", df)

    def test_wrong_identity_never_reads_original(self):
        with patch.object(tap.qsa, "preflight") as pre, \
             patch.object(tap, "stage") as staged:
            status = tap.main([
                "--expected-head", "0" * 40,
                "--confirm-original-id", "incorrect",
                "--stage",
            ])
        self.assertEqual(status, 2)
        pre.assert_not_called()
        staged.assert_not_called()


if __name__ == "__main__":
    unittest.main()
