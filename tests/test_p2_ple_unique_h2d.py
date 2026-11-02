"""P2 BF16 unique-only H2D CPU exactness (torch/numpy optional on host).

These tests never run CUDA, model, Docker, or inference. Production timing and
CUDA index-select correctness remain unverified.
"""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    import numpy as np
    import torch
    from src.vllm_ple_mmap import MmapPleTable, _ple_unique_h2d_lookup
except ImportError:
    np = None
    torch = None


@unittest.skipIf(np is None or torch is None, "requires preinstalled CPU torch+numpy")
class PleUniqueH2DTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = Path(self.tmp.name) / "rows.bin"
        # Four BF16 columns per row. Each row must survive reorder and duplicates.
        arr = torch.arange(64, dtype=torch.float32).reshape(16, 4).to(torch.bfloat16)
        self.data.write_bytes(arr.view(torch.uint8).numpy().tobytes())
        self.rowbytes = 8

    def build(self, enabled="1"):
        with patch.dict(os.environ, {"VLLM_PLE_UNIQUE_H2D": enabled}, clear=False):
            table = MmapPleTable(
                {0: (str(self.data), 0, 16)}, shard_size=16,
                row_bytes=self.rowbytes, torch_dtype=torch.bfloat16,
                workers=1,
            )
        self.addCleanup(table.pool.shutdown)
        return table

    def test_cpu_byte_exact_random_and_duplicates(self):
        table = self.build()
        patterns = ([1, 1, 1, 5, 3, 5, 0], [15, 0, 15, 2],
                    [], [0], list(range(16)), [3] * 32)
        for p in patterns:
            with self.subTest(p=p):
                ids_np = np.asarray(p, dtype=np.int64)
                ids = torch.tensor(p, dtype=torch.int64)
                result = _ple_unique_h2d_lookup(table, ids_np, ids, 4)
                oracle = (torch.from_numpy(table.gather(ids_np)).view(torch.bfloat16)
                          if p else torch.empty((0, 4), dtype=torch.bfloat16))
                self.assertTrue(torch.equal(result, oracle))
                self.assertEqual(tuple(result.shape), (len(p), 4))

    def test_optin_default_off_and_fp8_unchanged(self):
        t = self.build(enabled="0")
        self.assertFalse(t.unique_h2d_enabled)
        u = self.build(enabled="1")
        self.assertTrue(u.unique_h2d_enabled)

    def test_unique_transfer_n_less_than_output_rows(self):
        t = self.build()
        ids = torch.tensor([2, 2, 3, 2, 3, 2, 3, 2], dtype=torch.long)
        seen = []
        old = t.gather
        def capture(rows):
            seen.append(np.asarray(rows).copy())
            return old(rows)
        t.gather = capture
        result = _ple_unique_h2d_lookup(t, ids.numpy(), ids, 4)
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0].tolist(), [2, 3])
        self.assertEqual(tuple(result.shape), (8, 4))

    def test_wrong_ids_fail_in_existing_gather(self):
        t = self.build()
        ids = torch.tensor([17], dtype=torch.int64)
        with self.assertRaises(IndexError):
            _ple_unique_h2d_lookup(t, ids.numpy(), ids, 4)


if __name__ == "__main__":
    unittest.main()
