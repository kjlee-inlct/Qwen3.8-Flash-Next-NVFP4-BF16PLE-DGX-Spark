"""CPU-only contract for live P1 observer. No Docker or CUDA invoked."""
import contextlib
import io
import json
import unittest
from src import p1_prefix_live_observer as obs

class Scalar:
    def __init__(self, value):
        self.value = value
    def item(self):
        return self.value

class Vector:
    shape = (8,)
    device = "cuda:0"
    def __getitem__(self, i):
        return Scalar(7 + i)
    def stride(self):
        return (1,)
    def storage_offset(self):
        return 0
    def element_size(self):
        return 8
    class Storage:
        def nbytes(self):
            return 64
    def untyped_storage(self):
        return self.Storage()

class Mamba:
    def __init__(self):
        self._mamba_state_idx_gpu = Vector()
        self._align_mode = True
        self.cache_config = type("Cfg", (), {})()
        self.cache_config.__dict__.update(block_size=16, mamba_block_size=32)
    def add_request(self, req_index):
        return req_index

class Scheduler:
    def __init__(self):
        self.block_size = 16
        self.cache_config = type("Cfg", (), {})()
        self.cache_config.__dict__.update(block_size=16, mamba_block_size=32)
    def _mamba_block_aligned_split(self):
        return 42

