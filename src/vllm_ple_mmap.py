"""vllm_ple_mmap — serve the Qwen3.8-Flash-Next N-gram (PLE) table from NVMe via mmap.

Why: the 51B-parameter n-gram table is about 44 GiB in FP8 or 95.37 GiB in BF16,
and vLLM normally keeps it resident (GPU, or pinned host RAM with
VLLM_PLE_CPU_OFFLOAD). On a DGX Spark / GX10 the host and GPU share one 121 GiB
pool, so a full BF16 table cannot fit beside the compute trunk and a useful KV
cache. A token only touches 16 rows of that table, however, so the table can
remain file-backed on NVMe and be served through the page cache — exactly what
llama.cpp does with GGUF mmap.

How: with VLLM_PLE_MMAP=1 this module patches ``Qwen3_8FlashNextNGramEmbedding``:
  * ``__init__`` swaps the 44/95 GiB ``VocabParallelEmbedding`` for a tiny
    placeholder whose ``forward(ids)`` gathers rows from ``np.memmap`` views of the
    checkpoint's PLE safetensors shards (zero-copy, page-cache backed);
  * ``load_weights`` drops the 128 shard tensors on the floor and opens the
    memmaps. FP8 retains the global ``weight_scale`` as
    ``_offload_weight_scale``; BF16 needs no scale and stock vLLM passes those
    embeddings through without dequantization.
  * ``forward_impl`` (hashing + lookup) is wrapped in a custom op
    ``vllm::ple_mmap_lookup`` so that (a) torch.compile treats it as opaque — the
    stock version trips an Inductor int64 indexing assert on sm_121 — and (b) it can
    be listed in ``-cc.splitting_ops`` and run OUTSIDE piecewise CUDA graphs: the
    gather is CPU work + a pageable H2D copy, which cannot live inside a capture.
    Use ``-cc.cudagraph_mode=PIECEWISE`` (not FULL*) with the splitting op list in
    serve-flashnext-vllm.sh, or ``--enforce-eager``.
Nothing else in vLLM changes: the n-gram hashing, the short-conv, the dequant path
are the stock ones.

Knobs (env):
  VLLM_PLE_MMAP=1            enable
  VLLM_PLE_MMAP_WORKERS=32   gather threads (page faults overlap across threads)
  VLLM_PLE_MMAP_CHUNK=2048   rows per gather task
  VLLM_PLE_FAST_GATHER=0    1 = opt in to decode-sized inline CPU gather (default OFF)
  VLLM_PLE_FAST_GATHER_ROWS=512  max rows in opt-in inline path (not applied when OFF)
  VLLM_PLE_PHASE_STATS=0    opt-in CPU phases + legacy gather counters (no GPU/I-O stats)
  VLLM_PLE_MMAP_PREWARM=0    1 = stream the whole table once at load to fill the
                             page cache with whatever memory is free. Keep this
                             at 0 for a 95.37 GiB BF16 table on a 128 GB system.

Install: the Dockerfile copies this file next to vllm and appends
``_ple_mmap_apply(Qwen3_8FlashNextNGramEmbedding)`` to the end of
``vllm/models/qwen3_8_flash_next/nvidia/ple_layer.py``. See the repo README.
"""

from __future__ import annotations

import glob
import json
import logging
import math
import os
import re
import struct
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import torch
import torch.nn as nn

logger = logging.getLogger("vllm.ple_mmap")

ENV_ENABLE = "VLLM_PLE_MMAP"


@dataclass(frozen=True)
class PleStorageDType:
    torch_dtype: torch.dtype
    itemsize: int
    needs_scale: bool


_PLE_DTYPES = {
    "F8_E4M3": PleStorageDType(torch.float8_e4m3fn, 1, True),
    "F8_E5M2": PleStorageDType(torch.float8_e5m2, 1, True),
    "BF16": PleStorageDType(torch.bfloat16, 2, False),
}


def _resolve_ple_dtype(dtype_str: str) -> PleStorageDType:
    try:
        return _PLE_DTYPES[dtype_str]
    except KeyError as exc:
        raise ValueError(f"unsupported PLE shard dtype {dtype_str}") from exc


def _row_bytes(cols: int, storage_dtype: PleStorageDType) -> int:
    return int(cols) * storage_dtype.itemsize


