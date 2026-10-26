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


def _legacy_api_observation(port: int, target: str) -> dict[str, Any]:
    """Bounded read-only localhost probes. API status does not grant ownership."""
    import urllib.request
    import urllib.error
    base = f"http://127.0.0.1:{port}"
    observed: dict[str, Any] = {
        "health": "NOT_CHECKED", "models": "NOT_CHECKED",
        "expected_model_id": f"qwen3.8-flash-next-{target}",
    }
    try:
        with urllib.request.urlopen(base + "/health", timeout=3) as reply:
            observed["health"] = "PASS" if 200 <= reply.status < 300 else "FAIL"
    except (OSError, ValueError, urllib.error.URLError):
        observed["health"] = "UNAVAILABLE"
    try:
        with urllib.request.urlopen(base + "/v1/models", timeout=4) as reply:
            document = json.loads(reply.read(128 * 1024))
        models = document.get("data", []) if isinstance(document, dict) else []
        model_ids = [entry.get("id") for entry in models if isinstance(entry, dict)]
        observed["models"] = ("PASS" if observed["expected_model_id"] in model_ids
                              else "MODEL_ID_NOT_FOUND")
    except (OSError, ValueError, urllib.error.URLError, TypeError):
        observed["models"] = "UNAVAILABLE"
    return observed


