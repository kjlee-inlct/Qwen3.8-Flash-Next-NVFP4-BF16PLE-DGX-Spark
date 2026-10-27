"""Phase 2 stdlib-only tests of unmodified PLE parsing/layout functions.

Do not import vllm_ple_mmap as a module here: it eagerly imports torch/numpy.
Instead compile the four unchanged pure functions from its AST. This is a
source-contract test, NOT a full torch/vLLM/CUDA import or mmap gather test.
The separate src/test_ple_phase2_cpu.py exercises the full production module.
"""

from __future__ import annotations

import ast
import glob
import json
import math
import os
import re
import struct
import tempfile
import unittest
from pathlib import Path

from phase2_ple_fixtures import PREFIX, make_bf16_fixture

SOURCE = Path(__file__).resolve().parents[1] / "src" / "vllm_ple_mmap.py"
NAMES = {
    "parse_safetensors_header", "_itemsize",
    "_find_shards", "_validate_shard_layout",
}


def production_pure_functions() -> dict[str, object]:
    """Compile only real source functions, without depending on host torch."""
    source_text = SOURCE.read_text(encoding="utf-8")
    parsed = ast.parse(source_text, filename=str(SOURCE))
    selected = [
        item for item in parsed.body
        if isinstance(item, ast.FunctionDef) and item.name in NAMES
    ]
    if {node.name for node in selected} != NAMES:
        raise AssertionError("production PLE API changed; update Phase 2 tests")
    context: dict[str, object] = {
        "glob": glob, "json": json, "math": math, "os": os,
        "re": re, "struct": struct,
    }
    module = ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[]))
    exec(compile(module, str(SOURCE), "exec"), context)
    return context


class Phase2PleSourceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ple = production_pure_functions()

    def find(self, path: Path):
        found, dtype, scale = self.ple["_find_shards"](str(path), 1)
        width = found.pop("__cols__", None)
        return found, dtype, scale, width

    def test_bf16_shard_header_offsets_and_byte_exact_rows(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = make_bf16_fixture(Path(temporary))
            shards, dtype, scale, width = self.find(fixture.root)
            self.assertEqual((dtype, scale, width), ("BF16", None, 7))
            self.assertEqual(sorted(shards), [0, 1, 2, 3])
            shard_size = self.ple["_validate_shard_layout"](
                shards, fixture.parts, fixture.vocab
            )
            self.assertEqual(shard_size, 4)
            self.assertEqual([shards[i][2] for i in range(4)], [4, 4, 4, 1])
            # Validate real bytes at the absolute offsets returned by PLE,
            # not merely values reconstructed from our own header.
            for row_id in (0, 3, 4, 7, 8, 11, 12, 3, 0, 12):
                part, local = divmod(row_id, shard_size)
                path, offset, _rows = shards[part]
                with open(path, "rb") as stream:
                    stream.seek(offset + local * fixture.row_bytes)
                    actual = stream.read(fixture.row_bytes)
                self.assertEqual(actual, fixture.rows[row_id], row_id)
            header, start = self.ple["parse_safetensors_header"](
                str(fixture.root / "synthetic-ple-0.safetensors")
            )
            self.assertEqual(start, 8 + len(json.dumps(
                {"__metadata__": {"fixture": "blazux-phase2-synthetic"},
                 **{
                     k: v for k, v in header.items()
                 }},
                separators=(",", ":"),
            ).encode("utf-8")))
            self.assertNotIn("__metadata__", header)
            self.assertGreater(shards[0][1], start)

    def test_scan_without_safetensors_index(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = make_bf16_fixture(Path(temporary), with_index=False)
            shards, dtype, scale, width = self.find(fixture.root)
            self.assertEqual((len(shards), dtype, scale, width), (4, "BF16", None, 7))
            self.assertEqual(self.ple["_validate_shard_layout"](shards, 4, 13), 4)

    def test_missing_middle_or_last_shard_fails_closed_at_layout_gate(self):
        for missing in (1, 3):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as tmp:
                fixture = make_bf16_fixture(Path(tmp), omit=(missing,))
                shards, _dtype, _scale, _width = self.find(fixture.root)
                with self.assertRaisesRegex(RuntimeError, "PLE shard indices"):
                    self.ple["_validate_shard_layout"](shards, 4, 13)

    def test_mixed_shard_width_is_rejected_before_mmap(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = make_bf16_fixture(Path(tmp), width_override={2: 8})
            with self.assertRaisesRegex(ValueError, "mixed widths"):
                self.find(fixture.root)

    def test_mixed_dtype_is_rejected_before_mmap(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = make_bf16_fixture(
                Path(tmp), dtype_override={2: "F8_E4M3"}
            )
            with self.assertRaisesRegex(ValueError, "mixed dtypes"):
                self.find(fixture.root)

    def test_payload_size_must_match_header_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = make_bf16_fixture(Path(tmp), corrupt_payload_length=(2,))
            with self.assertRaisesRegex(ValueError, "size/shape mismatch"):
                self.find(fixture.root)

    def test_short_final_shard_wrong_row_count_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = make_bf16_fixture(Path(tmp), rows_override={3: 2})
            shards, dtype, _, width = self.find(fixture.root)
            self.assertEqual((dtype, width), ("BF16", 7))
            with self.assertRaisesRegex(RuntimeError, "PLE shard 3 has 2 rows, expected 1"):
                self.ple["_validate_shard_layout"](shards, 4, 13)

    def test_only_correct_layer_is_selected(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = make_bf16_fixture(Path(tmp))
            found, dtype, scale = self.ple["_find_shards"](str(fixture.root), 0)
            self.assertEqual((found, dtype, scale), ({}, None, None))

    def test_valid_bf16_needs_no_fp8_weight_scale(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = make_bf16_fixture(Path(tmp))
            _, dtype, scale, _ = self.find(fixture.root)
            self.assertEqual(dtype, "BF16")
            self.assertIsNone(scale)

    @unittest.expectedFailure
    def test_known_gap_duplicate_shard_names_across_two_headers(self):
        """Known gap: _find_shards silently overwrites a duplicate index.

        This is intentionally XFAIL: accept no false claim of fail-closed
        protection. If the core is fixed in a later Phase, remove decorator.
        """
        with tempfile.TemporaryDirectory() as tmp:
            fixture = make_bf16_fixture(Path(tmp))
            path = fixture.root / "duplicate.safetensors"
            # An extra file may be scanned in no-index mode; duplicate shard 0.
            import phase2_ple_fixtures as helper
            helper._write_safetensors(
                path, [(f"{PREFIX}.shard_0.weight", "BF16", (4, 7),
                        b"".join(fixture.rows[:4]))]
            )
            (fixture.root / "model.safetensors.index.json").unlink()
            with self.assertRaisesRegex(ValueError, "duplicate"):
                self.find(fixture.root)


if __name__ == "__main__":
    unittest.main()
