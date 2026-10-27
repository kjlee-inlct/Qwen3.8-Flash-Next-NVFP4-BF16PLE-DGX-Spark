#!/usr/bin/env python3
"""Phase6 A2 deployment and benchmark provenance read-only inspection.

Only docker inspect, git rev-parse, and file reads/hashes are permitted.
Never print Docker raw JSON, environment variables, paths, auth, or command lines.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CONTAINER = "qwen38-flash-orca-uncensored-bf16-mtp"
PINNED_IMAGE = "sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a"
BENCH_SHA = "e9be344578cec17745066b220798b80a0d2686d3"
BASELINE_SHA = "25f6abf3968efbf94cf08b02297140f7be2e8b29f8f2192b1d246e7432959edf"
BASELINE = ROOT / "results/llama-benchy/baseline/pre-blazux/20261026T221925Z/result.json"
BENCH_RUNNER = Path.home() / "Workspace/llm/llama-benchy-runner"
HISTORICAL = Path.home() / "Workspace/llm/bench-results-staging/20261026T221925Z-pre-blazux"
CORPUS_URL = "https://www.gutenberg.org/files/1661/1661-0.txt"
NUMERIC = frozenset(("--block-size", "--max-model-len", "--gpu-memory-utilization",
                     "--max-num-seqs", "--max-num-batched-tokens",
                     "--num-speculative-tokens", "--tensor-parallel-size",
                     "--pipeline-parallel-size"))
BOOL = frozenset(("--enable-prefix-caching", "--disable-prefix-caching", "--enforce-eager"))
NUM_RE = re.compile(r"^[0-9]+(?:\.[0-9]+)?$")


def readonly(*argv):
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, check=False, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def flag_allowlist(argv):
    if not isinstance(argv, list) or not all(isinstance(item, str) for item in argv):
        return {}
    out = {}
    for i, item in enumerate(argv):
        key, equals, value = item.partition("=")
        if key in BOOL and (not equals or value.lower() in ("true", "false")):
            out[key] = (value.lower() == "true") if equals else True
        elif key in NUMERIC:
            value = value if equals else argv[i + 1] if i + 1 < len(argv) else ""
            if NUM_RE.fullmatch(value):
                out[key] = value
    return out


def sanitize_inspect(payload):
    if not isinstance(payload, list) or len(payload) != 1 or not isinstance(payload[0], dict):
        return {"status": "BLOCKED", "reason": "docker inspect unavailable"}
    data = payload[0]
    cfg, state = data.get("Config"), data.get("State")
    if not isinstance(cfg, dict) or not isinstance(state, dict):
        return {"status": "BLOCKED", "reason": "docker inspect incomplete"}
    cmd = []
    for name in ("Entrypoint", "Cmd"):
        part = cfg.get(name) or []
        if isinstance(part, str):
            part = [part]
        if isinstance(part, list):
            cmd.extend(x for x in part if isinstance(x, str))
    running = state.get("Running") is True
    image_match = data.get("Image") == PINNED_IMAGE
    return {
        "status": "PASS" if running and image_match else "BLOCKED",
        "running": running,
        "pinned_image_digest_match": image_match,
        "deployment_launch_numeric_flags_only": flag_allowlist(cmd),
        "scope": "Docker deployment metadata only, NOT active in-process configuration",
    }


def digest(path):
    try:
        h = hashlib.sha256()
        with path.open("rb") as fp:
            for block in iter(lambda: fp.read(1024 * 1024), b""):
                h.update(block)
        return h.hexdigest()
    except OSError:
        return None


def historical_corpus():
    for fname in ("environment.json", "environment.private.json"):
        try:
            obj = json.loads((HISTORICAL / fname).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(obj, dict):
            for key in ("book_sha256", "corpus_sha256"):
                value = obj.get(key)
                if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value):
                    return value, True
    return None, False


def bench_check():
    runner = readonly("git", "-C", str(BENCH_RUNNER), "rev-parse", "HEAD")
    runner_ok = runner == BENCH_SHA
    original_ok = digest(BASELINE) == BASELINE_SHA
    cache_key = hashlib.md5(CORPUS_URL.encode("utf-8")).hexdigest() + ".txt"
    current_sha = digest(Path.home() / ".cache/llama-benchy" / cache_key)
    historical_sha, historical_known = historical_corpus()
    return {
        "status": "PARTIAL" if runner_ok and original_ok else "BLOCKED",
        "pinned_benchmark_runner_sha_match": runner_ok,
        "baseline_raw_result_sha256_match": original_ok,
        "cached_gutenberg_corpus_exists": bool(current_sha),
        "cached_gutenberg_corpus_sha256": current_sha,
        "historical_corpus_sha256_available": historical_known,
        "historical_corpus_matches_current": (
            current_sha == historical_sha if historical_known and current_sha else None
        ),
        "sampling_and_kv_equal_to_baseline": "UNVERIFIED",
        "performance_comparison_authorized": False,
    }


def main():
    raw = readonly("docker", "inspect", "--type", "container", CONTAINER)
    try:
        obj = json.loads(raw) if raw is not None else None
    except ValueError:
        obj = None
    result = {
        "gate": "P6-A2-READONLY-PREFLIGHT",
        "deployment": sanitize_inspect(obj),
        "benchmark": bench_check(),
        "active_scheduler_class": "NOT_OBSERVED",
        "active_cache_and_mamba_block_sizes": "NOT_OBSERVED",
        "active_state_group_tensor_block_table_pointers": "NOT_OBSERVED",
        "p6_a_runtime_status": "BLOCKED",
        "gpu_model_http_benchmark_ci": "NOT_RUN",
        "patch_approved": False,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    print("PHASE6_A2_READONLY_PREFLIGHT_COMPLETED_NOT_RUNTIME_CERTIFIED")


if __name__ == "__main__":
    main()
