"""P2 numeric offline CLI contract: synthetic events, no runtime traffic."""
import hashlib
import unittest

from src.p2_numeric_report import analyze_payload


def sample():
    events = []
    for i, (logit_hash, prob_hash, value) in enumerate(
            [("a", "b", -1.0), ("c", "d", -1.002)], start=1):
        events.append({
            "sequence": i,
            "worker_pid": 123,
            "witness_kind": "P2_SAMPLER_SELECTED_TOKEN",
            "status": "BOUNDARY_CAPTURED",
            "logprobs_mode": "raw_logprobs",
            "sampler_raw_logprobs_not_overridden": True,
            "shape": [1, 248320],
            "logits_dtype": "torch.float32",
            "logprobs_dtype": "torch.float32",
            "pre_sampling_logits_sha256": logit_hash * 64,
            "pre_gather_logprobs_sha256": prob_hash * 64,
            "selected_token_id_sha256": hashlib.sha256(b"7").hexdigest(),
            "selected_token_logprob": value,
        })
    return {
        "runs": [{"token_ids": [7], "finish_reason": "length",
                  "logprobs": [value]} for value in (-1.0, -1.002)],
        "events": events,
        "provenance": {"prefix_off_verified": True, "mtp_off_verified": True,
                       "single_active_request_verified": True},
    }


class NumericReportTests(unittest.TestCase):
    def test_aligned_upstream_divergence(self):
        result = analyze_payload(sample())
        self.assertTrue(result["provenance_verified"])
        self.assertEqual(result["first_observed_difference"], "RAW_LOGITS_OR_UPSTREAM")
        self.assertTrue(result["strict_api_failed"])
        self.assertFalse(result["numeric_root_cause_fixed"])

    def test_missing_isolation_blocks_attribution(self):
        case = sample()
        case["provenance"]["mtp_off_verified"] = False
        result = analyze_payload(case)
        self.assertFalse(result["provenance_verified"])
        self.assertEqual(result["reason"], "RUNTIME_ISOLATION_UNVERIFIED")

    def test_scalar_mismatch_inconclusive(self):
        case = sample()
        case["events"][1]["selected_token_logprob"] = -1.5
        result = analyze_payload(case)
        self.assertFalse(result["provenance_verified"])
        self.assertEqual(result["reason"], "WITNESS_TO_API_SCALAR_MISMATCH")

    def test_missing_runs_rejected(self):
        with self.assertRaises(ValueError):
            analyze_payload({"runs": [], "events": [], "provenance": {}})

    def test_not_echoing_sensitive_input(self):
        case = sample()
        case["prompt"] = "SENSITIVE"
        result = analyze_payload(case)
        self.assertNotIn("SENSITIVE", str(result))
        self.assertNotIn("token_ids", result)


if __name__ == "__main__":
    unittest.main()
