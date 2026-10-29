"""Export exact-pin Preview Prefix-cache candidate source to a private CPU-only stage.

DOES NOT install into vLLM, load a model, enable CUDA, or touch Docker.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
from src import preview_p1_prefix_candidate as candidate

STAGE = Path("/stage")
NAMES = {"mamba": "mamba_hybrid.py", "scheduler": "scheduler.py"}

class StageBlocked(Exception):
    pass

def stage_files(out: Path, *, read=None, patch=None):
    read = candidate._read_pinned if read is None else read
    patch = candidate.patch_source if patch is None else patch
    if out.is_symlink() or not out.is_dir():
        raise StageBlocked("OUTPUT_DIRECTORY_MISSING")
    if stat.S_IMODE(out.stat().st_mode) & 0o077:
        raise StageBlocked("OUTPUT_DIRECTORY_NOT_PRIVATE")
    if any(out.iterdir()):
        raise StageBlocked("OUTPUT_NOT_EMPTY")
    root = candidate._installed_root()
    source = {}
    patched = {}
    for label, (_, expected) in candidate.SPECS.items():
        source[label] = read(root, label)
        patched[label] = patch(label, source[label], expected)
        if patched[label] == source[label]:
            raise StageBlocked("PATCH_NO_CHANGE")
        candidate._parse(patched[label])
    if any(read(root, key) != value for key, value in source.items()):
        raise StageBlocked("INSTALLED_SOURCE_DRIFT")
    digests = {}
    for label, name in NAMES.items():
        path = out / name
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
        with os.fdopen(os.open(path, flags, 0o600), "wb") as f:
            f.write(patched[label])
            f.flush()
            os.fsync(f.fileno())
        if path.is_symlink() or path.read_bytes() != patched[label]:
            raise StageBlocked("OUTPUT_CONTENT_DRIFT")
        digests[name] = hashlib.sha256(patched[label]).hexdigest()
    return {"status": "SOURCE_STAGE_ONLY_NOT_INSTALLED",
            "files": 2, "sha256": digests,
            "actual_gpu_or_model_run": False}

def main(args=None):
    argv = sys.argv[1:] if args is None else args
    if argv != ["--stage-files", "--output", "/stage"]:
        print("P1_PREFIX_STAGE_BLOCKED_USAGE")
        return 2
    try:
        print(json.dumps(stage_files(STAGE), sort_keys=True))
        print("P1_PREFIX_GPU_SOURCE_STAGE_READY_ONLY_NOT_APPLIED")
        return 0
    except (StageBlocked, candidate.Blocked, OSError, ValueError, TypeError):
        print("P1_PREFIX_STAGE_BLOCKED_FAIL_CLOSED")
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
