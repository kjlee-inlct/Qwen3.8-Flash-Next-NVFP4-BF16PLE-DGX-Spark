"""Read-only, fail-conservative inventory of DGX Workspace/llm children.

No move/delete/mkdir, no Docker state changes, no model or API calls. Git
queries are observational; contents of model directories are not traversed.
All archive indications require manual cross-checks of scripts/mounts/links.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any

PROTECTED = {
    "blazux-phase6-gates": "ACTIVE_P2_CHECKOUT",
    "yslab-qwen38-bf16ple-dgx-spark": "ORIGINAL_SERVICE_CHECKOUT",
    "bench-results-staging": "EVIDENCE_PRESERVE",
    "qwen38-orca-uncensored": "POSSIBLE_MODEL_OR_CACHE_DATA",
}
PAST_PHASE = re.compile(r"blazux-phase[1-5]-[a-zA-Z0-9_-]+\Z")
MAX_CONTAINERS = 128


def call(argv: list[str], *, timeout: int = 10) -> tuple[bool, str]:
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                              check=False, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    except (OSError, subprocess.TimeoutExpired, UnicodeError):
        return False, ""
    return proc.returncode == 0, proc.stdout.strip()


def docker_mount_sources() -> tuple[str, list[Path]]:
    """Inspect only existing container mount source paths, including stopped ones."""
    ok, ids = call(["docker", "container", "ls", "-aq"], timeout=15)
    if not ok:
        return "UNAVAILABLE", []
    containers = ids.splitlines()
    if len(containers) > MAX_CONTAINERS:
        return "INCOMPLETE_TOO_MANY_CONTAINERS", []
    if not containers:
        return "AVAILABLE", []
    ok, out = call(["docker", "container", "inspect", *containers], timeout=20)
    if not ok:
        return "UNAVAILABLE", []
    try:
        payload = json.loads(out)
        if not isinstance(payload, list) or len(payload) != len(containers):
            raise ValueError("partial container list")
        sources = []
        for record in payload:
            mounts = record.get("Mounts")
            if not isinstance(mounts, list):
                raise ValueError("mount metadata missing")
            for mount in mounts:
                source = mount.get("Source")
                if (mount.get("Type") == "bind" and isinstance(source, str)
                        and source.startswith("/")):
                    sources.append(Path(source).resolve(strict=False))
        return "AVAILABLE", sources
    except (ValueError, TypeError, AttributeError, OSError):
        return "UNAVAILABLE", []


def overlaps(a: Path, b: Path) -> bool:
    """Mount inside workspace child OR workspace child nested in mount."""
    try:
        a = a.resolve(strict=False)
        b = b.resolve(strict=False)
        return a == b or a in b.parents or b in a.parents
    except (OSError, RuntimeError, ValueError):
        return True  # ambiguous realpath: never suggest archiving


def git_metadata(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "git_repo": False, "branch": None, "tracked_change": "UNKNOWN",
        "untracked_change": "UNKNOWN", "linked_worktree": False,
        "additional_worktrees": "UNKNOWN", "origin_is_expected_fork": None,
    }
    dot_git = path / ".git"
    if not dot_git.exists() and not dot_git.is_symlink():
        return result
    result["git_repo"] = True
    if dot_git.is_file() or dot_git.is_symlink():
        result["linked_worktree"] = True
    ok, top = call(["git", "-C", str(path), "rev-parse", "--show-toplevel"])
    if not ok or Path(top).resolve(strict=False) != path.resolve(strict=False):
        return result
    ok, branch = call(["git", "-C", str(path), "branch", "--show-current"])
    if ok:
        result["branch"] = branch or "DETACHED"
    ok, changes = call(["git", "-C", str(path), "status", "--porcelain=v1",
                        "--untracked-files=normal"], timeout=15)
    if ok:
        lines = changes.splitlines()
        result["tracked_change"] = any(line[:2] != "??" for line in lines)
        result["untracked_change"] = any(line[:2] == "??" for line in lines)
    ok, origin = call(["git", "-C", str(path), "remote", "get-url", "origin"])
    if ok:
        trimmed = origin.removesuffix(".git")
        result["origin_is_expected_fork"] = trimmed in {
            "https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark",
            "git@github.com:kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark",
            "ssh://git@github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark",
        }
    ok, worktrees = call(["git", "-C", str(path), "worktree", "list", "--porcelain"])
    if ok:
        result["additional_worktrees"] = sum(line.startswith("worktree ")
                                                for line in worktrees.splitlines()) > 1
    return result


def inventory(root: Path, docker_status: str, mounts: list[Path]) -> dict[str, Any]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("workspace root must be a real directory")
    children = sorted(root.iterdir(), key=lambda p: p.name)
    report = []
    for path in children:
        if path.name.startswith("."):
            continue
        if path.is_symlink():
            report.append({"name": path.name, "kind": "SYMLINK",
                           "classification": "HOLD_REFERENCE", "reason": "SYMLINK_ALIAS"})
            continue
        if not path.is_dir():
            continue
        mounted = any(overlaps(path, source) for source in mounts)
        git = git_metadata(path)
        reason = PROTECTED.get(path.name)
        if reason:
            decision = "RETAIN_PROTECTED"
        elif mounted:
            decision, reason = "RETAIN_PROTECTED", "DOCKER_BIND_MOUNT_OVERLAP"
        elif git["linked_worktree"] or git["additional_worktrees"] is True:
            decision, reason = "HOLD_REFERENCE", "GIT_WORKTREE_RELATION"
        elif git["tracked_change"] is True or git["untracked_change"] is True:
            decision, reason = "HOLD_REFERENCE", "LOCAL_CHANGES_OR_UNTRACKED"
        elif PAST_PHASE.fullmatch(path.name):
            decision, reason = "REVIEW_FOR_ARCHIVE", "OLD_PHASE_CHECKOUT_NOT_PROVEN_UNUSED"
        else:
            decision, reason = "HOLD_REFERENCE", "UNCLASSIFIED_POSSIBLE_DEPENDENCY"
        if docker_status != "AVAILABLE" and decision == "REVIEW_FOR_ARCHIVE":
            reason = "DOCKER_MOUNTS_UNVERIFIED_" + reason
        report.append({"name": path.name, "kind": "DIRECTORY",
                       "classification": decision, "reason": reason,
                       "docker_bind_overlap": mounted if docker_status == "AVAILABLE" else None,
                       **git})
    return {
        "status": "READ_ONLY_WORKSPACE_INVENTORY",
        "root": str(root), "docker_inventory": docker_status,
        "entries": report,
        "writes_or_moves_performed": False,
        "archive_actions_authorized": False,
        "note": "REVIEW_FOR_ARCHIVE is NOT safe-to-delete. Verify external references and backups first.",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path.home() / "Workspace" / "llm")
    p.add_argument("--json", action="store_true", help="JSON report to stdout; no file created")
    args = p.parse_args(argv)
    try:
        status, mounts = docker_mount_sources()
        report = inventory(args.root.expanduser(), status, mounts)
    except (ValueError, OSError, PermissionError):
        print("WORKSPACE_INVENTORY_BLOCKED", file=__import__("sys").stderr)
        return 2
    if args.json:
        print(json.dumps(report, sort_keys=True, ensure_ascii=False, indent=2))
    else:
        print("WORKSPACE_INVENTORY_READ_ONLY root=" + report["root"]
              + " docker=" + report["docker_inventory"])
        for entry in report["entries"]:
            print("  {name:36} {classification:21} {reason}".format(**entry))
        print("NO_FILES_MOVED_OR_DELETED. REVIEW_FOR_ARCHIVE_NEEDS_APPROVAL.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
