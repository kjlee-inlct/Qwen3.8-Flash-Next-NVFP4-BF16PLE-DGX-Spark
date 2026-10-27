"""CPU-only regression for the Phase5 grouped shell gate; never imports vLLM.

Synthetic oracles model contract assumptions; they are not Triton kernel tests.
"""

import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/phase5-mamba-batch-check.sh"


def embedded_python():
    body = SCRIPT.read_text(encoding="utf-8")
    marker = "<<'PYCODE'\n"
    if body.count(marker) != 1 or body.count("\nPYCODE\n") != 1:
        raise ValueError("expected exactly one bounded Python heredoc")
    return body.split(marker, 1)[1].split("\nPYCODE\n", 1)[0]


def pure_oracles():
    code = embedded_python()
    pure = code.split('\nspec = importlib.util.find_spec("vllm")', 1)
    if len(pure) != 2:
        raise ValueError("installed vLLM source gate unexpectedly moved")
    scope = {}
    exec(compile(pure[0], "phase5_batch_pure_oracles", "exec"), scope)
    return scope


class Phase5MambaPhysicalBatchGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.o = pure_oracles()

    def test_python_heredoc_ast_parses(self):
        self.assertIsInstance(ast.parse(embedded_python()), ast.Module)

    def test_source_sha_inventory_is_pinned(self):
        self.assertEqual(len(self.o["EXPECTED"]), 4)
        self.assertEqual(self.o["EXPECTED"]["v1/worker/mamba_utils.py"],
                         "25254d005f42b64dd55d15a5c646018f5599d971c23e7ca395eb5acaf4f41ed3")

    def test_script_requires_offline_gate_before_docker(self):
        s = SCRIPT.read_text(encoding="utf-8")
        self.assertLess(s.index("scripts/phase5-check-offline.sh"), s.index("docker run"))
        self.assertIn("PHASE5_BATCH_SOURCE_HEAD", s)

    def test_script_is_explicitly_cpu_only(self):
        s = SCRIPT.read_text(encoding="utf-8")
        for anchor in ("--network=none", "--runtime=runc", "--read-only",
                       "--cap-drop=ALL", "NVIDIA_VISIBLE_DEVICES=void",
                       "CUDA_VISIBLE_DEVICES=-1", "--pull=never"):
            with self.subTest(anchor=anchor):
                self.assertIn(anchor, s)

    def test_checkpoints_g1_to_g7(self):
        code = embedded_python()
        for i in range(1, 8):
            self.assertIn(f'print("G{i} PASS:', code) if i != 6 else self.assertIn('print(f"G6 PASS:', code)
        self.assertIn("RUNTIME_CORRECTNESS_VERIFIED=False", code)
        self.assertIn("PATCH_APPROVED=False", code)

    def test_mapping_v1_identity(self):
        self.assertEqual(self.o["mapped_row"](2), (2, 2))

    def test_mapping_v2_separates_batch_row_from_request_slot(self):
        self.assertEqual(self.o["mapped_row"](0, [5, -1, 2]), (0, 5))

    def test_mapping_negative_sentinel(self):
        self.assertIsNone(self.o["mapped_row"](1, [5, -1, 2]))

    def test_mapping_rejects_bad_batch(self):
        f = self.o["mapped_row"]
        for args in [(-1, [0]), (2, [0]), (True, [0]), (0, [None])]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                f(*args)

    def test_equal_block_size_boundary(self):
        f = self.o["index_for_positive"]
        self.assertEqual([f(n, 16) for n in (0, 1, 16, 17, 32, 33)],
                         [-1, 0, 0, 1, 1, 2])

    def test_mismatched_block_sensitivity_not_bug_proof(self):
        f = self.o["index_for_positive"]
        self.assertEqual((f(17, 16), f(17, 32)), (1, 0))

    def test_invalid_block_or_position(self):
        f = self.o["index_for_positive"]
        for pair in [(-1, 16), (1, 0), (1, -2), (True, 16), (3, True)]:
            with self.subTest(pair=pair), self.assertRaises(ValueError):
                f(*pair)

    def test_postprocess_skip(self):
        self.assertEqual(self.o["post"](31, 1, 1, 16)[0], "SKIP")

    def test_postprocess_same_column_noop(self):
        self.assertEqual(self.o["post"](32, 1, 1, 16), ("NOOP", 1, 0))

    def test_postprocess_same_column_nonzero_bias_still_copies(self):
        self.assertEqual(self.o["post"](32, 2, 1, 16), ("COPY", 1, 1))

    def test_postprocess_changed_column(self):
        self.assertEqual(self.o["post"](32, 2, 0, 16), ("COPY", 1, 1))

    def test_postprocess_invalid_synthetic_destination(self):
        self.assertEqual(self.o["post"](0, 1, -1, 16)[0], "INVALID_SYNTHETIC")

    def test_postprocess_rejects_bad_inputs(self):
        f = self.o["post"]
        for values in [(-1, 1, 0, 16), (32, 2, 0, 0), (32, -1, 0, 16),
                       (32, 2, 0, True)]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                f(*values)

    def test_sd_conv_bias_and_length(self):
        dst = bytearray([255] * 30)
        src = bytearray(range(30))
        self.o["copy_span"](src, dst, 2*3*2, (5-2)*3*2)
        self.assertEqual(dst[:18], src[12:30])
        self.assertEqual(dst[18:], bytes([255] * 12))

    def test_ds_conv_rows_with_padding(self):
        src, dst = bytearray(range(42)), bytearray([255] * 42)
        for d in range(3):
            self.o["copy_span"](src, dst, d*14+4, 6, d*14)
        self.assertTrue(all(dst[d*14:d*14+6] == src[d*14+4:d*14+10]
                            for d in range(3)))

    def test_temporal_natural_bytes_not_page_stride(self):
        src, dst = bytearray(range(128)), bytearray([255] * 128)
        self.o["copy_span"](src, dst, 0, 34)
        self.assertEqual(dst[34:], bytes([255] * 94))

    def test_bounds_reject_overrun_and_negative(self):
        f = self.o["copy_span"]
        for off, length in [(-1, 1), (9, 2), (0, 11)]:
            with self.subTest(off=off, length=length), self.assertRaises(ValueError):
                f(bytearray(10), bytearray(10), off, length)

    def test_zero_length_copy_does_not_modify_destination(self):
        dst = bytearray([77] * 7)
        self.o["copy_span"](bytearray(7), dst, 3, 0)
        self.assertEqual(dst, bytes([77] * 7))

    def test_partial_tail_coverage(self):
        spans = [list(range(i, min(i+1024, 2051))) for i in range(0, 2051, 1024)]
        self.assertEqual([n for item in spans for n in item], list(range(2051)))
        self.assertEqual(len(spans), 3)



