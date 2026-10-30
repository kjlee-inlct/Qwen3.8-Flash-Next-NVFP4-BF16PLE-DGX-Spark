"""Read-only P1 oracle evidence extraction and per-HIT comparison regressions."""
import json
import tempfile
import unittest
from pathlib import Path
from src import p1_prefix_gpu_oracle as oracle
from src import p1_prefix_offline_evidence as audit


def sample(digest="a" * 64, physical_id=7, index=0):
    return {
        "group_id": 2, "physical_block_id": physical_id,
        "layer_sha256_prefix": "a" * 16,
        "state_kind_index": index, "block_boundary_tokens": 6400,
        "state_sha256": digest,
    }


def window(events):
    return {
        "status": "HTTP_SERIAL_WINDOW_BOUNDED_SNAPSHOTS",
        "events": events,
        "full_state_reuse_verified": False,
    }


def report():
    original = sample()
    frames = [
        window([{"phase": "after_postprocess", "samples": [original]}]),
        window([{"phase": "before_preprocess", "samples": [sample()]}]),
        window([{"phase": "before_preprocess", "samples": [sample()]}]),
        window([{"phase": "before_preprocess", "samples": [sample()]}]),
    ]
    return {
        "status": "INCONCLUSIVE_LOGPROB_DIFF_EXCEEDS_STRICT_GATE",
        "all_repeats_token_ids_equal": True,
        "cache_hit_repeat_request_indices_1_based": [2, 3, 4],
        "cache_hit_token_deltas_per_request": [0, 6400, 6400, 6400],
        "per_token_cold_repeat_max_deltas": [0.0, 0.00015, 0.00005, 0.0003],
        "cold_to_repeat_max_deltas": [0.0003, 0.00015, 0.0002],
        "repeat_to_repeat_consecutive_max_deltas": [0.00004, 0.00005],
        "no_hit_strict_numeric_baseline": {
            "status": "NO_HIT_BASELINE_WITHIN_STRICT_GATE",
            "no_hit_control_to_control_max_abs_delta": 0.00006,
        },
        "candidate_request_snapshot_windows": frames,
        "active_candidate_abi": {
            "candidate_state_snapshot_event_count": 24,
            "candidate_state_snapshot_sample_count": 96,
        },
    }


