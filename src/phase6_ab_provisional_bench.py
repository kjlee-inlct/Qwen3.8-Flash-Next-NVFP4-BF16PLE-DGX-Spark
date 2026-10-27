#!/usr/bin/env python3
"""User-approved single 12x3 provisional bench against existing pinned service.

The original baseline is immutable. The legacy runner is invoked once with a
separate phase/output directory, monitored for host RAM floor, timeout and
Docker identity drift. Only the benchmark child process group is stopped on
failure; the running model/container is never stopped or reconfigured.
Outputs are private local staging; console projection is allowlisted numeric.
This is NOT P6-A active ABI certification or P6-D final regression.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time

import phase6_ab_benchmark_plan as baseline_contract

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/benchmark/run-llama-benchy.sh"
RUNNER = Path.home() / "Workspace/llm/llama-benchy-runner"
OUT_ROOT = Path.home() / "Workspace/llm/bench-results-staging"
CORPUS_URL = "https://www.gutenberg.org/files/1661/1661-0.txt"
CORPUS_SHA = "8a2f79a2f4601cfe6e25830c29c1a25c7a3d906285a989948117568f8077ab2c"
IMAGE = "sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a"
CONTAINER = "qwen38-flash-orca-uncensored-bf16-mtp"
PHASE = "phase6-pre-b-provisional"
MEM_BEFORE_MIB = 8192
MEM_STOP_MIB = 4096
MAX_SECONDS = 3600
INTERVAL_SEC = 10
MODEL_ID = baseline_contract.MODEL_ID
TAGS = ("result.json", "progress.jsonl", "run.log", "environment.private.json",
        "memory-before.txt", "gpu-before.txt", "memory-after.txt",
        "gpu-after.txt", "python-packages.txt")
RESULT_BASENAME = re.compile(
    r"^[0-9]{8}T[0-9]{6}Z-phase6-pre-b-provisional-[A-Za-z0-9]{6}$"
)
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def command(*argv: str) -> str | None:
    try:
        result = subprocess.run(
            list(argv), capture_output=True, text=True, check=False, timeout=15
        )
        if result.returncode != 0 or len(result.stdout) > 2 * 1024 * 1024:
            return None
        return result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return None


def memory_available_mib() -> int | None:
    try:
        text = Path("/proc/meminfo").read_text(encoding="ascii")
    except (OSError, UnicodeError):
        return None
    values = re.findall(r"^MemAvailable:\s+([0-9]+)\s+kB\s*$", text, re.M)
    return int(values[0]) // 1024 if len(values) == 1 else None


def deployment_identity() -> tuple[str, str, str] | None:
    raw = command("docker", "inspect", "--type", "container", CONTAINER)
    if raw is None:
        return None
    try:
        x = json.loads(raw)
        if not isinstance(x, list) or len(x) != 1:
            return None
        d = x[0]
        if not isinstance(d, dict) or d.get("Image") != IMAGE:
            return None
        state = d.get("State")
        if not isinstance(state, dict) or state.get("Running") is not True:
            return None
        keys = (d.get("Id"), d.get("Image"), state.get("StartedAt"))
        return keys if all(isinstance(k, str) and k for k in keys) else None
    except (ValueError, TypeError):
        return None


def digest(path: Path) -> str | None:
    if path.is_symlink() or not path.is_file():
        return None
    try:
        h = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def cached_corpus() -> Path:
    return Path.home() / ".cache/llama-benchy" / (
        hashlib.md5(CORPUS_URL.encode("utf-8")).hexdigest() + ".txt"
    )


def preflight() -> dict:
    baseline = baseline_contract.verify_immutable_baseline()
    if baseline.get("status") != "SOURCE_BASELINE_MATRIX_VALIDATED":
        return {"status": "BLOCKED", "reason": "immutable baseline provenance drift"}
    runner = command("git", "-C", str(RUNNER), "rev-parse", "HEAD")
    if runner != baseline_contract.RUNNER_SHA:
        return {"status": "BLOCKED", "reason": "benchmark runner SHA drift"}
    if not (RUNNER / ".venv/bin/python").is_file():
        return {"status": "BLOCKED", "reason": "pinned benchmark Python unavailable"}
    if digest(cached_corpus()) != CORPUS_SHA:
        return {"status": "BLOCKED", "reason": "cached input corpus drift"}
    if not OUT_ROOT.is_dir() or OUT_ROOT.is_symlink():
        return {"status": "BLOCKED", "reason": "private staging root unavailable"}
    identity = deployment_identity()
    if identity is None:
        return {"status": "BLOCKED", "reason": "pinned service identity unavailable"}
    mem = memory_available_mib()
    if mem is None or mem < MEM_BEFORE_MIB:
        return {"status": "BLOCKED", "reason": "host available RAM below 8GiB preflight floor"}
    return {
        "status": "READY_FOR_APPROVED_PROVISIONAL_BENCH",
        "mem_available_mib": mem,
        "source_baseline_matrix": "12/12_36_REPEATS_VERIFIED",
        "runner_sha_verified": True,
        "current_cached_corpus_sha_verified": True,
        "image_running_pinned_verified": True,
        "current_active_scheduler_mamba_gpu_abi": "NOT_OBSERVED",
        "p6_a_runtime": "BLOCKED",
        "p6_b_c_d": "NOT_RUN",
        "historical_2026_baseline_strict_comparison": "UNVERIFIED_SAMPLER_KV_CORPUS",
        "scope": "existing production service load; user explicitly approved this benchmark",
    }


def _stop_child(proc: subprocess.Popen) -> None:
    # The child is a separately created session; NEVER send a signal to Docker
    # or any pre-existing server process, only the owned benchmark group.
    if proc.poll() is not None:
        return
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(proc.pid, sig)
        except ProcessLookupError:
            return
        try:
            proc.wait(timeout=8)
            return
        except subprocess.TimeoutExpired:
            continue


def _result_directory(private_log: Path) -> Path | None:
    try:
        with private_log.open(encoding="utf-8", errors="replace") as stream:
            matches = re.findall(r"^BENCH_OUTPUT_DIR=(.+)$", stream.read(4 * 1024 * 1024), re.M)
        if len(matches) != 1:
            return None
        path = Path(matches[0])
        if not path.is_absolute() or path.is_symlink():
            return None
        if not RESULT_BASENAME.fullmatch(path.name) or path.parent.resolve() != OUT_ROOT.resolve():
            return None
        return path if path.is_dir() else None
    except OSError:
        return None


def verify_run_dir(path: Path) -> dict:
    """Allowlisted run result facts only; keep full private logs/config local."""
    try:
        if path.is_symlink() or not path.is_dir():
            return {"status": "INCOMPLETE"}
        raw = (path / "result.json")
        if raw.stat().st_size > 8 * 1024 * 1024:
            return {"status": "INCOMPLETE"}
        dataset = json.loads(raw.read_text(encoding="utf-8"))
        result = baseline_contract.verify_matrix(dataset)
        if result["status"] != "SOURCE_BASELINE_MATRIX_VALIDATED":
            return {"status": "INCOMPLETE", "reason": "missing 12x3 result matrix"}
        provenance = json.loads(
            (path / "environment.private.json").read_text(encoding="utf-8")
        )
        if not isinstance(provenance, dict):
            return {"status": "INCOMPLETE"}
        if any((
            provenance.get("phase") != PHASE,
            provenance.get("visibility") != "PRIVATE_DO_NOT_COMMIT",
            provenance.get("tool_git_sha") != baseline_contract.RUNNER_SHA,
            provenance.get("tokenizer_sha256") != baseline_contract.TOKENIZER_SHA,
            provenance.get("book_sha256") != CORPUS_SHA,
            provenance.get("served_model") != MODEL_ID,
        )):
            return {"status": "INCOMPLETE", "reason": "candidate fingerprint mismatch"}
        params = provenance.get("parameters")
        if not isinstance(params, dict) or any((
            params.get("pp") != [2048,8192], params.get("tg") != [128,256],
            params.get("depth") != [0,4096,16384],
            params.get("concurrency") != [1], params.get("runs") != 3,
            params.get("warmup_runs") != 1, params.get("exact_tg") is not True,
            params.get("latency_mode") != "generation",
            provenance.get("prompt_rng_seed") != 20261027
        )):
            return {"status": "INCOMPLETE", "reason": "benchmark options drift"}
        checksums = (path / "SHA256SUMS").read_text(encoding="ascii")
        digest_lines = checksums.splitlines()
        parsed = {}
        for line in digest_lines:
            m = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9.-]+)", line)
            if not m or m.group(2) in parsed:
                return {"status": "INCOMPLETE", "reason": "checksum ledger malformed"}
            parsed[m.group(2)] = m.group(1)
        if set(parsed) != set(TAGS):
            return {"status": "INCOMPLETE", "reason": "incomplete checksum ledger"}
        if any(digest(path / tag) != parsed[tag] for tag in TAGS):
            return {"status": "INCOMPLETE", "reason": "checksum mismatch"}
        compact = []
        for entry in sorted(dataset["benchmarks"],
                            key=lambda row:(row["context_size"],row["prompt_size"],row["response_size"])):
            compact.append({
                "pp": entry["prompt_size"],
                "tg": entry["response_size"],
                "depth": entry["context_size"],
                "pp_estimate_tokens_per_second": round(entry["pp_throughput"]["mean"], 3),
                "tg_decode_tokens_per_second": round(entry["tg_throughput"]["mean"], 3),
                "e2e_ttft_ms": round(entry["e2e_ttft"]["mean"], 3),
            })
        return {
            "status": "PASS_PROVISIONAL_PRE_B_36",
            "matrix_conditions": 12,
            "measured_repeats": 36,
            "bench_result_sha256": parsed["result.json"],
            "actual_runtime_abi": "BLOCKED",
            "formal_p6_d_comparison": "NOT_RUN",
            "historical_strict_a_b_comparison": "UNVERIFIED",
            "metrics": compact,
            "scope": "new measurements of unchanged existing service, separate from historical raw baseline",
        }
    except (OSError, TypeError, KeyError, IndexError, ValueError):
        return {"status": "INCOMPLETE", "reason": "run files missing or invalid"}


def execute() -> dict:
    pre = preflight()
    if pre["status"] != "READY_FOR_APPROVED_PROVISIONAL_BENCH":
        return pre
    # Linux flock prevents two copies of this *new* wrapper from overlapping.
    # Does not guarantee absence of other service clients. Store only outside
    # the Git checkout, with user-only permissions.
    os.umask(0o077)
    lock_path = OUT_ROOT / ".phase6-ab-provisional.lock"
    with lock_path.open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"status": "BLOCKED", "reason": "benchmark already running"}
        # Recheck just prior to launching the load, so preflight cannot be
        # interpreted as a durable safety certificate.
        identity = deployment_identity()
        mem = memory_available_mib()
        if identity is None or mem is None or mem < MEM_BEFORE_MIB:
            return {"status": "BLOCKED", "reason": "last-moment guard failed"}
        if digest(cached_corpus()) != CORPUS_SHA:
            return {"status": "BLOCKED", "reason": "corpus changed before run"}
        private = Path(tempfile.mkdtemp(
            prefix="phase6-ab-guard-", dir=str(OUT_ROOT)
        ))
        outlog = private / "runner.private.log"
        env = os.environ.copy()
        env.update({
            "LLAMA_BENCHY_RUNNER": str(RUNNER),
            "LLAMA_BENCHY_API": "http://127.0.0.1:8000/v1",
            "LLAMA_BENCHY_CONTAINER": CONTAINER,
            "LLAMA_BENCHY_MODEL": MODEL_ID,
            "LLAMA_BENCHY_RESULTS_ROOT": str(OUT_ROOT),
            "LLAMA_BENCHY_PHASE": PHASE,
            "PYTHONDONTWRITEBYTECODE": "1",
            "NO_PROXY": "127.0.0.1,localhost",
            "no_proxy": "127.0.0.1,localhost",
        })
        print("P6_AB_BENCH_STATUS=RUNNING_APPROVED_EXISTING_SERVICE_LOAD", flush=True)
        print("P6_AB_BENCH_PRIVATE_GUARD_DIR=" + str(private), flush=True)
        problem = None
        rc = None
        with outlog.open("wb") as log:
            try:
                proc = subprocess.Popen(
                    ["bash", str(SCRIPT)], cwd=str(ROOT), env=env,
                    stdout=log, stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            except OSError:
                return {"status": "BLOCKED", "reason": "benchmark child could not start"}
            started = time.monotonic()
            last_report_minute = -1
            try:
                while (rc := proc.poll()) is None:
                    available = memory_available_mib()
                    elapsed_minute = int(time.monotonic() - started) // 60
                    if elapsed_minute > last_report_minute:
                        last_report_minute = elapsed_minute
                        print(
                            f"P6_AB_WATCH_MINUTE={elapsed_minute} "
                            f"HOST_AVAILABLE_MIB={available if available is not None else 'UNKNOWN'}",
                            flush=True,
                        )
                    if available is None or available < MEM_STOP_MIB:
                        problem = "host memory fell below 4GiB watch floor"
                    elif deployment_identity() != identity:
                        problem = "pinned legacy container changed during benchmark"
                    elif time.monotonic() - started > MAX_SECONDS:
                        problem = "one-hour benchmark deadline exceeded"
                    if problem is not None:
                        _stop_child(proc)
                        break
                    time.sleep(INTERVAL_SEC)
            except BaseException:
                _stop_child(proc)
                raise
            if rc is None:
                rc = proc.wait()
        if deployment_identity() != identity:
            return {"status": "BLOCKED", "reason": "service identity drift after load"}
        if digest(cached_corpus()) != CORPUS_SHA:
            return {"status": "INCOMPLETE", "reason": "input corpus changed during load"}
        if problem is not None:
            return {"status": "INCOMPLETE", "reason": problem,
                    "private_guard_directory": str(private)}
        if rc != 0:
            return {"status": "INCOMPLETE", "reason": "pinned benchmark wrapper failed",
                    "private_guard_directory": str(private)}
        run_dir = _result_directory(outlog)
        if run_dir is None:
            return {"status": "INCOMPLETE", "reason": "runner result path missing",
                    "private_guard_directory": str(private)}
        result = verify_run_dir(run_dir)
        result["private_guard_directory"] = str(private)
        if result["status"] == "PASS_PROVISIONAL_PRE_B_36":
            result["private_benchmark_directory"] = str(run_dir)
        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--preflight", action="store_true")
    modes.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    result = preflight() if args.preflight else execute()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2), flush=True)
    if args.execute and result["status"] == "PASS_PROVISIONAL_PRE_B_36":
        print("PHASE6_AB_NEW_12X3_BENCH_RECORDED_EXISTING_SERVICE_NOT_A_PASS", flush=True)
    if args.preflight and result["status"] == "READY_FOR_APPROVED_PROVISIONAL_BENCH":
        print("PHASE6_AB_LIVE_BENCH_PREFLIGHT_PASS_NO_LOAD", flush=True)
    return 0 if result["status"] in (
        "READY_FOR_APPROVED_PROVISIONAL_BENCH", "PASS_PROVISIONAL_PRE_B_36"
    ) else 2


if __name__ == "__main__":
    sys.exit(main())