def enabled() -> bool:
    return os.environ.get(ENV_ENABLE, "0").lower() in ("1", "true", "yes")


def _env_flag(name: str) -> bool:
    """Explicit opt-in only; no effect when unset or invalid."""
    return os.environ.get(name, "0").strip().lower() in ("1", "true", "yes")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


# --------------------------------------------------------------------------- #
# safetensors header parsing (no dependency on the safetensors package: we need
# raw file offsets, which its Python API does not expose)
# --------------------------------------------------------------------------- #
def parse_safetensors_header(path: str) -> tuple[dict, int]:
    """Return (header_dict, data_start_offset) of a safetensors file."""
    with open(path, "rb") as f:
        (header_len,) = struct.unpack("<Q", f.read(8))
        header = json.loads(f.read(header_len))
    header.pop("__metadata__", None)
    return header, 8 + header_len


class MmapPleTable:
    """Row gather over a table split into ``split_ngram_parts`` shard files.

    ``shards``: {shard_index: (path, absolute_byte_offset, rows)}. Shard ``i``
    holds global rows ``[i*shard_size, i*shard_size + rows)`` (vLLM's
    ``copy_ple_embedding_shard_`` layout).
    """

    def __init__(
        self,
        shards: dict[int, tuple[str, int, int]],
        shard_size: int,
        row_bytes: int,
        torch_dtype: torch.dtype,
        workers: int = 32,
        chunk: int = 2048,
    ) -> None:
        if not shards:
            raise ValueError("no PLE shards")
        self.shard_size = int(shard_size)
        self.row_bytes = int(row_bytes)
        self.torch_dtype = torch_dtype
        self.chunk = max(1, int(chunk))
        self.paths: list[str | None] = [None] * (max(shards) + 1)
        self.mm: list[np.memmap | None] = [None] * (max(shards) + 1)
        self.rows_total = 0
        for idx, (path, offset, rows) in shards.items():
            self.paths[idx] = path
            self.mm[idx] = np.memmap(
                path, dtype=np.uint8, mode="r", offset=offset, shape=(rows, row_bytes)
            )
            self.rows_total += rows
        self.pool = ThreadPoolExecutor(max_workers=max(1, int(workers)))
        # Independent, default-OFF switch: preserve the original dedup+pool
        # gather contract unless the caller explicitly opts into fast gather.
        self.fast_gather_rows = (
            max(0, _env_int("VLLM_PLE_FAST_GATHER_ROWS", 512))
            if _env_flag("VLLM_PLE_FAST_GATHER") else 0
        )
        # Off by default. Scoped per-table, never global Prometheus counters.
        self.phase_stats_enabled = _env_flag("VLLM_PLE_PHASE_STATS")
        self._stats_lock = threading.Lock() if self.phase_stats_enabled else None
        self._stats = (
            {
                "calls": 0, "errors": 0, "rows": 0, "logical_bytes": 0,
                "gather_s": 0.0, "fast_calls": 0,
                "normalize_s": 0.0, "dedup_s": 0.0,
                "gather_work_s": 0.0, "wait_s": 0.0, "stage_s": 0.0,
                # Scope markers prevent reporting asynchronous H2D completion,
                # kernel duration or physical NVMe I/O as if observed.
                "h2d_transfer_s": "NOT_INSTRUMENTED",
                "nvme_read_bytes": "NOT_INSTRUMENTED",
            }
            if self.phase_stats_enabled else None
        )

    def stats_snapshot(self) -> dict[str, int | float | str] | None:
        """Thread-safe copy of CPU gather observations, or None when disabled.

        gather_s: inclusive gather() wall time (legacy meaning).
        normalize_s: input conversion to contiguous int64.
        dedup_s: np.unique(ids, return_inverse=True) on the default path.
        gather_work_s: SUM of completed per-task memmap indexing wall times;
            concurrent tasks overlap, so this may exceed gather_s.
        wait_s: main-thread wall time consuming executor results; includes
            worker execution and scheduling, NOT exclusive idle time.
        stage_s: CPU output allocation and inverse-order restoration only.
            NOT a measurement of H2D upload, CUDA sync, or GPU staging.
        nvme_read_bytes: NOT_INSTRUMENTED; logical_bytes counts returned bytes.
        Phase totals are non-additive, especially with concurrent workers.
        """
        if not self.phase_stats_enabled:
            return None
        assert self._stats_lock is not None and self._stats is not None
        with self._stats_lock:
            return dict(self._stats)

    def _record_gather_stats(
        self, count: int, elapsed_s: float, failed: bool, fast: bool,
        phases: dict[str, float],
    ) -> None:
        assert self._stats_lock is not None and self._stats is not None
        with self._stats_lock:
            self._stats["calls"] += 1
            self._stats["errors"] += int(failed)
            self._stats["gather_s"] += elapsed_s
            for key, duration in phases.items():
                self._stats[key] += duration
            # Failed calls can have partial phase durations, but never
            # contribute successful rows, bytes, or fast-call counters.
            if not failed:
                self._stats["rows"] += count
                self._stats["logical_bytes"] += count * self.row_bytes
                self._stats["fast_calls"] += int(fast)

    def gather(self, ids: np.ndarray) -> np.ndarray:
        """CPU row gather; stats OFF keeps the original dispatch path."""
        if not self.phase_stats_enabled:
            return self._gather_rows(ids)
        phases = {
            "normalize_s": 0.0, "dedup_s": 0.0,
            "gather_work_s": 0.0, "wait_s": 0.0, "stage_s": 0.0,
        }
        started = time.perf_counter()
        n = 0
        fast = False
        try:
            n = int(np.asarray(ids).size)
            fast = bool(n > 0 and n <= self.fast_gather_rows)
            result = self._gather_rows(ids, phases)
        except Exception:
            self._record_gather_stats(
                n, time.perf_counter() - started, True, fast, phases
            )
            raise
        self._record_gather_stats(
            n, time.perf_counter() - started, False, fast, phases
        )
        return result

    def _gather_rows(
        self, ids: np.ndarray, phases: dict[str, float] | None = None
    ) -> np.ndarray:
        """int64 row IDs -> uint8 [N,row_bytes]; optional CPU-only phases."""
        if phases is None:
            # Preserve the original OFF path without clock sampling.
            ids = np.ascontiguousarray(ids, dtype=np.int64).reshape(-1)
        else:
            t = time.perf_counter()
            try:
                ids = np.ascontiguousarray(ids, dtype=np.int64).reshape(-1)
            finally:
                phases["normalize_s"] += time.perf_counter() - t
        if ids.size == 0:
            if phases is None:
                return np.empty((0, self.row_bytes), dtype=np.uint8)
            t = time.perf_counter()
            try:
                return np.empty((0, self.row_bytes), dtype=np.uint8)
            finally:
                phases["stage_s"] += time.perf_counter() - t
        if ids.size <= self.fast_gather_rows:
            # Fast path deliberately skips row dedup and executor wait.
            lo, hi = int(ids.min()), int(ids.max())
            if lo < 0 or hi >= self.shard_size * len(self.mm):
                raise IndexError(
                    f"PLE row id out of range: [{lo}, {hi}] for {self.rows_total} rows"
                )
            shard = ids // self.shard_size
            if phases is None:
                out = np.empty((ids.size, self.row_bytes), dtype=np.uint8)
            else:
                t = time.perf_counter()
                out = np.empty((ids.size, self.row_bytes), dtype=np.uint8)
                phases["stage_s"] += time.perf_counter() - t
            for si in np.unique(shard):
                mm = self.mm[int(si)]
                if mm is None:
                    raise IndexError(f"PLE shard {int(si)} missing")
                mask = shard == si
                if phases is None:
                    out[mask] = mm[ids[mask] - int(si) * self.shard_size]
                else:
                    t = time.perf_counter()
                    try:
                        out[mask] = mm[ids[mask] - int(si) * self.shard_size]
                    finally:
                        phases["gather_work_s"] += time.perf_counter() - t
            return out

        # Default dedup + sorted shard tasks, unchanged with stats OFF.
        if phases is None:
            uniq, inverse = np.unique(ids, return_inverse=True)
        else:
            t = time.perf_counter()
            try:
                uniq, inverse = np.unique(ids, return_inverse=True)
            finally:
                phases["dedup_s"] += time.perf_counter() - t
        if uniq[0] < 0 or uniq[-1] >= self.shard_size * len(self.mm):
            raise IndexError(
                f"PLE row id out of range: [{uniq[0]}, {uniq[-1]}] "
                f"for {self.rows_total} rows"
            )
        shard = uniq // self.shard_size
        local = uniq - shard * self.shard_size
        if phases is None:
            out = np.empty((uniq.size, self.row_bytes), dtype=np.uint8)
        else:
            t = time.perf_counter()
            out = np.empty((uniq.size, self.row_bytes), dtype=np.uint8)
            phases["stage_s"] += time.perf_counter() - t

        bounds = np.flatnonzero(np.diff(shard)) + 1
        starts = np.concatenate(([0], bounds))
        ends = np.concatenate((bounds, [uniq.size]))
        tasks: list[tuple[int, int, int]] = []
        for s, e in zip(starts.tolist(), ends.tolist()):
            si = int(shard[s])
            for c in range(s, e, self.chunk):
                tasks.append((si, c, min(c + self.chunk, e)))

        def run(task: tuple[int, int, int]) -> float | None:
            si, a, b = task
            mm = self.mm[si]
            if mm is None:
                raise IndexError(f"PLE shard {si} missing")
            # Includes memmap indexing and any page-fault stalls. This is
            # worker elapsed time, NOT NVMe read bandwidth or pure CPU time.
            if phases is None:
                out[a:b] = mm[local[a:b]]
                return None
            t = time.perf_counter()
            out[a:b] = mm[local[a:b]]
            return time.perf_counter() - t

        if len(tasks) == 1:
            duration = run(tasks[0])
            if phases is not None:
                assert duration is not None
                phases["gather_work_s"] += duration
        elif phases is None:
            for _ in self.pool.map(run, tasks):
                pass
        else:
            # Each next() measures the caller's wait/result-consumption
            # interval. Do not subtract overlapping worker task durations.
            results = iter(self.pool.map(run, tasks))
            for _ in tasks:
                t = time.perf_counter()
                try:
                    duration = next(results)
                finally:
                    phases["wait_s"] += time.perf_counter() - t
                assert duration is not None
                phases["gather_work_s"] += duration
        if phases is None:
            return out[inverse]
        t = time.perf_counter()
        try:
            return out[inverse]
        finally:
            phases["stage_s"] += time.perf_counter() - t

    def prewarm(self) -> None:
        """Stream every shard once so the page cache holds as much as it can."""
        block = 64 << 20
        for path, mm in zip(self.paths, self.mm):
            if path is None or mm is None:
                continue
            start = mm.offset
            end = start + mm.shape[0] * mm.shape[1]
            with open(path, "rb", buffering=0) as f:
                pos = start
                while pos < end:
                    n = f.readinto(bytearray(min(block, end - pos)))  # noqa: F841
                    if not n:
                        break
                    pos += n