class Tests(unittest.TestCase):
    def setUp(self):
        obs._counts.clear()
        obs._seen_calls.clear()
        obs._saved_mamba_tables.clear()
        obs._recent_mamba_slot.clear()

    def test_real_method_wrappers_emit_numeric_runtime_metadata(self):
        obs._counts.clear()
        obs.install(Mamba, "add_request", "mamba")
        obs.install(Scheduler, "_mamba_block_aligned_split", "scheduler")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(Mamba().add_request(2), 2)
            self.assertEqual(Scheduler()._mamba_block_aligned_split(), 42)
        events = [json.loads(x.split(obs.PREFIX, 1)[1])
                  for x in output.getvalue().splitlines()]
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["state_seed_value"], 9)
        self.assertTrue(events[0]["state_slot_index_in_bounds"])
        self.assertTrue(events[0]["tensor_metadata"]
                        ["_mamba_state_idx_gpu"]["view_within_allocation"])
        self.assertEqual(events[0]["cache_config"]["mamba_block_size"], 32)
        self.assertEqual(events[1]["self_block"]["block_size"], 16)
        self.assertNotIn("physical_mapping_verified", events[0])

    def test_missing_state_does_not_fake_mapping_or_crash(self):
        class Missing:
            def add_request(self, req_index):
                return True
        obs._counts.clear()
        obs.install(Missing, "add_request", "mamba")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertTrue(Missing().add_request(0))
        event = json.loads(out.getvalue().split(obs.PREFIX, 1)[1])
        self.assertFalse(event["state_seed_observed"])


    def test_live_init_links_slot_seed_to_bounded_physical_table_entry(self):
        class Table:
            shape = (8, 16)
            device = "cuda:0"
            def __getitem__(self, key):
                return Scalar(3) if key == (2, 4) else Scalar(-1)
            def stride(self):
                return (16, 1)
            def storage_offset(self):
                return 0
            def element_size(self):
                return 4
            class Storage:
                def nbytes(self):
                    return 8 * 16 * 4
            def untyped_storage(self):
                return self.Storage()
        class Spec:
            def __init__(self):
                self.block_size = 32
        class Group:
            def __init__(self):
                self.kv_cache_spec = {"gdn0": Spec()}
                self.layer_names = ["gdn0"]
        class CacheConfig:
            def __init__(self):
                self.kv_cache_groups = [Group()]
        class WrappedTables:
            def __init__(self):
                self.gpu = Table()
        class CacheTables:
            def __init__(self):
                self.block_tables = [WrappedTables()]
        class MambaInit(Mamba):
            def __init__(self):
                super().__init__()
                self._mamba_group_ids = [0]
                self._mamba_state_idx_gpu = Vector()
                self.vllm_config = VllmCfg()
            def _ensure_align_ctx(self, kv_cache_config, mamba_group_ids, block_tables):
                return True
            def add_request(self, req_index, new_req_data):
                return req_index
        class Config:
            def __init__(self):
                self.static_forward_context = {"gdn0": type(
                    "Attention", (), {"kv_cache": [Vector()]})()}
        class VllmCfg:
            def __init__(self):
                self.compilation_config = Config()
        class Request:
            def __init__(self):
                self.num_computed_tokens = 129
        # Use the same fake GPU seed as the expected resumed block column.
        old_getitem = Vector.__getitem__
        try:
            Vector.__getitem__ = lambda self, i: Scalar(4)
            obs._counts.clear()
            obs.install(MambaInit, "_ensure_align_ctx", "align_ctx")
            obs.install(MambaInit, "add_request", "mamba")
            obj = MambaInit()
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                obj._ensure_align_ctx(CacheConfig(), [0], CacheTables())
                obj.add_request(2, Request())
            events = [json.loads(x.split(obs.PREFIX, 1)[1])
                      for x in output.getvalue().splitlines()]
            self.assertEqual(events[0]["kind"], "align_ctx")
            self.assertEqual(events[0]["mamba_group_table_count"], 1)
            self.assertEqual(events[1]["expected_mamba_seed"], 4)
            self.assertTrue(events[1]["state_seed_matches_expected"])
            mapping = events[1]["physical_map_samples"][0]
            self.assertEqual(mapping["physical_block_id"], 3)
            self.assertTrue(mapping["physical_entry_nonnegative"])
            self.assertTrue(mapping["block_size_matches_mamba_config"])
            self.assertEqual(mapping["state_allocation_blocks"], 8)
            self.assertTrue(mapping["state_allocation_complete"])
            self.assertTrue(mapping["physical_id_within_state_allocation"])
        finally:
            Vector.__getitem__ = old_getitem

    def test_state_slot_arrives_before_align_context_and_samples_after(self):
        class Table:
            shape = (8, 16)
            device = "cuda:0"
            def stride(self): return (16, 1)
            def storage_offset(self): return 0
            def element_size(self): return 4
            def untyped_storage(self):
                return type("Storage", (), {"nbytes": lambda s: 512})()
            def __getitem__(self, indexes):
                return Scalar(3)
        class Group:
            layer_names = ["gdn"]
            kv_cache_spec = {"gdn": type("Spec", (), {"block_size": 32})()}
        class Config:
            kv_cache_groups = [Group()]
        class Wrapped:
            gpu = Table()
        class Tables:
            block_tables = [Wrapped()]
        class Req:
            num_computed_tokens = 129
        class Probe(Mamba):
            def add_request(self, req_index, new_req_data):
                return True
            def _ensure_align_ctx(self, kv_cache_config, mamba_group_ids,
                                  block_tables):
                return True
        obs._counts.clear()
        obs._recent_mamba_slot.clear()
        obs._saved_mamba_tables.clear()
        obs.install(Probe, "add_request", "mamba")
        obs.install(Probe, "_ensure_align_ctx", "align_ctx")
        instance = Probe()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertTrue(instance.add_request(2, Req()))
            self.assertTrue(instance._ensure_align_ctx(Config(), [0], Tables()))
        events = [json.loads(line.split(obs.PREFIX, 1)[1])
                  for line in output.getvalue().splitlines()]
        self.assertEqual([event["kind"] for event in events],
                         ["mamba", "align_ctx"])
        self.assertEqual(events[0]["physical_map_samples"], [])
        samples = events[1]["deferred_state_to_physical_samples"]
        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0]["physical_block_id"], 3)
        self.assertEqual(samples[0]["table_shape"], [8, 16])
        self.assertIsNone(samples[0]["physical_id_within_state_allocation"])

    def test_missing_model_state_allocation_remains_unknown(self):
        class Spec:
            block_size = 32
        class Group:
            layer_names = ["gdn"]
            kv_cache_spec = {"gdn": Spec()}
        class Config:
            kv_cache_groups = [Group()]
        obj = Mamba()
        allocation = obs._state_group_allocations(obj, Config(), 0)
        self.assertIsNone(allocation["allocation_blocks"])
        self.assertFalse(allocation["allocation_complete"])

    def test_uninitialized_tables_are_not_mapping_evidence(self):
        obs._counts.clear()
        class Request:
            num_computed_tokens = 65
        class MambaNoInit(Mamba):
            def add_request(self, req_index, new_req_data):
                return req_index
        obs.install(MambaNoInit, "add_request", "mamba")
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            MambaNoInit().add_request(1, Request())
        event = json.loads(captured.getvalue().split(obs.PREFIX, 1)[1])
        self.assertEqual(event["physical_map_samples"], [])


    def test_live_mamba_cache_config_is_an_observable_whitelisted_field(self):
        obj = Mamba()
        self.assertIs(obs._direct(obj, "cache_config"), obj.cache_config)
        event = obs._observe("scheduler", obj, Mamba.add_request, (), {})
        self.assertEqual(event["cache_config"]["block_size"], 16)
        self.assertEqual(event["cache_config"]["mamba_block_size"], 32)

    def test_slots_and_uniform_mamba_spec_are_observed_not_silently_missing(self):
        class SlottedSpec:
            __slots__ = ("block_size",)
            def __init__(self, value):
                self.block_size = value
        class UniformSpecs:
            __slots__ = ("kv_cache_specs",)
            def __init__(self):
                self.kv_cache_specs = {"gdn0": SlottedSpec(32)}
        class Group:
            __slots__ = ("kv_cache_spec", "layer_names")
            def __init__(self):
                self.kv_cache_spec = UniformSpecs()
                self.layer_names = ["gdn0"]
        class Config:
            __slots__ = ("kv_cache_groups",)
            def __init__(self):
                self.kv_cache_groups = [Group()]
        class SlottedRequest:
            __slots__ = ("num_computed_tokens",)
            def __init__(self):
                self.num_computed_tokens = 129
        self.assertEqual(
            obs._kv_spec_info(Config(), [0])[0]["specs"][0]["block_size"], 32)
        self.assertEqual(obs._direct(SlottedRequest(), "num_computed_tokens"), 129)
        self.assertIsNone(obs._direct(SlottedRequest(), "unreviewed_field"))

    def test_unknown_mamba_spec_size_is_not_reported_as_mismatch(self):
        class Table:
            shape = (1, 1)
            device = "cuda:0"
            def __getitem__(self, key):
                return Scalar(0)
            def stride(self):
                return (1, 1)
            def storage_offset(self):
                return 0
            def element_size(self):
                return 4
            class Storage:
                def nbytes(self):
                    return 4
            def untyped_storage(self):
                return self.Storage()
        class Instance:
            def __init__(self):
                self._p1_observer_mamba_tables = {
                    0: {"table": Table(), "meta": obs._tensor_metadata(Table()),
                        "group": {"specs": []},
                        "allocation": {"allocation_blocks": None}}}
        result = obs._sample_physical(Instance(), 0, 0, 32)
        self.assertEqual(len(result), 1)
        self.assertIsNone(result[0]["block_size_matches_mamba_config"])
        self.assertIsNone(result[0]["physical_id_within_state_allocation"])


    def test_preview_tuple_of_gpu_tensors_is_observed_without_gpu_index_read(self):
        class DirectGpuTable:
            shape = (8, 16)
            device = "cuda:0"
            def stride(self): return (16, 1)
            def storage_offset(self): return 0
            def element_size(self): return 4
            class Storage:
                def nbytes(self): return 512
            def untyped_storage(self): return self.Storage()
            def __getitem__(self, key):
                raise AssertionError("batch-order rows are not request slots")
        class Group:
            layer_names = ["gdn"]
            kv_cache_spec = {"gdn": type("Spec", (), {"block_size": 1600})()}
        class Config:
            kv_cache_groups = [Group()]
        class Model(Mamba):
            def _ensure_align_ctx(self, kv_cache_config, mamba_group_ids,
                                  block_tables):
                return True
        obj = Model()
        obs.install(Model, "_ensure_align_ctx", "align_ctx")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertTrue(obj._ensure_align_ctx(
                Config(), [0], (DirectGpuTable(),)))
        event = json.loads(output.getvalue().split(obs.PREFIX, 1)[1])
        self.assertEqual(event["mamba_group_table_count"], 1)
        self.assertEqual(event["physical_table_metadata"][0]["table"]["shape"],
                         [8, 16])
        self.assertEqual(event["physical_table_metadata"][0]
                         ["table_row_semantics"], "BATCH_ORDER_ROW_UNRESOLVED")
        sample = obs._sample_physical(obj, 2, 4, 1600)[0]
        self.assertFalse(sample["physical_entry_observed"])
        self.assertIsNone(sample["row_in_bounds"])
        self.assertIsNone(sample["physical_id_within_state_allocation"])
        self.assertEqual(sample["physical_read_skipped_reason"],
                         "BATCH_ROW_TO_REQUEST_SLOT_UNVERIFIED")

    def test_spaced_observer_events_capture_later_calls_not_only_startup(self):
        class Model:
            def add_request(self, req_index, new_req_data):
                return True
        obs.install(Model, "add_request", "mamba")
        obj = Model()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            for _ in range(130):
                self.assertTrue(obj.add_request(0, None))
        events = [json.loads(line.split(obs.PREFIX, 1)[1])
                  for line in output.getvalue().splitlines()]
        ordinals = [event["observer_call_ordinal"] for event in events]
        self.assertEqual(ordinals, [1, 2, 3, 4, 8, 16, 32, 64, 128])
        self.assertLessEqual(len(events), obs.MAX_EVENTS)

    def test_refuses_unapproved_hook(self):
        with self.assertRaises(ValueError):
            obs.install(Mamba, "dangerous", "other")

if __name__ == "__main__":
    unittest.main()
