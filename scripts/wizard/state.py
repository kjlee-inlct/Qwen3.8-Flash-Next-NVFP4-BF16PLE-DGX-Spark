"""Private, atomic deployment receipts; recorded IDs do not alone grant ownership."""
from __future__ import annotations
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any


class StateError(RuntimeError):
    """Unsafe or unreadable wizard state."""


def directory() -> Path:
    override = os.environ.get("QWEN38_WIZARD_STATE_DIR")
    base = os.environ.get("XDG_STATE_HOME")
    path = (Path(override) if override else
            (Path(base) if base else Path.home() / ".local" / "state") /
            ("qwen38-flash-dgx" if not override else ""))
    path = path.expanduser()
    if not path.is_absolute() or path == Path("/") or path == Path.home():
        raise StateError("wizard state must use a safe absolute directory")
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise StateError(f"symlink state component denied: {parent}")
    return path


def filename() -> Path:
    return directory() / "deployment-state.json"


def empty() -> dict[str, Any]:
    return {"schema_version": 1, "image": None, "containers": {}, "legacy_observation": None}


def load() -> dict[str, Any]:
    path = filename()
    if not path.exists():
        return empty()
    if path.is_symlink() or not path.is_file():
        raise StateError("state is not a regular file")
    if path.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise StateError("state file is readable/writable by group or others")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise StateError("cannot parse existing state; refuse mutation") from exc
    if (not isinstance(value, dict) or value.get("schema_version") != 1 or
            not isinstance(value.get("containers"), dict) or
            "image" not in value or "legacy_observation" not in value):
        raise StateError("unknown state schema; refuse mutation")
    return value


def save(data: dict[str, Any]) -> None:
    root = directory()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.is_symlink():
        raise StateError("state root is a symlink")
    os.chmod(root, 0o700)
    path = filename()
    if path.exists() and path.is_symlink():
        raise StateError("state file is a symlink")
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=root,
                                         prefix=".deployment-", delete=False) as handle:
            temporary = handle.name
            os.fchmod(handle.fileno(), 0o600)
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
