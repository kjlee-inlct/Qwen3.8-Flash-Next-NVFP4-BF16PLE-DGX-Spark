"""Read-only difference reporting and bounded host-health inventory.

No Docker writes, repository writes, state receipts writes, model download,
generation inference or command execution originate from this module.
"""
from __future__ import annotations
import shutil
from pathlib import Path
from typing import Any

import engine

_MISSING = object()
# Snapshot comparison uses an explicit allowlist, not arbitrary recursive JSON:
# historical fields can be added without creating false incident reports.
_FIELDS: tuple[tuple[str, str], ...] = (
    ("repo_dir", "identity"),
    ("cache_dir", "identity"),
    ("container_name", "identity"),
    ("recorded_container_id", "identity"),
    ("observed_container_id", "identity"),
    ("recorded_image_id", "identity"),
    ("observed_image_id", "identity"),
    ("image_tag", "identity"),
    ("mount_paths.hf_cache", "identity"),
    ("mount_paths.recipe_views", "identity"),
    ("container_status", "health"),
    ("checks.container_identity", "identity"),
    ("checks.docker_labels", "identity"),
    ("checks.image_identity", "identity"),
    ("checks.model_mounts", "identity"),
    ("checks.port_binding", "identity"),
    ("checks.recorded_paths", "identity"),
    ("read_only", "identity"),
    ("management_authority", "identity"),
    ("api.health", "health"),
    ("api.models", "health"),
    ("checkout.origin", "git"),
    ("checkout.head", "git"),
    ("checkout.tracked_worktree_clean", "git"),
)


def _value(source: dict[str, Any], path: str) -> Any:
    current: Any = source
    for key in path.split("."):
        if not isinstance(current, dict) or key not in current:
            return _MISSING
        current = current[key]
    return current


def compare_observations(saved: Any, current: Any) -> dict[str, Any]:
    """Compare immutable saved observation with *newly* observed host inventory.

    Missing fields are UNKNOWN (not a false 'changed'), particularly for old
    state schemas or inspection errors. Git drift is informational and cannot
    transfer or revoke container ownership.
    """
    if not isinstance(saved, dict):
        return {"status": "UNREGISTERED", "counts": {"identity": 0, "health": 0, "git": 0},
                "differences": [], "unknown": []}
    if not isinstance(current, dict):
        return {"status": "UNKNOWN", "counts": {"identity": 0, "health": 0, "git": 0},
                "differences": [], "unknown": ["current legacy inspection unavailable"]}
    diffs: list[dict[str, Any]] = []
    unknown: list[str] = []
    totals = {"identity": 0, "health": 0, "git": 0}
    for field, category in _FIELDS:
        before, after = _value(saved, field), _value(current, field)
        if before is _MISSING or after is _MISSING:
            unknown.append(field)
        elif before != after:
            # ID values are local-only; CLI summary prints paths, not full IDs.
            diffs.append({"field": field, "group": category,
                          "recorded": before, "current": after})
            totals[category] += 1
    if totals["identity"]:
        status = "CHANGED"
    elif unknown:
        status = "UNKNOWN"
    elif totals["health"]:
        status = "HEALTH_CHANGED"
    elif totals["git"]:
        status = "GIT_CHANGED"
    else:
        status = "UNCHANGED"
    return {"status": status, "counts": totals, "differences": diffs, "unknown": unknown}


def _disk(path: str | None, *, warning_free_gib: int = 100) -> dict[str, Any]:
    if not path:
        return {"status": "UNKNOWN", "reason": "path not recorded"}
    target = Path(path)
    if target.is_symlink() or not target.is_dir():
        return {"status": "UNKNOWN", "reason": "path missing or symlink"}
    try:
        usage = shutil.disk_usage(target)
    except OSError:
        return {"status": "UNKNOWN", "reason": "filesystem unavailable"}
    gib = 1024 ** 3
    free = round(usage.free / gib, 2)
    return {
        "status": "LOW_SPACE" if free < warning_free_gib else "PASS",
        "free_gib": free, "total_gib": round(usage.total / gib, 2),
        "warning_threshold_gib": warning_free_gib,
        "note": "space advisory only; an already-running service may use more disk",
    }


def _memory() -> dict[str, Any]:
    """Read kernel's MemAvailable; lack of /proc is not an error."""
    try:
        for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
            if line.startswith("MemAvailable:"):
                kib = int(line.split()[1])
                return {"status": "OBSERVED", "available_gib": round(kib / 1024**2, 2)}
    except (OSError, ValueError, IndexError):
        pass
    return {"status": "UNKNOWN"}


