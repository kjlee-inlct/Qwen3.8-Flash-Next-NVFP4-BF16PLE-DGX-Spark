"""Approved-P2 Numeric witness: owner-checked exclusive GPU window.

Four serial synthetic first-token requests to a one-COPY Sampler-only image,
Prefix OFF, MTP OFF. Preserves original container ID and restores its API in
finally, including strict failure. Image build is separately gated and safe
while original runs. No raw prompts, tokens or model tensors are printed.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import tarfile

from src import p1_legacy_service_window as legacy
from src import p1_prefix_release as release
from src import p1_preview_qsa_exact_topk as qsa
from src import p1_qsa_only_runtime as b
from src import p1_qsa_window_bundle as window
from src import p1_prefix_gpu_window as gpu
from src import p1_prefix_gpu_oracle as oracle
from src import p1_mtp_off_numeric_isolation as mtp_off
from src import p1_numeric_source_trace as trace
from src import p2_numeric_minimal_candidate as minimal
from src import p2_numeric_report as report

NAME = "p2-numeric-first-divergence-candidate"
LABEL = "ai.kjlee.p2-numeric-first-divergence"
IMAGE_PREFIX = "kjlee-qwen38-p2-numeric-first-divergence"
PORT = 18080
ORIGINAL_ID = trace.ORIGINAL_ID
ORIGINAL_IMAGE = trace.ORIGINAL_IMAGE
MIN_AFTER_STOP_KIB = gpu.MIN_AFTER_STOP_KIB
WITNESS_FILE = "/tmp/p2-numeric-witness.jsonl"
MAX_TAR_BYTES = 65536
MAX_LOG_BYTES = 262144
WITNESS_LOG_TAIL = 256


class Blocked(RuntimeError):
    pass


def tag(head: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", head):
        raise Blocked("HEAD_SHA_REQUIRED")
    return IMAGE_PREFIX + ":" + head[:12]


def labels(head: str) -> dict[str, str]:
    return {LABEL: head, LABEL + ".base-id": ORIGINAL_IMAGE,
            LABEL + ".sampler-sha": minimal.PIN_SOURCE_HASHES["sampler.py"]}


def verify_image(head: str) -> dict:
    """The existing candidate image must have exact ancestry and labels."""
    base = legacy.inspect("image", legacy.IMAGE_TAG)
    child = legacy.inspect("image", tag(head))
    if base.get("Id") != ORIGINAL_IMAGE:
        raise Blocked("BASE_IMAGE_DRIFT")
    bc = base.get("Config") or {}
    cc = child.get("Config") or {}
    roots = (child.get("RootFS") or {}).get("Layers")
    original_roots = (base.get("RootFS") or {}).get("Layers")
    if (not isinstance(roots, list) or not isinstance(original_roots, list)
            or not original_roots or roots[:len(original_roots)] != original_roots
            or len(roots) != len(original_roots) + 1):
        raise Blocked("SINGLE_COPY_IMAGE_ANCESTRY_DRIFT")
    if any((cc.get("Labels") or {}).get(k) != v for k, v in labels(head).items()):
        raise Blocked("CANDIDATE_IMAGE_PROVENANCE_DRIFT")
    if any(cc.get(k) != bc.get(k) for k in ("Cmd", "Entrypoint", "User", "WorkingDir")):
        raise Blocked("CANDIDATE_IMAGE_STARTUP_DEFAULT_DRIFT")
    env = cc.get("Env") or []
    for item in ("VLLM_P2_NUMERIC_WITNESS=0", "VLLM_PLE_UNIQUE_H2D=0",
                 "VLLM_P2_DRAFT_VOCAB=", "VLLM_P2_DRAFT_VOCAB_SHA256="):
        if env.count(item) != 1:
            raise Blocked("CANDIDATE_IMAGE_OPTIN_DEFAULT_DRIFT")
    return child


def candidate_ids() -> list[str]:
    value = release._run(["docker", "ps", "-aq", "--no-trunc",
                          "--filter", "name=^/" + NAME + "$"])
    ids = value.splitlines() if value else []
    if len(ids) > 1 or any(re.fullmatch("[0-9a-f]{64}", x) is None for x in ids):
        raise Blocked("CANDIDATE_ID_AMBIGUOUS")
    return ids


def absent_candidates() -> None:
    mtp_off.no_other_candidates()  # prior P1 B/C + integrated/prefix names
    if candidate_ids():
        raise Blocked("P2_CANDIDATE_ALREADY_EXISTS")


def original_running() -> tuple[dict, dict, dict, str]:
    receipt, original, base, state = mtp_off.inspect_original("running")
    if receipt["id"] != ORIGINAL_ID or original.get("Image") != ORIGINAL_IMAGE:
        raise Blocked("ORIGINAL_PIN_MISMATCH")
    return receipt, original, base, state


def verify_minimal_stage(stage: Path) -> dict:
    """Verify exactly the DGX-created 1-COPY stage, never re-stage 4-COPY."""
    if (not stage.is_absolute() or stage.parent != Path("/tmp")
            or not stage.name.startswith(minimal.SINGLE_CANDIDATE_PREFIX)
            or not re.fullmatch(r"p2-numeric-first-divergence-[A-Za-z0-9_-]{1,64}", stage.name)
            or stage.is_symlink() or not stage.is_dir()):
        raise Blocked("MINIMAL_STAGE_DIRECTORY_INVALID")
    st = stage.stat()
    if st.st_uid != os.geteuid() or stat.S_IMODE(st.st_mode) != 0o700:
        raise Blocked("MINIMAL_STAGE_OWNER_OR_MODE_DRIFT")
    if {p.name for p in stage.iterdir()} != {"sampler.py", "Dockerfile", "receipt.json"}:
        raise Blocked("MINIMAL_STAGE_FILE_SET_DRIFT")
    expected = {"sampler.py": minimal.PIN_SOURCE_HASHES["sampler.py"],
                "Dockerfile": hashlib.sha256(minimal.numeric_only_dockerfile()).hexdigest()}
    for name in ("sampler.py", "Dockerfile", "receipt.json"):
        f = stage / name
        if f.is_symlink() or not f.is_file():
            raise Blocked("MINIMAL_STAGE_FILE_NOT_REGULAR")
        fs = f.stat()
        if (fs.st_uid != os.geteuid() or stat.S_IMODE(fs.st_mode) != 0o600
                or not 0 < fs.st_size <= minimal.MAX_BYTES):
            raise Blocked("MINIMAL_STAGE_FILE_MODE_OR_SIZE_DRIFT")
        raw = f.read_bytes()
        if len(raw) != fs.st_size:
            raise Blocked("MINIMAL_STAGE_FILE_READ_LENGTH_DRIFT")
        if name in expected and hashlib.sha256(raw).hexdigest() != expected[name]:
            raise Blocked("MINIMAL_STAGE_SOURCE_OR_RECIPE_SHA_DRIFT")
        if name == "receipt.json":
            try:
                receipt = json.loads(raw)
            except (UnicodeError, ValueError, TypeError):
                raise Blocked("MINIMAL_STAGE_RECEIPT_INVALID") from None
            if (not isinstance(receipt, dict)
                    or receipt.get("status") != "P2_MINIMAL_NUMERIC_SOURCE_PLAN_NO_GPU_AUTHORIZATION"
                    or receipt.get("sampler_sha256") != expected["sampler.py"]
                    or receipt.get("dockerfile_sha256") != expected["Dockerfile"]
                    or receipt.get("original_id_verified") is not True
                    or receipt.get("original_image_verified") is not True
                    or receipt.get("numeric_witness_default_off") is not True
                    or receipt.get("gpu_window_authorized") is not False
                    or receipt.get("image_build_authorized") is not False):
                raise Blocked("MINIMAL_STAGE_RECEIPT_MISMATCH")
    return {"minimal_stage_pinned": True, "sampler_sha256": expected["sampler.py"]}


def image_preflight(head: str, stage: Path) -> dict:
    before = trace.original_identity()
    try:
        verify_minimal_stage(stage)
        minimal.read_only_original_guard()
        absent_candidates()
        receipt, original, base, _ = original_running()
        mtp_off.args_for(head, original, base, receipt)
    finally:
        if trace.original_identity() != before:
            raise Blocked("ORIGINAL_START_TIME_CHANGED_DURING_PREFLIGHT")
    return {"status": "P2_NUMERIC_WINDOW_PREFLIGHT_READ_ONLY",
            "stage_verified": True, "original_running": True,
            "other_candidates_absent": True, "gpu_not_executed": True,
            "service_outage_performed": False}


def build(head: str, stage: Path) -> dict:
    """An image build only: pinned parent, --network=none; no GPU nor outage."""
    image_preflight(head, stage)
    original_before_build = trace.original_identity()
    try:
        old = release._inspect_image(tag(head))
    except (OSError, ValueError):
        raise Blocked("CANDIDATE_IMAGE_INSPECTION_FAILED") from None
    if old is None:
        # Validate the exact prepared 1-COPY input; original remains running.
        verify_minimal_stage(stage)
        argv = ["docker", "build", "--network=none", "--pull=false",
                "--no-cache", "--tag", tag(head)]
        for key, value in labels(head).items():
            argv += ["--label", key + "=" + value]
        argv += [str(stage)]
        release._run(argv, timeout=900)
    verify_image(head)
    original_running()
    absent_candidates()
    if trace.original_identity() != original_before_build:
        raise Blocked("ORIGINAL_START_TIME_CHANGED_DURING_IMAGE_BUILD")
    return {"status": "P2_NUMERIC_WITNESS_IMAGE_BUILT_NO_GPU",
            "image": tag(head), "same_id_original_running": True,
            "model_executed": False, "numeric_root_cause_fixed": False}


def args_for(head: str, original: dict, base: dict,
             receipt: dict, image_id: str) -> tuple[list[str], str]:
    """Reuse reviewed host/device/mount restrictions from P1 MTP-OFF candidate."""
    args, model = mtp_off.args_for(head, original, base, receipt)
    if args.count(mtp_off.TAG) != 1:
        raise Blocked("MTP_OFF_TEMPLATE_IMAGE_MISSING")
    position = args.index(mtp_off.TAG)
    cmd = args[position+1:]
    if not cmd or "--speculative-config" in cmd:
        raise Blocked("MTP_NOT_OFF")
    # Exact raw logprobs mode is needed for the pinned witness capture.
    if "--logprobs-mode" in cmd:
        i = cmd.index("--logprobs-mode")
        if i + 1 >= len(cmd) or cmd[i+1] != "raw_logprobs":
            raise Blocked("EXPLICIT_LOGPROBS_MODE_CONFLICT")
    else:
        cmd = cmd + ["--logprobs-mode", "raw_logprobs"]
    replacements = [
        (mtp_off.NAME, NAME),
        (mtp_off.LABEL + "=" + head, LABEL + "=" + head),
        (mtp_off.LABEL + ".image-id=" + ORIGINAL_IMAGE,
         LABEL + ".image-id=" + image_id),
    ]
    for old, new in replacements:
        if args.count(old) != 1:
            raise Blocked("CANDIDATE_TEMPLATE_LABEL_OR_NAME_DRIFT")
        args[args.index(old)] = new
    args[position] = tag(head)
    args = args[:position] + ["--label", LABEL + ".base-id=" + ORIGINAL_IMAGE,
                            "--env", "VLLM_P2_NUMERIC_WITNESS=1"] + [args[position]] + cmd
    if (args.count("--gpus=all") != 1 or args.count("--network=bridge") != 1
            or "--enable-prefix-caching" in args
            or args.count("--no-enable-prefix-caching") != 1
            or args.count("--speculative-config") != 0
            or args.count("VLLM_P2_NUMERIC_WITNESS=1") != 1
            or args.count("VLLM_PLE_UNIQUE_H2D=1") != 0
            or args.count("--logprobs-mode") != 1):
        raise Blocked("CANDIDATE_CLI_SCOPE_DRIFT")
    return args, model


def owned(head: str, image_id: str) -> dict:
    candidate = legacy.inspect("container", NAME)
    conf = candidate.get("Config") or {}
    hc = candidate.get("HostConfig") or {}
    labels_seen = conf.get("Labels") or {}
    original = legacy.inspect("container", legacy.NAME)
    if candidate.get("Name") != "/" + NAME or candidate.get("Image") != image_id:
        raise Blocked("FOREIGN_CANDIDATE_IMAGE_OR_NAME")
    if conf.get("Image") != tag(head):
        raise Blocked("CANDIDATE_TAG_DRIFT")
    if (labels_seen.get(LABEL) != head
            or labels_seen.get(LABEL + ".image-id") != image_id
            or labels_seen.get(LABEL + ".base-id") != ORIGINAL_IMAGE):
        raise Blocked("CANDIDATE_LABEL_OWNERSHIP_DRIFT")
    if ((hc.get("PortBindings") or {}).get("8000/tcp") !=
            [{"HostIp":"127.0.0.1", "HostPort":str(PORT)}]
            or (hc.get("RestartPolicy") or {}).get("Name") not in ("", "no")):
        raise Blocked("CANDIDATE_PORT_OR_RESTART_DRIFT")
    original_cmd = (original.get("Config") or {}).get("Cmd")
    expected_cmd = mtp_off.cmd_without_mtp(original_cmd)
    if "--logprobs-mode" not in expected_cmd:
        expected_cmd += ["--logprobs-mode", "raw_logprobs"]
    if (conf.get("Cmd") != expected_cmd
            or "VLLM_P2_NUMERIC_WITNESS=1" not in (conf.get("Env") or [])):
        raise Blocked("CANDIDATE_CMD_OR_WITNESS_DRIFT")
    return candidate


def cleanup(head: str, image_id: str, receipt: dict) -> None:
    ids = candidate_ids()
    if not ids:
        return
    ci = owned(head, image_id)
    if (ci.get("Id") != ids[0] or
            (ci.get("State") or {}).get("Status") not in ("created", "exited", "running")):
        raise Blocked("FOREIGN_CANDIDATE_ID_OR_STATE")
    b.verify_mounts(ci, receipt)
    release._run(["docker", "rm", "--force", ci["Id"]], timeout=120)
    if candidate_ids():
        raise Blocked("CANDIDATE_REMOVAL_UNCONFIRMED")


def restore(head: str, image_id: str, model: str) -> None:
    """Never restart original until this exact candidate is gone."""
    with window.recovery_signals():
        receipt, original, _, state = mtp_off.inspect_original()
        ids = candidate_ids()
        if ids:
            if state != "exited":
                raise Blocked("UNSAFE_TWO_MODELS_POSSIBLE")
            cleanup(head, image_id, receipt)
        if candidate_ids():
            raise Blocked("CANDIDATE_STILL_PRESENT_AFTER_CLEANUP")
        if state == "exited":
            b.restore_original(head, ORIGINAL_ID, model)
        window.check_original_running(model, ORIGINAL_ID)
        window.notify("P2_NUMERIC_CANDIDATE_REMOVED_ORIGINAL_SAME_ID_HTTP_PASS")


def _parse_witness_lines(lines: list[str]) -> list[dict]:
    """Parse only private opt-in diagnostic events, never raw model output."""
    if not 2 <= len(lines) <= 8:
        raise Blocked("WITNESS_EVENT_COUNT_INVALID")
    events = []
    for line in lines:
        if not line.startswith("P2_NUMERIC_WITNESS ") or len(line) > 1800:
            raise Blocked("WITNESS_EVENT_PREFIX_INVALID")
        try:
            event = json.loads(line[len("P2_NUMERIC_WITNESS "):])
        except (ValueError, TypeError):
            raise Blocked("WITNESS_EVENT_JSON_INVALID") from None
        if not isinstance(event, dict):
            raise Blocked("WITNESS_EVENT_SHAPE_INVALID")
        events.append(event)
    return events


def _witness_from_stderr(candidate_id: str) -> list[dict]:
    """Read bounded Docker log tail only when the worker-private file is absent.

    Never print the log (which can contain generated text or model details).
    Extract only complete prefixed events already emitted to fd=2 by the
    pinned Sampler witness. Missing evidence remains a blocked diagnosis.
    """
    try:
        cp = subprocess.run(["docker", "logs", "--tail", str(WITNESS_LOG_TAIL),
                             candidate_id], capture_output=True, check=False,
                            timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        raise Blocked("WITNESS_WORKER_LOG_UNAVAILABLE") from None
    if (cp.returncode != 0 or not isinstance(cp.stdout, bytes)
            or not isinstance(cp.stderr, bytes)):
        raise Blocked("WITNESS_WORKER_LOG_UNAVAILABLE")
    if len(cp.stdout) + len(cp.stderr) > MAX_LOG_BYTES:
        raise Blocked("WITNESS_WORKER_LOG_TAIL_OVERSIZE")
    raw = cp.stdout + b"\n" + cp.stderr
    if b"P2_WITNESS_FILE_WRITE_FAILED" in raw:
        raise Blocked("WITNESS_WORKER_FILE_WRITE_FAILED")
    try:
        # Limit accepted lines to exact witness prefix; ignore all other log
        # messages and never place them into errors or returned diagnostics.
        lines = [line for line in raw.decode("utf-8", errors="replace").splitlines()
                 if line.startswith("P2_NUMERIC_WITNESS ")]
    except (TypeError, ValueError):
        raise Blocked("WITNESS_WORKER_LOG_INVALID") from None
    if not lines:
        raise Blocked("WITNESS_NO_EVENTS_IN_BOUNDED_LOG_TAIL")
    return _parse_witness_lines(lines)


def read_witness(candidate_id: str) -> list[dict]:
    """Read candidate-private file first, then previously emitted stderr lines.

    The original implementation coalesced two very different errors (docker
    cp exit !=0 and tar oversize) and did not inspect witness fd=2 output.
    Both paths are strictly bounded; neither runs docker exec nor prints logs.
    """
    try:
        cp = subprocess.run(["docker", "cp", candidate_id + ":" + WITNESS_FILE, "-"],
                            capture_output=True, check=False, timeout=25)
    except (OSError, subprocess.TimeoutExpired):
        raise Blocked("WITNESS_DOCKER_CP_FAILED") from None
    if cp.returncode != 0:
        return _witness_from_stderr(candidate_id)
    if not isinstance(cp.stdout, bytes) or len(cp.stdout) > MAX_TAR_BYTES:
        raise Blocked("WITNESS_ARCHIVE_OVERSIZE_OR_NONBINARY")
    try:
        with tarfile.open(fileobj=io.BytesIO(cp.stdout), mode="r:") as tf:
            all_members = tf.getmembers()
            if len(all_members) != 1:
                raise Blocked("WITNESS_ARCHIVE_SHAPE")
            entry = all_members[0]
            if not entry.isfile() or not 0 < entry.size <= 16_384:
                raise Blocked("WITNESS_ENTRY_INVALID")
            fh = tf.extractfile(entry)
            if fh is None:
                raise Blocked("WITNESS_ENTRY_UNREADABLE")
            raw = fh.read(16_385)
        lines = raw.decode("utf-8").splitlines()
        return _parse_witness_lines(lines)
    except (tarfile.TarError, UnicodeError, ValueError, TypeError, KeyError):
        raise Blocked("WITNESS_ARCHIVE_OR_JSON_INVALID") from None



def first_token(model: str, candidate_id: str,
                image_id: str, head: str) -> dict:
    """One serial synthetic request; retain only token ID and scalar in memory."""
    original_state = mtp_off.inspect_original("exited")
    if original_state[0]["id"] != ORIGINAL_ID:
        raise Blocked("ORIGINAL_ID_CHANGED")
    ci = owned(head, image_id)
    if ci.get("Id") != candidate_id or (ci.get("State") or {}).get("Status") != "running":
        raise Blocked("CANDIDATE_NOT_RUNNING")
    payload = oracle.build_payload(model, long_prompt=True)
    payload["max_tokens"] = 1
    response = oracle.extract(oracle.request_json(PORT, payload))
    token_ids, logprobs = response.get("token_ids"), response.get("logprobs")
    if (not isinstance(token_ids, list) or len(token_ids) != 1
            or not isinstance(logprobs, list) or len(logprobs) != 1
            or type(token_ids[0]) is not int or type(logprobs[0]) not in (int, float)
            or not math.isfinite(logprobs[0])
            or response.get("finish_reason") not in ("length", "stop")):
        raise Blocked("FIRST_TOKEN_API_SHAPE_INVALID")
    ci = owned(head, image_id)
    if ci.get("Id") != candidate_id or (ci.get("State") or {}).get("Status") != "running":
        raise Blocked("CANDIDATE_DRIFT_AFTER_FIRST_TOKEN")
    return {"token_ids": token_ids, "logprobs": logprobs,
            "finish_reason": response["finish_reason"]}


def measure(head: str, image_id: str, candidate_id: str, model: str) -> dict:
    runs = [first_token(model, candidate_id, image_id, head) for _ in range(4)]
    witness = read_witness(candidate_id)
    result = report.analyze_payload({
        "runs": runs, "events": witness,
        "provenance": {
            "prefix_off_verified": True, "mtp_off_verified": True,
            "single_active_request_verified": True,
        },
    })
    return {"status": "P2_NUMERIC_FIRST_DIVERGENCE_MEASUREMENT",
            "analysis": result, "requests": len(runs),
            "strict_numeric_root_cause_resolved": False,
            "candidate_gpu_runtime_executed": True,
            "release_approved": False}


def execute(head: str, stage: Path, original_id: str,
            original_image: str) -> tuple[dict, bool]:
    if original_id != ORIGINAL_ID or original_image != ORIGINAL_IMAGE:
        raise Blocked("EXPLICIT_ORIGINAL_ID_IMAGE_CONFIRMATION_REQUIRED")
    image_preflight(head, stage)
    child = verify_image(head)
    image_id = child.get("Id")
    if not isinstance(image_id, str) or not re.fullmatch(r"sha256:[a-f0-9]{64}", image_id):
        raise Blocked("CANDIDATE_IMAGE_ID_INVALID")
    receipt, original, base, _ = original_running()
    args, model = args_for(head, original, base, receipt, image_id)
    absent_candidates()
    window.check_original_running(model, ORIGINAL_ID)
    window.notify("P2_NUMERIC_WINDOW_EXCLUSIVE_STOP_PENDING")
    result = None
    try:
        window.stop_original(head, ORIGINAL_ID)
        if gpu.available_kib() < MIN_AFTER_STOP_KIB:
            raise Blocked("MEMORY_AFTER_ORIGINAL_STOP_BELOW_SAFE_FLOOR")
        release._run(args, timeout=90)
        created = owned(head, image_id)
        if (created.get("State") or {}).get("Status") != "created":
            raise Blocked("CANDIDATE_CREATE_STATE_DRIFT")
        b.verify_mounts(created, receipt)
        mtp_off.inspect_original("exited")
        release._run(["docker", "start", created["Id"]], timeout=90)
        gpu.wait_ready(PORT, model, timeout_s=1200)
        window.notify("P2_NUMERIC_CANDIDATE_HTTP_READY")
        result = measure(head, image_id, created["Id"], model)
    finally:
        restore(head, image_id, model)
    assert result is not None
    result["original_same_id_http_restored"] = True
    window.notify("P2_NUMERIC_DIAGNOSIS", **result)
    return result, bool(result["analysis"]["provenance_verified"])


def recovery(head: str, original_id: str, original_image: str) -> None:
    if original_id != ORIGINAL_ID or original_image != ORIGINAL_IMAGE:
        raise Blocked("EXPLICIT_RECOVERY_ORIGINAL_PINS_REQUIRED")
    child = verify_image(head)
    image_id = child.get("Id")
    if not isinstance(image_id, str):
        raise Blocked("RECOVERY_IMAGE_ID_INVALID")
    receipt, original, _, _ = mtp_off.inspect_original()
    if receipt["id"] != ORIGINAL_ID:
        raise Blocked("RECOVERY_ORIGINAL_PIN_DRIFT")
    _, model = b.original_command((original.get("Config") or {}).get("Cmd"))
    restore(head, image_id, model)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--preflight", action="store_true")
    g.add_argument("--build", action="store_true")
    g.add_argument("--execute", action="store_true")
    g.add_argument("--recover", action="store_true")
    p.add_argument("--expected-head", required=True)
    p.add_argument("--stage", type=Path)
    p.add_argument("--confirm-original-id")
    p.add_argument("--confirm-original-image")
    args = p.parse_args(argv)
    try:
        os.chdir(qsa.ROOT)
        qsa.preflight(args.expected_head)
        if args.recover:
            recovery(args.expected_head, args.confirm_original_id,
                     args.confirm_original_image)
            return 0
        if args.stage is None:
            raise Blocked("EXACT_MINIMAL_STAGE_REQUIRED")
        if args.preflight:
            if args.confirm_original_id or args.confirm_original_image:
                raise Blocked("PREFLIGHT_CONFIRM_FORBIDDEN")
            receipt = image_preflight(args.expected_head, args.stage)
            window.notify("P2_NUMERIC_PREFLIGHT", result_status=receipt["status"],
                          **{k: v for k, v in receipt.items() if k != "status"})
            return 0
        if args.build:
            if args.confirm_original_id or args.confirm_original_image:
                raise Blocked("IMAGE_BUILD_CONFIRM_NOT_REQUIRED")
            receipt = build(args.expected_head, args.stage)
            window.notify("P2_NUMERIC_BUILD", result_status=receipt["status"],
                          **{k: v for k, v in receipt.items() if k != "status"})
            return 0
        signal.signal(signal.SIGTERM,
                      lambda *_: (_ for _ in ()).throw(Blocked("SIGTERM_RECOVERY_REQUESTED")))
        result, good = execute(args.expected_head, args.stage,
                               args.confirm_original_id, args.confirm_original_image)
        window.notify("P2_NUMERIC_WINDOW_COMPLETE_RELEASE_BLOCKED",
                      first_divergence_observed=good, release_approved=False)
        return 0 if good else 2
    except BaseException as exc:
        reason = str(exc) if isinstance(exc, Blocked) else "UNEXPECTED_" + type(exc).__name__.upper()
        if re.fullmatch(r"[A-Z][A-Z0-9_]{2,96}", reason) is None:
            reason = "UNCLASSIFIED_FAILURE"
        window.notify("P2_NUMERIC_WINDOW_BLOCKED_OR_INCONCLUSIVE",
                      reason=reason, original_recovery_requires_check=True,
                      strict_numeric_root_cause_resolved=False)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