def legacy_observation(policy: dict[str, Any]) -> dict[str, Any]:
    """Validate existing deployment identity separately from its mutable Git checkout.

    No Git checkout/reset, Docker stop/rm/build or legacy-state writes are performed.
    A verified observation NEVER grants destructive ownership to the new wizard.
    """
    cfg = policy["legacy"]
    root = Path.home()
    custom_state = os.environ.get("YSLAB_STATE_DIR")
    state_dir = Path(custom_state) if custom_state else root / cfg["state_relative"]
    if not state_dir.is_absolute() or state_dir.is_symlink():
        raise ProbeError("unsafe legacy state directory")
    record: dict[str, Any] = {
        "source": "legacy-reference-installer",
        "state_dir": str(state_dir),
        "verified": False, "identity_verified": False,
        "read_only": True, "management_authority": "OBSERVE_ONLY",
        "reasons": [], "checkout_warnings": [],
        "checks": {
            "recorded_paths": False, "image_identity": False,
            "container_identity": False, "docker_labels": False,
            "port_binding": False, "model_mounts": False,
        },
        "checkout": {
            "origin": None, "head": None,
            "origin_matches_install": None, "head_matches_install_pin": None,
            "install_pin_available": None, "same_checkout_as_wizard": None,
            "tracked_worktree_clean": None,
        },
    }
    reasons: list[str] = record["reasons"]
    warnings: list[str] = record["checkout_warnings"]
    checks: dict[str, bool] = record["checks"]
    paths = _plain(state_dir / "paths")
    if paths is None:
        reasons.append("legacy paths receipt missing")
        return record
    lines = paths.splitlines()
    if (len(lines) != 2 or not all(Path(p).is_absolute() for p in lines)
            or any(p in ("/", str(root)) for p in lines)):
        reasons.append("legacy paths receipt invalid")
        return record
    repo_dir, cache_dir = map(Path, lines)
    record.update({"repo_dir": str(repo_dir), "cache_dir": str(cache_dir)})
    expected_repo = root / cfg["repo_relative"]
    if repo_dir != expected_repo and not os.environ.get("YSLAB_REPO_DIR"):
        reasons.append("nonstandard legacy checkout; manual review required")
    if cache_dir != repo_dir / cfg["cache_name"] and not os.environ.get("YSLAB_CACHE_DIR"):
        reasons.append("legacy external cache; manual review required")
    if repo_dir.is_symlink() or cache_dir.is_symlink():
        reasons.append("legacy repo/cache symlink; manual review required")
    elif not repo_dir.is_dir() or not cache_dir.is_dir():
        reasons.append("legacy repo/cache missing")
    else:
        checks["recorded_paths"] = True

    # Docker receipts and actual runtime identify the existing deployment;
    # the Git remote/HEAD can legitimately change AFTER the container is built.
    try:
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
        checks["image_identity"] = bool(
            exact_id(stored_image) and img is not None and img.get("Id") == stored_image
        )
        if not checks["image_identity"]:
            reasons.append("legacy image ID missing/different")
        checks["container_identity"] = bool(
            exact_id(stored_container) and cont is not None and cont.get("Id") == stored_container
        )
        if not checks["container_identity"]:
            reasons.append("legacy container ID missing/different")
        if cont is not None and checks["container_identity"]:
            try:
                validate_container(cont, expected_id=stored_container, target=cfg["target"],
                                   image_id=stored_image)
                checks["docker_labels"] = True
            except ProbeError:
                reasons.append("legacy recipe/target labels or attached image mismatch")
            bindings = ((cont.get("HostConfig") or {}).get("PortBindings") or {}).get("8000/tcp") or []
            checks["port_binding"] = any(
                str(port.get("HostPort")) == str(cfg["port"]) and
                port.get("HostIp") == cfg["bind"]
                for port in bindings
            )
            if not checks["port_binding"]:
                reasons.append("legacy published port/bind differs from reference")
            mounts = {
                entry.get("Destination"): entry.get("Source")
                for entry in (cont.get("Mounts") or []) if isinstance(entry, dict)
            }
            checks["model_mounts"] = bool(
                mounts.get("/recipe/hf-cache") == str(cache_dir) and
                mounts.get("/recipe/recipe-views") == str(repo_dir / "recipe-views")
            )
            record["mount_paths"] = {
                "hf_cache": mounts.get("/recipe/hf-cache"),
                "recipe_views": mounts.get("/recipe/recipe-views"),
            }
            if not checks["model_mounts"]:
                reasons.append("legacy cache/recipe-view Docker mounts differ from state paths")
            if (checks["port_binding"] and checks["docker_labels"] and
                    record["container_status"] == "running"):
                record["api"] = _legacy_api_observation(cfg["port"], cfg["target"])
            else:
                record["api"] = {"health": "NOT_CHECKED", "models": "NOT_CHECKED"}
        elif cont is None:
            reasons.append("legacy container not present")
    except (ProbeError, OSError, UnicodeError, ValueError, TypeError) as exc:
        reasons.append(f"legacy Docker inspection incomplete: {type(exc).__name__}")

    # Checkout drift is reported, not conflated with recorded Docker ownership.
    checkout: dict[str, Any] = record["checkout"]
    checkout["same_checkout_as_wizard"] = repo_dir.resolve() == Path(__file__).resolve().parents[2]
    try:
        origin = command(["git", "-C", str(repo_dir), "remote", "get-url", "origin"]).stdout.strip()
        head = command(["git", "-C", str(repo_dir), "rev-parse", "HEAD"]).stdout.strip()
        pin = command(["git", "-C", str(repo_dir), "cat-file", "-t", cfg["pin"]],
                      check=False)
        status = command(["git", "-C", str(repo_dir), "status", "--porcelain",
                          "--untracked-files=no"])
        checkout.update({
            "origin": origin, "head": head,
            "origin_matches_install": origin in (
                cfg["origin_url"], cfg["origin_url"].removesuffix(".git")),
            "head_matches_install_pin": head == cfg["pin"],
            "install_pin_available": pin.returncode == 0 and pin.stdout.strip() == "commit",
            "tracked_worktree_clean": not bool(status.stdout.strip()),
        })
        if not checkout["origin_matches_install"]:
            warnings.append("Git origin changed since legacy installation")
        if not checkout["head_matches_install_pin"]:
            warnings.append("Git HEAD changed since legacy image build")
        if not checkout["install_pin_available"]:
            warnings.append("original pinned commit no longer available locally")
        if not checkout["tracked_worktree_clean"]:
            warnings.append("tracked checkout has uncommitted changes")
    except (ProbeError, OSError, UnicodeError, ValueError) as exc:
        warnings.append(f"legacy checkout inspection unavailable: {type(exc).__name__}")

    record["identity_verified"] = all(checks.values()) and not reasons
    record["verified"] = record["identity_verified"]  # Backward-compatible observation flag.
    record["checkout_matches_install_pin"] = checkout["head_matches_install_pin"]
    record["legacy_management_mode"] = "READ_ONLY"
    return record
