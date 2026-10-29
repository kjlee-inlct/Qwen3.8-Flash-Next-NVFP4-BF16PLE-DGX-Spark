"""Candidate-only state content hook. No GPU needed for structural tests."""
import json
import os
import unittest
from unittest.mock import patch
from src import p1_prefix_state_snapshot as snap


class MambaHybridModelState:
    def add_request(self, req_index, new_req_data):
        self.steps.append("request_added")
        return "request_added"

    def __init__(self):
        self.steps = []

    def preprocess_state(self, input_batch, block_tables, kv_cache_config,
                         num_computed_tokens):
        self.steps.append("before_align")
        self._ensure_align_ctx(kv_cache_config, [0], block_tables)
        self.steps.append("after_align")
        return "pre_return"

    def _ensure_align_ctx(self, kv_cache_config, mamba_group_ids, block_tables):
        self.steps.append("align_initialized")
        return "ctx"

    def postprocess_state(self, idx_mapping, num_sampled,
                          num_computed_tokens=None):
        self.steps.append("post_called")
        return "post_return"


class FakeBatch:
    idx_mapping = [0]


class Tests(unittest.TestCase):
    def setUp(self):
        snap._seen.clear()
        snap._contexts.clear()
        snap._request_epochs.clear()

    def tearDown(self):
        snap._seen.clear()
        snap._contexts.clear()
        snap._request_epochs.clear()

    def test_disabled_by_default_does_not_wrap_or_touch_gpu(self):
        class Disabled(MambaHybridModelState):
            pass
        original = Disabled.preprocess_state
        with patch.dict(os.environ, {"P1_PREFIX_STATE_SNAPSHOT": ""}):
            snap.install(Disabled)
        self.assertIs(Disabled.preprocess_state, original)
        self.assertFalse(getattr(Disabled.preprocess_state,
                                 "_p1_content_probe", False))

    def test_rejects_unapproved_class_when_opted_in(self):
        class Unsupported:
            pass
        with patch.dict(os.environ, {"P1_PREFIX_STATE_SNAPSHOT": "1"}):
            with self.assertRaisesRegex(ValueError,
                                        "P1_SNAPSHOT_UNAPPROVED_CLASS"):
                snap.install(Unsupported)

    def test_align_initialized_before_initial_snapshot_then_postprocess(self):
        Instrumented = type("MambaHybridModelState", (MambaHybridModelState,), {})
        b = FakeBatch()
        i = Instrumented()
        config = object()
        with patch.dict(os.environ, {"P1_PREFIX_STATE_SNAPSHOT": "1"}):
            snap.install(Instrumented)
            original_wrapped = Instrumented.preprocess_state
            snap.install(Instrumented)
            self.assertIs(Instrumented.preprocess_state, original_wrapped)
        phases = []
        def sampled(instance, *, phase, **kwargs):
            phases.append((phase, tuple(instance.steps)))
            return {"status": "SNAPSHOTS_COLLECTED_NOT_REUSE_PROOF",
                    "block_boundary_tokens": 6400,
                    "samples": [{"state_sha256": "0" * 64}]}
        with patch.object(snap, "_sample", side_effect=sampled), \
                patch.object(snap, "_emit") as emit:
            self.assertEqual(
                i.preprocess_state(b, ["table"], config, [6400]),
                "pre_return")
            self.assertEqual(
                i.postprocess_state([0], 1, [6400]),
                "post_return")
        self.assertEqual([x[0] for x in phases],
                         ["before_preprocess", "after_postprocess"])
        self.assertEqual(phases[0][1],
                         ("before_align", "align_initialized"))
        self.assertEqual(phases[1][1][-1], "post_called")
        self.assertEqual(emit.call_count, 2)

    def test_silent_empty_step_no_fake_state_event(self):
        Instrumented = type("MambaHybridModelState", (MambaHybridModelState,), {})
        with patch.dict(os.environ, {"P1_PREFIX_STATE_SNAPSHOT": "1"}):
            snap.install(Instrumented)
        i = Instrumented()
        with patch.object(snap, "_sample", return_value={
                "status": "INCONCLUSIVE_NO_VALID_BOUNDARY",
                "samples": []}), patch.object(snap, "_emit") as event:
            i.preprocess_state(FakeBatch(), ["table"], object(), [0])
            event.assert_not_called()

    def test_boundary_requires_positive_exact_multiple_not_estimate(self):
        self.assertEqual(snap._boundary(6400, 1600), 3)
        self.assertEqual(snap._boundary(1600, 1600), 0)
        for n, block in [(0, 1600), (9503, 1600), (6400, 0),
                         (-1, 1600), (True, 1600), (6400.0, 1600)]:
            self.assertIsNone(snap._boundary(n, block))

    def test_long_cold_prompt_9503_and_hit_6400_select_same_block(self):
        self.assertEqual(snap.TARGET_PREFIX_TOKENS, 6400)
        self.assertEqual(snap._target_column(9503, 1600), 3)
        self.assertEqual(snap._target_column(6400, 1600), 3)
        self.assertEqual(snap._target_column(9600, 1600), 3)
        self.assertIsNone(snap._target_column(6399, 1600))
        self.assertIsNone(snap._target_column(9503, 1024))
        self.assertIsNone(snap._target_column(True, 1600))

    def test_snapshot_budget_rearmed_by_add_request_not_repeated_forward(self):
        Instrumented = type("MambaHybridModelState", (MambaHybridModelState,), {})
        i = Instrumented()
        with patch.dict(os.environ, {"P1_PREFIX_STATE_SNAPSHOT": "1"}):
            snap.install(Instrumented)
        values = {"status": "SNAPSHOTS_COLLECTED_NOT_REUSE_PROOF",
                  "block_boundary_tokens": 6400,
                  "samples": [{"state_sha256": "a" * 64}]}
        cfg = object()
        def consume_forward():
            i.preprocess_state(FakeBatch(), ["table"], cfg, [9503])
            i.postprocess_state([0], 1, [9503])
        with patch.object(snap, "_sample", return_value=values), \
                patch("builtins.print") as emit:
            self.assertEqual(i.add_request(0, None), "request_added")
            for _ in range(12):
                consume_forward()  # Cold prefill + decoding.
            self.assertEqual(emit.call_count, 4)
            self.assertEqual(i.add_request(1, None), "request_added")
            consume_forward()  # First HIT request.
            self.assertEqual(emit.call_count, 6)
            consume_forward()
            self.assertEqual(emit.call_count, 8)
            consume_forward()
            self.assertEqual(emit.call_count, 8)
        raw = [json.loads(call.args[0].split(snap.PREFIX, 1)[1])
               for call in emit.call_args_list]
        by_epoch = {(x["request_epoch_ordinal"], x["phase"])
                    for x in raw}
        self.assertEqual(by_epoch, {
            (1, "before_preprocess"), (1, "after_postprocess"),
            (2, "before_preprocess"), (2, "after_postprocess")})
        self.assertTrue(all(not x["content_reuse_verified"] for x in raw))
        self.assertTrue(all(x["ordinal"] <= snap.MAX_EVENTS_PER_PHASE
                            for x in raw))

    def test_epoch_cap_blocks_excess_without_crashing_model(self):
        Instrumented = type("MambaHybridModelState", (MambaHybridModelState,), {})
        i = Instrumented()
        with patch.dict(os.environ, {"P1_PREFIX_STATE_SNAPSHOT": "1"}):
            snap.install(Instrumented)
        for _ in range(snap.MAX_REQUEST_EPOCHS + 3):
            self.assertEqual(i.add_request(0, None), "request_added")
        self.assertEqual(snap._epoch(i), snap.MAX_REQUEST_EPOCHS + 1)
        self.assertFalse(snap._capture_allowed(i, "before_preprocess"))

    def test_epoch_is_only_advanced_after_successful_model_add(self):
        class Failing(MambaHybridModelState):
            def add_request(self, req_index, new_req_data):
                raise ValueError("original add failed")
        Failing.__name__ = "MambaHybridModelState"
        with patch.dict(os.environ, {"P1_PREFIX_STATE_SNAPSHOT": "1"}):
            snap.install(Failing)
        i = Failing()
        with self.assertRaisesRegex(ValueError, "original add failed"):
            i.add_request(0, None)
        self.assertEqual(snap._epoch(i), 0)

    def test_bad_mapping_error_does_not_reach_model_state(self):
        class NoContext:
            _mamba_ctx = None
        sample = snap._sample(NoContext(), phase="before_preprocess",
                              mapping=[0], computed=[1600],
                              tables=[], kv_config=None)
        self.assertFalse(sample["content_reuse_verified"])
        self.assertEqual(sample["status"], "INCONCLUSIVE_CONTEXT_UNINITIALIZED")

    def test_snapshot_marks_never_reuse_verified(self):
        with patch("builtins.print") as printable:
            snap._emit("after_postprocess", {
                "status": "SNAPSHOTS_COLLECTED_NOT_REUSE_PROOF",
                "samples": [{"state_sha256": "a" * 64}]})
        self.assertEqual(printable.call_count, 1)
        text = printable.call_args.args[0]
        self.assertTrue(text.startswith("P1_PREFIX_STATE_SNAPSHOT_JSON:"))
        self.assertIn('"actual_cold_hit_pair_verified":false', text)
        self.assertIn('"content_reuse_verified":false', text)

    def test_sample_limits_are_small_and_explicit(self):
        self.assertLessEqual(snap.MAX_EVENTS_PER_PHASE, 2)
        self.assertLessEqual(snap.MAX_REQUEST_EPOCHS, 8)
        self.assertLessEqual(snap.MAX_TOTAL_EVENTS, 40)
        self.assertLessEqual(snap.MAX_STATES_PER_EVENT, 4)
        self.assertLessEqual(snap.MAX_STATE_BYTES, 32 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
