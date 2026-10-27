#!/usr/bin/env python3
"""Phase6 actual running-service ABI exposure audit: fail-closed, read-only.

This tries documented *existing* vLLM /metrics cache_config_info plus
/v1/models against 127.0.0.1:8000, while verifying the pinned Docker
container identity before and after. It NEVER attaches to Python processes,
execs Docker, starts models, executes inference, or claims full P6-A ABI.
Only allowlisted numbers/booleans are printed. Any missing group tables or
GPU tensor strides leave active P6-A BLOCKED.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.request import build_opener, HTTPRedirectHandler, Request

CONTAINER = "qwen38-flash-orca-uncensored-bf16-mtp"
PINNED_IMAGE = "sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a"
MODEL_ID = "qwen3.8-flash-next-orca-uncensored-bf16-mtp"
METRICS = "http://127.0.0.1:8000/metrics"
MODELS = "http://127.0.0.1:8000/v1/models"
MAX_HTTP_BYTES = 4 * 1024 * 1024
METRIC_LINE = re.compile(
    r'^vllm:cache_config_info\{([^{}\r\n]{1,8192})\}\s+1(?:\.0+)?\s*$'
)
BLOCK_SIZE = re.compile(r'(?:^|,)block_size="([1-9][0-9]{0,5})"(?:,|$)')
CACHE_ENABLED = re.compile(
    r'(?:^|,)enable_prefix_caching="(True|False|true|false)"(?:,|$)'
)
GPU_MEMORY_UTIL = re.compile(
    r'(?:^|,)gpu_memory_utilization="(0(?:\.[0-9]{1,5})?|1(?:\.0{1,5})?)"(?:,|$)'
)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _read_http(url: str) -> str | None:
    # Only fixed loopback URLs authored above; no external redirects.
    if url not in (METRICS, MODELS):
        return None
    try:
        request = Request(url, headers={"Accept": "text/plain, application/json"})
        with build_opener(NoRedirect).open(request, timeout=8) as response:
            body = response.read(MAX_HTTP_BYTES + 1)
        if len(body) > MAX_HTTP_BYTES:
            return None
        return body.decode("utf-8")
    except (OSError, UnicodeError, HTTPError, URLError, TimeoutError, ValueError):
        return None


def _docker_state() -> tuple[bool, tuple[str, str, str] | None]:
    try:
        p = subprocess.run(
            ["docker", "inspect", "--type", "container", CONTAINER],
            capture_output=True, text=True, timeout=10, check=False,
        )
        if p.returncode != 0 or len(p.stdout) > 2 * 1024 * 1024:
            return False, None
        data = json.loads(p.stdout)
        if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
            return False, None
        obj = data[0]
        state = obj.get("State")
        if not isinstance(state, dict):
            return False, None
        valid = state.get("Running") is True and obj.get("Image") == PINNED_IMAGE
        fields = (obj.get("Id"), obj.get("Image"), state.get("StartedAt"))
        if not all(isinstance(x, str) and x for x in fields):
            return False, None
        return valid, fields
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return False, None


def parse_cache_metric(raw: str | None) -> dict:
    if not isinstance(raw, str):
        return {"status": "NOT_OBSERVED"}
    rows: list[dict] = []
    for line in raw.splitlines():
        if not line.startswith("vllm:cache_config_info"):
            continue
        m = METRIC_LINE.fullmatch(line.strip())
        if m is None:
            return {"status": "INCONSISTENT_OR_UNPARSEABLE"}
        labels = m.group(1)
        values = BLOCK_SIZE.findall(labels)
        if len(values) != 1:
            return {"status": "INCONSISTENT_OR_UNPARSEABLE"}
        size = int(values[0])
        if size < 1 or size > 65536:
            return {"status": "INCONSISTENT_OR_UNPARSEABLE"}
        enable = CACHE_ENABLED.findall(labels)
        gpu = GPU_MEMORY_UTIL.findall(labels)
        if len(enable) > 1 or len(gpu) > 1:
            return {"status": "INCONSISTENT_OR_UNPARSEABLE"}
        rows.append({
            "block_size": size,
            "enable_prefix_caching": (
                enable[0].lower() == "true" if len(enable) == 1 else None
            ),
            "gpu_memory_utilization": (
                float(gpu[0]) if len(gpu) == 1 else None
            ),
        })
    if not rows:
        return {"status": "NOT_EXPOSED"}
    # Multiple engine-series with conflicting cache sizing are not collapsed.
    if any(row != rows[0] for row in rows[1:]):
        return {"status": "AMBIGUOUS_MULTI_ENGINE"}
    return {"status": "ACTIVE_METRIC_EXPOSED", "cache_config": rows[0],
            "metric_series_count": len(rows)}


def parse_models(raw: str | None) -> dict:
    if raw is None:
        return {"status": "NOT_OBSERVED"}
    try:
        data = json.loads(raw)
        rows = data["data"]
        if not isinstance(rows, list) or len(rows) != 1:
            return {"status": "BLOCKED"}
        item = rows[0]
        if not isinstance(item, dict) or item.get("id") != MODEL_ID:
            return {"status": "BLOCKED"}
        return {"status": "MATCHED_PINNED_SERVED_ID"}
    except (ValueError, KeyError, TypeError):
        return {"status": "BLOCKED"}


def observe() -> dict:
    before_ok, before = _docker_state()
    if not before_ok:
        return {"gate": "P6-A-LIVE-PASSIVE", "status": "BLOCKED",
                "reason": "pinned operational container not verified",
                "p6_a_runtime_status": "BLOCKED"}
    models = parse_models(_read_http(MODELS))
    cache = parse_cache_metric(_read_http(METRICS))
    after_ok, after = _docker_state()
    if not after_ok or before != after:
        return {"gate": "P6-A-LIVE-PASSIVE", "status": "BLOCKED",
                "reason": "pinned deployment changed or disappeared",
                "p6_a_runtime_status": "BLOCKED"}
    if models["status"] != "MATCHED_PINNED_SERVED_ID":
        return {"gate": "P6-A-LIVE-PASSIVE", "status": "BLOCKED",
                "reason": "served model ID mismatched or unavailable",
                "p6_a_runtime_status": "BLOCKED"}
    return {
        "gate": "P6-A-LIVE-PASSIVE",
        "status": ("PARTIAL_EXPOSED_RUNTIME_CACHE_METADATA" if
                   cache["status"] == "ACTIVE_METRIC_EXPOSED"
                   else "ABI_METRICS_NOT_USABLE"),
        "served_model_id": "MATCHED_PINNED_SERVED_ID",
        "pinned_legacy_identity_before_after": True,
        "active_cache_config_metric": cache,
        "active_scheduler_class": "NOT_OBSERVED",
        "effective_scheduler_hash_block_sizes": "NOT_OBSERVED",
        "effective_mamba_spec_group_block_sizes": "NOT_OBSERVED",
        "actual_group_block_table_rows_strides": "NOT_OBSERVED",
        "actual_gpu_tensor_ptr_shape_stride_allocations": "NOT_OBSERVED",
        "p6_a_runtime_status": "BLOCKED",
        "p6_b_c_d": "NOT_RUN",
        "source_of_truth": "existing read-only /metrics startup cache label, not live Python object or GPU state",
        "docker_exec_ptrace_gpu_model_benchmark_in_this_probe": False,
    }


def main() -> int:
    data = observe()
    print(json.dumps(data, sort_keys=True, ensure_ascii=False, indent=2))
    print("PHASE6_A_LIVE_METADATA_AUDIT_COMPLETED_NOT_FULL_ABI")
    return 2 if data["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    sys.exit(main())
