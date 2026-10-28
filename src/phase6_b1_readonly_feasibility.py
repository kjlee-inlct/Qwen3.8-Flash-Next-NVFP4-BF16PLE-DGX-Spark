#!/usr/bin/env python3
"""P6-B1a passive readiness feasibility audit, NEVER GPU execution permission.

Reuses Phase6-A3a's allowlisted host/GPU telemetry parsers. A stable running
pinned Docker identity and a host observation floor are necessary for this
passive audit, not sufficient for isolated model or GPU memory allocation.
No new model, torch, vLLM, CUDA, Docker exec/run, HTTP, process attach or write.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from phase6_a3_readonly_resources import (
    GPU_FORMAT, GPU_QUERY, parse_meminfo, parse_nvidia_smi,
)

CONTAINER = "qwen38-flash-orca-uncensored-bf16-mtp"
PIN_IMAGE = "sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a"
OBSERVATION_HOST_FLOOR_MIB = 8192  # metadata audit guard, NOT GPU capacity
MAX_INSPECT_OUTPUT_BYTES = 2 * 1024 * 1024
MAX_GPU_OUTPUT_BYTES = 16 * 1024
ID_PATTERN = re.compile(r"^[0-9a-f]{64}$")
STARTED_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z$"
)


def _command(*argv: str, limit: int) -> str | None:
    """No echo of stdout/stderr; cap a successful command's output."""
    try:
        proc = subprocess.run(
            argv, text=True, capture_output=True, timeout=12, check=False
        )
    except (OSError, subprocess.TimeoutExpired, UnicodeError):
        return None
    if proc.returncode != 0 or len(proc.stdout.encode("utf-8")) > limit:
        return None
    return proc.stdout


def parse_identity(raw: str | None) -> dict[str, Any]:
    """The identity tuple MUST NEVER be printed; only non-identifying flags."""
    try:
        payload = json.loads(raw) if isinstance(raw, str) else None
    except (ValueError, TypeError):
        payload = None
    if not isinstance(payload, list) or len(payload) != 1:
        return {"status": "BLOCKED", "reason": "container metadata unavailable"}
    item = payload[0]
    if not isinstance(item, dict):
        return {"status": "BLOCKED", "reason": "container metadata malformed"}
    state = item.get("State")
    if not isinstance(state, dict):
        return {"status": "BLOCKED", "reason": "container state unavailable"}
    ident = item.get("Id")
    started = state.get("StartedAt")
    if not (isinstance(ident, str) and ID_PATTERN.fullmatch(ident)
            and isinstance(started, str) and STARTED_PATTERN.fullmatch(started)):
        return {"status": "BLOCKED", "reason": "container identity unavailable"}
    if item.get("Image") != PIN_IMAGE or state.get("Running") is not True:
        return {"status": "BLOCKED", "reason": "expected pinned running deployment absent"}
    return {"status": "VERIFIED", "_identity": (ident, started, PIN_IMAGE)}


def evaluate(before: dict, after: dict, host_before: dict,
             host_after: dict, gpu: dict) -> dict:
    """Pure, deny-by-default inference from A3a-compatible parsed observations."""
    reasons = []
    if before.get("status") != "VERIFIED" or after.get("status") != "VERIFIED":
        reasons.append("PINNED_DEPLOYMENT_UNVERIFIED")
    elif before.get("_identity") != after.get("_identity"):
        reasons.append("DEPLOYMENT_IDENTITY_DRIFT")

    for tag, host in (("BEFORE", host_before), ("AFTER", host_after)):
        if host.get("status") != "OBSERVED":
            reasons.append("HOST_MEMORY_" + tag + "_UNAVAILABLE")
        elif (type(host.get("mem_available_mib")) is not int
              or host["mem_available_mib"] < OBSERVATION_HOST_FLOOR_MIB):
            reasons.append("HOST_MEMORY_" + tag + "_BELOW_METADATA_FLOOR")

    # Even fully present NVML numbers do NOT prove GB10 unified-memory safety.
    gpu_status = gpu.get("status") if isinstance(gpu, dict) else None
    if gpu_status not in ("OBSERVED", "PARTIAL"):
        gpu_verdict = "UNKNOWN"
    elif gpu_status == "PARTIAL":
        gpu_verdict = "PARTIAL"
    else:
        gpu_verdict = "TELEMETRY_ONLY"

    if not reasons:
        status = "PASSIVE_METADATA_COLLECTED_NOT_GPU_READY"
    else:
        status = "BLOCKED"

    # NEVER reflect any raw telemetry, Docker IDs, host paths, or addresses.
    return {
        "gate": "P6-B1a-READONLY-RESOURCE-FEASIBILITY",
        "status": status,
        "reasons": sorted(set(reasons)),
        "pinned_legacy_identity_stable": (
            before.get("status") == "VERIFIED" and after.get("status") == "VERIFIED"
            and before.get("_identity") == after.get("_identity")
        ),
        "host_observation_floor_mib": OBSERVATION_HOST_FLOOR_MIB,
        "host_available_mib_before": (
            host_before.get("mem_available_mib")
            if host_before.get("status") == "OBSERVED" else None
        ),
        "host_available_mib_after": (
            host_after.get("mem_available_mib")
            if host_after.get("status") == "OBSERVED" else None
        ),
        "gpu_telemetry_scope": gpu_verdict,
        "unified_memory_headroom_proven": False,
        "second_model_feasible_proven": False,
        "gpu_allocation_authorized": False,
        "p6_a_active_abi": "BLOCKED",
        "p6_b0_cpu_synthetic": "PASS_AT_PRIOR_EXACT_DGX_SHA",
        "p6_b1_gpu_runtime": "NOT_RUN",
        "p6_b_formal_gate": "BLOCKED",
        "p6_c_d": "NOT_RUN",
        "observation_scope": "host/Docker/NVML metadata only, not a GPU memory budget",
        "docker_gpu_model_http_inference_benchmark_executed": False,
    }


def _meminfo() -> dict:
    try:
        raw = Path("/proc/meminfo").read_text(encoding="ascii")
    except (OSError, UnicodeError):
        raw = None
    return parse_meminfo(raw)


def collect() -> dict:
    before = parse_identity(_command(
        "docker", "inspect", "--type", "container", CONTAINER,
        limit=MAX_INSPECT_OUTPUT_BYTES
    ))
    host_before = _meminfo()
    raw_gpu = _command("nvidia-smi", GPU_QUERY, GPU_FORMAT,
                       limit=MAX_GPU_OUTPUT_BYTES)
    gpu = parse_nvidia_smi(raw_gpu)
    host_after = _meminfo()
    after = parse_identity(_command(
        "docker", "inspect", "--type", "container", CONTAINER,
        limit=MAX_INSPECT_OUTPUT_BYTES
    ))
    return evaluate(before, after, host_before, host_after, gpu)


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--observe", action="store_true")
    args = parser.parse_args(argv)
    if not args.observe:
        parser.error("only --observe is supported; no GPU execution flag")
    result = collect()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    print("PHASE6_B1A_PASSIVE_FEASIBILITY_DONE_NOT_GPU_APPROVAL")
    return 2 if result["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
