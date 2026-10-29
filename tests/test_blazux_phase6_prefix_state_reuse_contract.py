"""CPU-only counterexample tests for P1 full-state reuse evidence."""
import copy
import hashlib
import unittest
from src import p1_prefix_state_reuse_contract as contract

DIGEST = hashlib.sha256(b"p1 synthetic full state").hexdigest()
PROBE = hashlib.sha256(b"synthetic p1 reference prompt").hexdigest()


def live_pair():
    events = []
    for layer, block in (("gdn", 15), ("ple_conv", 17)):
        for phase in ("cold_capture", "hit_restore"):
            events.append({
                "phase": phase, "layer_kind": layer,
                "provenance": "LIVE_CANDIDATE_WORKER",
                "scope": "FULL_STATE_BYTES",
                "timing_verified": True,
                "cache_write_completed": phase == "cold_capture",
                "cache_copy_completed": phase == "hit_restore",
                "has_initial_state": phase == "hit_restore",
                "state_location": ("PERSISTENT_CACHE_BLOCK" if
                                   phase == "cold_capture" else
                                   "RESTORED_RUNNING_STATE"),
                "synthetic_probe_sha256": PROBE,
                "block_boundary_tokens": 3200,
                "group_id": 0, "physical_block_id": block,
                "shape": [1600, 8], "dtype": "bfloat16",
                "state_sha256": DIGEST,
            })
    return events


class StateReuseEvidenceTests(unittest.TestCase):
    def test_equal_full_state_still_needs_actual_live_hook_audit(self):
        x = contract.validate_state_reuse(live_pair(), prefix_hit_tokens=6400)
        self.assertTrue(x["state_content_digests_match"])
        self.assertFalse(x["verified"])
        self.assertEqual(x["matching_layer_kinds"], 2)

    def test_no_hit_never_passes(self):
        x = contract.validate_state_reuse(live_pair(), prefix_hit_tokens=0)
        self.assertEqual(x["status"], "INCONCLUSIVE_NO_PREFIX_HIT")

    def test_missing_ple_conv_rejected(self):
        x = contract.validate_state_reuse(live_pair()[:2], prefix_hit_tokens=6400)
        self.assertFalse(x["verified"])

    def test_duplicate_cannot_replace_missing_layer(self):
        v = live_pair()
        v[2] = copy.deepcopy(v[0])
        v[3] = copy.deepcopy(v[1])
        x = contract.validate_state_reuse(v, prefix_hit_tokens=6400)
        self.assertEqual(x["status"], "INCONCLUSIVE_DUPLICATE_STATE_EVENT")

    def test_checksum_mismatch_is_failure_not_unknown(self):
        v = live_pair()
        v[3]["state_sha256"] = hashlib.sha256(b"all zero").hexdigest()
        x = contract.validate_state_reuse(v, prefix_hit_tokens=6400)
        self.assertEqual(x["status"], "FAIL_RESTORED_STATE_CONTENT_DIFFERS")

    def test_synthetic_or_static_evidence_never_passes(self):
        v = live_pair()
        v[1]["provenance"] = "SYNTHETIC_CPU"
        x = contract.validate_state_reuse(v, prefix_hit_tokens=6400)
        self.assertFalse(x["verified"])

    def test_missing_restore_completion_rejected(self):
        v = live_pair()
        v[1]["cache_copy_completed"] = False
        x = contract.validate_state_reuse(v, prefix_hit_tokens=6400)
        self.assertEqual(x["status"], "INCONCLUSIVE_HIT_RESTORE_POINT")

    def test_wrong_block_identity_rejected(self):
        v = live_pair()
        v[1]["physical_block_id"] = 4
        x = contract.validate_state_reuse(v, prefix_hit_tokens=6400)
        self.assertEqual(x["status"], "INCONCLUSIVE_COLD_HIT_IDENTITY_DRIFT")

    def test_wrong_probe_id_rejected(self):
        v = live_pair()
        v[3]["synthetic_probe_sha256"] = "0" * 64
        x = contract.validate_state_reuse(v, prefix_hit_tokens=6400)
        self.assertEqual(x["status"], "INCONCLUSIVE_COLD_HIT_IDENTITY_DRIFT")

    def test_sparse_sample_not_full_state(self):
        v = live_pair()
        v[0]["scope"] = "SELECTED_SCALAR"
        x = contract.validate_state_reuse(v, prefix_hit_tokens=6400)
        self.assertEqual(x["status"], "INCONCLUSIVE_STATE_SNAPSHOT_PROVENANCE")

    def test_missing_has_initial_state_rejected(self):
        v = live_pair()
        v[1]["has_initial_state"] = None
        x = contract.validate_state_reuse(v, prefix_hit_tokens=6400)
        self.assertEqual(x["status"], "INCONCLUSIVE_HIT_RESTORE_POINT")

    def test_no_state_data_in_stage_source_inspector(self):
        fake = (
            "class MambaHybridModelState:\n"
            "  def add_request(self, req_index, new_req_data): return None\n"
            "  def _ensure_align_ctx(self, kv_cache_config, mamba_group_ids, block_tables): return None\n"
            "  def preprocess_state(self, input_batch, block_tables, kv_cache_config, num_computed_tokens):\n"
            "    self._copy_state()\n"
            "  def postprocess_state(self, idx_mapping, num_sampled, num_computed_tokens):\n"
            "    self._copy_state()\n"
        ).encode("utf-8")
        result = contract.inspect_stage_source(fake)
        self.assertIn("self._copy_state", result["methods"]["preprocess_state"]["calls"])
        self.assertFalse(result["gpu_loaded"])
        self.assertFalse(result["runtime_state_content_verified"])

    def test_stage_method_drift_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "MAMBA_MODEL_CLASS_ABI_DRIFT"):
            contract.inspect_stage_source(b"class SomethingElse: pass\n")
        with self.assertRaisesRegex(ValueError, "MAMBA_RESTORE_METHOD_ABI_DRIFT"):
            contract.inspect_stage_source(
                b"class MambaHybridModelState:\n def add_request(self): pass\n")


if __name__ == "__main__":
    unittest.main()
