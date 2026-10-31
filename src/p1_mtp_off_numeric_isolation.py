"""P1 C-arm: stock original image, Prefix OFF, MTP disabled; strict A/C diagnosis.

This is a *new* maintenance window controller, not covered by a past GPU
approval. Preflight reads metadata only. Execute requires separately approved
service interruption and exact original full ID. No image builds/patches.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import signal
import sys

from src import p1_legacy_service_window as legacy
from src import p1_prefix_release as release
from src import p1_prefix_gpu_window as gpu
from src import p1_preview_qsa_exact_topk as qsa
from src import p1_original_numeric_baseline as baseline
from src import p1_qsa_only_runtime as b
from src import p1_qsa_window_bundle as window
from src import p1_prefix_gpu_oracle as oracle

NAME = "p1-mtp-off-candidate"
LABEL = "ai.kjlee.p1-mtp-off-runtime"
PORT = 18080
PIN_ORIGINAL_ID = window.ORIGINAL_ID
PIN_IMAGE_ID = legacy.IMAGE_ID
TAG = legacy.IMAGE_TAG


class Blocked(Exception):
    pass


def cmd_without_mtp(original: list[str]) -> list[str]:
    """Remove precisely one --speculative-config pair. Everything else unchanged."""
    b.original_command(original)  # exact Prefix-OFF + MTP2 original contract
    if original.count("--speculative-config") != 1 or any(
            v.startswith("--speculative-config=") for v in original):
        raise Blocked("MTP_FLAG_AMBIGUOUS")
    index = original.index("--speculative-config")
    if index + 1 >= len(original):
        raise Blocked("MTP_VALUE_MISSING")
    updated = original[:index] + original[index + 2:]
    if (len(updated) != len(original) - 2 or
            any("speculative" in value for value in updated) or
            updated.count("--no-enable-prefix-caching") != 1):
        raise Blocked("MTP_OR_PREFIX_CMD_DRIFT")
    return updated


def inspect_original(required: str | None = None) -> tuple[dict, dict, dict, str]:
    receipt, original, base, state = b.original_state(required)
    if receipt["id"] != PIN_ORIGINAL_ID or original.get("Id") != PIN_ORIGINAL_ID:
        raise Blocked("ORIGINAL_FULL_ID_MISMATCH")
    if original.get("Image") != PIN_IMAGE_ID or base.get("Id") != PIN_IMAGE_ID:
        raise Blocked("ORIGINAL_IMAGE_MISMATCH")
    return receipt, original, base, state


def ids() -> list[str]:
    out = release._run(["docker", "ps", "-aq", "--no-trunc",
                        "--filter", "name=^/" + NAME + "$"])
    value = out.splitlines() if out else []
    if len(value) > 1 or any(re.fullmatch("[0-9a-f]{64}", x) is None for x in value):
        raise Blocked("CANDIDATE_ID_AMBIGUOUS")
    return value


def no_other_candidates() -> None:
    b.no_other_candidates()
    if ids():
        raise Blocked("C_CANDIDATE_ALREADY_EXISTS")


def args_for(head: str, original: dict, base: dict,
             receipt: dict) -> tuple[list[str], str]:
    """Reuse B's reviewed resource isolation; change only image, labels, MTP."""
    args, model = b.container_args(head, original, base, receipt)
    original_cmd = (original.get("Config") or {}).get("Cmd")
    if not isinstance(original_cmd, list) or args[-len(original_cmd):] != original_cmd:
        raise Blocked("ORIGINAL_CMD_NOT_AT_TAIL")
    # Labels/image/name are administrative isolation, not model parameters.
    if args.count(b.PIN_TAG) != 1:
        raise Blocked("B_IMAGE_MARKER_MISSING")
    image_pos = args.index(b.PIN_TAG)
    if args[image_pos + 1:] != original_cmd:
        raise Blocked("ORIGINAL_CMD_TAIL_DRIFT")
    for old, new in (
        (b.NAME, NAME),
        (b.LABEL + "=" + head, LABEL + "=" + head),
        (b.LABEL + ".image-id=" + b.PIN_IMAGE_ID,
         LABEL + ".image-id=" + PIN_IMAGE_ID),
    ):
        if args.count(old) != 1:
            raise Blocked("C_TEMPLATE_MARKER_MISSING")
        args[args.index(old)] = new
    args[image_pos] = TAG
    args = args[:image_pos + 1] + cmd_without_mtp(original_cmd)
    if (TAG not in args or b.PIN_TAG in args or
            "--speculative-config" in args or
            args.count("--no-enable-prefix-caching") != 1 or
            "--enable-prefix-caching" in args or
            any("VLLM_QSA_EXACT_TOPK=1" in arg for arg in args)):
        raise Blocked("C_NOT_STOCK_PREFIX_OFF_MTP_OFF")
    return args, model