def _open_ple_table(
    shards: dict[int, tuple[str, int, int]],
    shard_size: int,
    cols: int,
    dtype_str: str,
    workers: int = 32,
    chunk: int = 2048,
) -> MmapPleTable:
    storage = _resolve_ple_dtype(dtype_str)
    return MmapPleTable(
        shards,
        shard_size,
        _row_bytes(cols, storage),
        storage.torch_dtype,
        workers=workers,
        chunk=chunk,
    )


# --------------------------------------------------------------------------- #
# Placeholder that stands in for VocabParallelEmbedding
# --------------------------------------------------------------------------- #
class _MmapNgramEmbedding(nn.Module):
    """Duck-types the bits of VocabParallelEmbedding the PLE code reads.

    No ``weight`` attribute on purpose: ``Qwen3_8FlashNextPLELayer`` then falls
    back to ``ple_embedding._offload_weight_scale`` for the FP8 scale.
    """

    def __init__(self, num_embeddings: int, embedding_dim: int) -> None:
        super().__init__()
        self.num_embeddings = int(num_embeddings)
        self.org_vocab_size = int(num_embeddings)
        self.embedding_dim = int(embedding_dim)
        self.table: MmapPleTable | None = None
        self._zeros_dtype = torch.bfloat16

    def forward(self, ids: torch.Tensor) -> torch.Tensor:
        table = self.table
        if table is None:
            # Weights never loaded (e.g. --load-format dummy): keep the plumbing
            # alive with zeros so kernel tests can run without the 44 GiB table.
            return torch.zeros(
                (*ids.shape, self.embedding_dim),
                dtype=self._zeros_dtype,
                device=ids.device,
            )
        ids_np = ids.detach().to("cpu", non_blocking=False).numpy().reshape(-1)
        rows = table.gather(ids_np)  # uint8 [N, row_bytes], fresh & writable
        out = torch.from_numpy(rows).view(table.torch_dtype)
        out = out.to(ids.device, non_blocking=True)
        return out.reshape(*ids.shape, self.embedding_dim)


