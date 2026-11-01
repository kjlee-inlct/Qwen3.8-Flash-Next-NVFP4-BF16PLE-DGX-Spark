"""Synthetic CPU/source checks for exact SHA RejectionSampler tap."""
from __future__ import annotations

import ast
import hashlib
import unittest
from unittest.mock import patch

from src import p1_numeric_rejection_stage as rejection


def synthetic() -> bytes:
    return (
        "class RejectionSampler:\n"
        "    def forward(self, metadata, sampling_metadata):\n"
        + rejection.FORWARD_ANCHOR
        + "        return 0\n"
        + "    def _get_logprobs_tensors(self, accepted_logits):\n"
        + rejection.ACCEPTED_ANCHOR
        + "            accepted_logprobs, 1, accepted_tokens)\n"
    ).encode("utf-8")


class RejectionStageTests(unittest.TestCase):
    def test_transform_has_forward_and_accepted_boundary_taps(self):
        source = synthetic()
        with patch.object(rejection, "ORIGINAL_SOURCE_SHA",
                          hashlib.sha256(source).hexdigest()):
            patched = rejection.transform(source)
        ast.parse(patched)
        self.assertIn(b"REJECTION_FORWARD_ENTERED", patched)
        self.assertIn(b"REJECTION_ACCEPTED_BOUNDARY", patched)
        self.assertIn(b"first_row_logits_sha256", patched)
        self.assertIn(b"first_row_logprobs_sha256", patched)
        self.assertIn(rejection.HELPER_MARKER.encode(), patched)

    def test_sha_drift_fails_closed(self):
        with self.assertRaisesRegex(rejection.Blocked, "SHA_DRIFT"):
            rejection.transform(synthetic())

    def test_anchor_drift_fails_closed(self):
        # Keep Python valid so SHA and AST checks pass before the anchor gate.
        raw = synthetic().replace(
            b"if self.is_logits_logprobs_mode\n",
            b"if not self.is_logits_logprobs_mode\n",
            1,
        )
        ast.parse(raw)
        with patch.object(rejection, "ORIGINAL_SOURCE_SHA",
                          hashlib.sha256(raw).hexdigest()):
            with self.assertRaisesRegex(rejection.Blocked, "ANCHOR_DRIFT"):
                rejection.transform(raw)

    def test_double_patch_rejected(self):
        raw = synthetic()
        with patch.object(rejection, "ORIGINAL_SOURCE_SHA",
                          hashlib.sha256(raw).hexdigest()):
            patched = rejection.transform(raw)
        with patch.object(rejection, "ORIGINAL_SOURCE_SHA",
                          hashlib.sha256(patched).hexdigest()):
            with self.assertRaisesRegex(rejection.Blocked, "ALREADY_PATCHED"):
                rejection.transform(patched)

    def test_one_copy_no_run_and_tap_disabled(self):
        df = rejection.dockerfile()
        self.assertEqual(df.count("COPY "), 1)
        self.assertEqual(df.count("FROM "), 1)
        self.assertTrue(df.startswith("FROM " + rejection.PARENT_TAG))
        self.assertIn("ENV VLLM_P1_REJECTION_TAP=0", df)
        self.assertNotIn("RUN ", df)

    def test_parent_id_drift_blocks_before_original_source_copy(self):
        with patch.object(rejection.legacy, "inspect",
                          return_value={"Id": "wrong"}), \
             patch.object(rejection, "read_original_source") as source:
            with self.assertRaisesRegex(rejection.Blocked, "PARENT_IMAGE_ID_DRIFT"):
                rejection.stage()
        source.assert_not_called()

    def test_wrong_original_id_does_not_stage(self):
        with patch.object(rejection.qsa, "preflight") as pre, \
             patch.object(rejection, "stage") as staged:
            code = rejection.main([
                "--expected-head", "0" * 40,
                "--confirm-original-id", "invalid", "--stage"])
        self.assertEqual(code, 2)
        pre.assert_not_called()
        staged.assert_not_called()

    def test_tap_file_candidate_private_not_host_mount(self):
        self.assertEqual(
            rejection.TAP_FILE, "/tmp/p1-numeric-rejection-tap.jsonl")
        self.assertIn("O_NOFOLLOW", rejection.HELPER)
        self.assertIn("_p1_r_os.write(2, payload)", rejection.HELPER)


if __name__ == "__main__":
    unittest.main()