def owned(head: str) -> dict:
    ci = legacy.inspect("container", NAME)
    conf = ci.get("Config") or {}
    hc = ci.get("HostConfig") or {}
    labels = conf.get("Labels") or {}
    original_conf = (legacy.inspect("container", legacy.NAME).get("Config") or {})
    expected_cmd = cmd_without_mtp(original_conf.get("Cmd"))
    if (ci.get("Name") != "/" + NAME or ci.get("Image") != PIN_IMAGE_ID
            or conf.get("Image") != TAG
            or conf.get("Cmd") != expected_cmd
            or labels.get(LABEL) != head
            or labels.get(LABEL + ".image-id") != PIN_IMAGE_ID
            or (hc.get("RestartPolicy") or {}).get("Name") not in ("", "no")
            or (hc.get("PortBindings") or {}).get("8000/tcp") !=
            [{"HostIp": "127.0.0.1", "HostPort": str(PORT)}]):
        raise Blocked("FOREIGN_CANDIDATE_OR_PORT_DRIFT")
    return ci


def guarded_cleanup(head: str, receipt: dict) -> None:
    current_ids = ids()
    if not current_ids:
        return
    ci = owned(head)
    if ci.get("Id") != current_ids[0] or (
            ci.get("State") or {}).get("Status") not in ("created", "running", "exited"):
        raise Blocked("CANDIDATE_ID_OR_STATE_DRIFT")
    b.verify_mounts(ci, receipt)
    release._run(["docker", "rm", "--force", current_ids[0]], timeout=120)
    if ids():
        raise Blocked("CANDIDATE_REMOVAL_UNCONFIRMED")


def restore(head: str, model: str) -> None:
    # Called under a finally, even when docker create/start or inference fails.
    with window.recovery_signals():
        receipt, _, _, state = inspect_original()
        if ids():
            if state != "exited":
                raise Blocked("TWO_GPU_MODELS_POSSIBLE_FAIL_CLOSED")
            guarded_cleanup(head, receipt)
        if state == "exited":
            if ids():
                raise Blocked("CANDIDATE_STILL_PRESENT")
            b.restore_original(head, PIN_ORIGINAL_ID, model)
        if ids():
            raise Blocked("CANDIDATE_STILL_PRESENT_AFTER_RESTORE")
        window.check_original_running(model, PIN_ORIGINAL_ID)
        window.notify("C_REMOVED_ORIGINAL_SAME_ID_HTTP_PASS")


def preflight(head: str) -> dict:
    receipt, original, base, state = inspect_original("running")
    no_other_candidates()
    args, model = args_for(head, original, base, receipt)
    if TAG not in args:
        raise Blocked("BASE_IMAGE_TAG_NOT_IN_CREATE")
    return {"status": "C_MTP_OFF_PREFLIGHT_NO_GPU_NO_MUTATION",
            "original_state": state, "original_id": receipt["id"],
            "candidate_image_id": PIN_IMAGE_ID, "mtp": "OFF",
            "prefix": "OFF", "qsa": "stock", "model": model,
            "port": PORT, "p1_final_pass": False}


def guard(head: str, candidate_id: str, receipt: dict) -> None:
    inspect_original("exited")
    ci = owned(head)
    if (ci.get("Id") != candidate_id or
            (ci.get("State") or {}).get("Status") != "running"):
        raise Blocked("CANDIDATE_NOT_RUNNING_SAME_ID")
    b.verify_mounts(ci, receipt)


def measurement(a_runs: list[dict], c_runs: list[dict], prompt_sha: str,
                spec_accepted_delta: float) -> dict:
    a = baseline.compare(a_runs)
    c = baseline.compare(c_runs)
    c["status"] = c["status"].replace("ORIGINAL_PREFIX_OFF",
                                     "MTP_OFF_STOCK_PREFIX_OFF")
    for key in ("original_qsa", "original_prefix_caching",
                "original_mtp_speculative_tokens",
                "original_reproducible_at_strict", "p1_candidate_numeric_pass"):
        c.pop(key, None)
    c["qsa"] = "stock"
    c["prefix_caching"] = "OFF"
    c["mtp_speculative_tokens"] = 0
    c["numeric_reproducible_at_strict"] = (
        c["status"] == "MTP_OFF_STOCK_PREFIX_OFF_NUMERIC_WITHIN_STRICT")
    complete = a["status"] in (
        "ORIGINAL_PREFIX_OFF_NUMERIC_WITHIN_STRICT",
        "ORIGINAL_PREFIX_OFF_NUMERIC_ABOVE_STRICT") and c["status"] in (
        "MTP_OFF_STOCK_PREFIX_OFF_NUMERIC_WITHIN_STRICT",
        "MTP_OFF_STOCK_PREFIX_OFF_NUMERIC_ABOVE_STRICT")
    same = complete and all(
        x["token_ids"] == y["token_ids"] and
        x["finish_reason"] == y["finish_reason"]
        for x, y in zip(a_runs, c_runs))
    return {
        "status": "AC_MTP_ISOLATION_MEASURED" if complete else "AC_INCONCLUSIVE",
        "A_MTP2": a, "C_MTP_OFF": c,
        "cross_arm_identical_token_ids_and_finish": same,
        "mtp_off_accepted_draft_token_delta": spec_accepted_delta,
        "mtp_off_runtime_counter_zero": spec_accepted_delta == 0,
        "synthetic_prompt_sha256": prompt_sha,
        "strict_abs_tolerance": baseline.STRICT_ABS,
        "causal_mtp_conclusion": "NOT_PROVEN",
        "p1_final_pass": False,
    }


