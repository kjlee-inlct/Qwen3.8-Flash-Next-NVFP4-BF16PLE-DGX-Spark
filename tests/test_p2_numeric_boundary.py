"""CPU-only contract tests; never import CUDA, torch or call production API."""
import unittest

from src.p2_numeric_boundary import classify, STRICT_ABS


FLAGS = dict(prefix_off_verified=True, mtp_off_verified=True,
             single_active_request_verified=True, row_api_alignment_verified=True)


def api(values):
    return [dict(token_ids=[7], finish_reason="length", logprobs=[v]) for v in values]


def taps(logits=("a", "a"), probs=("b", "b")):
    return [dict(status="BOUNDARY_CAPTURED", logprobs_mode="raw_logprobs",
                 sampler_raw_logprobs_not_overridden=True,
                 shape=[1, 248320], logits_dtype="torch.float32",
                 logprobs_dtype="torch.float32",
                 pre_sampling_logits_sha256=c*64,
                 pre_gather_logprobs_sha256=p*64)
            for c, p in zip(logits, probs)]


class BoundaryTriageTests(unittest.TestCase):
    def test_first_upstream_divergence(self):
        report = classify(api([-1.0, -1.002]), taps(("a", "c")), **FLAGS)
        self.assertEqual(report["first_observed_difference"], "RAW_LOGITS_OR_UPSTREAM")
        self.assertTrue(report["strict_api_failed"])
        self.assertFalse(report["root_cause_fixed"])

    def test_first_logprobs_divergence(self):
        report = classify(api([-1.0, -1.002]), taps(probs=("b", "d")), **FLAGS)
        self.assertEqual(report["first_observed_difference"],
                         "LOGPROBS_COMPUTATION_OR_PRE_GATHER")

    def test_only_post_sampler_differs(self):
        report = classify(api([-1.0, -1.002]), taps(), **FLAGS)
        self.assertEqual(report["first_observed_difference"], "POST_SAMPLER_OR_API")

    def test_without_provenance_stays_inconclusive(self):
        report = classify(api([-1.0, -1.002]), taps())
        self.assertEqual(report["reason"], "ROW_TO_API_PROVENANCE_UNVERIFIED")
        self.assertFalse(report["boundary_provenance_verified"])

    def test_missing_tap_is_not_api_origin_evidence(self):
        report = classify(api([-1.0, -1.002]), [])
        self.assertEqual(report["reason"], "MISSING_OR_INVALID_SAMPLER_BOUNDARY")

    def test_no_strict_failure_is_not_root_cause_fixed(self):
        report = classify(api([-1.0, -1.0 + STRICT_ABS / 2]), taps(), **FLAGS)
        self.assertEqual(report["first_observed_difference"],
                         "NO_STRICT_API_FAILURE_IN_SAMPLE")
        self.assertFalse(report["root_cause_fixed"])

    def test_mismatched_tokens_not_compared(self):
        runs = api([-1.0, -1.002]); runs[1]["token_ids"] = [8]
        report = classify(runs, taps(), **FLAGS)
        self.assertEqual(report["reason"], "API_TOKEN_OR_FINISH_MISMATCH")
        self.assertIsNone(report["strict_api_failed"])

    def test_rejects_nan_and_shape_drift(self):
        report = classify(api([-1.0, float("nan")]), taps(), **FLAGS)
        self.assertEqual(report["reason"], "API_LOGPROBS_INVALID")
        broken = taps(); broken[1]["shape"] = [2, 248320]
        report = classify(api([-1.0, -1.002]), broken, **FLAGS)
        self.assertEqual(report["reason"], "MISSING_OR_INVALID_SAMPLER_BOUNDARY")


if __name__ == "__main__":
    unittest.main()
