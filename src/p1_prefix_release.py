"""P1 Prefix ON local release image and isolated service lifecycle.

Build is CPU-only and uses a pinned local image plus exact SHA-pinned Stage
sources. Release image does NOT include candidate-only diagnostic observers.
Launch NEVER stops production: it requires the original same-ID container
ALREADY exited via the separately authorized P1 service window.
Stop removes ONLY this label-owned release container and restores same-ID
original via the existing P1 script. Does not change port 8000 routing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

from src import p1_legacy_service_window as legacy
from src import p1_prefix_gpu_window as gpu

REPO = Path(__file__).resolve().parents[1]
RELEASE_NAME = "p1-prefix-release"
RELEASE_PORT = 18080
RELEASE_LABEL = "ai.kjlee.p1-prefix-release"
RELEASE_BASE = legacy.IMAGE_TAG
RELEASE_IMAGE_PREFIX = "kjlee-qwen38-p1-prefix"
PINNED_ROOT_SUFFIXES = (
    "/v1/worker/gpu/model_states/mamba_hybrid.py",
    "/v1/core/sched/scheduler.py",
)


class ReleaseBlocked(Exception):
    pass


def release_tag(head: str) -> str:
    if not isinstance(head, str) or not re.fullmatch(r"[0-9a-f]{40}", head):
        raise ReleaseBlocked("INVALID_HEAD")
    return RELEASE_IMAGE_PREFIX + ":" + head[:12]


def dockerfile_for(root: str) -> str:
    """Only two COPY ops, no RUN, no network, no model or observer payload."""
    if not isinstance(root, str) or not re.fullmatch(
            r"/(?:[A-Za-z0-9_.+-]+/)+vllm", root):
        raise ReleaseBlocked("VLLM_ROOT_INVALID")
    return (
        f"FROM {RELEASE_BASE}\n"
        "COPY --chown=0:0 --chmod=0644 mamba_hybrid.py "
        f"{root}{PINNED_ROOT_SUFFIXES[0]}\n"
        "COPY --chown=0:0 --chmod=0644 scheduler.py "
        f"{root}{PINNED_ROOT_SUFFIXES[1]}\n"
    )


def _run(args: list[str], *, timeout: int = 120, input_data=None) -> str:
    try:
        cp = subprocess.run(args, input=input_data, capture_output=True,
                            text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        raise ReleaseBlocked("DOCKER_COMMAND_UNAVAILABLE") from None
    if cp.returncode:
        code = args[1].upper() if args[0] == "docker" and args[1] in (
            "build", "start", "create", "rm", "ps") else "SERVICE_SCRIPT"
        raise ReleaseBlocked("RELEASE_COMMAND_FAILED_" + code)
    return cp.stdout.strip()


def _inspect_image(tag: str) -> dict | None:
    try:
        cp = subprocess.run(["docker", "image", "inspect", tag],
                            text=True, capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        raise ReleaseBlocked("IMAGE_INSPECT_UNAVAILABLE") from None
    if cp.returncode:
        if "No such image" in cp.stderr:
            return None
        raise ReleaseBlocked("IMAGE_INSPECT_FAILED")
    try:
        data = json.loads(cp.stdout)
    except ValueError:
        raise ReleaseBlocked("IMAGE_INSPECT_INVALID") from None
    if not isinstance(data, list) or len(data) != 1:
        raise ReleaseBlocked("IMAGE_INSPECT_SHAPE")
    return data[0]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _source_bytes() -> dict[str, bytes]:
    gpu.verify_stage()
    sources = {}
    for name, (_, expected) in gpu.PATCHES.items():
        file = gpu.STAGE / name
        if file.is_symlink() or not file.is_file():
            raise ReleaseBlocked("STAGE_SOURCE_INVALID")
        data = file.read_bytes()
        if _sha(data) != expected:
            raise ReleaseBlocked("STAGE_SOURCE_SHA_DRIFT")
        sources[name] = data
    return sources


def _labels(head: str, root: str) -> dict[str, str]:
    return {
        RELEASE_LABEL: head,
        "ai.kjlee.p1-prefix.base": gpu.IMAGE,
        "ai.kjlee.p1-prefix.mamba": gpu.PATCHES["mamba_hybrid.py"][1],
        "ai.kjlee.p1-prefix.scheduler": gpu.PATCHES["scheduler.py"][1],
        "ai.kjlee.p1-prefix.vllm-root": root,
        "ai.kjlee.p1-prefix.observer": "absent",
        "ai.kjlee.p1-prefix.mode": "prefix-on-mtp2",
    }


def check_image(image: dict, head: str, *, root: str | None = None) -> dict:
    """Check release provenance and full original layer ancestry."""
    if not isinstance(image, dict) or not re.fullmatch(
            r"sha256:[a-f0-9]{64}", image.get("Id", "")):
        raise ReleaseBlocked("RELEASE_IMAGE_ID_INVALID")
    base = _inspect_image(RELEASE_BASE)
    if not isinstance(base, dict) or base.get("Id") != gpu.IMAGE:
        raise ReleaseBlocked("PINNED_BASE_IMAGE_CHANGED")
    layers = (image.get("RootFS") or {}).get("Layers")
    base_layers = (base.get("RootFS") or {}).get("Layers")
    if (not isinstance(layers, list) or not isinstance(base_layers, list)
            or not base_layers or len(layers) != len(base_layers) + 2
            or layers[:len(base_layers)] != base_layers):
        raise ReleaseBlocked("RELEASE_IMAGE_PARENT_LAYERS_DRIFT")
    labels = (image.get("Config") or {}).get("Labels") or {}
    if root is None:
        root = labels.get("ai.kjlee.p1-prefix.vllm-root")
    dockerfile_for(root)
    if any(labels.get(k) != v for k, v in _labels(head, root).items()):
        raise ReleaseBlocked("RELEASE_IMAGE_PROVENANCE_MISMATCH")
    return {"image_id": image["Id"], "vllm_root": root,
            "base_image_id": gpu.IMAGE, "head": head}


def _owner_inspect(head: str, image_id: str) -> dict:
    ci = legacy.inspect("container", RELEASE_NAME)
    conf = ci.get("Config") or {}
    labels = conf.get("Labels") or {}
    if (ci.get("Name") != "/" + RELEASE_NAME or ci.get("Image") != image_id
            or labels.get(RELEASE_LABEL) != head
            or (ci.get("HostConfig") or {}).get("RestartPolicy", {}).get("Name")
            not in ("no", "")):
        raise ReleaseBlocked("RELEASE_CONTAINER_OWNERSHIP_MISMATCH")
    return ci


def _no_release_container() -> None:
    # Never confuse a Docker daemon failure with "container not found".
    ids = _run(["docker", "ps", "-aq", "--no-trunc",
                "--filter", f"name=^/{RELEASE_NAME}$"])
    if ids:
        raise ReleaseBlocked("RELEASE_CONTAINER_ALREADY_EXISTS")


def build(head: str) -> dict:
    """Create a persistent local Prefix ON image WITHOUT running a GPU model."""
    receipt, ci, _, cmd, _, _ = gpu.preflight()
    if (ci.get("State") or {}).get("Status") != "running":
        raise ReleaseBlocked("BUILD_REQUIRES_ORIGINAL_RUNNING")
    root = gpu.probe_vllm_root((ci.get("Config") or {}).get("User") or "")
    source = _source_bytes()
    tag = release_tag(head)
    existing = _inspect_image(tag)
    if existing is not None:
        result = check_image(existing, head, root=root)
        return dict(result, status="RELEASE_ALREADY_BUILT_NO_GPU", image=tag)
    # Ensure the original model/image configuration is not disturbed by a
    # local Docker build. Only two small pinned Stage code files are staged.
    original_id = ci["Id"]
    with tempfile.TemporaryDirectory(prefix="p1-prefix-release-") as td:
        context = Path(td)
        context.chmod(0o700)
        for name, data in source.items():
            out = context / name
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            with os.fdopen(os.open(out, flags, 0o600), "wb") as f:
                f.write(data)
        dockerfile = dockerfile_for(root)
        (context / "Dockerfile").write_text(dockerfile, encoding="utf-8")
        args = ["docker", "build", "--network=none", "--pull=false",
                "--no-cache", "--tag", tag]
        for key, value in _labels(head, root).items():
            args += ["--label", key + "=" + value]
        args.append(str(context))
        _run(args, timeout=900)
    result = _inspect_image(tag)
    if result is None:
        raise ReleaseBlocked("BUILD_IMAGE_NOT_PRESENT")
    verified = check_image(result, head, root=root)
    after = legacy.inspect("container", legacy.NAME)
    if after.get("Id") != original_id or (
            after.get("State") or {}).get("Status") != "running":
        raise ReleaseBlocked("LEGACY_CHANGED_DURING_BUILD")
    return dict(verified, status="PREFIX_ON_RELEASE_IMAGE_BUILT_CPU_ONLY",
                image=tag)


def _legacy_state_for_release() -> tuple[dict, dict, dict, str]:
    receipt = legacy.state_receipt(Path.home())
    ci = legacy.inspect("container", legacy.NAME)
    base = legacy.inspect("image", RELEASE_BASE)
    state = legacy.verify_identity(ci, base, receipt)
    if ci.get("Image") != gpu.IMAGE or base.get("Id") != gpu.IMAGE:
        raise ReleaseBlocked("ORIGINAL_IMAGE_DRIFT")
    return receipt, ci, base, state


def _release_image(head: str) -> dict:
    tag = release_tag(head)
    image = _inspect_image(tag)
    if image is None:
        raise ReleaseBlocked("RELEASE_IMAGE_NOT_BUILT")
    check_image(image, head)
    return image


def launch(head: str, confirm_id: str) -> dict:
    """Launch only after operator has STOPPED original via P1 stop.sh.

    Never stops original here, never binds port 8000 and never edits weights.
    """
    receipt, ci, base, state = _legacy_state_for_release()
    if confirm_id != receipt["id"]:
        raise ReleaseBlocked("ORIGINAL_RECEIPT_CONFIRMATION_MISMATCH")
    if state != "exited":
        raise ReleaseBlocked("ORIGINAL_MUST_ALREADY_BE_STOPPED")
    _no_release_container()
    if gpu.candidate_ids():
        raise ReleaseBlocked("DEBUG_CANDIDATE_STILL_EXISTS")
    image = _release_image(head)
    cmd, model = gpu.candidate_cmd((ci.get("Config") or {}).get("Cmd"))
    env = gpu.environment_delta(ci.get("Config") or {}, base.get("Config") or {})
    run_args = ["docker", "create", "--name", RELEASE_NAME, "--pull=never",
                "--label", RELEASE_LABEL + "=" + head,
                "--network=bridge", f"--publish=127.0.0.1:{RELEASE_PORT}:8000",
                "--gpus=all", "--ipc=host",
                "--memory=112g", "--memory-swap=112g", "--pids-limit=1024",
                "--restart=no", "--security-opt=no-new-privileges"]
    runtime = (ci.get("HostConfig") or {}).get("Runtime") or ""
    user = (ci.get("Config") or {}).get("User") or ""
    workdir = (ci.get("Config") or {}).get("WorkingDir") or ""
    if runtime:
        run_args += ["--runtime=" + runtime]
    if user:
        run_args += ["--user", user]
    if workdir:
        run_args += ["--workdir", workdir]
    for source, dest in ((receipt["cache"], "/recipe/hf-cache"),
                         (receipt["views"], "/recipe/recipe-views")):
        run_args += ["--mount", f"type=bind,src={source},dst={dest},readonly"]
    for value in env:
        run_args += ["--env", value]
    run_args += ["--env", "HF_HUB_OFFLINE=1", "--env", "TRANSFORMERS_OFFLINE=1",
                 "--env", "PYTHONDONTWRITEBYTECODE=1",
                 release_tag(head), *cmd]
    # Release image contains no diagnostic observer or snapshot instrumentation.
    created = False
    try:
        _run(run_args, timeout=90)
        created = True
        actual = _owner_inspect(head, image["Id"])
        if (actual.get("State") or {}).get("Status") != "created":
            raise ReleaseBlocked("RELEASE_NOT_CREATED_STOPPED")
        mounts = actual.get("Mounts") or []
        if (len(mounts) != 2 or any(m.get("Type") != "bind" or
                m.get("RW") is not False for m in mounts)
                or {(m.get("Source"), m.get("Destination")) for m in mounts}
                != {(receipt["cache"], "/recipe/hf-cache"),
                    (receipt["views"], "/recipe/recipe-views")}):
            raise ReleaseBlocked("RELEASE_MOUNTS_DRIFT")
        _run(["docker", "start", actual["Id"]], timeout=90)
        gpu.wait_ready(RELEASE_PORT, model, timeout_s=1200)
    except BaseException:
        # A failed launch must never leave a second GPU model running.
        # Recover same-ID original ONLY AFTER successful owned cleanup.
        if created:
            try:
                cleanup_release(head, image["Id"])
            except (ReleaseBlocked, legacy.Blocked, gpu.Blocked, OSError):
                raise ReleaseBlocked(
                    "RELEASE_CLEANUP_FAILED_ORIGINAL_LEFT_STOPPED") from None
        try:
            _run(["bash", str(REPO / "scripts/start.sh"),
                  "--expected-head", head, "--confirm-id", receipt["id"],
                  "--execute"], timeout=120)
            restored = legacy.inspect("container", legacy.NAME)
            if (restored.get("Id") != receipt["id"] or
                    (restored.get("State") or {}).get("Status") != "running"):
                raise ReleaseBlocked("RESTORE_IDENTITY_MISMATCH")
            gpu.wait_ready(8000, model, timeout_s=900)
        except (ReleaseBlocked, legacy.Blocked, gpu.Blocked, OSError):
            raise ReleaseBlocked(
                "LAUNCH_FAILED_ORIGINAL_RESTORE_NOT_CONFIRMED") from None
        raise ReleaseBlocked("LAUNCH_FAILED_ORIGINAL_SAME_ID_HTTP_RESTORED") from None
    return {"status": "PREFIX_ON_RELEASE_HTTP_READY_ORIGINAL_STILL_EXITED",
            "release_container_id": actual["Id"],
            "release_image_id": image["Id"], "port": RELEASE_PORT,
            "original_id": receipt["id"],
            "original_automatically_stopped": False}


def cleanup_release(head: str, image_id: str,
                    confirm_release_id: str | None = None) -> None:
    ci = _owner_inspect(head, image_id)
    if confirm_release_id is not None and ci["Id"] != confirm_release_id:
        raise ReleaseBlocked("RELEASE_ID_CONFIRMATION_MISMATCH")
    if (ci.get("State") or {}).get("Status") not in (
            "created", "exited", "running"):
        raise ReleaseBlocked("RELEASE_STATE_UNSAFE_FOR_CLEANUP")
    _run(["docker", "rm", "--force", ci["Id"]], timeout=120)


def stop_and_restore(head: str, original_id: str,
                     release_id: str) -> dict:
    """Remove only owned release and restart exact same legacy original ID."""
    receipt, _, _, state = _legacy_state_for_release()
    if original_id != receipt["id"] or state != "exited":
        raise ReleaseBlocked("ORIGINAL_RECEIPT_OR_STATE_DRIFT")
    image = _release_image(head)
    cleanup_release(head, image["Id"], release_id)
    # Delegate all ownership/ID/status checks to existing P1 start script.
    _run(["bash", str(REPO / "scripts/start.sh"),
          "--expected-head", head, "--confirm-id", original_id,
          "--execute"], timeout=120)
    actual = legacy.inspect("container", legacy.NAME)
    if actual.get("Id") != original_id or (
            actual.get("State") or {}).get("Status") != "running":
        raise ReleaseBlocked("LEGACY_SAME_ID_RESTORE_FAILED")
    _, model = gpu.candidate_cmd((actual.get("Config") or {}).get("Cmd"))
    gpu.wait_ready(8000, model, timeout_s=900)
    return {"status": "RELEASE_REMOVED_LEGACY_SAME_ID_HTTP_RESTORED",
            "original_id": original_id}


def run(args: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-head", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--build", action="store_true")
    group.add_argument("--launch", action="store_true")
    group.add_argument("--stop-and-restore", action="store_true")
    parser.add_argument("--confirm-original-id")
    parser.add_argument("--confirm-release-id")
    a = parser.parse_args(args)
    try:
        head = a.expected_head
        release_tag(head)
        if os.geteuid() == 0:
            raise ReleaseBlocked("ROOT_USER_FORBIDDEN")
        if a.build:
            if a.confirm_original_id or a.confirm_release_id:
                raise ReleaseBlocked("BUILD_CANNOT_TAKE_IDS")
            result = build(head)
        elif a.launch:
            if not re.fullmatch(r"[a-f0-9]{64}", a.confirm_original_id or "") or a.confirm_release_id:
                raise ReleaseBlocked("LAUNCH_REQUIRES_EXACT_ORIGINAL_ID")
            result = launch(head, a.confirm_original_id)
        else:
            if (not re.fullmatch(r"[a-f0-9]{64}", a.confirm_original_id or "")
                    or not re.fullmatch(r"[a-f0-9]{64}", a.confirm_release_id or "")):
                raise ReleaseBlocked("STOP_REQUIRES_BOTH_EXACT_IDS")
            result = stop_and_restore(head, a.confirm_original_id,
                                      a.confirm_release_id)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ReleaseBlocked, legacy.Blocked, gpu.Blocked, OSError, KeyError,
            TypeError, ValueError) as err:
        reason = (str(err) if isinstance(err, ReleaseBlocked)
                  else type(err).__name__)
        print("P1_PREFIX_RELEASE_BLOCKED_" + reason, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(run())