def execute(head: str) -> tuple[dict, bool]:
    qsa.preflight(head)
    receipt, original, base, _ = inspect_original("running")
    args, model = args_for(head, original, base, receipt)
    no_other_candidates()
    window.check_original_running(model, PIN_ORIGINAL_ID)
    payload = oracle.build_payload(model, long_prompt=True)
    prompt_sha = hashlib.sha256(json.dumps(payload["messages"], ensure_ascii=True,
                                    sort_keys=True).encode()).hexdigest()
    window.notify("A_STOCK_MTP2_NUMERIC_STARTED")
    a_runs = window.collect(8000, payload,
                            lambda: window.check_original_running_id_only(PIN_ORIGINAL_ID))
    a_report = baseline.compare(a_runs)
    if a_report["status"] not in (
            "ORIGINAL_PREFIX_OFF_NUMERIC_WITHIN_STRICT",
            "ORIGINAL_PREFIX_OFF_NUMERIC_ABOVE_STRICT"):
        raise Blocked("A_INCOMPLETE_NO_SERVICE_STOP")
    window.check_original_running(model, PIN_ORIGINAL_ID)
    window.notify("A_STOCK_MTP2_COMPLETED",
                  all_pairs_max_abs_delta=a_report["all_pairs_max_abs_delta"])
    # Re-inspect state and re-derive pinned launch args before stop.
    preflight(head)
    window.notify("C_MTP_OFF_SERVICE_WINDOW_STOP_ATTEMPT")
    try:
        window.stop_original(head, PIN_ORIGINAL_ID)
        release._run(args, timeout=90)
        ci = owned(head)
        if (ci.get("State") or {}).get("Status") != "created":
            raise Blocked("CANDIDATE_CREATE_STATE_DRIFT")
        b.verify_mounts(ci, receipt)
        inspect_original("exited")
        release._run(["docker", "start", ci["Id"]], timeout=90)
        gpu.wait_ready(PORT, model, timeout_s=1200)
        window.notify("C_GPU_READY", candidate_id=ci["Id"])
        before = oracle.metrics(PORT)
        c_runs = window.collect(PORT, payload,
                                lambda: guard(head, ci["Id"], receipt))
        after = oracle.metrics(PORT)
        accepted_delta = oracle.counter_delta(
            before, after, "spec_decode_num_accepted_tokens_total")
        result = measurement(a_runs, c_runs, prompt_sha, accepted_delta)
    finally:
        restore(head, model)
    result["original_same_id_http_restored"] = True
    window.notify("AC_MEASUREMENT", report=result)
    return result, (result["status"] == "AC_MTP_ISOLATION_MEASURED" and
                    result["C_MTP_OFF"]["numeric_reproducible_at_strict"] is True and
                    result["mtp_off_runtime_counter_zero"] is True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--confirm-original-id")
    parser.add_argument("--confirm-image-id")
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--preflight", action="store_true")
    actions.add_argument("--execute", action="store_true")
    opts = parser.parse_args()
    try:
        os.chdir(qsa.ROOT)
        qsa.preflight(opts.expected_head)
        if opts.preflight:
            if opts.confirm_original_id or opts.confirm_image_id:
                raise Blocked("PREFLIGHT_MUST_BE_UNCONFIRMED")
            window.notify("C_PREFLIGHT", result=preflight(opts.expected_head))
            return 0
        if (opts.confirm_original_id != PIN_ORIGINAL_ID or
                opts.confirm_image_id != PIN_IMAGE_ID):
            raise Blocked("EXACT_ORIGINAL_AND_IMAGE_CONFIRMATION_REQUIRED")
        signal.signal(signal.SIGTERM,
                      lambda *_: (_ for _ in ()).throw(
                          Blocked("SIGTERM_RECOVERY_REQUIRED")))
        _, good = execute(opts.expected_head)
        window.notify("AC_WINDOW_COMPLETE_P1_NOT_PROVEN", p1_final_pass=False)
        return 0 if good else 2
    except BaseException as exc:
        reason = str(exc) if isinstance(exc, Blocked) else type(exc).__name__
        window.notify("C_WINDOW_STOPPED_OR_INCONCLUSIVE_CHECK_RESTORE_MARKER",
                      reason=reason, p1_final_pass=False)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