# --------------------------------------------------------------------------- #
# Patch
# --------------------------------------------------------------------------- #
def _find_shards(
    model_path: str, layer_idx: int
) -> tuple[
    dict[int, tuple[str, int, int]],
    str | None,
    tuple[str, int, int, str] | None,
]:
    """Locate ``layers.<idx>.ple.ple_embedding.ngram_embedding.shard_N.weight``.

    Returns (shards, dtype_str, scale_entry) where scale_entry is
    (path, abs_offset, nbytes) of ``ngram_embedding.weight_scale`` or None.
    """
    shard_re = re.compile(
        rf"layers\.{layer_idx}\.ple\.ple_embedding\.ngram_embedding\.shard_(\d+)\.weight$"
    )
    scale_re = re.compile(
        rf"layers\.{layer_idx}\.ple\.ple_embedding\.ngram_embedding\.weight_scale$"
    )
    index_path = os.path.join(model_path, "model.safetensors.index.json")
    if os.path.exists(index_path):
        with open(index_path) as f:
            weight_map = json.load(f)["weight_map"]
        files = sorted(
            {
                os.path.join(model_path, fn)
                for name, fn in weight_map.items()
                if shard_re.search(name) or scale_re.search(name)
            }
        )
    else:
        files = sorted(glob.glob(os.path.join(model_path, "*.safetensors")))

    shards: dict[int, tuple[str, int, int]] = {}
    dtype_str: str | None = None
    scale_entry: tuple[str, int, int, str] | None = None
    shard_cols: int | None = None
    for path in files:
        header, data_start = parse_safetensors_header(path)
        for name, meta in header.items():
            m = shard_re.search(name)
            if m:
                shard_index = int(m.group(1))
                if shard_index in shards:
                    raise ValueError(
                        f"PLE duplicate shard index {shard_index} for layer {layer_idx}"
                    )
                start, end = meta["data_offsets"]
                rows, cols = meta["shape"]
                if dtype_str is None:
                    dtype_str = meta["dtype"]
                elif meta["dtype"] != dtype_str:
                    raise ValueError("PLE shards have mixed dtypes")
                if end - start != rows * cols * _itemsize(dtype_str):
                    raise ValueError(f"PLE shard {name}: size/shape mismatch")
                if shard_cols is None:
                    shard_cols = cols
                elif cols != shard_cols:
                    raise ValueError(
                        "PLE shards have mixed widths: "
                        f"expected {shard_cols}, got {cols} for {name}"
                    )
                shards[shard_index] = (path, data_start + start, rows)
            elif scale_re.search(name):
                start, end = meta["data_offsets"]
                scale_entry = (path, data_start + start, end - start, meta["dtype"])
    if shards:
        # Return cols through dtype_str consumer; keep it simple: stash on dict.
        assert shard_cols is not None
        shards["__cols__"] = shard_cols  # type: ignore[index]
    return shards, dtype_str, scale_entry


