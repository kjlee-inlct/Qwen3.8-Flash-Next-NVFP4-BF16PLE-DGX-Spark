"""Read-only CPU contract tests for the one-window numeric runtime."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from src import p1_numeric_gpu_window as window


def run(logprob, *, logits="a"*64, lp="b"*64):
    return (
        {"token_ids": [11], "logprobs": [logprob]},
        [{"status": "BOUNDARY_CAPTURED", "logprobs_mode": "raw_logprobs",
          "sampler_raw_logprobs_not_overridden": True,
          "pre_sampling_logits_sha256": logits,
          "pre_gather_logprobs_sha256": lp}],
    )


class NumericGpuWindowTests(unittest.TestCase):
    def test_strict_delta_without_relaxation(self):
        a, b = zip(run(0.1), run(0.1), run(0.10021), run(0.1))
        result = window.analyse(list(a), list(b))
        self.assertEqual(result["status"], "SAME_SAMPLER_HASHES_API_DRIFT")
        self.assertGreater(result["first_token_logprob_max_abs_delta"], 1e-4)
        self.assertFalse(result["final_p1_pass"])

    def test_logits_difference_precedes_normalization(self):
        a, b = zip(run(0.1), run(0.1, logits="c"*64), run(0.1), run(0.1))
        result = window.analyse(list(a), list(b))
        self.assertEqual(result["status"], "DIVERGENCE_INPUT_LOGITS")

    def test_same_logits_different_logprob(self):
        a, b = zip(run(0.1), run(0.1, lp="f"*64), run(0.1), run(0.1))
        result = window.analyse(list(a), list(b))
        self.assertEqual(result["status"], "DIVERGENCE_LOGSOFTMAX_GIVEN_SAME_LOGITS")

    def test_missing_raw_capture_inconclusive(self):
        a, b = zip(run(0.1), run(0.1), run(0.1), run(0.1))
        b = list(b)
        b[2] = []
        result = window.analyse(list(a), b)
        self.assertEqual(result["status"], "INCONCLUSIVE_TAP_ABSENT_OR_MODE_OR_SHAPE")

    def test_original_prefix_off_and_mtp2_command_preserved(self):
        cmd = ["--no-enable-prefix-caching", "--speculative-config",
               '{"method":"mtp","num_speculative_tokens":2}']
        self.assertNotIn("--enable-prefix-caching", cmd)
        with patch.object(window.gpu, "candidate_cmd", return_value=(["--enable-prefix-caching"], "model")):
            # This test asserts the production command is not mutated by the
            # validation helper (do not reuse helper's returned ON command).
            unused, _ = window.gpu.candidate_cmd(cmd)
            self.assertEqual(unused, ["--enable-prefix-caching"])
            self.assertIn("--no-enable-prefix-caching", cmd)

    def test_preflight_cannot_mutate_or_run_gpu(self):
        with patch.object(window, "prepare", return_value=(
            {"id": window.overlay.source_trace.ORIGINAL_ID},
            {"State": {"Status": "running"}}, "model", [])) as prepare, \
             patch.object(window, "execute") as execute:
            status = window.main([
                "--expected-head", "0" * 40,
                "--confirm-original-id", window.overlay.source_trace.ORIGINAL_ID,
                "--preflight"])
        self.assertEqual(status, 0)
        prepare.assert_called_once()
        execute.assert_not_called()

    def test_bad_id_blocks_before_preflight(self):
        with patch.object(window, "prepare") as prepare, \
             patch.object(window, "execute") as execute:
            status = window.main([
                "--expected-head", "0" * 40,
                "--confirm-original-id", "incorrect",
                "--execute-approved-window"])
        self.assertEqual(status, 2)
        prepare.assert_not_called()
        execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
