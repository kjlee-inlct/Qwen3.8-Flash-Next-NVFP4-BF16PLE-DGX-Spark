"""P1 candidate-only *CPU contract* for verifying cached Mamba state contents.

No CUDA, Docker, tensor imports, runtime patching or state bytes are handled.
A matching fake event can prove only this validator's rules. Live proof requires
a separately reviewed GPU-worker hook at actual post-write/post-copy sites.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import stat
from pathlib import Path

STAGE = Path("/tmp/p1-prefix-stage.2dSPVPR6/mamba_hybrid.py")
STAGE_SHA256 = "1dfb7b5566c8e683afff6640b1764c774c27daaa817437862fd465e63da9f381"
REQUIRED = frozenset(("gdn", "ple_conv"))
PHASES = frozenset(("cold_capture", "hit_restore"))
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def _result(status: str, **fields: object) -> dict:
    return {"status": status, "verified": False, **fields}


def validate_state_reuse(events: object, *, prefix_hit_tokens: int) -> dict:
    """Fail-closed content-level parity contract for *actual* GPU evidence.

    Requires both GDN and PLE conv, same synthetic probe/boundary/group/block,
    full-byte digests of captured cache blocks vs restored running state, and
    positive cache hits. Never trust physical-ID parity or output ID equality
    as a substitute for real state bytes.
    """
    if type(prefix_hit_tokens) is not int or prefix_hit_tokens <= 0:
        return _result("INCONCLUSIVE_NO_PREFIX_HIT")
    if not isinstance(events, (list, tuple)) or len(events) != 4:
        return _result("INCONCLUSIVE_REQUIRED_STATE_EVENTS_MISSING")
    keyed = {}
    for item in events:
        if not isinstance(item, dict):
            return _result("INCONCLUSIVE_EVENT_SHAPE")
        phase, layer = item.get("phase"), item.get("layer_kind")
        if phase not in PHASES or layer not in REQUIRED:
            return _result("INCONCLUSIVE_UNAPPROVED_STATE_EVENT")
        key = (phase, layer)
        if key in keyed:
            return _result("INCONCLUSIVE_DUPLICATE_STATE_EVENT")
        if (item.get("provenance") != "LIVE_CANDIDATE_WORKER" or
                item.get("scope") != "FULL_STATE_BYTES" or
                item.get("timing_verified") is not True):
            return _result("INCONCLUSIVE_STATE_SNAPSHOT_PROVENANCE")
        if (phase == "cold_capture" and
                (item.get("state_location") != "PERSISTENT_CACHE_BLOCK" or
                 item.get("cache_write_completed") is not True)):
            return _result("INCONCLUSIVE_COLD_CAPTURE_POINT")
        if (phase == "hit_restore" and
                (item.get("state_location") != "RESTORED_RUNNING_STATE" or
                 item.get("cache_copy_completed") is not True or
                 item.get("has_initial_state") is not True)):
            return _result("INCONCLUSIVE_HIT_RESTORE_POINT")
        if (not isinstance(item.get("state_sha256"), str)
                or HEX64.fullmatch(item["state_sha256"]) is None):
            return _result("INCONCLUSIVE_FULL_STATE_HASH_UNAVAILABLE")
        if (not isinstance(item.get("synthetic_probe_sha256"), str)
                or HEX64.fullmatch(item["synthetic_probe_sha256"]) is None):
            return _result("INCONCLUSIVE_PROBE_IDENTITY")
        if (type(item.get("block_boundary_tokens")) is not int or
                item["block_boundary_tokens"] <= 0 or
                type(item.get("group_id")) is not int or
                item["group_id"] < 0 or
                type(item.get("physical_block_id")) is not int or
                item["physical_block_id"] < 0):
            return _result("INCONCLUSIVE_BLOCK_IDENTITY")
        shape = item.get("shape")
        if (not isinstance(shape, list) or not shape or len(shape) > 8 or
                not all(type(n) is int and 0 < n <= 100_000_000 for n in shape)
                or item.get("dtype") not in ("float32", "float16", "bfloat16")):
            return _result("INCONCLUSIVE_STATE_TENSOR_LAYOUT")
        keyed[key] = item

    for layer in sorted(REQUIRED):
        cold = keyed[("cold_capture", layer)]
        hit = keyed[("hit_restore", layer)]
        for name in ("synthetic_probe_sha256", "block_boundary_tokens", "group_id",
                     "physical_block_id", "shape", "dtype"):
            if cold[name] != hit[name]:
                return _result("INCONCLUSIVE_COLD_HIT_IDENTITY_DRIFT",
                               layer_kind=layer, field=name)
        if cold["state_sha256"] != hit["state_sha256"]:
            return _result("FAIL_RESTORED_STATE_CONTENT_DIFFERS",
                           layer_kind=layer)
    return {"status": "CPU_CONTRACT_MATCH_REQUIRES_LIVE_HOOK_AUDIT",
            "verified": False,
            "state_content_digests_match": True,
            "required_layer_kinds": sorted(REQUIRED),
            "matching_layer_kinds": len(REQUIRED)}


def inspect_stage_source(data: bytes) -> dict:
    """Bounded AST inventory for *exact* Preview Mamba candidate source."""
    try:
        text = data.decode("utf-8")
        tree = ast.parse(text)
    except (UnicodeError, SyntaxError, ValueError):
        raise ValueError("STAGE_SOURCE_UNPARSEABLE") from None
    matches = [c for c in tree.body
               if isinstance(c, ast.ClassDef) and
               c.name == "MambaHybridModelState"]
    if len(matches) != 1:
        raise ValueError("MAMBA_MODEL_CLASS_ABI_DRIFT")
    names = ("add_request", "_ensure_align_ctx", "preprocess_state",
             "postprocess_state")
    lines = text.splitlines()
    result = {}
    for name in names:
        ms = [n for n in matches[0].body if
              isinstance(n, ast.FunctionDef) and n.name == name]
        if len(ms) != 1:
            raise ValueError("MAMBA_RESTORE_METHOD_ABI_DRIFT_" + name)
        fn = ms[0]
        # Only approved code text; no model data, tensor contents or GPU access.
        result[name] = {
            "line_start": fn.lineno,
            "line_end": fn.end_lineno,
            "args": [arg.arg for arg in fn.args.args],
            "source": [f"{i}: {lines[i - 1]}"
                       for i in range(fn.lineno, fn.end_lineno + 1)],
            "calls": sorted({
                ast.unparse(n.func) for n in ast.walk(fn)
                if isinstance(n, ast.Call) and
                any(word in ast.unparse(n.func).lower()
                    for word in ("copy", "state", "align", "preprocess", "postprocess"))
            })[:40],
        }
    return {
        "status": "STAGE_RESTORE_ABI_SOURCE_INSPECTED_CPU_ONLY",
        "class": "MambaHybridModelState",
        "methods": result,
        "gpu_loaded": False,
        "runtime_state_content_verified": False,
    }


def inspect_pinned_stage(path: Path = STAGE) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
        raise ValueError("STAGE_SOURCE_UNAVAILABLE")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != STAGE_SHA256:
        raise ValueError("STAGE_SHA256_DRIFT")
    return inspect_stage_source(data)


def main() -> int:
    ap = argparse.ArgumentParser(description="P1 pinned Mamba source-only restore inspection")
    ap.add_argument("--inspect-stage", action="store_true", required=True)
    args = ap.parse_args()
    try:
        result = inspect_pinned_stage()
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "BLOCKED_READ_ONLY",
                          "reason": str(exc) if isinstance(exc, ValueError)
                          else "STAGE_SOURCE_ACCESS_FAILED"}, sort_keys=True))
        return 2
    for name, details in result["methods"].items():
        print(f"=== {name} ({details['line_start']}-{details['line_end']}) ===")
        for line in details["source"]:
            print(line)
    print("P1_PINNED_STAGE_RESTORE_SOURCE_ONLY_PASS_NO_GPU")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
