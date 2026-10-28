"""P6-B0 synthetic CPU-only physical block-copy bounds rehearsal.

No vLLM, torch, CUDA, Docker, sockets, subprocesses, or file reads.
This is NOT a test of installed Triton kernels or active GPU memory.
"""
from __future__ import annotations

import argparse
import json
import re

MAX_GROUPS = 8
MAX_STATES = 64
MAX_OPS = 128
MAX_STORAGE_BYTES = 65536
MAX_BLOCKS = 1024
KINDS = frozenset(("conv_sd", "conv_ds", "temporal"))


class Blocked(ValueError):
    """Invalid or untrusted synthetic metadata; no result can be certified."""


def _fields(value, expected, label):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise Blocked(f"{label}: invalid field inventory")


def _number(value, label, low=0, high=1 << 30):
    if type(value) is not int or not low <= value <= high:
        raise Blocked(f"{label}: invalid integer")
    return value


def _list(value, label, low=1, high=128):
    if not isinstance(value, list) or not low <= len(value) <= high:
        raise Blocked(f"{label}: invalid array length")
    return value


def evaluate(case):
    """Validate the *entire* synthetic transaction before copying any bytes.

    Each operation explicitly supplies byte offsets; it does not purport to
    derive Conv SD/DS or temporal token bias from a real kernel invocation.
    Returns final synthetic byte arrays only to its caller, not a GPU PASS.
    """
    _fields(case, ("tables", "states", "operations"), "case")
    tables = []
    for gi, table in enumerate(_list(case["tables"], "tables", high=MAX_GROUPS)):
        _fields(table, ("dtype", "columns", "row_stride_elements", "physical_ids"), "table")
        if table["dtype"] != "int32":
            raise Blocked("block table dtype must be int32")
        cols = _number(table["columns"], "columns", 1, 64)
        stride = _number(table["row_stride_elements"], "row stride", cols, 256)
        rows = _list(table["physical_ids"], "table rows", high=64)
        for row in rows:
            if not isinstance(row, list) or len(row) != cols:
                raise Blocked("table row width differs from column count")
            for item in row:
                _number(item, "table physical id", -1, MAX_BLOCKS - 1)
        tables.append((cols, stride, rows))
    states = []
    for state in _list(case["states"], "states", high=MAX_STATES):
        _fields(state, ("group_index", "kind", "block_stride_bytes",
                        "payload_bytes", "physical_blocks", "storage_hex"), "state")
        group = _number(state["group_index"], "group index", 0, len(tables) - 1)
        if not isinstance(state["kind"], str) or state["kind"] not in KINDS:
            raise Blocked("unsupported state kind")
        step = _number(state["block_stride_bytes"], "state byte stride", 1, MAX_STORAGE_BYTES)
        payload = _number(state["payload_bytes"], "payload", 1, step)
        count = _number(state["physical_blocks"], "physical count", 1, MAX_BLOCKS)
        hextext = state["storage_hex"]
        if not isinstance(hextext, str) or len(hextext) > MAX_STORAGE_BYTES * 2 \
                or len(hextext) % 2 or re.fullmatch(r"[0-9a-f]*", hextext) is None:
            raise Blocked("storage must be bounded lower-case hex bytes")
        storage = bytes.fromhex(hextext)
        if len(storage) < count * step:
            raise Blocked("state physical allocation underflow")
        states.append((group, step, payload, count, storage))

    operations = _list(case["operations"], "operations", high=MAX_OPS)
    prepared = []
    for op in operations:
        _fields(op, ("state_index", "row_index", "src_column", "dst_column",
                     "src_offset_bytes", "dst_offset_bytes", "length_bytes"), "operation")
        si = _number(op["state_index"], "state index", 0, len(states) - 1)
        group, step, payload, count, storage = states[si]
        cols, row_stride, rows = tables[group]
        ri = _number(op["row_index"], "table row", 0, len(rows) - 1)
        src_col = _number(op["src_column"], "src column", 0, cols - 1)
        dst_col = _number(op["dst_column"], "dst column", 0, cols - 1)
        src = rows[ri][src_col]
        dst = rows[ri][dst_col]
        if src == -1 or dst == -1:
            raise Blocked("selected sentinel or unallocated physical ID")
        if src >= count or dst >= count:
            raise Blocked("physical ID exceeds state allocation")
        src_offset = _number(op["src_offset_bytes"], "source offset", 0, payload)
        dst_offset = _number(op["dst_offset_bytes"], "destination offset", 0, payload)
        length = _number(op["length_bytes"], "copy length", 0, payload)
        if src_offset + length > payload or dst_offset + length > payload:
            raise Blocked("copy exceeds natural payload")
        source_start = src * step + src_offset
        dest_start = dst * step + dst_offset
        if source_start + length > len(storage) or dest_start + length > len(storage):
            raise Blocked("copy exceeds allocated backing bytes")
        if length and max(source_start, dest_start) < min(
                source_start + length, dest_start + length
        ) and source_start != dest_start:
            raise Blocked("ambiguous overlapping alias copy")
        prepared.append((si, source_start, dest_start, length))

    # Copy-on-write: caller's input and states are never mutated. All
    # malformed operations above fail before any copy is performed.
    after = [bytearray(state[4]) for state in states]
    for si, source_start, dest_start, length in prepared:
        source = bytes(after[si][source_start:source_start + length])
        after[si][dest_start:dest_start + length] = source
    return {
        "status": "CPU_SYNTHETIC_ONLY_NOT_GPU",
        "p6_a_active_abi": "BLOCKED",
        "p6_b_gpu_status": "NOT_RUN",
        "tables": len(tables),
        "states": len(states),
        "operations_checked": len(prepared),
        "buffers": tuple(bytes(item) for item in after),
    }


