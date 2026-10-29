"""Exact Preview Mamba state-copy semantics: CPU negative/control cases."""
import unittest
from src import p1_prefix_copy_region_contract as contract


class Tests(unittest.TestCase):
    def test_sd_conv_shift_and_untouched_suffix(self):
        plan = contract.plan_mamba_copy(
            layout="SD_CONV", block_stride_bytes=24,
            source_column=0, destination_column=1,
            block_table_columns=8, token_bias=2,
            conv_width=5, inner_size=2, element_size=1)
        self.assertEqual(plan["segments"], ((4, 0, 6),))
        before = bytes(range(24))
        after = before[4:10] + b'\xff' * 18
        result = contract.compare_cpu_snapshots(plan, before, after)
        self.assertTrue(result["copied_region_matches"])
        self.assertFalse(result["live_state_content_reuse_verified"])

    def test_ds_conv_row_stride_shift_with_padding(self):
        plan = contract.plan_mamba_copy(
            layout="DS_CONV", block_stride_bytes=32,
            source_column=1, destination_column=2,
            block_table_columns=8, token_bias=2,
            conv_width=5, inner_size=1, element_size=2,
            dim_rows=2, row_stride_bytes=16)
        self.assertEqual(plan["segments"], ((4, 0, 6), (20, 16, 6)))
        old = bytes(range(32))
        new = bytearray([255] * 32)
        for src, dst, n in plan["segments"]:
            new[dst:dst+n] = old[src:src+n]
        self.assertTrue(contract.compare_cpu_snapshots(
            plan, old, bytes(new))["copied_region_matches"])

    def test_temporal_accepted_column_and_page_padding_excluded(self):
        plan = contract.plan_mamba_copy(
            layout="TEMPORAL", block_stride_bytes=64,
            source_column=1, destination_column=4,
            block_table_columns=8, token_bias=2,
            conv_width=0, inner_size=7, element_size=2)
        self.assertEqual(plan["source_block_table_column"], 3)
        self.assertEqual(plan["segments"], ((0, 0, 14),))
        old = bytes(range(64))
        new = old[:14] + b"\xcc" * 50
        self.assertTrue(contract.compare_cpu_snapshots(
            plan, old, new)["copied_region_matches"])

    def test_corrupted_copied_region_fails_even_if_padding_same(self):
        plan = contract.plan_mamba_copy(
            layout="TEMPORAL", block_stride_bytes=16,
            source_column=0, destination_column=1,
            block_table_columns=4, token_bias=0,
            conv_width=0, inner_size=8, element_size=1)
        old = b"\x01" * 16
        new = b"\x01" * 7 + b"\x02" + b"\x01" * 8
        result = contract.compare_cpu_snapshots(plan, old, new)
        self.assertFalse(result["copied_region_matches"])
        self.assertFalse(result["live_state_content_reuse_verified"])

    def test_alias_source_before_and_destination_after_must_be_separate(self):
        plan = contract.plan_mamba_copy(
            layout="SD_CONV", block_stride_bytes=10,
            source_column=1, destination_column=1,
            block_table_columns=4, token_bias=1,
            conv_width=4, inner_size=2, element_size=1)
        old = bytes(range(10))
        after = old[2:8] + old[6:]
        self.assertTrue(contract.compare_cpu_snapshots(
            plan, old, after)["copied_region_matches"])
        self.assertTrue(plan["in_place_copy_overlap_not_audited"])

    def test_invalid_conv_shift_is_rejected(self):
        with self.assertRaisesRegex(contract.CopyPlanBlocked, "CONV_TOKEN_BIAS"):
            contract.plan_mamba_copy(
                layout="SD_CONV", block_stride_bytes=16,
                source_column=0, destination_column=1,
                block_table_columns=4, token_bias=4,
                conv_width=4, inner_size=2, element_size=1)

    def test_temporal_source_column_overrun_rejected(self):
        with self.assertRaisesRegex(contract.CopyPlanBlocked, "TEMPORAL_SOURCE_COLUMN_OOB"):
            contract.plan_mamba_copy(
                layout="TEMPORAL", block_stride_bytes=32,
                source_column=3, destination_column=1,
                block_table_columns=4, token_bias=1,
                conv_width=0, inner_size=4, element_size=2)

    def test_row_stride_and_block_size_bounds_rejected(self):
        kwargs = dict(layout="DS_CONV", block_stride_bytes=22,
                      source_column=1, destination_column=2,
                      block_table_columns=4, token_bias=1,
                      conv_width=5, inner_size=1, element_size=2,
                      dim_rows=2, row_stride_bytes=14)
        with self.assertRaisesRegex(contract.CopyPlanBlocked, "COPY_REGION_EXCEEDS"):
            contract.plan_mamba_copy(**kwargs)
        kwargs["block_stride_bytes"] = 30
        kwargs["row_stride_bytes"] = 8
        with self.assertRaisesRegex(contract.CopyPlanBlocked, "DS_CONV_LAYOUT_METADATA_DRIFT"):
            contract.plan_mamba_copy(**kwargs)

    def test_unexpected_layout_never_accepted(self):
        with self.assertRaisesRegex(contract.CopyPlanBlocked, "UNKNOWN_STATE_LAYOUT"):
            contract.plan_mamba_copy(
                layout="GDN_UNKNOWN", block_stride_bytes=16,
                source_column=0, destination_column=0,
                block_table_columns=2, token_bias=0,
                conv_width=0, inner_size=8, element_size=2)

    def test_fake_partial_snapshots_are_rejected(self):
        plan = contract.plan_mamba_copy(
            layout="TEMPORAL", block_stride_bytes=8,
            source_column=0, destination_column=1,
            block_table_columns=2, token_bias=0,
            conv_width=0, inner_size=8, element_size=1)
        with self.assertRaisesRegex(contract.CopyPlanBlocked, "SNAPSHOT_SIZE_OR_SHAPE"):
            contract.compare_cpu_snapshots(plan, b"\x00" * 7, b"\x00" * 8)


if __name__ == "__main__":
    unittest.main()
