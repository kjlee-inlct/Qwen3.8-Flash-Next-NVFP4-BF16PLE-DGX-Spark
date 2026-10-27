#!/usr/bin/env python3
"""Phase 6 A3a passive resource snapshot; no model load or GPU kernels.

Read only: /proc/meminfo, Docker inspect (fixed container), nvidia-smi NVML
telemetry. All untrusted stdout/stderr is suppressed except allowlisted numeric
values. This does NOT establish isolated-GPU headroom or active Mamba ABI.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
from typing import Any

CONTAINER = "qwen38-flash-orca-uncensored-bf16-mtp"
PIN_IMAGE = "sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a"
GPU_QUERY = "--query-gpu=memory.total,memory.free,memory.used,utilization.gpu,temperature.gpu"
GPU_FORMAT = "--format=csv,noheader,nounits"
NUMERIC = re.compile(r"^[0-9]+(?:\.[0-9]+)?$")
MB = 1024 * 1024


def read_command(*argv: str) -> str | None:
    """Suppress diagnostics to avoid leaking host identifiers, paths or env."""
    try:
        p = subprocess.run(
            argv, capture_output=True, text=True, timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return p.stdout if p.returncode == 0 else None


def parse_meminfo(text: str | None) -> dict[str, Any]:
    if not isinstance(text, str):
        return {"status": "UNAVAILABLE"}
    values = {}
    for line in text.splitlines():
        match = re.fullmatch(r"(MemTotal|MemAvailable|SwapTotal|SwapFree):\s*(\d+)\s+kB\s*", line)
        if match:
            values[match.group(1)] = int(match.group(2))
    if not all(k in values for k in ("MemTotal", "MemAvailable")):
        return {"status": "UNAVAILABLE"}
    if values["MemTotal"] < 1 or values["MemAvailable"] > values["MemTotal"]:
        return {"status": "INVALID"}
    result: dict[str, Any] = {
        "status": "OBSERVED",
        "mem_total_mib": values["MemTotal"] // 1024,
        "mem_available_mib": values["MemAvailable"] // 1024,
        "scope": "host-wide instantaneous MemAvailable, not guaranteed GPU allocation headroom",
    }
    if "SwapTotal" in values and "SwapFree" in values:
        if values["SwapFree"] > values["SwapTotal"]:
            return {"status": "INVALID"}
        result["swap_total_mib"] = values["SwapTotal"] // 1024
        result["swap_free_mib"] = values["SwapFree"] // 1024
    return result


def _number(raw: str) -> float | None:
    raw = raw.strip()
    if not NUMERIC.fullmatch(raw):
        return None
    value = float(raw)
    return value if value >= 0 and value < 1e15 else None


def parse_nvidia_smi(text: str | None) -> dict[str, Any]:
    if not isinstance(text, str) or not text.strip():
        return {"status": "UNAVAILABLE", "reason": "telemetry query unsupported or unavailable"}
    lines = text.strip().splitlines()
    if len(lines) > 8:
        return {"status": "INVALID", "reason": "unexpected device count"}
    devices = []
    for line in lines:
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 5:
            return {"status": "INVALID", "reason": "unexpected telemetry shape"}
        numbers = [_number(part) for part in parts]
        # Single DGX Spark may report N/A for some unified-memory NVML fields.
        devices.append({
            "memory_total_mib": numbers[0],
            "memory_free_mib": numbers[1],
            "memory_used_mib": numbers[2],
            "utilization_percent": numbers[3],
            "temperature_celsius": numbers[4],
        })
    known = sum(v is not None for d in devices for v in d.values())
    return {
        "status": "OBSERVED" if known == len(devices) * 5 else "PARTIAL",
        "devices": devices,
        "scope": "NVML telemetry only; N/A is unknown, not zero or proof of allocatability",
    }


def inspect_limits(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, list) or len(payload) != 1 or not isinstance(payload[0], dict):
        return {"status": "BLOCKED", "reason": "container metadata unavailable"}
    obj = payload[0]
    state, host = obj.get("State"), obj.get("HostConfig")
    if not isinstance(state, dict) or not isinstance(host, dict):
        return {"status": "BLOCKED", "reason": "container metadata incomplete"}
    running = state.get("Running") is True
    image_match = obj.get("Image") == PIN_IMAGE
    limit = host.get("Memory")
    # 0 means no explicit Docker memory limit, not unlimited physical memory.
    limit_mib = limit // MB if type(limit) is int and limit > 0 else None
    return {
        "status": "OBSERVED" if running and image_match else "BLOCKED",
        "legacy_running": running,
        "pinned_image_digest_match": image_match,
        "explicit_container_memory_limit_mib": limit_mib,
        "scope": "deployment metadata only; actual in-process Scheduler/Mamba pointers NOT inspected",
    }


def collect() -> dict[str, Any]:
    raw = read_command("docker", "inspect", "--type", "container", CONTAINER)
    try:
        parsed = json.loads(raw) if raw is not None else None
    except ValueError:
        parsed = None
    try:
        mem = Path("/proc/meminfo").read_text(encoding="ascii")
    except (OSError, UnicodeError):
        mem = None
    host = parse_meminfo(mem)
    gpu = parse_nvidia_smi(read_command("nvidia-smi", GPU_QUERY, GPU_FORMAT))
    deployment = inspect_limits(parsed)
    # Resource observation is never permission to start a second GPU workload.
    return {
        "gate": "P6-A3a-PASSIVE-RESOURCE-OBSERVATION",
        "status": ("OBSERVED_METADATA_ONLY"
                   if deployment["status"] == "OBSERVED" and host["status"] == "OBSERVED"
                   else "BLOCKED"),
        "deployment": deployment,
        "host_memory": host,
        "gpu_telemetry": gpu,
        "active_scheduler_cache_mamba_group_and_state_pointers": "NOT_OBSERVED",
        "isolated_gpu_startup_safe": "NOT_DETERMINABLE_FROM_SNAPSHOT",
        "p6_a_runtime_status": "BLOCKED",
        "p6_b_c_d_status": "NOT_RUN",
        "gpu_compute_and_model_load_executed": False,
        "operational_service_mutated": False,
        "requires_separate_runtime_approval": True,
    }


def main() -> int:
    result = collect()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    print("PHASE6_A3A_PASSIVE_RESOURCE_OBSERVATION_COMPLETED_NOT_GPU_CERTIFIED")
    return 0 if result["status"] == "OBSERVED_METADATA_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
