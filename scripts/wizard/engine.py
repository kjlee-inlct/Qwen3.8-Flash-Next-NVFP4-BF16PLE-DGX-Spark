"""Bounded installer/uninstaller actions; no implicit migration of existing services."""
from __future__ import annotations
import json
import os
import shutil
import socket
import subprocess
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any
from model import ROOT, PolicyError, policy, select_target
from state import load, save
from probe import ProbeError, command, container, image, exact_id, image_in_use, legacy_observation, validate_container

class WizardError(RuntimeError):
    """Fail closed with an actionable message."""


def require_user() -> None:
    if os.geteuid() == 0:
        raise WizardError("run as the normal DGX user, never root/sudo")


def require_checkout() -> None:
    if not (ROOT / ".git").exists():
        raise WizardError("run from a Git checkout; no automatic git clone/reset is performed")
    status = command(["git", "-C", str(ROOT), "status", "--porcelain=v1", "--untracked-files=all"])
    if status.stdout.strip():
        raise WizardError("checkout has uncommitted/untracked files; build/prepare refused")


def cache_path() -> Path:
    # Current checkout's cache; NEVER silently use or alter YSLAB legacy cache.
    return ROOT / "hf-cache"


def cli(*args: str) -> str:
    entry = ROOT / "scripts" / "qwen38-dgx-spark"
    if args and args[0] == "login":
        # Interactive HF login must be visible on the user's terminal.
        command([str(entry), *args], capture=False)
        return ""
    result = command([str(entry), *args])
    return result.stdout.strip()


def _runtime_target(name: str, mtp: int) -> dict[str, Any]:
    return select_target(name, mtp)


def _model_path(name: str, image_tag: str) -> Path:
    target = cli("path", name, "--cache", str(cache_path()), "--image", image_tag)
    path = Path(target)
    if not path.is_absolute():
        raise WizardError("recipe returned non-absolute model path")
    allowed = (cache_path().resolve(), (cache_path().parent / "recipe-views").resolve())
    resolved = path.resolve()
    if not any(resolved == p or resolved.is_relative_to(p) for p in allowed):
        raise WizardError("recipe model path outside approved checkpoint locations")
    return path


def _image_id(tag: str) -> str | None:
    info = image(tag)
    return info.get("Id") if info else None


def _image_owned(tag: str, receipt: dict[str, Any]) -> str:
    image_info = image(tag)
    recorded = receipt.get("image")
    if (not image_info or not isinstance(recorded, dict)
            or recorded.get("tag") != tag or not exact_id(recorded.get("id"))
            or image_info.get("Id") != recorded["id"]):
        raise WizardError("image tag/ID has no matching wizard ownership receipt; refusing operation")
    return recorded["id"]