def _itemsize(dtype_str: str) -> int:
    return {
        "F8_E4M3": 1,
        "F8_E5M2": 1,
        "U8": 1,
        "I8": 1,
        "BF16": 2,
        "F16": 2,
        "F32": 4,
    }[dtype_str]


def _read_scale(entry: tuple) -> torch.Tensor:
    path, offset, nbytes, dtype_str = entry
    with open(path, "rb") as f:
        f.seek(offset)
        raw = f.read(nbytes)
    if dtype_str == "F32":
        return torch.tensor(struct.unpack("<f", raw[:4])[0], dtype=torch.float32)
    if dtype_str == "BF16":
        u16 = struct.unpack("<H", raw[:2])[0]
        return torch.tensor(u16 << 16, dtype=torch.int32).view(torch.float32).squeeze()
    if dtype_str == "F16":
        return torch.frombuffer(bytearray(raw[:2]), dtype=torch.float16).clone().squeeze()
    raise ValueError(f"unsupported weight_scale dtype {dtype_str}")


def _read_required_scale(dtype_str: str, scale_entry: tuple | None) -> torch.Tensor | None:
    storage = _resolve_ple_dtype(dtype_str)
    if not storage.needs_scale:
        return None
    if scale_entry is None:
        raise RuntimeError("PLE mmap: FP8 shards without ngram_embedding.weight_scale")
    return _read_scale(scale_entry)


