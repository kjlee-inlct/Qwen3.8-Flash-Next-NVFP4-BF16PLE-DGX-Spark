"""Phase 2 GPU-free, byte-exact BF16 PLE mmap production-module regression.

Needs NumPy + PyTorch from an existing compatible image. Does not import or
instantiate vLLM, open any real model, or modify checkpoint/cache files.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "src"))

from phase2_ple_fixtures import make_bf16_fixture  # noqa: E402
import vllm_ple_mmap as ple  # noqa: E402


def exercise() -> None:
    """Exercise actual production NumPy mmap gather and torch BF16 forward."""
    if torch.cuda.is_available():
        raise RuntimeError("Phase 2 PLE CPU test requires CUDA_VISIBLE_DEVICES=-1")

    with tempfile.TemporaryDirectory(prefix="ple-phase2-") as temporary:
        fixture = make_bf16_fixture(Path(temporary))
        shards, dtype_str, scale = ple._find_shards(str(fixture.root), 1)
        cols = shards.pop("__cols__")
        assert dtype_str == "BF16" and scale is None and cols == 7
        shard_size = ple._validate_shard_layout(shards, fixture.parts, fixture.vocab)
        assert shard_size == 4
        assert sum(value[2] for value in shards.values()) == fixture.vocab

        # Unsorted cross-shard IDs, duplicate-heavy ordering, boundaries,
        # short final shard, and empty input are tested independently for
        # serial and worker-pool gathering.
        ids = np.array(
            [12, 0, 3, 4, 7, 8, 11, 12, 4, 0, 12, 1, 6, 2, 2, 10],
            dtype=np.int64,
        )
        oracle = np.frombuffer(
            b"".join(fixture.rows[int(i)] for i in ids),
            dtype=np.uint8,
        ).reshape(len(ids), fixture.row_bytes).copy()
        for workers, chunk in ((1, 1024), (4, 2)):
            table = ple._open_ple_table(
                shards, shard_size, cols, dtype_str, workers=workers, chunk=chunk
            )
            try:
                got = table.gather(ids)
                assert got.dtype == np.uint8 and got.shape == oracle.shape
                assert np.array_equal(got, oracle), (workers, chunk)
                assert np.array_equal(
                    table.gather(np.empty(0, dtype=np.int64)),
                    np.empty((0, fixture.row_bytes), dtype=np.uint8),
                )
                for bad_id in (-1, fixture.vocab):
                    try:
                        table.gather(np.array([bad_id], dtype=np.int64))
                    except IndexError:
                        pass
                    else:
                        raise AssertionError(f"out-of-range accepted: {bad_id}")

                embedding = ple._MmapNgramEmbedding(fixture.vocab, cols)
                embedding.table = table
                input_ids = torch.from_numpy(ids.copy()).reshape(2, 8)
                actual = embedding(input_ids)
                assert actual.dtype == torch.bfloat16
                assert actual.shape == (2, 8, cols)

                expected = torch.from_numpy(oracle.copy()).view(torch.bfloat16)
                expected = expected.reshape(2, 8, cols)
                assert torch.equal(actual, expected)
                assert (
                    actual.contiguous().view(torch.uint8).cpu().numpy().tobytes()
                    == oracle.tobytes()
                )
                print(
                    f"PASS: BF16 mmap gather/torch forward byte-exact "
                    f"workers={workers} chunk={chunk}"
                )
            finally:
                table.pool.shutdown(wait=True)

    # Phase 3: exercise duplicate detection in the real imported module,
    # not only the stdlib-only AST extraction used by unit tests.
    with tempfile.TemporaryDirectory(prefix="ple-phase3-duplicate-") as duplicate_tmp:
        fixture = make_bf16_fixture(
            Path(duplicate_tmp), duplicate_shard_zero_in_second_file=True
        )
        try:
            ple._find_shards(str(fixture.root), 1)
        except ValueError as exc:
            if "duplicate shard index 0" not in str(exc):
                raise
        else:
            raise AssertionError("PLE duplicate shard index was accepted")
    print("PHASE3_PLE_DUPLICATE_GUARD_ALL_OK")
    print("PHASE2_PLE_CPU_ALL_OK")


if __name__ == "__main__":
    exercise()
