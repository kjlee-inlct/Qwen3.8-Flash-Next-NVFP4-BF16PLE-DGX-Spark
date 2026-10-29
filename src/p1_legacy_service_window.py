"""P1 ONLY: pause/stop/restore same exact YSLAB installer-owned container.

The original uninstall.sh --keep-image REMOVES the container. New Wizard uninstall/stop-only logic must not be used for the original legacy
service. P1 scripts/stop.sh and scripts/start.sh delegate to this separate
same-ID verifier. This controller never removes anything.
"""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

# Source SHA/permissions are already verified by the shell wrapper.
# This file consumes the DEPLOYMENT policy; original YSLAB receipts are
# independently verified. No container identity is selected from CLI arguments.
POLICY_PATH = Path(__file__).resolve().parents[1] / "scripts/deployment-manifest.json"


class Blocked(Exception):
    pass


def _relative(value: str) -> bool:
    if not isinstance(value, str) or not value or value.startswith("/") or "\\" in value:
        return False
    parts = value.split("/")
    return all(part not in ("", ".", "..") for part in parts) and str(PurePosixPath(value)) == value


def policy_legacy(raw: dict) -> dict:
    """Schema-check the reviewed deployment Manifest, not a CLI-selected target."""
    if not isinstance(raw, dict) or raw.get("schema_version") != 1 or raw.get("policy_id") != "kjlee-qwen38-dgx-spark-wizard":
        raise Blocked("POLICY_SCHEMA_MISMATCH")
    origin = raw.get("origin")
    if not isinstance(origin, dict) or origin.get("repo") != "kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark":
        raise Blocked("POLICY_REPOSITORY_MISMATCH")
    cfg = raw.get("legacy")
    if not isinstance(cfg, dict):
        raise Blocked("POLICY_LEGACY_MISSING")
    required = ("container", "image", "image_id", "target",
                "legacy_recipe_label", "port", "bind", "repo_relative",
                "state_relative", "cache_name")
    if any(not isinstance(cfg.get(key), str) or not cfg[key]
           for key in required if key != "port"):
        raise Blocked("POLICY_LEGACY_FIELDS_INVALID")
    if not isinstance(cfg.get("port"), int) or isinstance(cfg["port"], bool) or not 1 <= cfg["port"] <= 65535:
        raise Blocked("POLICY_PORT_INVALID")
    if (not re.fullmatch(r"sha256:[0-9a-f]{64}", cfg["image_id"]) or
            not all(_relative(cfg[name]) for name in
                    ("repo_relative", "state_relative", "cache_name")) or
            "/" in cfg["cache_name"]):
        raise Blocked("POLICY_IMAGE_OR_PATH_INVALID")
    return cfg


def load_legacy_policy() -> dict:
    if POLICY_PATH.is_symlink() or not POLICY_PATH.is_file() or POLICY_PATH.stat().st_size > 65536:
        raise Blocked("POLICY_FILE_UNAVAILABLE")
    try:
        raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        raise Blocked("POLICY_FILE_UNREADABLE") from None
    return policy_legacy(raw)


LEGACY = load_legacy_policy()
NAME = LEGACY["container"]
IMAGE_TAG = LEGACY["image"]
IMAGE_ID = LEGACY["image_id"]
TARGET = LEGACY["target"]
RECIPE = LEGACY["legacy_recipe_label"]


def state_receipt(home: Path) -> dict:
    base = home / LEGACY["state_relative"]
    if not base.is_dir() or base.is_symlink():
        raise Blocked("STATE_UNAVAILABLE")
    files = {}
    for key in ("paths", "container-id", "image-id"):
        p = base / key
        if p.is_symlink() or not p.is_file():
            raise Blocked("RECEIPT_UNAVAILABLE")
        try:
            files[key] = p.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError):
            raise Blocked("RECEIPT_UNREADABLE") from None
    expected_repo = home / LEGACY["repo_relative"]
    expected_cache = expected_repo / LEGACY["cache_name"]
    expected_views = expected_repo / "recipe-views"
    if files["paths"].splitlines() != [str(expected_repo), str(expected_cache)]:
        raise Blocked("RECORDED_PATHS_MISMATCH")
    for p in (expected_repo, expected_cache, expected_views):
        if p.is_symlink() or not p.is_dir():
            raise Blocked("RECORDED_MOUNTS_UNAVAILABLE")
    if not re.fullmatch(r"[0-9a-f]{64}", files["container-id"]):
        raise Blocked("RECORDED_CONTAINER_ID_INVALID")
    if files["image-id"] != IMAGE_ID:
        raise Blocked("RECORDED_IMAGE_ID_MISMATCH")
    return {"id": files["container-id"], "cache": str(expected_cache),
            "views": str(expected_views)}