def _validate_shard_layout(
    shards: dict[int, tuple[str, int, int]],
    parts: int,
    vocab: int,
) -> int:
    expected_indices = list(range(parts))
    actual_indices = sorted(shards)
    if actual_indices != expected_indices:
        raise RuntimeError(
            f"PLE shard indices {actual_indices}, expected {expected_indices}"
        )
    shard_size = math.ceil(vocab / parts)
    for idx, (_path, _offset, rows) in shards.items():
        expected_rows = max(0, min(shard_size, vocab - idx * shard_size))
        if rows != expected_rows:
            raise RuntimeError(
                f"PLE shard {idx} has {rows} rows, expected {expected_rows}"
            )
    return shard_size


_REGISTRY: dict[str, nn.Module] = {}
_OP_NAME = "ple_mmap_lookup"


def _lookup_impl(
    input_ids: torch.Tensor,
    query_start_loc: torch.Tensor,
    ngram_context: torch.Tensor,
    output: torch.Tensor,
    layer_name: str,
) -> None:
    layer = _REGISTRY[layer_name]
    result = layer._ple_mmap_orig_forward_impl(
        None, input_ids, query_start_loc, ngram_context
    )
    output[: result.shape[0]].copy_(result.to(output.dtype))


def _lookup_fake(
    input_ids: torch.Tensor,
    query_start_loc: torch.Tensor,
    ngram_context: torch.Tensor,
    output: torch.Tensor,
    layer_name: str,
) -> None:
    return


def _register_op() -> None:
    if hasattr(torch.ops.vllm, _OP_NAME):
        return
    from vllm.utils.torch_utils import direct_register_custom_op

    direct_register_custom_op(
        op_name=_OP_NAME,
        op_func=_lookup_impl,
        mutates_args=["output"],
        fake_impl=_lookup_fake,
    )


