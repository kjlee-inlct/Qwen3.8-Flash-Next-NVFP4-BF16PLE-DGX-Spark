"""Phase 4 bundled PLE OFF/ON matrix (NumPy + PyTorch, CPU-only).

Uses tiny synthetic BF16 safetensors. Never imports vLLM, uses checkpoint
snapshots, starts a GPU process, or modifies the serving container.
Run only in an isolated environment with CUDA_VISIBLE_DEVICES=-1.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "src"))

from phase2_ple_fixtures import make_bf16_fixture  # noqa: E402
import vllm_ple_mmap as ple  # noqa: E402


def oracle_rows(ids: np.ndarray, fixture) -> np.ndarray:
    data = b"".join(fixture.rows[int(row)] for row in ids)
    return np.frombuffer(data, dtype=np.uint8).reshape(-1, fixture.row_bytes).copy()


def exercise() -> None:
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "-1" or torch.cuda.is_available():
        raise RuntimeError("CPU-only Phase 4 test requires CUDA_VISIBLE_DEVICES=-1")

    cases = (
        np.array([], dtype=np.int64),
        np.array([12], dtype=np.int64),
        np.array([12, 0, 3, 4, 7, 8, 11, 12, 4, 0, 1, 6, 2, 10], dtype=np.int64),
        *((np.arange(n, dtype=np.int64) * 7 + 12) % 13
          for n in (16, 64, 512, 513, 1024)),
    )

    with tempfile.TemporaryDirectory(prefix="ple-phase4-") as tmp:
        fixture = make_bf16_fixture(Path(tmp))
        shards, dtype_str, scale = ple._find_shards(str(fixture.root), 1)
        cols = shards.pop("__cols__")
        assert (dtype_str, scale, cols) == ("BF16", None, 7)
        shard_size = ple._validate_shard_layout(shards, fixture.parts, fixture.vocab)

        # Independent feature flags. OFF/OFF must return exactly the old rows.
        for fast, stats in ((False, False), (True, False), (False, True), (True, True)):
            with patch.dict(os.environ, {
                "VLLM_PLE_FAST_GATHER": "1" if fast else "0",
                "VLLM_PLE_FAST_GATHER_ROWS": "512",
                "VLLM_PLE_PHASE_STATS": "1" if stats else "0",
            }):
                table = ple._open_ple_table(
                    shards, shard_size, cols, dtype_str, workers=4, chunk=2
                )
                try:
                    assert table.fast_gather_rows == (512 if fast else 0)
                    for ids in cases:
                        got = table.gather(ids)
                        expected = oracle_rows(ids, fixture)
                        assert got.dtype == np.uint8
                        assert got.shape == expected.shape
                        assert np.array_equal(got, expected), (fast, stats, ids.size)

                    # Full torch forward is checked in every flag combination.
                    ids = np.array([12, 0, 12, 7, 4, 8, 3, 12], dtype=np.int64)
                    model = ple._MmapNgramEmbedding(fixture.vocab, cols)
                    model.table = table
                    observed = model(torch.from_numpy(ids).reshape(2, 4))
                    expected_bytes = oracle_rows(ids, fixture)
                    expected = torch.from_numpy(expected_bytes.copy())
                    expected = expected.view(torch.bfloat16).reshape(2, 4, cols)
                    assert observed.shape == expected.shape
                    assert observed.dtype == torch.bfloat16
                    assert torch.equal(observed, expected)
                    assert (
                        observed.contiguous().view(torch.uint8).numpy().tobytes()
                        == expected_bytes.tobytes()
                    )

                    for bad in (-1, fixture.vocab):
                        try:
                            table.gather(np.array([bad], dtype=np.int64))
                        except IndexError:
                            pass
                        else:
                            raise AssertionError("out-of-range accepted: " + str(bad))

                    snapshot = table.stats_snapshot()
                    if stats:
                        assert snapshot is not None
                        assert snapshot["calls"] == len(cases) + 3
                        assert snapshot["errors"] == 2
                        valid_rows = sum(ids.size for ids in cases) + 8
                        assert snapshot["rows"] == valid_rows
                        assert snapshot["logical_bytes"] == valid_rows * fixture.row_bytes
                        assert snapshot["gather_s"] >= 0.0
                        fast_calls = sum(
                            0 < ids.size <= 512 for ids in cases
                        ) + 1 if fast else 0
                        assert snapshot["fast_calls"] == fast_calls
                        # The snapshot must be a copy, not mutable table state.
                        snapshot["calls"] = -1
                        assert table.stats_snapshot()["calls"] == len(cases) + 3
                    else:
                        assert snapshot is None
                    print(
                        f"PASS: PHASE4_FLAG_MATRIX fast={int(fast)} "
                        f"stats={int(stats)} byte_exact=1"
                    )
                finally:
                    table.pool.shutdown(wait=True)

    # OFF is also guaranteed when the flags are completely absent.
    with patch.dict(os.environ, {}, clear=True):
        assert not ple._env_flag("VLLM_PLE_FAST_GATHER")
        assert not ple._env_flag("VLLM_PLE_PHASE_STATS")
    print("PHASE4_CPU_MATRIX_ALL_OK")


if __name__ == "__main__":
    exercise()
