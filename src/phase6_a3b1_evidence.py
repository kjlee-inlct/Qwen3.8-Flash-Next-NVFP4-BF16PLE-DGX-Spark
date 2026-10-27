"""Fail-closed allowlisted host validator for disposable CPU-only audit stdout.

Do not expose raw Docker output. The pinned-image audit is source SHA/AST only,
not reconstructed CacheConfig or observed live runtime objects.
"""
from __future__ import annotations

import json
import sys

EXPECTED_PATHS = frozenset({
    "config/scheduler.py", "v1/engine/core.py",
    "v1/core/sched/scheduler.py",
    "v1/worker/gpu/model_states/mamba_hybrid.py",
    "v1/attention/backends/mamba_attn.py", "config/cache.py",
    "v1/worker/mamba_utils.py", "v1/core/kv_cache_utils.py",
})
MARKER = "PHASE6_A3B_CPU_PREPARATION_ONLY_NOT_ACTIVE_CONFIG_VERIFIED"
MAX_OUTPUT = 65536


def summarize(raw: str) -> dict:
    blocked = {"status": "BLOCKED", "p6_a_runtime_status": "BLOCKED"}
    if not isinstance(raw, str) or len(raw) > MAX_OUTPUT:
        return blocked
    try:
        normalized = raw.lstrip()
        data, index = json.JSONDecoder().raw_decode(normalized)
        if normalized[index:].strip() != MARKER or not isinstance(data, dict):
            return blocked
        if data.get("status") != "PINNED_SOURCE_AST_ONLY_NOT_CONFIG_CONSTRUCTION":
            return blocked
        if data.get("p6_a_runtime_status") != "BLOCKED":
            return blocked
        for field in (
            "actual_scheduler_cache_mamba_config_reproduced",
            "actual_gpu_block_table_or_state_observed",
            "vllm_modules_imported", "gpu_model_http_benchmark_ci_executed",
        ):
            if data.get(field) is not False:
                return blocked
        components = data.get("components")
        if not isinstance(components, list) or len(components) != len(EXPECTED_PATHS):
            return blocked
        names = set()
        for component in components:
            if not isinstance(component, dict):
                return blocked
            name = component.get("component")
            if name not in EXPECTED_PATHS or name in names:
                return blocked
            names.add(name)
            if component.get("kind") != "PARSED_SOURCE_NOT_EXECUTED":
                return blocked
            if component.get("declared_anchor_present") is not True:
                return blocked
            if name != "v1/core/kv_cache_utils.py":
                if component.get("historical_dgx_sha_match") is not True:
                    return blocked
            elif component.get("historical_dgx_sha_match") is not None:
                return blocked
        if names != EXPECTED_PATHS:
            return blocked
        return {
            "status": "PASS_PINNED_SOURCE_AST_ONLY",
            "component_count": len(names),
            "source_historical_shas_checked": 7,
            "kv_resolver_ast_anchor_present_unpinned_sha": True,
            "active_scheduler_cache_mamba_reproduced": False,
            "physical_gpu_tables_or_state_observed": False,
            "p6_a_runtime_status": "BLOCKED",
            "p6_b_c_d_status": "NOT_RUN",
            "gpu_model_http_benchmark_ci": "NOT_RUN",
            "result_scope": "isolated CPU-only source AST, not active configuration",
        }
    except (json.JSONDecodeError, TypeError, ValueError):
        return blocked


def main() -> int:
    raw = sys.stdin.read(MAX_OUTPUT + 1)
    result = summarize(raw)
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result["status"] == "PASS_PINNED_SOURCE_AST_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
