"""CPU contracts for bounded RejectionSampler GPU window; no Docker/GPU actions."""
from __future__ import annotations

import io
import json
import tarfile
import unittest
from unittest.mock import patch

from src import p1_numeric_gpu_window as window


def run(logprob, *, logits="a"*64, lp="b"*64, accepted=True):
    sample = {"token_ids": list(range(window.MAX_TOKENS)),
              "logprobs": [logprob] + [0.0] * (window.MAX_TOKENS - 1)}
    events = [{"status": "REJECTION_FORWARD_ENTERED"}]
    if accepted:
        events.append({
            "status": "REJECTION_ACCEPTED_BOUNDARY",
            "first_row_logits_sha256": logits,
            "first_row_logprobs_sha256": lp,
            "raw_logits_shape": [1, 1000],
            "logprobs_shape": [1, 1000],
            "raw_logits_dtype": "torch.float32",
            "logprobs_dtype": "torch.float32",
            "mode": "raw_logprobs",
            "processed_mode": False, "logits_mode": False,
        })
    return sample, events


class NumericGpuWindowTests(unittest.TestCase):
    def test_strict_delta_without_relaxation(self):
        a, b = zip(run(0.1), run(0.1), run(0.10021), run(0.1))
        result = window.analyse(list(a), list(b))
        self.assertEqual(
            result["status"], "REJECTION_FIRST_BOUNDARY_SAME_API_DRIFT_UNATTRIBUTED")
        self.assertGreater(result["api_first_token_max_abs_delta"], 1e-4)
        self.assertFalse(result["final_p1_pass"])
        self.assertFalse(result["first_boundary_to_api_token_mapping_proven"])

    def test_rejection_first_boundary_logits_different_unattributed(self):
        a, b = zip(run(0.1), run(0.1, logits="c"*64), run(0.1), run(0.1))
        result = window.analyse(list(a), list(b))
        self.assertEqual(
            result["status"], "REJECTION_FIRST_BOUNDARY_LOGITS_DIFFER_UNATTRIBUTED")

    def test_same_logits_different_logprobs_unattributed(self):
        a, b = zip(run(0.1), run(0.1, lp="f"*64), run(0.1), run(0.1))
        result = window.analyse(list(a), list(b))
        self.assertEqual(
            result["status"], "REJECTION_FIRST_BOUNDARY_LOGPROBS_DIFFER_UNATTRIBUTED")

    def test_missing_rejection_accepted_capture_inconclusive(self):
        a, b = zip(run(0.1), run(0.1), run(0.1, accepted=False), run(0.1))
        result = window.analyse(list(a), list(b))
        self.assertEqual(result["status"], "INCONCLUSIVE_REJECTION_CAPTURE_INCOMPLETE")

    def test_missing_rejection_forward_inconclusive(self):
        a, b = zip(run(0.1, accepted=False), run(0.1, accepted=False),
                   run(0.1, accepted=False), run(0.1, accepted=False))
        result = window.analyse(list(a), [[], [], [], []])
        self.assertEqual(result["status"], "INCONCLUSIVE_NO_REJECTION_FORWARD")

    def test_parse_candidate_private_tar(self):
        items = [
            {"status": "REJECTION_FORWARD_ENTERED", "sequence": 1},
            {"status": "REJECTION_ACCEPTED_BOUNDARY", "sequence": 2},
        ]
        content = "".join("P1_REJECTION_TAP " + json.dumps(x) + "\n" for x in items).encode()
        target = io.BytesIO()
        with tarfile.open(fileobj=target, mode="w:") as archive:
            info = tarfile.TarInfo("p1-numeric-rejection-tap.jsonl")
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
        self.assertEqual(window.parse_rejection_tar(target.getvalue()), items)

    def test_invalid_tar_rejected(self):
        with self.assertRaises(window.Blocked):
            window.parse_rejection_tar(b"not a tar file")

    def test_original_prefix_off_and_mtp2_command_preserved(self):
        cmd = ["--no-enable-prefix-caching", "--speculative-config",
               '{"method":"mtp","num_speculative_tokens":2}']
        with patch.object(window.gpu, "candidate_cmd",
                          return_value=(["--enable-prefix-caching"], "model")):
            on_cmd, _ = window.gpu.candidate_cmd(cmd)
        self.assertIn("--no-enable-prefix-caching", cmd)
        self.assertNotIn("--enable-prefix-caching", cmd)
        self.assertIn("--enable-prefix-caching", on_cmd)

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
