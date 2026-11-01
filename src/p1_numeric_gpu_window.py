"""One approved P1 GPU diagnostic window: pinned MTP rejection image, same-ID restore.

This is a runtime MUTATION, not a preflight: do not use --execute absent
explicit approval. No Prefix/QSA/PLE source modifications or image builds.
A candidate cleanup failure BLOCKS original restart to prevent two GPU owners.
The caller must not SIGKILL this program: SIGTERM/SIGINT/SIGHUP are handled.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import re
import signal
import subprocess
import sys
import tarfile
import time

from src import p1_integrated_runtime as integrated
from src import p1_legacy_service_window as legacy
from src import p1_numeric_sampler_overlay as overlay
from src import p1_numeric_rejection_stage as rejection
from src import p1_prefix_gpu_oracle as oracle
from src import p1_prefix_gpu_window as gpu
from src import p1_prefix_release as release
from src import p1_preview_qsa_exact_topk as qsa

IMAGE_TAG = "kjlee-qwen38-p1-numeric-rejection:1cbd6361d610"
IMAGE_ID = "sha256:e16c45ce13b52a874b3caf95c2963e42c27340a0cd421f1924d6ae97c627f4aa"
PATCH_SHA = "0de6c713a944dc781e3ff64c23f6e378b7b37ecbd28c2d5d080a3130da8c5e4e"
NAME = "p1-numeric-rejection-window"
LABEL = "ai.kjlee.p1-numeric-rejection-window"
PORT = 18080
N_REQUESTS = 4
MAX_TOKENS = 64
STRICT_ABS = 1e-4


class Blocked(Exception):
    pass


def verify_image() -> None:
    rejection.verify_parent()
    parent = legacy.inspect("image", rejection.PARENT_TAG)
    child = legacy.inspect("image", IMAGE_TAG)
    if parent.get("Id") != rejection.PARENT_ID or child.get("Id") != IMAGE_ID:
        raise Blocked("REJECTION_CHILD_IMAGE_ID_DRIFT")
    old = (parent.get("RootFS") or {}).get("Layers") or []
    new = (child.get("RootFS") or {}).get("Layers") or []
    if not old or len(new) != len(old) + 1 or new[:len(old)] != old:
        raise Blocked("REJECTION_CHILD_ANCESTRY_DRIFT")
    pc = parent.get("Config") or {}
    cc = child.get("Config") or {}
    for key in ("Entrypoint", "Cmd", "User", "WorkingDir"):
        if pc.get(key) != cc.get(key):
            raise Blocked("REJECTION_CHILD_CONFIG_DRIFT_" + key)
    p_env = set(pc.get("Env") or [])
    c_env = set(cc.get("Env") or [])
    if (c_env - p_env != {rejection.TAP_ENV + "=0"} or p_env - c_env):
        raise Blocked("REJECTION_CHILD_ENV_DRIFT")
    if (rejection.TAP_ENV + "=0" not in c_env or
            overlay.TAP_ENV + "=0" not in c_env):
        raise Blocked("REJECTION_TAPS_DEFAULT_NOT_OFF")

def candidate_ids() -> list[str]:
    data = release._run(["docker", "ps", "-aq", "--no-trunc",
                         "--filter", "name=^/" + NAME + "$"])
    ids = data.splitlines() if data else []
    if len(ids) > 1 or any(re.fullmatch(r"[a-f0-9]{64}", x) is None for x in ids):
        raise Blocked("CANDIDATE_ID_LIST_AMBIGUOUS")
    return ids


def owned(head: str, expected_id: str | None = None) -> dict:
    ci = legacy.inspect("container", NAME)
    tags = (ci.get("Config") or {}).get("Labels") or {}
    policy = ((ci.get("HostConfig") or {}).get("RestartPolicy") or {}).get("Name")
    if (ci.get("Name") != "/" + NAME or ci.get("Image") != IMAGE_ID
            or tags.get(LABEL) != head or policy not in ("no", "")):
        raise Blocked("CANDIDATE_OWNERSHIP_DRIFT")
    if expected_id is not None and ci.get("Id") != expected_id:
        raise Blocked("CANDIDATE_ID_DRIFT")
    return ci


def prepare(head: str, original_id: str) -> tuple[dict, dict, str, list[str]]:
    qsa.preflight(head)
    receipt, original, base, state = release._legacy_state_for_release()
    if (state != "running" or receipt["id"] != original_id
            or original.get("Id") != original_id
            or original.get("Image") != overlay.BASE_IMAGE_ID):
        raise Blocked("ORIGINAL_NOT_RUNNING_SAME_ID")
    # Validate exact MTP=2, Prefix OFF, sampling/model flags, without applying
    # candidate_cmd's Prefix-ON replacement to the actual candidate argv.
    config = original.get("Config") or {}
    original_cmd = config.get("Cmd")
    _unused_prefix_on_cmd, model = gpu.candidate_cmd(original_cmd)
    if ((config.get("Entrypoint") != (base.get("Config") or {}).get("Entrypoint"))
            or (original.get("HostConfig") or {}).get("IpcMode") != "host"):
        raise Blocked("ORIGINAL_LAUNCH_ABI_DRIFT")
    extra = gpu.environment_delta(config, base.get("Config") or {})
    if any(v.partition("=")[0] in (
            overlay.TAP_ENV, rejection.TAP_ENV, "VLLM_QSA_EXACT_TOPK", "VLLM_PLE_FAST_GATHER",
            "VLLM_PLE_PHASE_STATS") for v in extra):
        raise Blocked("EXPERIMENT_ENV_DRIFT")
    verify_image()
    integrated.no_other_candidates()
    if candidate_ids():
        raise Blocked("NUMERIC_CANDIDATE_ALREADY_EXISTS")
    runtime = (original.get("HostConfig") or {}).get("Runtime") or ""
    if runtime not in ("", "runc", "nvidia"):
        raise Blocked("ORIGINAL_RUNTIME_DRIFT")
    argv = ["docker", "create", "--pull=never", "--name", NAME,
            "--label", LABEL + "=" + head,
            "--network=bridge", "--publish", f"127.0.0.1:{PORT}:8000",
            "--gpus=all", "--ipc=host", "--memory=112g",
            "--memory-swap=112g", "--pids-limit=1024",
            "--restart=no", "--security-opt=no-new-privileges"]
    if runtime:
        argv.append("--runtime=" + runtime)
    if config.get("User"):
        argv += ["--user", config["User"]]
    if config.get("WorkingDir"):
        argv += ["--workdir", config["WorkingDir"]]
    for key, target in (("cache", "/recipe/hf-cache"),
                        ("views", "/recipe/recipe-views")):
        argv += ["--mount",
                 f"type=bind,src={receipt[key]},dst={target},readonly"]
    for item in extra:
        argv += ["--env", item]
    argv += ["--env", "HF_HUB_OFFLINE=1",
             "--env", "TRANSFORMERS_OFFLINE=1",
             "--env", "PYTHONDONTWRITEBYTECODE=1",
             "--env", overlay.TAP_ENV + "=0",
             "--env", rejection.TAP_ENV + "=1",
             IMAGE_TAG, *original_cmd]
    return receipt, original, model, argv


def verify_candidate(head: str, cid: str, receipt: dict,
                     original_cmd: list[str]) -> None:
    ci = owned(head, cid)
    if (ci.get("State") or {}).get("Status") != "created":
        raise Blocked("CANDIDATE_NOT_CREATED")
    conf = ci.get("Config") or {}
    if conf.get("Cmd") != original_cmd:
        raise Blocked("CANDIDATE_PREFIX_OR_MTP_DRIFT")
    env = conf.get("Env") or []
    if (env.count(rejection.TAP_ENV + "=1") != 1 or
            env.count(overlay.TAP_ENV + "=0") != 1 or
            rejection.TAP_ENV + "=0" in env or overlay.TAP_ENV + "=1" in env):
        raise Blocked("CANDIDATE_TAP_CONFIG_DRIFT")
    mounts = ci.get("Mounts") or []
    expected = {(receipt["cache"], "/recipe/hf-cache"),
                (receipt["views"], "/recipe/recipe-views")}
    if (len(mounts) != 2 or
            {(m.get("Source"), m.get("Destination")) for m in mounts} != expected
            or any(m.get("Type") != "bind" or m.get("RW") is not False
                   for m in mounts)):
        raise Blocked("CANDIDATE_MOUNTS_DRIFT")
    binds = ((ci.get("HostConfig") or {}).get("PortBindings") or {}).get("8000/tcp")
    if binds != [{"HostIp": "127.0.0.1", "HostPort": str(PORT)}]:
        raise Blocked("CANDIDATE_BIND_DRIFT")
    # Verify the exact installed two-file source payload before stopping legacy.
    for path, digest in ((rejection.SOURCE_PATH, PATCH_SHA),
                         (overlay.source_trace.PACKAGE_ROOT + overlay.SAMPLER_PATH,
                          rejection.PARENT_PATCH_SHA)):
        try:
            cp = subprocess.run(["docker", "cp", cid + ":" + path, "-"],
                                capture_output=True, timeout=25)
            if cp.returncode != 0:
                raise Blocked("CANDIDATE_SOURCE_COPY_FAILED")
            raw = overlay.source_trace.extract_python_tar(cp.stdout)
        except (OSError, subprocess.TimeoutExpired, overlay.source_trace.Blocked):
            raise Blocked("CANDIDATE_SOURCE_READ_UNAVAILABLE") from None
        if hashlib.sha256(raw).hexdigest() != digest:
            raise Blocked("CANDIDATE_SOURCE_SHA_DRIFT")


def parse_rejection_tar(raw: bytes) -> list[dict]:
    """Parse one bounded candidate-private JSONL file, never extract to host."""
    if not raw or len(raw) > 160_000:
        raise Blocked("REJECTION_TAP_ARCHIVE_SIZE_INVALID")
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as tar:
            members = [m for m in tar.getmembers() if m.isfile()]
            if (len(members) != 1 or members[0].issym() or members[0].islnk()
                    or not members[0].name.endswith("p1-numeric-rejection-tap.jsonl")
                    or members[0].size > 131_072):
                raise Blocked("REJECTION_TAP_ARCHIVE_CONTENT_INVALID")
            data = tar.extractfile(members[0])
            if data is None:
                raise Blocked("REJECTION_TAP_ARCHIVE_READ_INVALID")
            source = data.read(131_073)
            if len(source) != members[0].size:
                raise Blocked("REJECTION_TAP_ARCHIVE_LENGTH_DRIFT")
    except (tarfile.TarError, OSError, EOFError):
        raise Blocked("REJECTION_TAP_ARCHIVE_INVALID") from None
    result = []
    try:
        for line in source.decode("utf-8").splitlines():
            if not line.startswith("P1_REJECTION_TAP "):
                raise Blocked("REJECTION_TAP_LINE_PREFIX_INVALID")
            event = json.loads(line[len("P1_REJECTION_TAP "):])
            if not isinstance(event, dict) or event.get("status") not in (
                    "REJECTION_FORWARD_ENTERED", "REJECTION_ACCEPTED_BOUNDARY"):
                raise Blocked("REJECTION_TAP_EVENT_INVALID")
            if (type(event.get("sequence")) is not int or
                    not 1 <= event["sequence"] <= 32):
                raise Blocked("REJECTION_TAP_SEQUENCE_INVALID")
            result.append(event)
    except (ValueError, UnicodeError, TypeError):
        raise Blocked("REJECTION_TAP_JSON_INVALID") from None
    if len(result) > 256:
        raise Blocked("REJECTION_TAP_EVENT_COUNT_EXCEEDED")
    return result


def read_rejection_events(cid: str) -> list[dict] | None:
    """None means missing tap file; any other Docker failure is fatal."""
    try:
        cp = subprocess.run(
            ["docker", "cp", cid + ":" + rejection.TAP_FILE, "-"],
            capture_output=True, timeout=25,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise Blocked("REJECTION_TAP_DOCKER_UNAVAILABLE") from None
    if cp.returncode != 0:
        error = cp.stderr.decode("utf-8", errors="replace").lower()
        if ("could not find the file" in error or
                "no such file or directory" in error):
            return None
        raise Blocked("REJECTION_TAP_DOCKER_COPY_FAILED")
    return parse_rejection_tar(cp.stdout)


def probe_logs(cid: str) -> list[dict]:
    """Sanitize stderr records; never print raw logs."""
    try:
        cp = subprocess.run(["docker", "logs", "--tail", "1000", cid],
                            capture_output=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        raise Blocked("CANDIDATE_LOGS_UNAVAILABLE") from None
    if cp.returncode != 0 or len(cp.stdout) + len(cp.stderr) > 2_000_000:
        raise Blocked("CANDIDATE_LOGS_UNAVAILABLE_OR_OVERSIZE")
    records = []
    for line in (cp.stdout + b"\n" + cp.stderr).decode("utf-8", errors="replace").splitlines():
        if "P1_REJECTION_TAP " not in line:
            continue
        try:
            item = json.loads(line.split("P1_REJECTION_TAP ", 1)[1])
        except (ValueError, TypeError):
            continue
        if isinstance(item, dict) and item.get("status") in (
                "REJECTION_FORWARD_ENTERED", "REJECTION_ACCEPTED_BOUNDARY"):
            records.append(item)
    return records

def analyse(runs: list[dict], taps: list[list[dict]]) -> dict:
    ids = [r.get("token_ids") for r in runs]
    logprobs = [r.get("logprobs") for r in runs]
    valid = (
        len(runs) == N_REQUESTS and len(taps) == N_REQUESTS
        and all(isinstance(v, list) and len(v) >= 2 for v in ids)
        and all(x == ids[0] for x in ids)
        and all(isinstance(p, list) and len(p) == len(ids[0])
                and all(type(x) in (int, float) and math.isfinite(x)
                        for x in p) for p in logprobs)
    )
    first_delta = (
        max(abs(logprobs[0][0] - p[0]) for p in logprobs[1:])
        if valid else None
    )
    max_delta = (
        max(abs(a - b) for p in logprobs[1:]
            for a, b in zip(logprobs[0], p))
        if valid else None
    )
    forwards = [[e for e in group if e.get("status") == "REJECTION_FORWARD_ENTERED"]
                for group in taps]
    accepted = [[e for e in group if e.get("status") == "REJECTION_ACCEPTED_BOUNDARY"]
                for group in taps]
    first = [events[0] if events else None for events in accepted]
    hashes_valid = len(first) == N_REQUESTS and all(
        isinstance(item, dict)
        and re.fullmatch(r"[0-9a-f]{64}", item.get("first_row_logits_sha256", ""))
        and re.fullmatch(r"[0-9a-f]{64}", item.get("first_row_logprobs_sha256", ""))
        and isinstance(item.get("raw_logits_shape"), list)
        and isinstance(item.get("logprobs_shape"), list)
        for item in first
    )
    shape_keys = ("raw_logits_shape", "logprobs_shape", "raw_logits_dtype",
                  "logprobs_dtype", "mode", "processed_mode", "logits_mode")
    comparable = bool(hashes_valid and all(
        all(item.get(key) == first[0].get(key) for key in shape_keys)
        for item in first[1:]
    ))
    logits_same = (len({item["first_row_logits_sha256"] for item in first}) == 1
                   if comparable else None)
    probs_same = (len({item["first_row_logprobs_sha256"] for item in first}) == 1
                  if comparable else None)
    # Hash of first rejection boundary is NOT proven to correspond to API's
    # first token. Never attribute the first-token drift to this boundary.
    status = (
        "INCONCLUSIVE_API_OR_TOKEN_IDENTITY" if not valid else
        "INCONCLUSIVE_NO_REJECTION_FORWARD" if not any(forwards) else
        "INCONCLUSIVE_REJECTION_CAPTURE_INCOMPLETE" if not comparable else
        "REJECTION_FIRST_BOUNDARY_LOGITS_DIFFER_UNATTRIBUTED"
        if not logits_same else
        "REJECTION_FIRST_BOUNDARY_LOGPROBS_DIFFER_UNATTRIBUTED"
        if not probs_same else
        "REJECTION_FIRST_BOUNDARY_SAME_API_DRIFT_UNATTRIBUTED"
        if max_delta > STRICT_ABS else
        "REJECTION_FIRST_BOUNDARY_SAME_API_WITHIN_STRICT_DIAGNOSTIC_ONLY"
    )
    return {
        "status": status,
        "request_count": len(runs),
        "tokens_each": [len(r.get("token_ids") or []) for r in runs],
        "all_same_token_ids": valid,
        "api_first_token_max_abs_delta": first_delta,
        "api_all_tokens_max_abs_delta": max_delta,
        "strict_abs_tolerance": STRICT_ABS,
        "rejection_forward_events_per_request": [len(x) for x in forwards],
        "rejection_accepted_events_per_request": [len(x) for x in accepted],
        "first_boundary_shapes_comparable": comparable,
        "first_boundary_logits_identical_sha256": logits_same,
        "first_boundary_logprobs_identical_sha256": probs_same,
        "first_boundary_to_api_token_mapping_proven": False,
        "prefix_cache": "OFF", "mtp_draft_tokens": 2, "qsa": "stock",
        "final_p1_pass": False, "diagnostic_only": True,
    }

def mtp_metrics_delta(before: dict | None, after: dict | None) -> dict:
    """Bounded candidate-only evidence; missing and zero counters differ."""
    counters = (
        "spec_decode_num_drafts_total",
        "spec_decode_num_draft_tokens_total",
        "spec_decode_num_accepted_tokens_total",
    )
    out = {"mtp_metrics_status": "UNAVAILABLE", "mtp_drafts_delta": None,
           "mtp_draft_tokens_delta": None,
           "mtp_accepted_draft_tokens_delta": None,
           "mtp_acceptance_observed": None}
    if not isinstance(before, dict) or not isinstance(after, dict):
        return out
    def contains(metrics: dict, name: str) -> bool:
        return any(k.split("{", 1)[0] == "vllm:" + name for k in metrics)
    if not all(contains(before, c) and contains(after, c) for c in counters):
        out["mtp_metrics_status"] = "MISSING_COUNTERS"
        return out
    vals = [oracle.counter_delta(before, after, c) for c in counters]
    out.update(mtp_metrics_status="OBSERVED_CANDIDATE_COUNTERS",
               mtp_drafts_delta=vals[0],
               mtp_draft_tokens_delta=vals[1],
               mtp_accepted_draft_tokens_delta=vals[2],
               mtp_acceptance_observed=vals[2] > 0)
    return out


def run_diagnostic(model: str, cid: str) -> dict:
    payload = oracle.build_payload(model, long_prompt=True)
    payload["max_tokens"] = MAX_TOKENS
    # The accepted MTP counter is observed on the candidate, not on the
    # restored original whose counters reset after each maintenance window.
    try:
        mtp_before = oracle.metrics(PORT)
    except oracle.OracleBlocked:
        mtp_before = None
    runs, snapshots = [], []
    initial = read_rejection_events(cid)
    previous = len(initial or [])
    for _ in range(N_REQUESTS):
        sample = oracle.extract(oracle.request_json(PORT, payload))
        if (not isinstance(sample.get("token_ids"), list)
                or len(sample["token_ids"]) != MAX_TOKENS):
            raise Blocked("API_TOKEN_COUNT_MISSING")
        runs.append(sample)
        events = read_rejection_events(cid)
        for _ in range(15):
            if events is not None and len(events) > previous:
                break
            time.sleep(0.2)
            events = read_rejection_events(cid)
        current = events or []
        if len(current) < previous:
            raise Blocked("REJECTION_TAP_FILE_TRUNCATED_OR_RESET")
        snapshots.append(current[previous:])
        previous = len(current)
    report = analyse(runs, snapshots)
    # Asynchronous vLLM metrics need a short bounded flush window.
    mtp_after = None
    for attempt in range(4):
        if attempt:
            time.sleep(1.0)
        try:
            mtp_after = oracle.metrics(PORT)
        except oracle.OracleBlocked:
            continue
        delta = mtp_metrics_delta(mtp_before, mtp_after)
        if delta["mtp_drafts_delta"] is not None and delta["mtp_drafts_delta"] > 0:
            break
    report.update(mtp_metrics_delta(mtp_before, mtp_after))
    if report["status"] == "INCONCLUSIVE_NO_REJECTION_FORWARD":
        if report["mtp_drafts_delta"] is not None:
            report["status"] = (
                "INCONCLUSIVE_MTP_ACTIVE_BUT_REJECTION_TAP_ABSENT"
                if report["mtp_drafts_delta"] > 0 else
                "INCONCLUSIVE_NO_MTP_DRAFTS_OBSERVED")
    stderr = probe_logs(cid)
    report["rejection_tap_file_events_total"] = previous
    report["rejection_tap_stderr_events_total"] = len(stderr)
    report["stderr_transport_missing_with_file_evidence"] = (
        previous > 0 and len(stderr) == 0
    )
    return report

def restore_original(head: str, original_id: str, model: str) -> None:
    release._run(["bash", str(qsa.ROOT / "scripts/start.sh"),
                  "--expected-head", head,
                  "--confirm-id", original_id, "--execute"], timeout=120)
    current = legacy.inspect("container", legacy.NAME)
    if (current.get("Id") != original_id or current.get("Image") != overlay.BASE_IMAGE_ID
            or (current.get("State") or {}).get("Running") is not True):
        raise Blocked("ORIGINAL_RESTORE_ID_OR_STATE_DRIFT")
    gpu.wait_ready(8000, model, timeout_s=900)


def cleanup(head: str) -> None:
    ids = candidate_ids()
    if not ids:
        return
    owned(head, ids[0])
    release._run(["docker", "rm", "--force", ids[0]], timeout=120)
    if candidate_ids():
        raise Blocked("CANDIDATE_CLEANUP_UNCONFIRMED")


def execute(head: str, original_id: str) -> dict:
    receipt, original, model, argv = prepare(head, original_id)
    # Catch the stop/start side effects even if a subprocess exits with an
    # error after changing Docker state.
    cleanup_confirmed = False
    diagnostic = None
    failure = None
    try:
        # Create first: if source/config/port cannot be staged, no downtime.
        release._run(argv, timeout=120)
        ci = owned(head)
        verify_candidate(head, ci["Id"], receipt, (original.get("Config") or {})["Cmd"])
        release._run(["bash", str(qsa.ROOT / "scripts/stop.sh"),
                      "--expected-head", head, "--confirm-id",
                      original_id, "--execute"], timeout=120)
        now = legacy.inspect("container", legacy.NAME)
        if (now.get("Id") != original_id
                or (now.get("State") or {}).get("Status") != "exited"):
            raise Blocked("ORIGINAL_STOP_UNCONFIRMED")
        if gpu.available_kib() < gpu.MIN_AFTER_STOP_KIB:
            raise Blocked("MEMAVAILABLE_BELOW_EXISTING_POLICY")
        release._run(["docker", "start", ci["Id"]], timeout=120)
        gpu.wait_ready(PORT, model, timeout_s=1200)
        diagnostic = run_diagnostic(model, ci["Id"])
        print(json.dumps(diagnostic, sort_keys=True), flush=True)
    except BaseException as exc:
        failure = (str(exc) if isinstance(exc, Blocked) else type(exc).__name__)
        print("P1_NUMERIC_GPU_DIAGNOSTIC_INTERRUPTED_OR_BLOCKED_" + failure,
              file=sys.stderr, flush=True)
    finally:
        # Do not restart the original while a possibly running candidate can
        # still own GPU memory. Only remove exactly the owned candidate.
        try:
            cleanup(head)
            cleanup_confirmed = True
        except BaseException:
            print("CRITICAL: CANDIDATE_CLEANUP_UNCONFIRMED_ORIGINAL_NOT_RESTARTED",
                  file=sys.stderr, flush=True)
        if cleanup_confirmed:
            try:
                orig = legacy.inspect("container", legacy.NAME)
                if orig.get("Id") != original_id:
                    raise Blocked("ORIGINAL_CONTAINER_ID_DRIFT")
                if (orig.get("State") or {}).get("Status") == "exited":
                    restore_original(head, original_id, model)
                else:
                    # Original can remain running if stop failed without side
                    # effect. Still require its health after candidate cleanup.
                    if (orig.get("State") or {}).get("Status") != "running":
                        raise Blocked("ORIGINAL_UNEXPECTED_STATE")
                    gpu.wait_ready(8000, model, timeout_s=900)
                print("P1_NUMERIC_ORIGINAL_SAME_ID_HTTP_RESTORED", flush=True)
            except BaseException:
                print("CRITICAL: ORIGINAL_HTTP_RESTORE_UNCONFIRMED",
                      file=sys.stderr, flush=True)
                cleanup_confirmed = False
    if not cleanup_confirmed:
        raise Blocked("RECOVERY_UNCONFIRMED")
    if failure is not None:
        raise Blocked("WINDOW_FAILED_ORIGINAL_RESTORED_" + failure)
    if diagnostic is None:
        raise Blocked("DIAGNOSTIC_MISSING")
    return diagnostic


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--expected-head", required=True)
    p.add_argument("--confirm-original-id", required=True)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight", action="store_true")
    group.add_argument("--execute-approved-window", action="store_true")
    args = p.parse_args(argv)
    try:
        if (os.geteuid() == 0 or
                not re.fullmatch(r"[a-f0-9]{40}", args.expected_head or "") or
                args.confirm_original_id != overlay.source_trace.ORIGINAL_ID):
            raise Blocked("EXACT_CONFIRMATION_OR_USER_REQUIRED")
        if args.preflight:
            receipt, original, model, _ = prepare(
                args.expected_head, args.confirm_original_id)
            print(json.dumps({
                "status": "P1_NUMERIC_GPU_PREFLIGHT_READY_NOT_EXECUTED",
                "original_id": receipt["id"], "candidate_image_id": IMAGE_ID,
                "original_state": original["State"]["Status"],
                "candidate_port": PORT,
                "model": model,
                "original_will_be_stopped": False,
            }, sort_keys=True))
            return 0
        result = execute(args.expected_head, args.confirm_original_id)
        return 0 if not result["status"].startswith("INCONCLUSIVE_") else 2
    except (Blocked, qsa.Blocked, release.ReleaseBlocked,
            legacy.Blocked, gpu.Blocked, oracle.OracleBlocked,
            OSError, ValueError, TypeError, KeyError):
        print("P1_NUMERIC_GPU_WINDOW_BLOCKED_OR_INCONCLUSIVE",
              file=sys.stderr, flush=True)
        return 2


def _on_signal(*_):
    raise Blocked("INTERRUPTED")


if __name__ == "__main__":
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, _on_signal)
    raise SystemExit(main())
