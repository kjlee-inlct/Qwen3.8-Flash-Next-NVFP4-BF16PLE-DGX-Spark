"""P1 exact-Preview byte-copy semantics: CPU-only, fail-closed planning.

Grounded in installed vllm/v1/worker/mamba_utils.py SHA256:
25254d005f42b64dd55d15a5c646018f5599d971c23e7ca395eb5acaf4f41ed3

The kernel chooses a group-specific physical block via a batch-order table
and uses *natural state bytes* rather than page stride for temporal copy.
This module does not access GPU memory, install hooks, or declare live reuse
verified. A future worker hook must audit the source/destination physical
block IDs, stream completion, copy decisions and state tensor provenance.
"""
from __future__ import annotations

import hmac
from hashlib import sha256

PINNED_MAMBA_UTILS_SHA256 = (
    "25254d005f42b64dd55d15a5c646018f5599d971c23e7ca395eb5acaf4f41ed3"
)
MAX_CAPTURE_BYTES = 64 * 1024 * 1024
MAX_DIM_ROWS = 4096
LAYOUTS = frozenset(("SD_CONV", "DS_CONV", "TEMPORAL"))


class CopyPlanBlocked(ValueError):
    pass


def _bounded_int(value: object, minimum: int, maximum: int, name: str) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise CopyPlanBlocked("INVALID_" + name)
    return value


def plan_mamba_copy(
    *, layout: str, block_stride_bytes: int, source_column: int,
    destination_column: int, block_table_columns: int, token_bias: int,
    conv_width: int, inner_size: int, element_size: int,
    dim_rows: int = 0, row_stride_bytes: int = 0,
) -> dict:
    """Construct a CPU region model of _copy_mamba_state_block.

    Offsets are WITHIN an already-resolved physical cache block, not
    GPU addresses. Resolving group, batch-row, state type and physical
    IDs is required separately before any runtime evidence is admissible.

    SD conv: src[bias * inner_size * element_size:] -> dst[:len]
    DS conv: for each dim row, src[row + bias*element_size:] -> dst[row:]
    temporal: src physical ID from block_table[source_col + bias],
              copy inner_size*element_size (NOT padded block stride)
    """
    if layout not in LAYOUTS:
        raise CopyPlanBlocked("UNKNOWN_STATE_LAYOUT")
    stride = _bounded_int(block_stride_bytes, 1, MAX_CAPTURE_BYTES,
                          "BLOCK_STRIDE_BYTES")
    cols = _bounded_int(block_table_columns, 1, 1_000_000,
                        "BLOCK_TABLE_COLUMNS")
    src_col = _bounded_int(source_column, 0, cols - 1, "SOURCE_COLUMN")
    dst_col = _bounded_int(destination_column, 0, cols - 1,
                           "DESTINATION_COLUMN")
    bias = _bounded_int(token_bias, 0, cols, "TOKEN_BIAS")
    width = _bounded_int(conv_width, 0, 1_000_000, "CONV_WIDTH")
    inner = _bounded_int(inner_size, 1, MAX_CAPTURE_BYTES, "INNER_SIZE")
    elem = _bounded_int(element_size, 1, 16, "ELEMENT_SIZE")
    row_count = _bounded_int(dim_rows, 0, MAX_DIM_ROWS, "DIM_ROWS")
    row_stride = _bounded_int(row_stride_bytes, 0, MAX_CAPTURE_BYTES,
                              "ROW_STRIDE_BYTES")

    segments = []
    source_block_table_column = src_col
    if layout == "TEMPORAL":
        if width != 0 or row_count or row_stride:
            raise CopyPlanBlocked("TEMPORAL_LAYOUT_METADATA_DRIFT")
        source_block_table_column = src_col + bias
        if source_block_table_column >= cols:
            raise CopyPlanBlocked("TEMPORAL_SOURCE_COLUMN_OOB")
        copy_size = inner * elem
        segments.append((0, 0, copy_size))
    else:
        if not 0 < width or bias >= width:
            raise CopyPlanBlocked("CONV_TOKEN_BIAS_OR_WIDTH_INVALID")
        if layout == "SD_CONV":
            if row_count or row_stride:
                raise CopyPlanBlocked("SD_CONV_LAYOUT_METADATA_DRIFT")
            segments.append((bias * inner * elem, 0,
                             (width - bias) * inner * elem))
        else:
            if row_count < 1 or row_stride < width * elem or inner != 1:
                raise CopyPlanBlocked("DS_CONV_LAYOUT_METADATA_DRIFT")
            for row in range(row_count):
                segments.append((row * row_stride + bias * elem,
                                 row * row_stride, (width - bias) * elem))

    total = 0
    for src_offset, dst_offset, length in segments:
        if (length <= 0 or src_offset + length > stride or
                dst_offset + length > stride):
            raise CopyPlanBlocked("COPY_REGION_EXCEEDS_BLOCK_STRIDE")
        total += length
    if total > MAX_CAPTURE_BYTES:
        raise CopyPlanBlocked("COPY_REGION_TOO_LARGE")
    return {
        "status": "CPU_SOURCE_GROUNDED_COPY_PLAN_NOT_GPU_PROOF",
        "layout": layout,
        "source_block_table_column": source_block_table_column,
        "destination_block_table_column": dst_col,
        "token_bias": bias,
        "block_stride_bytes": stride,
        "natural_copy_bytes": total,
        "segment_count": len(segments),
        "segments": tuple(segments),
        "in_place_copy_overlap_not_audited": True,
        "live_state_content_reuse_verified": False,
        "p1_strict_gate_changed": False,
    }


def compare_cpu_snapshots(plan: dict, source_before: bytes,
                          destination_after: bytes) -> dict:
    """Compare copied regions from two synthetic CPU byte snapshots.

    Source MUST come from before the copy, destination from after it; the
    caller must establish those facts independently. This cannot validate
    real GPU transfer or cold-prefix reuse by itself.
    """
    stride = plan.get("block_stride_bytes")
    segments = plan.get("segments")
    if (type(stride) is not int or stride <= 0 or
            not isinstance(segments, tuple) or not segments or
            not isinstance(source_before, bytes) or
            not isinstance(destination_after, bytes) or
            len(source_before) != stride or len(destination_after) != stride):
        raise CopyPlanBlocked("SNAPSHOT_SIZE_OR_SHAPE_INVALID")
    src = sha256()
    dst = sha256()
    for segment in segments:
        if (not isinstance(segment, tuple) or len(segment) != 3 or
                any(type(n) is not int for n in segment)):
            raise CopyPlanBlocked("SNAPSHOT_SEGMENT_INVALID")
        s, d, n = segment
        if n < 1 or min(s, d) < 0 or max(s+n, d+n) > stride:
            raise CopyPlanBlocked("SNAPSHOT_SEGMENT_OOB")
        src.update(source_before[s:s+n])
        dst.update(destination_after[d:d+n])
    same = hmac.compare_digest(src.digest(), dst.digest())
    return {
        "status": ("CPU_COPY_REGION_MATCH_NOT_GPU_PROOF" if same
                   else "CPU_COPY_REGION_MISMATCH_NOT_GPU_PROOF"),
        "copied_region_matches": same,
        "live_state_content_reuse_verified": False,
        "real_gpu_copy_execution_observed": False,
    }
