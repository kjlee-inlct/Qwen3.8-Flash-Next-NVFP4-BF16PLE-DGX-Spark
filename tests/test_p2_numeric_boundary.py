"""CPU-only contract tests; never import CUDA, torch or call production API."""
import hashlib
import unittest

from src.p2_numeric_boundary import classify, classify_witness, STRICT_ABS

FLAGS = dict(prefix_off_verified=True, mtp_off_verified=True,
             single_active_request_verified=True, row_api_alignment_verified=True)
WITNESS_FLAGS = dict(prefix_off_verified=True, mtp_off_verified=True,
                     single_active_request_verified=True)


def api(values):
    return [dict(token_ids=[7], finish_reason="length", logprobs=[v]) for v in values]


def taps(logits=("a", "a"), probs=("b", "b"), values=None):
    events = [dict(status="BOUNDARY_CAPTURED", logprobs_mode="raw_logprobs",
                   sampler_raw_logprobs_not_overridden=True,
                   shape=[1, 248320], logits_dtype="torch.float32",
                   logprobs_dtype="torch.float32",
                   pre_sampling_logits_sha256=c*64,
                   pre_gather_logprobs_sha256=p*64)
              for c, p in zip(logits, probs)]
    if values is not None:
        for i, (e, value) in enumerate(zip(events, values), 1):
            e.update(witness_kind="P2_SAMPLER_SELECTED_TOKEN",
                     sequence=i, worker_pid=111,
                     selected_token_id_sha256=hashlib.sha256(b"7").hexdigest(),
                     selected_token_logprob=value)
    return events


class BoundaryTriageTests(unittest.TestCase):
    def test_first_upstream_divergence(self):
        self.assertEqual(classify(api([-1., -1.002]), taps(("a", "c")), **FLAGS)[
            "first_observed_difference"], "RAW_LOGITS_OR_UPSTREAM")

    def test_first_logprobs_divergence(self):
        self.assertEqual(classify(api([-1., -1.002]), taps(probs=("b", "d")), **FLAGS)[
            "first_observed_difference"], "LOGPROBS_COMPUTATION_OR_PRE_GATHER")

    def test_only_post_sampler_differs(self):
        self.assertEqual(classify(api([-1., -1.002]), taps(), **FLAGS)[
            "first_observed_difference"], "POST_SAMPLER_OR_API")

    def test_without_provenance_stays_inconclusive(self):
        self.assertEqual(classify(api([-1., -1.002]), taps())["reason"],
                         "ROW_TO_API_PROVENANCE_UNVERIFIED")

    def test_missing_tap_is_not_api_origin_evidence(self):
        self.assertEqual(classify(api([-1., -1.002]), [])["reason"],
                         "MISSING_OR_INVALID_SAMPLER_BOUNDARY")

    def test_no_strict_failure_is_not_root_cause_fixed(self):
        r = classify(api([-1., -1. + STRICT_ABS / 2]), taps(), **FLAGS)
        self.assertEqual(r["first_observed_difference"], "NO_STRICT_API_FAILURE_IN_SAMPLE")
        self.assertFalse(r["root_cause_fixed"])

    def test_mismatched_tokens_not_compared(self):
        runs = api([-1., -1.002]); runs[1]["token_ids"] = [8]
        self.assertEqual(classify(runs, taps(), **FLAGS)["reason"],
                         "API_TOKEN_OR_FINISH_MISMATCH")

    def test_rejects_nan_and_shape_drift(self):
        self.assertEqual(classify(api([-1., float("nan")]), taps(), **FLAGS)["reason"],
                         "API_LOGPROBS_INVALID")
        broken = taps(); broken[1]["shape"] = [2, 248320]
        self.assertEqual(classify(api([-1., -1.002]), broken, **FLAGS)["reason"],
                         "MISSING_OR_INVALID_SAMPLER_BOUNDARY")

    def test_witness_selected_scalar_correlates_api(self):
        r = classify_witness(api([-1., -1.002]),
                             taps(probs=("b", "d"), values=[-1., -1.002]),
                             **WITNESS_FLAGS)
        self.assertTrue(r["boundary_provenance_verified"])
        self.assertEqual(r["first_observed_difference"],
                         "LOGPROBS_COMPUTATION_OR_PRE_GATHER")
        self.assertTrue(r["strict_api_failed"])

    def test_witness_wrong_selected_token_fails_closed(self):
        data = taps(values=[-1., -1.002]); data[0]["selected_token_id_sha256"] = "0"*64
        self.assertEqual(classify_witness(api([-1., -1.002]), data,
                                          **WITNESS_FLAGS)["reason"],
                         "WITNESS_TOKEN_ID_NOT_ALIGNED")

    def test_witness_scalar_mismatch_fails_closed(self):
        data = taps(values=[-1., -1.5])
        self.assertEqual(classify_witness(api([-1., -1.002]), data,
                                          **WITNESS_FLAGS)["reason"],
                         "WITNESS_TO_API_SCALAR_MISMATCH")

    def test_witness_sequence_and_worker_drift_fail(self):
        data = taps(values=[-1., -1.002]); data[1]["sequence"] = 1
        self.assertEqual(classify_witness(api([-1., -1.002]), data,
                                          **WITNESS_FLAGS)["reason"],
                         "WITNESS_SEQUENCE_OR_ORIGIN_INVALID")
        data = taps(values=[-1., -1.002]); data[1]["worker_pid"] = 222
        self.assertEqual(classify_witness(api([-1., -1.002]), data,
                                          **WITNESS_FLAGS)["reason"],
                         "WITNESS_WORKER_CHANGED")

    def test_witness_requires_runtime_isolation(self):
        self.assertEqual(classify_witness(api([-1., -1.002]),
                                          taps(values=[-1., -1.002]))["reason"],
                         "RUNTIME_ISOLATION_UNVERIFIED")


if __name__ == "__main__":
    unittest.main()
