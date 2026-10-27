#!/usr/bin/env python3
"""Phase6 A->B benchmark checkpoint: immutable baseline inspection ONLY.

No network, Docker, model, GPUs, external runner or runtime API calls.
Success means the pre-blazux baseline artifact is intact and a 12x3
checkpoint PLAN is ready; it does NOT mean A PASS or benchmark executed.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import math
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASELINE_REL = "results/llama-benchy/baseline/pre-blazux/20261026T221925Z/result.json"
ENV_REL = "results/llama-benchy/baseline/pre-blazux/20261026T221925Z/environment.public.json"
BASELINE_SHA = "25f6abf3968efbf94cf08b02297140f7be2e8b29f8f2192b1d246e7432959edf"
RUNNER_SHA = "e9be344578cec17745066b220798b80a0d2686d3"
TOKENIZER_SHA = "06b9509352d2af50381ab2247e083b80d32d5c0aba91c272ca9ff729b6a0e523"
MODEL_ID = "qwen3.8-flash-next-orca-uncensored-bf16-mtp"
CHECKPOINT = "P6-A_TO_B_PRECHANGE_BENCHMARK_CHECKPOINT"
MEASURES = ("pp_throughput", "tg_throughput", "e2e_ttft", "ttfr", "peak_throughput")
MATRIX = frozenset(itertools.product((2048, 8192), (128, 256), (0, 4096, 16384)))
MAX_BYTES = 8 * 1024 * 1024


def _blocked(reason: str) -> dict[str, Any]:
    return {"status": "BLOCKED", "reason": reason}


def _finite_positive_number(value: Any) -> bool:
    return type(value) in (float, int) and math.isfinite(value) and value > 0


def verify_matrix(data: Any) -> dict[str, Any]:
    """Check schema and 36 repeats. Do not infer sampler/corpus equivalence."""
    if not isinstance(data, dict):
        return _blocked("result is not a JSON object")
    if data.get("latency_mode") != "generation" or data.get("model") != MODEL_ID:
        return _blocked("model or latency mode differs from frozen contract")
    if type(data.get("max_concurrency")) is not int or data["max_concurrency"] != 1:
        return _blocked("concurrency differs from frozen contract")
    rows = data.get("benchmarks")
    if not isinstance(rows, list) or len(rows) != len(MATRIX):
        return _blocked("not exactly 12 benchmark combinations")
    seen: set[tuple[int, int, int]] = set()
    for row in rows:
        if not isinstance(row, dict):
            return _blocked("invalid row")
        key_fields = ("prompt_size", "response_size", "context_size")
        if any(type(row.get(k)) is not int for k in key_fields):
            return _blocked("invalid matrix element type")
        key = tuple(row[k] for k in key_fields)
        if key not in MATRIX or key in seen:
            return _blocked("duplicate or unexpected matrix element")
        seen.add(key)
        if row.get("concurrency") != 1 or type(row.get("concurrency")) is not int:
            return _blocked("invalid row concurrency")
        if row.get("is_context_prefill_phase") is not False:
            return _blocked("invalid prefill phase")
        for metric in MEASURES:
            stat = row.get(metric)
            if not isinstance(stat, dict):
                return _blocked("missing metric or invalid statistic")
            values = stat.get("values")
            if not isinstance(values, list) or len(values) != 3:
                return _blocked("metric repeat count differs from three")
            if not all(_finite_positive_number(v) for v in values):
                return _blocked("metric contains nonpositive or nonfinite values")
            expected = sum(values) / 3
            mean = stat.get("mean")
            if not _finite_positive_number(mean) or not math.isclose(
                expected, mean, rel_tol=1e-8, abs_tol=1e-8
            ):
                return _blocked("metric arithmetic mean mismatch")
    if seen != MATRIX:
        return _blocked("matrix incomplete")
    return {
        "status": "SOURCE_BASELINE_MATRIX_VALIDATED",
        "matrix_conditions": 12,
        "measured_repeats_per_condition": 3,
        "measured_runs": 36,
        "warmup_runs_per_condition_from_provenance": 1,
        "latency_mode": "generation",
        "model_id_is_pinned": True,
        "scope": "numeric raw result values, not historical inputs/config or live runtime",
    }


def bounded_bytes(path: Path) -> bytes | None:
    if path.is_symlink() or not path.is_file():
        return None
    try:
        if path.stat().st_size > MAX_BYTES:
            return None
        return path.read_bytes()
    except OSError:
        return None


def verify_immutable_baseline(root: Path = ROOT) -> dict[str, Any]:
    payload = bounded_bytes(root / BASELINE_REL)
    if payload is None or hashlib.sha256(payload).hexdigest() != BASELINE_SHA:
        return _blocked("baseline original SHA256 mismatch or unavailable")
    try:
        data = json.loads(payload)
    except (UnicodeError, ValueError):
        return _blocked("baseline JSON unparsable")
    result = verify_matrix(data)
    if result["status"] == "BLOCKED":
        return result
    environment_bytes = bounded_bytes(root / ENV_REL)
    if environment_bytes is None:
        return _blocked("baseline public environment missing")
    try:
        env = json.loads(environment_bytes)
    except (UnicodeError, ValueError):
        return _blocked("baseline public environment unparsable")
    if not isinstance(env, dict):
        return _blocked("baseline environment invalid")
    if (env.get("served_model") != MODEL_ID or
            env.get("tool_git_sha") != RUNNER_SHA or
            env.get("tokenizer_sha256") != TOKENIZER_SHA or
            env.get("original_result_sha256") != BASELINE_SHA):
        return _blocked("baseline environment source provenance mismatch")
    params = env.get("parameters")
    if not isinstance(params, dict) or (
        params.get("pp") != [2048, 8192] or
        params.get("tg") != [128, 256] or
        params.get("depth") != [0, 4096, 16384] or
        params.get("concurrency") != [1] or
        params.get("runs") != 3 or
        params.get("warmup_runs") != 1 or
        params.get("exact_tg") is not True or
        params.get("latency_mode") != "generation" or
        env.get("prompt_rng_seed") != 20261027
    ):
        return _blocked("baseline environment run matrix mismatch")
    return {
        **result,
        "original_sha256_match": True,
        "runner_sha_match": True,
        "tokenizer_sha_match": True,
        "provenance_matrix_match": True,
    }


def plan(root: Path = ROOT) -> dict[str, Any]:
    baseline = verify_immutable_baseline(root)
    ok = baseline.get("status") == "SOURCE_BASELINE_MATRIX_VALIDATED"
    return {
        "gate": CHECKPOINT,
        "status": "PLAN_READY_NOT_EXECUTED" if ok else "BLOCKED",
        "immutable_pre_blazux_baseline": baseline,
        "future_matrix": {
            "pp": [2048, 8192],
            "tg": [128, 256],
            "depth": [0, 4096, 16384],
            "concurrency": [1],
            "warmup_per_condition": 1,
            "measured_per_condition": 3,
            "total_measured": 36,
            "exact_tg": True,
            "latency_mode": "generation",
            "prompt_rng_seed": 20261027,
        },
        "historical_corpus_sha_available": False,
        "historical_sampling_kv_parity": "UNVERIFIED",
        "actual_p6_a_runtime_abi": "BLOCKED",
        "p6_a_to_b_transition": "BLOCKED_UNTIL_REAL_A_GATE",
        "pre_b_checkpoint_run": "NOT_RUN",
        "performance_benchmark_authorized": False,
        "p6_b_runtime": "NOT_RUN",
        "p6_d_formal_regression": "NOT_RUN",
        "production_service_benchmark_permitted": False,
        "no_docker_http_gpu_model_or_benchmark_called": True,
        "purpose": "freeze pre-B reference; future paired benchmark requires separate approval",
    }


def main() -> int:
    result = plan()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    print("PHASE6_AB_BENCH_CHECKPOINT_PLAN_ONLY_NO_LOAD")
    return 0 if result["status"] == "PLAN_READY_NOT_EXECUTED" else 2


if __name__ == "__main__":
    sys.exit(main())