def verify_identity(container: dict, image: dict, receipt: dict) -> str:
    if container.get("Id") != receipt["id"] or container.get("Name") != "/" + NAME:
        raise Blocked("CONTAINER_ID_OR_NAME_MISMATCH")
    if container.get("Image") != IMAGE_ID or image.get("Id") != IMAGE_ID:
        raise Blocked("IMAGE_ID_MISMATCH")
    config = container.get("Config") or {}
    if config.get("Image") != IMAGE_TAG:
        raise Blocked("IMAGE_TAG_MISMATCH")
    labels = config.get("Labels") or {}
    if labels.get("ai.yslab.recipe") != RECIPE or labels.get("ai.yslab.target") != TARGET:
        raise Blocked("TARGET_LABEL_MISMATCH")
    host = container.get("HostConfig") or {}
    if (host.get("RestartPolicy") or {}).get("Name", "no") not in ("no", ""):
        raise Blocked("RESTART_POLICY_MISMATCH")
    port = (host.get("PortBindings") or {}).get(str(LEGACY["port"]) + "/tcp")
    if port != [{"HostIp": LEGACY["bind"], "HostPort": str(LEGACY["port"])}]:
        raise Blocked("PORT_8000_BINDING_MISMATCH")
    mounts = {(m.get("Source"), m.get("Destination"))
              for m in container.get("Mounts") or [] if m.get("Type") == "bind"}
    if not {(receipt["cache"], "/recipe/hf-cache"),
            (receipt["views"], "/recipe/recipe-views")}.issubset(mounts):
        raise Blocked("MODEL_MOUNT_BINDINGS_MISMATCH")
    state = container.get("State") or {}
    status = state.get("Status")
    running = state.get("Running")
    paused = state.get("Paused")
    if (status, running, paused) not in (
        ("running", True, False),
        ("paused", True, True),
        ("exited", False, False),
    ):
        raise Blocked("AMBIGUOUS_DOCKER_STATE")
    return status


def inspect(kind: str, target: str) -> dict:
    subcommand = "container" if kind == "container" else "image"
    try:
        p = subprocess.run(["docker", subcommand, "inspect", target],
                           capture_output=True, text=True, check=True, timeout=20)
        data = json.loads(p.stdout)
    except (OSError, ValueError, subprocess.CalledProcessError,
            subprocess.TimeoutExpired):
        raise Blocked("DOCKER_INSPECT_FAILED") from None
    if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
        raise Blocked("DOCKER_INSPECT_AMBIGUOUS")
    return data[0]


def run(args: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", choices=("preflight", "pause", "stop", "start"), required=True)
    parser.add_argument("--confirm-id")
    parser.add_argument("--execute", action="store_true")
    a = parser.parse_args(args)
    try:
        if os.geteuid() == 0:
            raise Blocked("ROOT_FORBIDDEN")
        if a.action == "preflight":
            if a.confirm_id is not None or a.execute:
                raise Blocked("READ_ONLY_PREFLIGHT_ARGUMENTS_INVALID")
        elif not a.execute or a.confirm_id is None:
            raise Blocked("EXPLICIT_CONFIRMATION_REQUIRED")
        receipt = state_receipt(Path.home())
        if a.action != "preflight" and a.confirm_id != receipt["id"]:
            raise Blocked("CONFIRMED_ID_MISMATCH")
        status = verify_identity(inspect("container", NAME),
                                 inspect("image", IMAGE_TAG), receipt)
        if a.action == "preflight":
            print("P1_LEGACY_WINDOW_PREFLIGHT_PASS_" + status.upper())
            return 0
        if a.action == "pause" and status != "running":
            raise Blocked("PAUSE_REQUIRES_RUNNING")
        if a.action == "stop" and status != "running":
            raise Blocked("STOP_REQUIRES_RUNNING")
        if a.action == "start" and status == "running":
            # Idempotent start: successful no-op only AFTER all ownership,
            # manifest, image, mount and running-state checks above pass.
            # Do not call Docker start or claim API readiness.
            print("P1_LEGACY_ALREADY_RUNNING_NOOP_SAME_ID_HEALTH_NOT_CHECKED")
            return 0
        if a.action == "pause":
            command = ["docker", "pause", receipt["id"]]
            expected, marker = ("paused", "PAUSED_SAME_ID_GPU_MEMORY_NOT_RELEASED")
        elif a.action == "stop":
            command = ["docker", "stop", "--time", "30", receipt["id"]]
            expected, marker = ("exited", "STOPPED_SAME_ID_NO_REMOVAL")
        elif status == "paused":
            command = ["docker", "unpause", receipt["id"]]
            expected, marker = ("running", "UNPAUSED_SAME_ID_HEALTH_NOT_YET_CHECKED")
        elif status == "exited":
            command = ["docker", "start", receipt["id"]]
            expected, marker = ("running", "RESTARTED_SAME_ID_HEALTH_NOT_YET_CHECKED")
        else:
            raise Blocked("UNKNOWN_START_STATE")
        try:
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=90)
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            raise Blocked("DOCKER_STATE_CHANGE_FAILED") from None
        now = verify_identity(inspect("container", NAME),
                              inspect("image", IMAGE_TAG), receipt)
        if now != expected:
            raise Blocked("POST_ACTION_STATE_MISMATCH")
        print("P1_LEGACY_" + marker)
        return 0
    except Blocked as exc:
        print("P1_LEGACY_WINDOW_BLOCKED_" + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(run())