def apply(cls: type) -> None:
    """Patch ``Qwen3_8FlashNextNGramEmbedding`` (pass the class) when enabled."""
    if not enabled():
        return
    if getattr(cls, "_ple_mmap_patched", False):
        return
    mod = sys.modules[cls.__module__]
    orig_init = cls.__init__
    orig_load_weights = cls.load_weights

    def __init__(self, config, embedding_dim, ple_dense_layer_id, max_total_tokens,
                 max_num_reqs, prefix, quant_config=None, params_dtype=None):
        # Run the stock constructor (hash buffers, workspaces, ...) with the
        # embedding class swapped for our placeholder so nothing large is
        # allocated. quant_config=None keeps the stock code from selecting an
        # FP8 quant method that would create an FP8 weight parameter.
        real_embedding_cls = mod.VocabParallelEmbedding
        mod.VocabParallelEmbedding = lambda n, d, **_kw: _MmapNgramEmbedding(n, d)
        try:
            orig_init(self, config, embedding_dim, ple_dense_layer_id,
                      max_total_tokens, max_num_reqs, prefix,
                      quant_config=None, params_dtype=params_dtype)
        finally:
            mod.VocabParallelEmbedding = real_embedding_cls
        self._ple_mmap_prefix = prefix
        _REGISTRY[prefix] = self
        self._ple_mmap_model_path = None
        try:
            from vllm.config import get_current_vllm_config
            self._ple_mmap_model_path = get_current_vllm_config().model_config.model
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("PLE mmap: cannot read model path from vllm config: %s", exc)
        if params_dtype is not None:
            self.ngram_embedding._zeros_dtype = params_dtype
        logger.info(
            "PLE mmap: %s -> placeholder embedding (%d rows x %d), table will be mmapped",
            prefix, self.ngram_embedding.org_vocab_size, self.head_dim,
        )

    def load_weights(self, weights: Iterable[tuple[str, torch.Tensor]]) -> set[str]:
        loaded: set[str] = set()
        rest: list[tuple[str, torch.Tensor]] = []
        for name, w in weights:
            if name.startswith("ngram_embedding.shard_") and name.endswith(".weight"):
                loaded.add(name)  # served from disk, never materialised
                continue
            if name == "ngram_embedding.weight_scale":
                self.register_buffer(
                    "_offload_weight_scale",
                    w.detach().to(device=torch.accelerator.current_accelerator()),
                    persistent=False,
                )
                loaded.add(name)
                continue
            rest.append((name, w))
        loaded.update(orig_load_weights(self, rest))
        _setup_table(self)
        return loaded

    def _setup_table(self) -> None:
        if self.ngram_embedding.table is not None:
            return
        model_path = self._ple_mmap_model_path
        if not model_path or not os.path.isdir(model_path):
            raise RuntimeError(
                f"PLE mmap: model path {model_path!r} is not a local directory; "
                "point --model at the downloaded snapshot"
            )
        m = re.search(r"layers\.(\d+)\.", self._ple_mmap_prefix)
        if not m:
            raise RuntimeError(f"PLE mmap: cannot find layer index in {self._ple_mmap_prefix!r}")
        layer_idx = int(m.group(1))
        shards, dtype_str, scale_entry = _find_shards(model_path, layer_idx)
        if not shards:
            raise RuntimeError(f"PLE mmap: no shard tensors for layer {layer_idx} under {model_path}")
        cols = shards.pop("__cols__")  # type: ignore[arg-type]
        if cols != self.head_dim:
            raise RuntimeError(f"PLE mmap: shard width {cols} != head_dim {self.head_dim}")
        storage = _resolve_ple_dtype(dtype_str)
        if storage.needs_scale and not hasattr(self, "_offload_weight_scale"):
            scale = _read_required_scale(dtype_str, scale_entry)
            assert scale is not None
            self.register_buffer(
                "_offload_weight_scale",
                scale.to(torch.accelerator.current_accelerator()),
                persistent=False,
            )
        parts = int(self.split_ngram_parts)
        vocab = int(self.ngram_embedding.org_vocab_size)
        shard_size = _validate_shard_layout(shards, parts, vocab)
        table = _open_ple_table(
            shards, shard_size, cols, dtype_str,
            workers=_env_int("VLLM_PLE_MMAP_WORKERS", 32),
            chunk=_env_int("VLLM_PLE_MMAP_CHUNK", 2048),
        )
        if _env_int("VLLM_PLE_MMAP_PREWARM", 0):
            logger.info(
                "PLE mmap: prewarming page cache (%.1f GiB)...",
                table.rows_total * table.row_bytes / 2**30,
            )
            table.prewarm()
        self.ngram_embedding.table = table
        logger.info(
            "PLE mmap: layer %d, %d shards, %d rows x %d B (%.1f GiB on disk), dtype %s, %d workers",
            layer_idx, len(shards), table.rows_total, table.row_bytes,
            table.rows_total * table.row_bytes / 2**30,
            dtype_str, table.pool._max_workers,
        )

    def forward_impl(self, hidden_states, input_ids, query_start_loc, ngram_context,
                     output_buffer=None):
        del hidden_states, output_buffer
        num_tokens = input_ids.reshape(-1).shape[0]
        table = self.ngram_embedding.table
        dtype = table.torch_dtype if table is not None else self.ngram_embedding._zeros_dtype
        output = torch.empty(
            (num_tokens, self.embedding_dim), dtype=dtype, device=input_ids.device
        )
        getattr(torch.ops.vllm, _OP_NAME)(
            input_ids, query_start_loc, ngram_context, output, self._ple_mmap_prefix
        )
        return output

    _register_op()
    cls._ple_mmap_orig_forward_impl = cls.forward_impl
    cls.forward_impl = forward_impl
    cls.__init__ = __init__
    cls.load_weights = load_weights
    cls._setup_table = _setup_table
    cls._ple_mmap_patched = True
    logger.info("PLE mmap patch applied to %s.%s", cls.__module__, cls.__name__)
