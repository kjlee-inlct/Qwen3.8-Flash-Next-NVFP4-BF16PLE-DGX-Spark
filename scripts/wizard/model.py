"""Strict, separated deployment policy and model-compatibility manifest parsing."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "scripts" / "deployment-manifest.json"
COMPAT_PATH = ROOT / "compatibility.json"


class PolicyError(RuntimeError):
    """Unsafe or unsupported deployment policy."""


def _object(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise PolicyError(f"symlink manifest denied: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PolicyError(f"manifest read failed: {path}") from exc
    if not isinstance(data, dict):
        raise PolicyError(f"manifest must be an object: {path}")
    return data


def policy() -> dict[str, Any]:
    data = _object(POLICY_PATH)
    if data.get("schema_version") != 1 or data.get("policy_id") != "kjlee-qwen38-dgx-spark-wizard":
        raise PolicyError("unknown deployment manifest schema or identity")
    try:
        service, legacy, rules = data["service"], data["legacy"], data["policies"]
        origin = data["origin"]
        if origin["initial_pin"] != "9492b78c6bc04638587b42f2ffeb0680b0fcb3ef":
            raise ValueError("initial pin")
        if service["host_bind"] != "127.0.0.1" or not 1 <= service["host_port"] <= 65535:
            raise ValueError("unsafe service binding")
        if service["context"] != 262144 or service["sequences"] != 8 or service["gpu_memory"] != 0.8:
            raise ValueError("unqualified service defaults")
        if service["recommended_target"] != "orca-uncensored-bf16-mtp" or service["recommended_mtp"] != 2:
            raise ValueError("unqualified default MTP")
        for flag in ("preserve_cache", "preserve_existing_service", "never_purge_repo",
                     "never_purge_hf_auth", "legacy_adoption_read_only",
                     "uninstall_requires_owned_receipt", "public_bind_requires_external_review",
                     "legacy_identity_requires_mount_match", "legacy_checkout_drift_is_informational",
                     "legacy_api_health_not_ownership_proof"):
            if rules[flag] is not True:
                raise ValueError(f"required policy disabled: {flag}")
        if service["image"] == legacy["image"] or service["host_port"] == legacy["port"]:
            raise ValueError("new deployment must not reuse legacy image or port")
        if legacy["pin"] != origin["initial_pin"] or legacy["port"] != 8000:
            raise ValueError("legacy fingerprint changed")
        if legacy["container"] != "qwen38-flash-orca-uncensored-bf16-mtp":
            raise ValueError("legacy container changed")
    except (KeyError, TypeError, ValueError) as exc:
        raise PolicyError(f"invalid/unsafe deployment policy: {exc}") from exc
    return data


def targets() -> dict[str, dict[str, Any]]:
    """Authoritative checkpoint identities live in compatibility.json, not policy."""
    data = _object(COMPAT_PATH)
    if data.get("schema_version") != 1 or not isinstance(data.get("targets"), list):
        raise PolicyError("unsupported checkpoint compatibility manifest")
    found = {item["name"]: item for item in data["targets"]}
    if len(found) != len(data["targets"]):
        raise PolicyError("duplicate model target name")
    return found


def select_target(alias: str, mtp: int) -> dict[str, Any]:
    item = targets().get(alias)
    if item is None:
        raise PolicyError(f"unknown checkpoint target: {alias}")
    if not isinstance(mtp, int) or isinstance(mtp, bool) or not 0 <= mtp <= 16:
        raise PolicyError("MTP must be an integer in 0..16")
    if item["mode"] != "mtp_overlay" and mtp != 0:
        raise PolicyError("non-overlay checkpoint cannot enable MTP")
    return item