def _port_free(address: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((address, port))
            return True
        except OSError:
            return False


def wizard_container_name(target: str) -> str:
    """Use the reviewed new-only namespace, never the legacy container name."""
    return f"{policy()['service']['container_prefix']}{target}"


def deployment_status() -> dict[str, Any]:
    manifest = policy()
    result: dict[str, Any] = {"wizard_policy": manifest["policy_id"], "legacy": None,
                              "wizard": {"image": None, "containers": []}, "warnings": []}
    try:
        state = load()
        configured_image = manifest["service"]["image"]
        info = image(configured_image)
        stored = state.get("image")
        result["wizard"]["image"] = {
            "tag": configured_image, "observed_id": info.get("Id") if info else None,
            "recorded_id": stored.get("id") if isinstance(stored, dict) else None,
            "owned": bool(info and isinstance(stored, dict)
                          and info.get("Id") == stored.get("id") and stored.get("tag") == configured_image),
        }
        for name, recorded in state["containers"].items():
            actual = container(name)
            item = {"name": name, "recorded_id": recorded.get("id"),
                    "observed_id": actual.get("Id") if actual else None,
                    "status": ((actual or {}).get("State") or {}).get("Status"), "verified": False}
            if actual:
                try:
                    validate_container(actual, expected_id=recorded["id"],
                                       target=recorded["target"], image_id=recorded["image_id"],
                                       expected_name=name, wizard_owned=True)
                    item["verified"] = True
                except (ProbeError, KeyError):
                    pass
            result["wizard"]["containers"].append(item)
        result["recorded_legacy"] = state.get("legacy_observation")
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        result["warnings"].append(f"wizard inventory incomplete: {exc}")
    try:
        result["legacy"] = legacy_observation(manifest)
    except (ProbeError, OSError) as exc:
        result["warnings"].append(f"legacy inspection incomplete: {exc}")
    return result


def inspect_only() -> dict[str, Any]:
    return deployment_status()


def adopt_legacy(confirm_container_id: str) -> dict[str, Any]:
    """Read-only import into wizard's *own* receipt, no Docker or legacy-state writes."""
    require_user()
    record = legacy_observation(policy())
    if not record.get("verified"):
        raise WizardError("legacy fingerprint incomplete/mismatched; no adoption: " +
                          ", ".join(record.get("reasons", [])))
    if (not exact_id(confirm_container_id) or
            confirm_container_id != record.get("observed_container_id")):
        raise WizardError("exact full legacy container ID must be provided for read-only adoption")
    state = load()
    state["legacy_observation"] = record
    save(state)
    return record


def build_image(*, dry_run: bool) -> str:
    manifest = policy()
    tag = manifest["service"]["image"]
    if dry_run:
        return f"PLAN: build/reuse {tag} from {ROOT} (no Docker writes)"
    require_user()
    require_checkout()
    state = load()
    existing = _image_id(tag)
    if existing:
        owned = _image_owned(tag, state)
        return f"REUSE: previously built wizard image {tag} ({owned})"
    # Never overwrite a pre-existing image with the same tag.
    command(["docker", "build", "-t", tag, str(ROOT)], capture=False)
    created = _image_id(tag)
    if not created or not exact_id(created):
        raise WizardError("Docker build completed but image identity is unavailable")
    state["image"] = {"tag": tag, "id": created, "source": "wizard-build"}
    save(state)
    return f"BUILT: {tag} ({created})"


def prepare(*, target: str, mtp: int, skip_login: bool, dry_run: bool) -> str:
    manifest = policy()
    _runtime_target(target, mtp)
    tag = manifest["service"]["image"]
    if dry_run:
        return f"PLAN: audit existing {target}, or login/download pinned target into {cache_path()}"
    require_user()
    state = load()
    _image_owned(tag, state)
    path = _model_path(target, tag)
    if path.is_dir():
        cli("audit", target, "--cache", str(cache_path()), "--image", tag)
        return f"REUSE: audited existing checkpoint view {path}"
    require_checkout()
    if not skip_login:
        if not os.isatty(0):
            raise WizardError("non-interactive prepare requires --skip-login and preconfigured HF access")
        cli("login", "--cache", str(cache_path()), "--image", tag)
    cli("prepare", target, "--cache", str(cache_path()), "--image", tag)
    path = _model_path(target, tag)
    if not path.is_dir():
        raise WizardError("checkpoint preparation returned without expected model directory")
    cli("audit", target, "--cache", str(cache_path()), "--image", tag)
    return f"PREPARED: {path}"


def _get(url: str, seconds: int = 4) -> Any:
    with urllib.request.urlopen(url, timeout=seconds) as response:
        raw = response.read()
    return json.loads(raw) if raw else {}


def _api_ready(bind: str, port: int, alias: str, seconds: int) -> None:
    base = f"http://{bind}:{port}"
    deadline = time.monotonic() + seconds
    last_error = "not ready"
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(base + "/health", timeout=4).close()
            models = _get(base + "/v1/models")
            if alias not in [item.get("id") for item in models.get("data", [])]:
                raise WizardError("health OK but expected model alias is absent")
            payload = json.dumps({"model": alias, "messages": [
                {"role": "user", "content": "Reply with the number 4."}],
                "max_tokens": 64, "temperature": 1.0}).encode("utf-8")
            req = urllib.request.Request(base + "/v1/chat/completions",
                        data=payload, headers={"Content-Type": "application/json"},
                        method="POST")
            with urllib.request.urlopen(req, timeout=60) as answer:
                body = json.load(answer)
            if not body.get("choices"):
                raise WizardError("API returned no choices")
            return
        except (OSError, ValueError, KeyError, WizardError, urllib.error.URLError) as exc:
            last_error = type(exc).__name__
        time.sleep(min(5, max(0.0, deadline - time.monotonic())))
    raise WizardError(f"readiness timeout ({seconds}s, last error: {last_error}); container left intact for inspection")


def activate(*, target: str, mtp: int, dry_run: bool) -> str:
    manifest = policy()
    target_info = _runtime_target(target, mtp)
    config = manifest["service"]
    tag, bind, port = config["image"], config["host_bind"], config["host_port"]
    name = wizard_container_name(target)
    if dry_run:
        return f"PLAN: audit {target}; require vacant container name {name} and {bind}:{port}; run MTP={mtp}; verify health/models/chat"
    require_user()
    state = load()
    recorded_image_id = _image_owned(tag, state)
    existing = container(name)
    if existing:
        raise WizardError(f"container name occupied: {name}; no replacement permitted")
    legacy = container(manifest["legacy"]["container"])
    if legacy and (legacy.get("State") or {}).get("Status") == "running":
        raise WizardError("legacy service running; single-GB10 concurrent GPU activation not qualified")
    if not _port_free(bind, port):
        raise WizardError(f"host port {bind}:{port} occupied; no service stopped")
    path = _model_path(target, tag)
    if not path.is_dir():
        raise WizardError("prepared checkpoint missing: use --prepare-only first")
    cli("audit", target, "--cache", str(cache_path()), "--image", tag)
    cli("serve", target, "--cache", str(cache_path()), "--image", tag,
        "--mtp", str(mtp), "--port", str(port), "--bind", bind,
        "--container-name", name)
    current = container(name)
    if current is None:
        raise WizardError("serve command returned success but container is missing")
    validate_container(current, expected_id=current.get("Id", ""), target=target,
                       image_id=recorded_image_id, expected_name=name, wizard_owned=True)
    # Save immediately: if readiness fails, an intentionally retained container is still tracked.
    state = load()
    state["containers"][name] = {
        "id": current["Id"], "target": target, "image_id": recorded_image_id,
        "port": port, "bind": bind, "mtp": mtp, "ready": False,
    }
    save(state)
    alias = f"{target_info['served_model_name']}-{target}"
    _api_ready(bind, port, alias, config["readiness_seconds"])
    state = load()
    state["containers"][name]["ready"] = True
    save(state)
    return f"READY: {alias} at http://{bind}:{port}/v1"


def stop_or_remove(*, target: str, operation: str, dry_run: bool) -> str:
    """Only wizard-owned *new* deployments; legacy observations never permit removal."""
    _runtime_target(target, 0)
    name = wizard_container_name(target)
    state = load()
    recorded = state["containers"].get(name)
    if not isinstance(recorded, dict):
        raise WizardError(f"no wizard ownership receipt for {name}; legacy deployment is protected")
    actual = container(name)
    if not actual:
        raise WizardError("container no longer exists; refusing destructive action on stale receipt")
    validate_container(actual, expected_id=recorded["id"], target=target,
                       image_id=recorded["image_id"], expected_name=name, wizard_owned=True)
    if dry_run:
        return f"PLAN: docker {operation} {name} ({recorded['id']}) after ID and label check"
    require_user()
    if operation == "stop":
        command(["docker", "stop", recorded["id"]])
        state["containers"][name]["ready"] = False
    elif operation == "remove":
        command(["docker", "rm", "-f", recorded["id"]])
        del state["containers"][name]
    else:
        raise WizardError("unknown container operation")
    save(state)
    return f"DONE: {operation} {name}; weights, caches and other containers preserved"


def remove_image(*, dry_run: bool) -> str:
    manifest = policy()
    tag = manifest["service"]["image"]
    state = load()
    expected = _image_owned(tag, state)
    if image_in_use(expected):
        raise WizardError("image is still referenced by one or more containers (running or stopped)")
    if dry_run:
        return f"PLAN: remove verified unused wizard image {tag} ({expected})"
    require_user()
    command(["docker", "image", "rm", tag])
    state["image"] = None
    save(state)
    return f"DONE: removed unused wizard image {tag}; caches/legacy data preserved"