class Tests(unittest.TestCase):
    def test_user_real_gpu_log_wrapper_prefix_parses_embedded_json(self):
        data = report()
        log = ("P1_PREFIX_CANDIDATE_READY\n"
               "2026-10-30 worker: " + json.dumps(data, sort_keys=True) + "\n"
               "P1_PREFIX_GPU_ORACLE_INCONCLUSIVE_LOGPROB_DIFF_EXCEEDS_STRICT_GATE\n")
        self.assertEqual(audit.parse_oracle_report(log), data)

    def test_last_complete_report_wins(self):
        first = report()
        last = report()
        last["per_token_cold_repeat_max_deltas"] = [0.0, 0.00021]
        data = json.dumps(first, sort_keys=True) + "\n" + json.dumps(last)
        parsed = audit.parse_oracle_report(data)
        self.assertEqual(parsed["per_token_cold_repeat_max_deltas"],
                         [0.0, 0.00021])

    def test_missing_json_rejects_without_guessing(self):
        with self.assertRaisesRegex(
                audit.OfflineEvidenceBlocked, "ORACLE_JSON_NOT_FOUND"):
            audit.parse_oracle_report('P1_PREFIX_GPU_ORACLE_INCONCLUSIVE')

    def test_per_token_above_gate_positions_without_model_text(self):
        s = audit.token_drift_summary(report())
        self.assertEqual(s["status"], "TOKEN_LOGPROB_DIFF_EXCEEDS_STRICT_GATE")
        self.assertEqual(s["over_tolerance_token_count"], 2)
        self.assertEqual(s["first_over_tolerance_token_index_1_based"], 2)
        self.assertEqual(
            [e["token_position"] for e in s["largest_token_positions_1_based"]],
            [4, 2, 3, 1])
        self.assertFalse(s["strict_logprob_gate_passed"])

    def test_missing_or_nan_token_deltas_never_pass(self):
        data = report()
        data["per_token_cold_repeat_max_deltas"] = [0.0, float("nan")]
        self.assertEqual(
            audit.token_drift_summary(data)["status"],
            "INCONCLUSIVE_NO_PER_TOKEN_LOGPROB_EVIDENCE")
        data["per_token_cold_repeat_max_deltas"] = None
        self.assertFalse(audit.token_drift_summary(data)[
            "strict_logprob_gate_passed"])

    def test_all_three_hit_requests_separately_match_not_full_proof(self):
        result = audit.analyze_report(report())
        checked = result["sampled_state_cold_hit"]
        self.assertEqual(checked["matched_selected_state_blocks"], 3)
        self.assertEqual(len(checked["per_hit_request_state_comparisons"]), 3)
        self.assertTrue(checked["all_hit_requests_have_comparable_samples"])
        self.assertEqual(
            [x["request_index_1_based"]
             for x in checked["per_hit_request_state_comparisons"]],
            [2, 3, 4])
        self.assertFalse(result["full_GDN_PLE_layer_reuse_verified"])
        self.assertFalse(result["p1_final_pass"])

    def test_one_hit_missing_no_longer_hidden_by_other_hits(self):
        data = report()
        data["candidate_request_snapshot_windows"][3]["events"] = []
        result = audit.analyze_report(data)["sampled_state_cold_hit"]
        self.assertEqual(result["matched_selected_state_blocks"], 2)
        self.assertFalse(result["all_hit_requests_have_comparable_samples"])
        self.assertEqual(
            result["status"], "INCONCLUSIVE_MISSING_COMPARABLE_STATE_FOR_HIT")
        self.assertEqual(result["per_hit_request_state_comparisons"][2]
                         ["comparable_state_count"], 0)

    def test_one_hit_digest_mismatch_does_not_get_overwritten(self):
        data = report()
        data["candidate_request_snapshot_windows"][1]["events"][0]["samples"] = [
            sample("f" * 64)]
        out = oracle.compare_snapshot_windows(
            data["candidate_request_snapshot_windows"],
            data["cache_hit_repeat_request_indices_1_based"])
        self.assertEqual(out["mismatched_selected_state_blocks"], 1)
        self.assertEqual(out["matched_selected_state_blocks"], 2)
        self.assertEqual(
            out["status"], "INCONCLUSIVE_SELECTED_STATE_CONTENT_DIFFERS")
        self.assertFalse(out["full_state_reuse_verified"])

    def test_reassigned_physical_block_is_inconclusive_not_false_match(self):
        data = report()
        data["candidate_request_snapshot_windows"][2]["events"][0]["samples"] = [
            sample(physical_id=40)]
        out = oracle.compare_snapshot_windows(
            data["candidate_request_snapshot_windows"],
            data["cache_hit_repeat_request_indices_1_based"])
        self.assertFalse(out["all_hit_requests_have_comparable_samples"])
        self.assertEqual(out["per_hit_request_state_comparisons"][1]
                         ["comparable_state_count"], 0)

    def test_input_log_symlink_rejected_no_file_write(self):
        with tempfile.TemporaryDirectory() as d:
            orig = Path(d) / "source.log"
            link = Path(d) / "linked.log"
            orig.write_text(json.dumps(report()), encoding="utf-8")
            link.symlink_to(orig)
            with self.assertRaisesRegex(
                    audit.OfflineEvidenceBlocked, "LOG_FILE_MISSING_OR_SYMLINK"):
                audit.read_existing_log(link)
            out = audit.read_existing_log(orig)
            self.assertFalse(out["p1_final_pass"])


if __name__ == "__main__":
    unittest.main()
