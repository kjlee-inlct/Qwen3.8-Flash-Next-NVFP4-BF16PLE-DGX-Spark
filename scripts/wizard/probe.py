"""Read-only Docker inspection, legacy recognition, and ownership guard."""
from __future__ import annotations
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

RECIPE_LABEL = "qwen38-flash-next-bf16-ple"
_ID = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")


class ProbeError(RuntimeError):
    """Inspection is unsafe, incomplete or unavailable."""


def command(args: list[str], *, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess[str]:
    """Do not run command strings via a shell or copy secrets into the argument list."""
    try:
        result = subprocess.run(args, text=True, capture_output=capture, check=False)
    except OSError as exc:
        raise ProbeError(f"command unavailable: {args[0]}") from exc
    if check and result.returncode != 0:
        # Do not echo stderr: subprocesses may include account identifiers or tokens.
        raise ProbeError(f"command failed: {args[0]} (exit {result.returncode})")
    return result


def _inspect(kind: str, name: str) -> dict[str, Any] | None:
    response = command(["docker", kind, "inspect", name], check=False)
    if response.returncode:
        # A Docker inspect failure can mean "not found" OR daemon error: distinguish.
        error = response.stderr.lower()
        if "no such" in error or "not found" in error:
            return None
        raise ProbeError(f"docker {kind} inspect unavailable")
    try:
        result = json.loads(response.stdout)
        if isinstance(result, list) and len(result) == 1 and isinstance(result[0], dict):
            return result[0]
    except ValueError:
        pass
    raise ProbeError(f"invalid Docker {kind} inspect response")


def container(name: str) -> dict[str, Any] | None:
    return _inspect("container", name)


def image(tag: str) -> dict[str, Any] | None:
    return _inspect("image", tag)


def exact_id(value: str) -> bool:
    return isinstance(value, str) and bool(_ID.fullmatch(value))


def validate_container(actual: dict[str, Any], *, expected_id: str, target: str,
                       image_id: str | None = None) -> None:
    labels = (actual.get("Config") or {}).get("Labels") or {}
    if (not exact_id(expected_id) or actual.get("Id") != expected_id or
            labels.get("ai.yslab.recipe") != RECIPE_LABEL or
            labels.get("ai.yslab.target") != target):
        raise ProbeError("container ID/recipe/target ownership mismatch")
    if image_id is not None and actual.get("Image") != image_id:
        raise ProbeError("container image ID differs from recorded deployment")


def image_in_use(image_id: str) -> bool:
    result = command(["docker", "ps", "-aq", "--no-trunc"])
    for item in result.stdout.splitlines():
        info = container(item)
        if info is None:
            raise ProbeError("container vanished while checking image usage")
        if info.get("Image") == image_id:
            return True
    return False


def _plain(path: Path) -> str | None:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 4096:
        return None
    return path.read_text(encoding="utf-8").strip()


def legacy_observation(policy: dict[str, Any]) -> dict[str, Any]:
    """Observe legacy assets only. Never assert ownership from mere names/labels."""
    cfg = policy["legacy"]
    root = Path.home()
    env_state = os.environ.get("YSLAB_STATE_DIR")
    state_dir = Path(env_state) if env_state else root / cfg["state_relative"]
    if not state_dir.is_absolute() or state_dir.is_symlink():
        raise ProbeError("unsafe legacy state directory")
    record: dict[str, Any] = {
        "source": "legacy-reference-installer",
        "state_dir": str(state_dir), "verified": False, "read_only": True, "reasons": [],
    }
    reasons: list[str] = record["reasons"]
    paths = _plain(state_dir / "paths")
    if paths is None:
        reasons.append("legacy paths receipt missing")
        return record
    lines = paths.splitlines()
    if len(lines) != 2 or not all(Path(p).is_absolute() for p in lines):
        reasons.append("legacy paths receipt invalid")
        return record
    repo_dir, cache_dir = map(Path, lines)
    record.update({"repo_dir": str(repo_dir), "cache_dir": str(cache_dir)})
    expected_repo = root / cfg["repo_relative"]
    if repo_dir != expected_repo and not os.environ.get("YSLAB_REPO_DIR"):
        # Non-default legacy checkouts remain observable but cannot be auto-verified.
        reasons.append("nonstandard legacy checkout; manual review required")
    if cache_dir != repo_dir / cfg["cache_name"]:
        reasons.append("legacy external cache; manual review required")
    try:
        if repo_dir.is_symlink() or cache_dir.is_symlink() or state_dir.is_symlink():
            raise ProbeError("legacy path is symlink")
        origin = command(["git", "-C", str(repo_dir), "remote", "get-url", "origin"]).stdout.strip()
        head = command(["git", "-C", str(repo_dir), "rev-parse", "HEAD"]).stdout.strip()
        if origin not in (cfg["origin_url"], cfg["origin_url"].removesuffix(".git")):
            reasons.append("legacy git origin mismatch")
        if head != cfg["pin"]:
            reasons.append("legacy git HEAD differs from pinned reference")
        record["git_head"] = head
        stored_image = _plain(state_dir / "image-id")
        stored_container = _plain(state_dir / "container-id")
        img = image(cfg["image"])
        cont = container(cfg["container"])
        record.update({
            "image_tag": cfg["image"], "container_name": cfg["container"],
            "recorded_image_id": stored_image, "recorded_container_id": stored_container,
            "observed_image_id": img.get("Id") if img else None,
            "observed_container_id": cont.get("Id") if cont else None,
            "container_status": ((cont or {}).get("State") or {}).get("Status"),
        })
        if not stored_image or not exact_id(stored_image) or img is None or img.get("Id") != stored_image:
            reasons.append("legacy image ID missing/different")
        if not stored_container or not exact_id(stored_container) or cont is None:
            reasons.append("legacy container ID missing/not present")
        elif cont.get("Id") != stored_container:
            reasons.append("legacy container ID changed")
        else:
            try:
                validate_container(cont, expected_id=stored_container,
                                   target=cfg["target"], image_id=stored_image)
            except ProbeError:
                reasons.append("legacy container labels or image mismatch")
            ports = ((cont.get("HostConfig") or {}).get("PortBindings") or {}).get("8000/tcp") or []
            if not any(str(p.get("HostPort")) == str(cfg["port"]) for p in ports):
                reasons.append("legacy published port differs from reference")
    except (ProbeError, OSError, UnicodeError, ValueError) as exc:
        reasons.append(f"legacy inspection incomplete: {type(exc).__name__}")
    record["verified"] = not reasons
    return record
