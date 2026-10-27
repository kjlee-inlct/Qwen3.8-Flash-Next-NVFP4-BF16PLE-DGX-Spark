#!/usr/bin/env python3
"""Phase6 A3b-0 CPU-only preparation, never real active runtime evidence.

Modes:
  --fixture PATH: independent stdlib arithmetic over synthetic JSON only.
  --installed-source-only: SHA/AST inspection of fixed vLLM source in separately
    approved isolated CPU container (no vLLM import; no GPU/model/HTTP).
Neither mode instantiates CacheConfig, a Scheduler or Mamba, or certifies P6-A.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sys
from typing import Any

MAX_FIXTURE_BYTES = 16 * 1024
MAX_SOURCE_BYTES = 2 * 1024 * 1024
MAX_GROUPS = 16
BLOCK_MAX = 65536
PINNED = {
    "config/scheduler.py": "bf399abc7216b4801fbba5fd8f5cbc1960c9458d7519a544ae3015d83dd7a7d6",
    "v1/engine/core.py": "f4b1e07b6d91fac1549bc74a5c804e5a88793d663b5dc045c9e455db6550f5ad",
    "v1/core/sched/scheduler.py": "c710f49e41e974e5b7b8f1cd2f5fb9722523f4da0165252e16351199ebd03124",
    "v1/worker/gpu/model_states/mamba_hybrid.py": "2e65f1da0a440f11a784bd36afe9206a7a2f674d522c047b838ad604e4c6acc0",
    "v1/attention/backends/mamba_attn.py": "9658330915daf4f8019a214317eb4be366eb52fd75fce8075cbb80d9ed7d3f6c",
    "config/cache.py": "8790351601be188ed1cc7ad9de2af1978b238269da4724873af1185c91165ef6",
    "v1/worker/mamba_utils.py": "25254d005f42b64dd55d15a5c646018f5599d971c23e7ca395eb5acaf4f41ed3",
}
# These are class/method NAME anchors from previously pinned Phase5 installed source.
# A match is not evidence that any class was selected or any branch executed.
METHODS = {
    "config/scheduler.py": ("SchedulerConfig", "get_scheduler_cls"),
    "v1/engine/core.py": ("EngineCore", "__init__"),
    "v1/core/sched/scheduler.py": ("Scheduler", "__init__"),
    "v1/worker/gpu/model_states/mamba_hybrid.py": ("MambaHybridModelState", "add_request"),
    "v1/worker/mamba_utils.py": ("MambaSpecDecodeGPUContext", "create"),
}
FUNCTIONS = {"v1/core/kv_cache_utils.py": "resolve_kv_cache_block_sizes"}
REQUIRED_FIELDS = frozenset({
    "source_kind", "cache_block_size", "scheduler_block_size",
    "hash_block_size", "dcp_size", "groups",
})


def _pos_int(value: Any, max_value: int = BLOCK_MAX) -> bool:
    return type(value) is int and 1 <= value <= max_value


def fixture_projection(data: Any) -> dict[str, Any]:
    """Diagnostic-only arithmetic, NOT a copy of vLLM's dynamic resolver."""
    blocked = lambda reason: {
        "gate": "P6-A3b-0", "status": "BLOCKED",
        "reasons": [reason], "p6_a_runtime_status": "BLOCKED",
    }
    if not isinstance(data, dict) or set(data) != REQUIRED_FIELDS:
        return blocked("fixture must have exactly the predefined nonsecret fields")
    if data["source_kind"] != "SYNTHETIC_CPU_FIXTURE":
        return blocked("only synthetic inputs are allowed; no operational config claims")
    for key in ("cache_block_size", "scheduler_block_size", "hash_block_size"):
        if not _pos_int(data[key]):
            return blocked("invalid block-size field")
    if not _pos_int(data["dcp_size"], 32):
        return blocked("invalid DCP size")
    groups = data["groups"]
    if not isinstance(groups, list) or not 1 <= len(groups) <= MAX_GROUPS:
        return blocked("missing or excessive synthetic groups")
    sizes: list[int] = []
    attention: list[int] = []
    mamba: list[int] = []
    for group in groups:
        if (not isinstance(group, dict) or set(group) != {"kind", "block_size"}
                or group["kind"] not in ("attention", "mamba", "other")
                or not _pos_int(group["block_size"])):
            return blocked("invalid group kind/shape/block size")
        value = group["block_size"]
        # A candidate arithmetic diagnostic only. Real resolver has early returns,
        # prefix/DCP/connector branches and actual grouping not observed here.
        sizes.append(value * data["dcp_size"] if group["kind"] == "attention" else value)
        if group["kind"] == "attention":
            attention.append(value)
        if group["kind"] == "mamba":
            mamba.append(value)
    candidate_lcm = math.lcm(*sizes)
    candidate_gcd = math.gcd(*sizes)
    different = sorted({value for value in mamba if value != data["cache_block_size"]})
    return {
        "gate": "P6-A3b-0",
        "status": "SYNTHETIC_GEOMETRY_ONLY_NOT_RUNTIME",
        "provenance": "operator-independent checked-in CPU fixture",
        "group_count": len(groups),
        "mamba_group_count": len(mamba),
        "candidate_group_lcm_not_resolved_scheduler": candidate_lcm,
        "candidate_group_gcd_not_resolved_hash": candidate_gcd,
        "declared_scheduler_block_matches_naive_lcm": (
            data["scheduler_block_size"] == candidate_lcm
        ),
        "declared_hash_block_matches_naive_gcd": (
            data["hash_block_size"] == candidate_gcd
        ),
        "synthetic_mamba_cache_block_difference": bool(different),
        "synthetic_different_mamba_block_sizes": different,
        "conditional_index_divergence_not_a_bug": bool(different),
        "actual_scheduler_resolver_branch_observed": False,
        "actual_scheduler_class_observed": False,
        "actual_mamba_group_sizes_observed": False,
        "physical_block_tables_or_tensors_observed": False,
        "p6_a_runtime_status": "BLOCKED",
        "gpu_or_model_executed": False,
        "note": "Diagnostic LCM/GCD ignores vLLM resolver early-return and prefix branches.",
    }