class Phase5MemcopyTiledPartitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = staticmethod(pure_oracles()["tiled_spans"])

    def test_g8_is_in_pinned_batch_gate(self):
        code = embedded_python()
        self.assertIsInstance(type(self).__dict__["f"], staticmethod)
        self.assertIn("G8 PASS:", code)
        self.assertIn('g8_cases == 13824', code)
        self.assertIn("((src_addr_i ^ dst_addr_i) & 7) == 0", code)

    def test_zero_length_all_tiles_empty(self):
        for tile in range(7):
            self.assertEqual(self.f(0x10003, 0x20003, 0, tile, 7, 8), [])

    def test_equal_modulo_alignment_takes_u64_body(self):
        chunks = self.f(0x10003, 0x20003, 37, 0, 1, 8)
        self.assertIn((5, 32, "u64_body"), chunks)
        self.assertIn((0, 5, "u8_head"), chunks)

    def test_different_alignment_uses_u8_fallback(self):
        chunks = self.f(0x10003, 0x20004, 37, 0, 1, 8)
        self.assertTrue(chunks)
        self.assertEqual({kind for _, _, kind in chunks}, {"u8_fallback"})

    def test_short_aligned_bytes_do_not_form_u64_body(self):
        chunks = self.f(0x10001, 0x20001, 5, 0, 1, 8)
        self.assertEqual(chunks, [(0, 5, "u8_head")])

    def test_tail_byte_range_owned_by_tile_zero(self):
        first = self.f(0x10000, 0x20000, 2051, 0, 3, 8)
        later = sum((self.f(0x10000, 0x20000, 2051, t, 3, 8)
                     for t in (1, 2)), [])
        self.assertIn((2048, 3, "u8_tail"), first)
        self.assertFalse(any(kind == "u8_tail" for _, _, kind in later))

    def test_late_tiles_can_be_empty(self):
        spans = [self.f(0x10000, 0x20000, 9, t, 7, 1024)
                 for t in range(7)]
        self.assertTrue(any(not s for s in spans[1:]))

    def test_fast_and_slow_partition_cover_exact_bytes(self):
        for sm, dm in ((0, 0), (7, 7), (0, 7), (7, 0)):
            for n in (0, 1, 7, 8, 9, 31, 32, 1025, 2051):
                for tiles in (1, 2, 3, 7):
                    coverage = [0] * n
                    for t in range(tiles):
                        for off, size, _ in self.f(
                                0x10000+sm, 0x20000+dm, n, t, tiles, 32):
                            self.assertGreater(size, 0)
                            for byte in range(off, off+size):
                                self.assertLess(byte, n)
                                coverage[byte] += 1
                    self.assertEqual(coverage, [1] * n)

    def test_u64_spans_have_aligned_both_addresses(self):
        for mod in range(8):
            for tile in range(3):
                for off, length, kind in self.f(
                        0x10000+mod, 0x20000+mod, 2051, tile, 3, 8):
                    if kind == "u64_body":
                        self.assertEqual((mod+off) % 8, 0)
                        self.assertEqual(length % 8, 0)

    def test_reject_invalid_tiling_inputs(self):
        samples = [
            (-1, 0, 8, 0, 1, 8),
            (0, 0, -1, 0, 1, 8),
            (0, 0, 8, -1, 1, 8),
            (0, 0, 8, 0, 0, 8),
            (0, 0, 8, 2, 2, 8),
            (0, 0, 8, 0, 1, 7),
            (True, 0, 8, 0, 1, 8),
        ]
        for values in samples:
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.f(*values)



if __name__ == "__main__":
    unittest.main()
