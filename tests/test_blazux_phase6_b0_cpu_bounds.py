"""P6-B0 bounded CPU-only synthetic rehearsal: never exercises live GPU/ABI."""
import copy
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
FILE = ROOT / "src/phase6_b0_cpu_bounds.py"
spec = importlib.util.spec_from_file_location("phase6_b0_cpu_bounds", FILE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def make_case():
    return {
        "tables": [
            {"dtype": "int32", "columns": 3, "row_stride_elements": 5,
             "physical_ids": [[0, 1, -1], [1, 0, -1]]},
            {"dtype": "int32", "columns": 2, "row_stride_elements": 4,
             "physical_ids": [[1, 0]]},
        ],
        "states": [
            {"group_index": 0, "kind": "conv_ds", "block_stride_bytes": 16,
             "payload_bytes": 12, "physical_blocks": 2,
             "storage_hex": bytes(range(48)).hex()},
            {"group_index": 1, "kind": "temporal", "block_stride_bytes": 16,
             "payload_bytes": 16, "physical_blocks": 2,
             "storage_hex": bytes(range(80, 112)).hex()},
        ],
        "operations": [
            {"state_index": 0, "row_index": 0, "src_column": 0,
             "dst_column": 1, "src_offset_bytes": 3,
             "dst_offset_bytes": 1, "length_bytes": 8},
            {"state_index": 1, "row_index": 0, "src_column": 0,
             "dst_column": 1, "src_offset_bytes": 0,
             "dst_offset_bytes": 0, "length_bytes": 16},
        ],
    }


class B0PhysicalBoundsTests(unittest.TestCase):
    def test_demo_is_cpu_only_and_a_remains_blocked(self):
        r = mod.demo()
        self.assertEqual(r["status"], "CPU_SYNTHETIC_ONLY_NOT_GPU")
        self.assertEqual(r["p6_a_active_abi"], "BLOCKED")
        self.assertEqual(r["p6_b_gpu_status"], "NOT_RUN")
        self.assertEqual((r["tables"], r["states"], r["operations_checked"]),
                         (2, 2, 2))

    def test_conv_ds_offset_bytes_and_padding(self):
        case = make_case()
        out = mod.evaluate(case)["buffers"][0]
        src = bytes(range(48))
        self.assertEqual(out[17:25], src[3:11])
        self.assertEqual(out[16:17], src[16:17])
        self.assertEqual(out[25:48], src[25:48])
        self.assertEqual(out[:16], src[:16])

    def test_temporal_copy_respects_group_mapping(self):
        original = bytes(range(80, 112))
        out = mod.evaluate(make_case())["buffers"][1]
        self.assertEqual(out[:16], original[16:32])
        self.assertEqual(out[16:], original[16:])

    def test_case_is_immutable_to_evaluator(self):
        case = make_case()
        frozen = copy.deepcopy(case)
        mod.evaluate(case)
        self.assertEqual(case, frozen)

    def test_second_row_is_not_request_slot_zero(self):
        case = make_case()
        case["operations"] = [dict(case["operations"][0], row_index=1)]
        out = mod.evaluate(case)["buffers"][0]
        orig = bytes(range(48))
        self.assertEqual(out[1:9], orig[19:27])
        self.assertEqual(out[17:25], orig[17:25])

    def test_conv_sd_is_valid_synthetic_kind(self):
        case = make_case()
        case["states"][0]["kind"] = "conv_sd"
        self.assertEqual(mod.evaluate(case)["states"], 2)

    def test_selected_negative_sentinel_rejected(self):
        case = make_case()
        case["operations"][0]["dst_column"] = 2
        with self.assertRaises(mod.Blocked):
            mod.evaluate(case)

    def test_physical_id_out_of_allocation_rejected(self):
        case = make_case()
        case["tables"][0]["physical_ids"][0][1] = 2
        with self.assertRaises(mod.Blocked):
            mod.evaluate(case)

    def test_unknown_physical_id_type_rejected(self):
        case = make_case()
        case["tables"][0]["physical_ids"][0][1] = True
        with self.assertRaises(mod.Blocked):
            mod.evaluate(case)

    def test_allocated_storage_underflow_rejected(self):
        case = make_case()
        case["states"][0]["storage_hex"] = bytes(range(31)).hex()
        with self.assertRaises(mod.Blocked):
            mod.evaluate(case)

    def test_payload_larger_than_stride_rejected(self):
        case = make_case()
        case["states"][0]["payload_bytes"] = 17
        with self.assertRaises(mod.Blocked):
            mod.evaluate(case)

    def test_copy_outside_natural_payload_rejected(self):
        case = make_case()
        case["operations"][0]["src_offset_bytes"] = 6
        case["operations"][0]["length_bytes"] = 7
        with self.assertRaises(mod.Blocked):
            mod.evaluate(case)

    def test_byte_stride_not_int32_table_stride(self):
        case = make_case()
        case["tables"][0]["row_stride_elements"] = 6
        self.assertEqual(mod.evaluate(case)["buffers"][0][17:25],
                         bytes(range(3, 11)))

    def test_too_small_row_stride_rejected(self):
        case = make_case()
        case["tables"][0]["row_stride_elements"] = 2
        with self.assertRaises(mod.Blocked):
            mod.evaluate(case)

    def test_bad_dtype_rejected(self):
        case = make_case()
        case["tables"][0]["dtype"] = "int64"
        with self.assertRaises(mod.Blocked):
            mod.evaluate(case)

    def test_ambiguous_alias_overlap_rejected(self):
        case = make_case()
        case["tables"][0]["physical_ids"][0][1] = 0
        with self.assertRaises(mod.Blocked):
            mod.evaluate(case)

    def test_exact_same_physical_range_is_noop(self):
        case = make_case()
        case["tables"][0]["physical_ids"][0][1] = 0
        case["operations"][0]["dst_offset_bytes"] = 3
        result = mod.evaluate(case)
        self.assertEqual(result["buffers"][0], bytes(range(48)))

    def test_zero_length_does_not_change_any_byte(self):
        case = make_case()
        case["operations"][0]["length_bytes"] = 0
        case["operations"][1]["length_bytes"] = 0
        result = mod.evaluate(case)
        self.assertEqual(result["buffers"][0], bytes(range(48)))
        self.assertEqual(result["buffers"][1], bytes(range(80, 112)))

    def test_late_invalid_operation_aborts_entire_transaction(self):
        case = make_case()
        first = copy.deepcopy(case)
        case["operations"][-1]["dst_column"] = 99
        with self.assertRaises(mod.Blocked):
            mod.evaluate(case)
        self.assertEqual(case["states"], first["states"])
        self.assertEqual(case["operations"][0], first["operations"][0])

    def test_bool_index_is_not_an_integer(self):
        case = make_case()
        case["operations"][0]["row_index"] = False
        with self.assertRaises(mod.Blocked):
            mod.evaluate(case)

    def test_unknown_case_fields_rejected(self):
        case = make_case()
        case["unsafe_runtime"] = "please launch"
        with self.assertRaises(mod.Blocked):
            mod.evaluate(case)

    def test_invalid_kind_list_fails_closed(self):
        case = make_case()
        case["states"][0]["kind"] = ["conv_ds"]
        with self.assertRaises(mod.Blocked):
            mod.evaluate(case)

    def test_storage_not_hex_or_too_large_rejected(self):
        case = make_case()
        case["states"][0]["storage_hex"] = "redacted-token"
        with self.assertRaises(mod.Blocked):
            mod.evaluate(case)
        case["states"][0]["storage_hex"] = "ff" * (mod.MAX_STORAGE_BYTES + 1)
        with self.assertRaises(mod.Blocked):
            mod.evaluate(case)

    def test_no_dgx_gpu_docker_network_imports(self):
        text = FILE.read_text(encoding="utf-8")
        for forbidden in ("import torch", "import vllm", "import triton",
                          "import docker", "import socket", "import subprocess",
                          "docker run", "docker exec", "requests.post("):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)

    def test_script_is_offline_fail_closed(self):
        shell = (ROOT / "scripts/phase6-b0-offline.sh").read_text(encoding="utf-8")
        self.assertIn("verify-source-state.py", shell)
        self.assertIn("phase6_b0_cpu_bounds.py --demo", shell)
        self.assertIn("feature/blazux-phase6-runtime-gates", shell)
        for forbidden in ("docker run", "docker exec", "curl ", "--execute",
                          "run-llama-benchy.sh"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, shell)


if __name__ == "__main__":
    unittest.main()
