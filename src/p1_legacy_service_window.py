"""P1 ONLY: stop/restart the same exact YSLAB installer-owned container.

The original uninstall.sh --keep-image REMOVES the container. New Wizard
scripts/stop.sh cannot manage the original legacy service. Both are unsuitable
for a reversible maintenance window. This controller never removes anything.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

NAME = "qwen38-flash-orca-uncensored-bf16-mtp"
IMAGE_TAG = "yslab-qwen38-bf16ple:9492b78c"
IMAGE_ID = "sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a"
TARGET = "orca-uncensored-bf16-mtp"
RECIPE = "qwen38-flash-next-bf16-ple"


class Blocked(Exception):
    pass


def state_receipt(home: Path) -> dict:
    base = home / ".local/state/yslab-qwen38-bf16ple"
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
    expected_repo = home / "Workspace/llm/yslab-qwen38-bf16ple-dgx-spark"
    expected_cache = expected_repo / "hf-cache"
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


def verify_identity(container: dict, image: dict, receipt: dict) -> bool:
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
    port = (host.get("PortBindings") or {}).get("8000/tcp")
    if port != [{"HostIp": "0.0.0.0", "HostPort": "8000"}]:
        raise Blocked("PORT_8000_BINDING_MISMATCH")
    mounts = {(m.get("Source"), m.get("Destination"))
              for m in container.get("Mounts") or [] if m.get("Type") == "bind"}
    if not {(receipt["cache"], "/recipe/hf-cache"),
            (receipt["views"], "/recipe/recipe-views")}.issubset(mounts):
        raise Blocked("MODEL_MOUNT_BINDINGS_MISMATCH")
    state = container.get("State") or {}
    status = (state.get("Status"), state.get("Running"))
    if status not in (("running", True), ("exited", False)):
        raise Blocked("AMBIGUOUS_DOCKER_STATE")
    return status[1]


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
    parser.add_argument("--action", choices=("preflight", "stop", "start"), required=True)
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
        running = verify_identity(inspect("container", NAME),
                                  inspect("image", IMAGE_TAG), receipt)
        if a.action == "preflight":
            print("P1_LEGACY_WINDOW_PREFLIGHT_PASS_" +
                  ("RUNNING" if running else "STOPPED"))
            return 0
        if a.action == "stop" and not running:
            raise Blocked("SERVICE_NOT_RUNNING")
        if a.action == "start" and running:
            raise Blocked("SERVICE_ALREADY_RUNNING")
        command = (["docker", "stop", "--time", "30", receipt["id"]]
                   if a.action == "stop" else ["docker", "start", receipt["id"]])
        try:
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=90)
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            raise Blocked("DOCKER_STATE_CHANGE_FAILED") from None
        after = verify_identity(inspect("container", NAME),
                                inspect("image", IMAGE_TAG), receipt)
        if after != (a.action == "start"):
            raise Blocked("POST_ACTION_STATE_MISMATCH")
        print("P1_LEGACY_" +
              ("STOPPED_SAME_ID_NO_REMOVAL" if a.action == "stop" else
               "RESTARTED_SAME_ID_HEALTH_NOT_YET_CHECKED"))
        return 0
    except Blocked as exc:
        print("P1_LEGACY_WINDOW_BLOCKED_" + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(run())