def read_fixture(path: Path) -> Any:
    """No path/symlink expansion, no secrets echoed on failure."""
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_FIXTURE_BYTES:
        raise ValueError("fixture invalid, symlinked or too large")
    return json.loads(path.read_text(encoding="utf-8"))


def _has_method(tree: ast.Module, cls: str, method: str) -> bool:
    matches = [node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == cls]
    return len(matches) == 1 and any(
        isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == method
        for n in matches[0].body
    )


def _has_function(tree: ast.Module, name: str) -> bool:
    return any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
               and n.name == name for n in tree.body)


def source_contract(root: Path) -> dict[str, Any]:
    """Import-free, no execution of installed vLLM; strict frozen source pins."""
    results: list[dict[str, Any]] = []
    if not root.is_dir() or root.is_symlink():
        return {"status": "BLOCKED", "reason": "source root unavailable"}
    root = root.resolve()
    # Verify seven frozen files plus the dedicated KV resolver source.
    for relative in (*PINNED, *FUNCTIONS):
        target = root / relative
        if target.is_symlink():
            return {"status": "BLOCKED", "reason": "symlinked source"}
        try:
            resolved = target.resolve(strict=True)
            if not resolved.is_relative_to(root) or not target.is_file():
                return {"status": "BLOCKED", "reason": "source outside installed root"}
            if target.stat().st_size > MAX_SOURCE_BYTES:
                return {"status": "BLOCKED", "reason": "source too large"}
            data = target.read_bytes()
            tree = ast.parse(data.decode("utf-8"))
        except (OSError, ValueError, SyntaxError, UnicodeError):
            return {"status": "BLOCKED", "reason": "source absent or unparsable"}
        digest = hashlib.sha256(data).hexdigest()
        pinned_ok = relative not in PINNED or digest == PINNED[relative]
        method_ok = (relative not in METHODS or _has_method(tree, *METHODS[relative]))
        function_ok = (relative not in FUNCTIONS or _has_function(tree, FUNCTIONS[relative]))
        results.append({
            "component": relative,
            "historical_dgx_sha_match": pinned_ok if relative in PINNED else None,
            "declared_anchor_present": method_ok and function_ok,
            "kind": "PARSED_SOURCE_NOT_EXECUTED",
        })
    complete = all(
        x["declared_anchor_present"] and x["historical_dgx_sha_match"] is not False
        for x in results
    )
    return {
        "status": "PINNED_SOURCE_AST_ONLY_NOT_CONFIG_CONSTRUCTION" if complete else "BLOCKED",
        "components": results,
        "p6_a_runtime_status": "BLOCKED",
        "actual_scheduler_cache_mamba_config_reproduced": False,
        "actual_gpu_block_table_or_state_observed": False,
        "vllm_modules_imported": False,
        "gpu_model_http_benchmark_ci_executed": False,
    }


def isolated_environment_guard(env: dict[str, str]) -> bool:
    expected = {
        "PHASE6_A3B_CPU_INSPECTION_ONLY": "1",
        "CUDA_VISIBLE_DEVICES": "-1",
        "NVIDIA_VISIBLE_DEVICES": "void",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    return all(env.get(k) == v for k, v in expected.items())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    choices = parser.add_mutually_exclusive_group(required=True)
    choices.add_argument("--fixture", type=Path)
    choices.add_argument("--installed-source-only", action="store_true")
    args = parser.parse_args(argv)
    if args.fixture is not None:
        try:
            result = fixture_projection(read_fixture(args.fixture))
        except (OSError, ValueError, TypeError):
            result = {"gate": "P6-A3b-0", "status": "BLOCKED",
                      "reasons": ["fixture unreadable or invalid"],
                      "p6_a_runtime_status": "BLOCKED"}
    else:
        if not isolated_environment_guard(dict(os.environ)):
            result = {"status": "BLOCKED", "reason": "CPU-only isolation environment guard failed"}
        else:
            # find_spec for a top-level package does not import the package.
            spec = importlib.util.find_spec("vllm")
            roots = [] if spec is None else list(spec.submodule_search_locations or [])
            result = (source_contract(Path(roots[0])) if len(roots) == 1
                      else {"status": "BLOCKED", "reason": "installed source ambiguous"})
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    print("PHASE6_A3B_CPU_PREPARATION_ONLY_NOT_ACTIVE_CONFIG_VERIFIED")
    return 2 if result["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    sys.exit(main())