def demo():
    left = bytes(range(48))
    right = bytes(range(32))
    case = {
        "tables": [
            {"dtype": "int32", "columns": 3, "row_stride_elements": 4,
             "physical_ids": [[0, 1, -1]]},
            {"dtype": "int32", "columns": 2, "row_stride_elements": 4,
             "physical_ids": [[1, 0]]},
        ],
        "states": [
            {"group_index": 0, "kind": "conv_ds", "block_stride_bytes": 16,
             "payload_bytes": 12, "physical_blocks": 2, "storage_hex": left.hex()},
            {"group_index": 1, "kind": "temporal", "block_stride_bytes": 16,
             "payload_bytes": 16, "physical_blocks": 2, "storage_hex": right.hex()},
        ],
        "operations": [
            {"state_index": 0, "row_index": 0, "src_column": 0, "dst_column": 1,
             "src_offset_bytes": 3, "dst_offset_bytes": 1, "length_bytes": 8},
            {"state_index": 1, "row_index": 0, "src_column": 0, "dst_column": 1,
             "src_offset_bytes": 0, "dst_offset_bytes": 0, "length_bytes": 16},
        ],
    }
    result = evaluate(case)
    if result["buffers"][0][17:25] != left[3:11]:
        raise Blocked("demo conv copy mismatch")
    if result["buffers"][0][28:32] != left[28:32]:
        raise Blocked("demo stride padding modified")
    if result["buffers"][1][:16] != right[16:32]:
        raise Blocked("demo temporal copy mismatch")
    return {k: value for k, value in result.items() if k != "buffers"}


def main(argv=None):
    parser = argparse.ArgumentParser(description="P6-B0 synthetic CPU-only rehearsal")
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args(argv)
    if not args.demo:
        parser.error("--demo is required; no runtime options exist")
    print(json.dumps(demo(), sort_keys=True))
    print("PHASE6_B0_CPU_SYNTHETIC_REHEARSAL_NOT_GPU_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
