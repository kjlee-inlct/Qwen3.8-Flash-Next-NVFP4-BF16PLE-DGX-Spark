"""P1 PLE per-phase CPU instrumentation regression (no GPU/model/network).

Run: CUDA_VISIBLE_DEVICES=-1 python3 src/test_ple_phase_stats_cpu.py
This script intentionally measures only small synthetic file-backed CPU rows.
"""
from __future__ import annotations

import os
import statistics
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]
from phase2_ple_fixtures import make_bf16_fixture  # noqa: E402
import vllm_ple_mmap as ple  # noqa: E402

OLD_KEYS = {"calls", "errors", "rows", "logical_bytes", "gather_s", "fast_calls"}
PHASE_KEYS = ("normalize_s", "dedup_s", "gather_work_s", "wait_s", "stage_s")
FORWARD_PHASES = ("ids_to_host_s", "tensor_view_s", "device_copy_call_s")


def run() -> None:
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "-1" or torch.cuda.is_available():
        raise RuntimeError("CPU-only test requires CUDA_VISIBLE_DEVICES=-1")
    with tempfile.TemporaryDirectory(prefix="ple-phases-") as root:
        fixture = make_bf16_fixture(Path(root))
        shards, dtype, scale = ple._find_shards(str(fixture.root), 1)
        width = shards.pop("__cols__")
        size = ple._validate_shard_layout(shards, fixture.parts, fixture.vocab)
        assert (dtype, scale, width) == ("BF16", None, 7)
        oracle = lambda ids: np.frombuffer(
            b"".join(fixture.rows[int(i)] for i in ids), dtype=np.uint8
        ).reshape(-1, fixture.row_bytes).copy()
        cases = (
            np.array([], dtype=np.int64),
            np.array([12, 0, 12, 4, 8, 3, 7, 0], dtype=np.int64),
            np.tile(np.arange(13, dtype=np.int64)[::-1], 45),
        )
        for fast in (False, True):
            for stats in (False, True):
                with patch.dict(os.environ, {
                    "VLLM_PLE_FAST_GATHER": str(int(fast)),
                    "VLLM_PLE_FAST_GATHER_ROWS": "512",
                    "VLLM_PLE_PHASE_STATS": str(int(stats)),
                }):
                    table = ple._open_ple_table(shards, size, width, dtype,
                                                workers=4, chunk=1)
                    try:
                        for ids in cases:
                            result = table.gather(ids)
                            assert result.tobytes() == oracle(ids).tobytes()
                            assert result.flags.writeable
                        snap = table.stats_snapshot()
                        if not stats:
                            assert snap is None
                            continue
                        assert snap is not None
                        assert OLD_KEYS <= snap.keys()
                        assert snap["calls"] == len(cases)
                        assert snap["errors"] == 0
                        assert snap["rows"] == sum(len(x) for x in cases)
                        assert snap["logical_bytes"] == snap["rows"] * fixture.row_bytes
                        assert snap["fast_calls"] == (1 if fast else 0)
                        assert snap["h2d_transfer_s"] == "NOT_INSTRUMENTED"
                        assert snap["nvme_read_bytes"] == "NOT_INSTRUMENTED"
                        assert snap["gather_s"] >= 0.0
                        assert all(0 <= snap[k] <= snap["gather_s"] * 4 + 1
                                   for k in PHASE_KEYS)
                        assert snap["dedup_s"] > 0  # 585 IDs always use default
                        assert snap["gather_work_s"] > 0
                        assert snap["stage_s"] > 0
                        snap["calls"] = -123
                        assert table.stats_snapshot()["calls"] == len(cases)
                        # Errors increment calls/errors, never completed rows/bytes.
                        old = table.stats_snapshot()
                        for bad in (-1, fixture.vocab):
                            try:
                                table.gather(np.array([bad], dtype=np.int64))
                            except IndexError:
                                pass
                            else:
                                raise AssertionError("out-of-bounds accepted")
                        try:
                            table.gather(np.array(["bad"], dtype=object))
                        except (TypeError, ValueError):
                            pass
                        else:
                            raise AssertionError("malformed ID accepted")
                        newer = table.stats_snapshot()
                        assert newer["calls"] == old["calls"] + 3
                        assert newer["errors"] == old["errors"] + 3
                        assert newer["rows"] == old["rows"]
                        assert newer["logical_bytes"] == old["logical_bytes"]
                        assert newer["fast_calls"] == old["fast_calls"]

                        # Real existing embedding.forward() CPU path, not just
                        # a gather-only synthetic oracle. Verify byte identity
                        # and count a rejected forward without crediting rows.
                        model = ple._MmapNgramEmbedding(fixture.vocab, width)
                        model.table = table
                        input_ids = torch.tensor([[12, 4, 12], [0, 7, 8]],
                                                 dtype=torch.int64)
                        observed = model(input_ids)
                        expected = oracle(input_ids.numpy().reshape(-1))
                        assert observed.shape == (2, 3, width)
                        assert observed.dtype == torch.bfloat16
                        assert observed.contiguous().view(torch.uint8).numpy().tobytes() == expected.tobytes()
                        recorded = table.stats_snapshot()
                        assert recorded["forward_calls"] == 1
                        assert recorded["forward_errors"] == 0
                        assert recorded["forward_s"] >= 0.0
                        assert all(0 <= recorded[k] <= recorded["forward_s"] + 1
                                   for k in FORWARD_PHASES)
                        assert recorded["h2d_transfer_s"] == "NOT_INSTRUMENTED"
                        assert recorded["nvme_read_bytes"] == "NOT_INSTRUMENTED"
                        try:
                            model(torch.tensor([fixture.vocab], dtype=torch.int64))
                        except IndexError:
                            pass
                        else:
                            raise AssertionError("invalid forward input accepted")
                        rejected = table.stats_snapshot()
                        assert (rejected["forward_calls"], rejected["forward_errors"]) == (2, 1)
                        assert rejected["rows"] == recorded["rows"]
                        assert rejected["logical_bytes"] == recorded["logical_bytes"]
                        assert rejected["errors"] == recorded["errors"] + 1
                    finally:
                        table.pool.shutdown(wait=True)

        # Missing shard reports error for both paths, and no rows are credited.
        sparse = dict(shards)
        del sparse[1]
        for fast in (False, True):
            with patch.dict(os.environ, {
                "VLLM_PLE_FAST_GATHER": str(int(fast)),
                "VLLM_PLE_PHASE_STATS": "1",
            }):
                table = ple._open_ple_table(sparse, size, width, dtype,
                                            workers=4, chunk=1)
                try:
                    try:
                        table.gather(np.array([size, size + 1], dtype=np.int64))
                    except IndexError as exc:
                        assert "missing" in str(exc)
                    else:
                        raise AssertionError("missing shard accepted")
                    s = table.stats_snapshot()
                    assert (s["calls"], s["errors"], s["rows"]) == (1, 1, 0)
                finally:
                    table.pool.shutdown(wait=True)

        # Concurrent callers must produce exactly one atomic counter update
        # per gather, with private per-call phase accumulators.
        ids = np.array([12, 0, 4, 12, 8, 9, 1, 3, 7], dtype=np.int64)
        with patch.dict(os.environ, {
            "VLLM_PLE_FAST_GATHER": "0", "VLLM_PLE_PHASE_STATS": "1",
        }):
            table = ple._open_ple_table(shards, size, width, dtype,
                                        workers=4, chunk=2)
            try:
                with ThreadPoolExecutor(max_workers=6) as clients:
                    results = list(clients.map(table.gather, [ids] * 24))
                assert all(x.tobytes() == oracle(ids).tobytes() for x in results)
                s = table.stats_snapshot()
                assert (s["calls"], s["errors"], s["rows"]) == (24, 0, 24 * len(ids))
                assert s["logical_bytes"] == s["rows"] * fixture.row_bytes
                assert all(s[k] >= 0 for k in PHASE_KEYS)
                assert (s["forward_calls"], s["forward_errors"]) == (0, 0)
                assert all(s[k] == 0 for k in FORWARD_PHASES)
            finally:
                table.pool.shutdown(wait=True)

        # Non-gating small-fixture overhead sample: this is not model TPS,
        # NVMe throughput, or an assertion that instrumentation is faster.
        timings = {}
        ids = np.tile(np.arange(13, dtype=np.int64), 2)
        for flag in (0, 1):
            with patch.dict(os.environ, {
                "VLLM_PLE_FAST_GATHER": "0",
                "VLLM_PLE_PHASE_STATS": str(flag),
            }):
                table = ple._open_ple_table(shards, size, width, dtype,
                                            workers=4, chunk=4)
                try:
                    for _ in range(4):
                        assert table.gather(ids).tobytes() == oracle(ids).tobytes()
                    samples = []
                    for _ in range(31):
                        t = time.perf_counter_ns()
                        b = table.gather(ids).tobytes()
                        samples.append((time.perf_counter_ns() - t) / 1000)
                        assert b == oracle(ids).tobytes()
                    timings[flag] = statistics.median(samples)
                finally:
                    table.pool.shutdown(wait=True)
        print("PLE_PHASE_STATS_CPU_PASS byte_exact=1 concurrency=24 "
              "off_median_us={:.3f} on_median_us={:.3f} "
              "sample=synthetic_warm_cpu_only".format(timings[0], timings[1]))


if __name__ == "__main__":
    run()