def host_health(legacy: Any, *, warning_free_gib: int = 100) -> dict[str, Any]:
    """Use the existing read-only legacy observation; no second Docker probe."""
    if not isinstance(legacy, dict):
        return {"status": "UNKNOWN", "container": "UNKNOWN", "api": "UNKNOWN",
                "model_list": "UNKNOWN", "disk": {"status": "UNKNOWN"},
                "memory": _memory()}
    running = legacy.get("container_status") == "running"
    api = legacy.get("api") if isinstance(legacy.get("api"), dict) else {}
    check_status = "PASS" if legacy.get("identity_verified") is True else "FAIL"
    paths = {x: legacy.get(x) for x in ("cache_dir", "repo_dir")}
    cache = _disk(paths["cache_dir"], warning_free_gib=warning_free_gib)
    views = _disk(
        str(Path(paths["repo_dir"]) / "recipe-views") if paths["repo_dir"] else None,
        warning_free_gib=warning_free_gib)
    health_states = [check_status,
                     "PASS" if running else "FAIL",
                     api.get("health", "UNKNOWN"), api.get("models", "UNKNOWN")]
    if "FAIL" in health_states or "MODEL_ID_NOT_FOUND" in health_states:
        overall = "FAIL"
    elif "UNKNOWN" in health_states or "UNAVAILABLE" in health_states or "NOT_CHECKED" in health_states:
        overall = "UNKNOWN"
    elif "UNKNOWN" in (cache["status"], views["status"]):
        overall = "UNKNOWN"
    elif "LOW_SPACE" in (cache["status"], views["status"]):
        overall = "WARN"
    else:
        overall = "PASS"
    return {
        "status": overall, "identity": check_status,
        "container": "PASS" if running else "FAIL",
        "api": api.get("health", "UNKNOWN"), "model_list": api.get("models", "UNKNOWN"),
        "disk": {"hf_cache": cache, "recipe_views": views},
        "memory": _memory(),
        "note": "read-only HTTP GET/host capacity; no generation inference; free space is advisory",
    }


def status_report(*, include_health: bool = False) -> dict[str, Any]:
    base = engine.deployment_status()
    saved = base.get("recorded_legacy")
    current = base.get("legacy")
    base["comparison"] = compare_observations(saved, current)
    if any("wizard inventory incomplete:" in str(warning)
           for warning in (base.get("warnings") or [])):
        # Corrupted or inaccessible saved receipt is NOT "UNREGISTERED".
        base["comparison"]["status"] = "UNKNOWN"
        base["comparison"]["unknown"].append("saved wizard state unreadable")
    if include_health:
        base["health"] = host_health(current)
    return base


def summary_lines(data: dict[str, Any]) -> list[str]:
    """Korean compact summary: identity, drift, runtime, optional disk/memory."""
    live = data.get("legacy")
    live = live if isinstance(live, dict) else {}
    cmp = data.get("comparison") or {}
    api = live.get("api") or {}
    warnings = live.get("checkout_warnings") or []
    checks = live.get("checks") or {}
    files = ", ".join(k for k, v in checks.items() if v is not True) or "없음"
    identity = ("PASS" if live.get("identity_verified") is True else
                "FAIL" if checks else "UNKNOWN")
    lines = [
        "DGX Spark 읽기 전용 상태",
        f"  기존 설치 식별: {identity} (불일치 항목: {files})",
        f"  컨테이너: {live.get('container_status') or 'UNKNOWN'} / "
        f"API: {api.get('health', 'UNKNOWN')} / 모델 목록: {api.get('models', 'UNKNOWN')}",
        f"  저장된 관찰 기록 대비: {cmp.get('status', 'UNKNOWN')} "
        f"(설치정체성 {cmp.get('counts', {}).get('identity', 0)} / "
        f"서비스 {cmp.get('counts', {}).get('health', 0)} / "
        f"Git {cmp.get('counts', {}).get('git', 0)})",
        f"  Git 변경 경고: {len(warnings)}건 (정보용, 소유권 변경 없음)",
        "  관리 권한: OBSERVE_ONLY / 신규 설치·제거 동작: 실행하지 않음",
    ]
    if "health" in data:
        h = data["health"]
        disk = h.get("disk") or {}
        parts = []
        for label, info in disk.items():
            if isinstance(info, dict):
                parts.append(f"{label}={info.get('free_gib', '?')}GiB({info.get('status', 'UNKNOWN')})")
        lines.append(f"  Health: {h.get('status', 'UNKNOWN')} / disk: {', '.join(parts)}")
        lines.append(f"  MemAvailable: {h.get('memory', {}).get('available_gib', '?')} GiB")
    if data.get("warnings"):
        lines.append("  조회 경고: " + ", ".join(data["warnings"]))
    return lines
