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

    def test_refuses_unapproved_hook(self):
        with self.assertRaises(ValueError):
            obs.install(Mamba, "dangerous", "other")

if __name__ == "__main__":
    unittest.main()
