"""Phase 5 synthetic CPU-only PLE gather latency experiment, NOT TPS.

No model checkpoint, GPU, network or output files. Compares only fast-gather
OFF and ON with statistics OFF using identical deterministic row IDs and a
small synthetic 13x7 BF16 table. Values are context-specific wallclock timings.
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]
from phase2_ple_fixtures import make_bf16_fixture  # noqa: E402
import vllm_ple_mmap as ple  # noqa: E402


def run() -> None:
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "-1" or torch.cuda.is_available():
        raise RuntimeError("CPU-only benchmark requires CUDA_VISIBLE_DEVICES=-1")
    with tempfile.TemporaryDirectory(prefix="ple-phase5-bench-") as temp:
        fixture = make_bf16_fixture(Path(temp))
        shards, dtype, _ = ple._find_shards(str(fixture.root), 1)
        width = shards.pop("__cols__")
        shard_size = ple._validate_shard_layout(shards, fixture.parts, fixture.vocab)
        if (width, dtype) != (7, "BF16"):
            raise AssertionError("unexpected fixture dtype/width")
        rows = (16, 64, 256, 512, 513, 1024)
        # 75% duplicates versus broadly distributed over this tiny 13-row
        # fixture, so it can isolate dispatcher overhead but NOT NVMe behavior.
        dup_sizes = (1, fixture.vocab)
        for n in rows:
            for uniq in dup_sizes:
                rng = np.random.default_rng(20261027 + n + uniq)
                ids = rng.integers(0, uniq, size=n, dtype=np.int64)
                oracle = np.frombuffer(
                    b"".join(fixture.rows[int(i)] for i in ids),
                    dtype=np.uint8,
                ).reshape(n, fixture.row_bytes).copy()
                measurements: dict[str, list[float]] = {}
                for fast in (False, True):
                    with patch.dict(os.environ, {
                        "VLLM_PLE_FAST_GATHER": "1" if fast else "0",
                        "VLLM_PLE_FAST_GATHER_ROWS": "512",
                        "VLLM_PLE_PHASE_STATS": "0",
                    }):
                        table = ple._open_ple_table(
                            shards, shard_size, width, dtype,
                            workers=4, chunk=2,
                        )
                        try:
                            for _ in range(4):
                                if not np.array_equal(table.gather(ids), oracle):
                                    raise AssertionError("non-byte-exact warmup")
                            times = []
                            for _ in range(21):
                                start = time.perf_counter_ns()
                                got = table.gather(ids)
                                elapsed = time.perf_counter_ns() - start
                                if not np.array_equal(got, oracle):
                                    raise AssertionError("non-byte-exact timed gather")
                                times.append(elapsed / 1_000_000.0)
                            measurements["on" if fast else "off"] = times
                        finally:
                            table.pool.shutdown(wait=True)
                off = sorted(measurements["off"])
                on = sorted(measurements["on"])
                # Explicitly not making a "faster" decision from this output.
                print(json.dumps({
                    "test": "phase5_synthetic_cpu_gather",
                    "source_head": "see git rev-parse HEAD",
                    "rows": n, "effective_unique_limit": uniq,
                    "fixture": "13x7 BF16 file-backed, warm page cache",
                    "off_median_ms": round(statistics.median(off), 5),
                    "on_median_ms": round(statistics.median(on), 5),
                    "off_p95_ms": round(off[19], 5),
                    "on_p95_ms": round(on[19], 5),
                    "repeats": 21, "stats_enabled": False,
                    "byte_exact": True, "gpu": "NOT_RUN",
                }, sort_keys=True))
    print("PHASE5_SYNTHETIC_CPU_BENCH_ALL_OK")


if __name__ == "__main__":
    run()
