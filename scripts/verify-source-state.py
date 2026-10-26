#!/usr/bin/env python3
"""Read-only Git-source snapshot verifier.

Checks exact Git blob content, tracked file modes and expected branch. This is
NOT a runtime / model / CI test and never touches Docker, model files or state.
The manifest does not list itself to avoid self-referential content hashes; this
file is checked against the HEAD Git blob separately.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "scripts" / "source-state-manifest.json"
MANIFEST_RELPATH = "scripts/source-state-manifest.json"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
EXPECTED_ID = "kjlee-qwen38-wizard-source-snapshot"
EXPECTED_REPO = "kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark"
# Both named branches must retain the identical tracked source inventory.
# Do not broaden this list to arbitrary branches without reviewed code changes.
RELEASE_BRANCHES = ("feature/install-uninstall-wizard-20261026", "main")


def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(ROOT), *args], capture_output=True, text=True,
        check=False,
    )
    if completed.returncode:
        raise ValueError("Git read failed: " + " ".join(args[:3]))
    return completed.stdout.strip()


def git_blob(path: Path) -> str:
    """Compute SHA-1 Git blob ID from literal working-tree bytes (no writes)."""
    digest = hashlib.sha1()
    size = path.stat().st_size
    digest.update(f"blob {size}\0".encode("ascii"))
    with path.open("rb") as source:
        while True:
            piece = source.read(1024 * 1024)
            if not piece:
                break
            digest.update(piece)
    return digest.hexdigest()


def committed_files() -> dict[str, tuple[str, str]]:
    """Read entire tracked file tree from HEAD, preserving exact path names."""
    result = subprocess.run(
        ["git", "-C", str(ROOT), "ls-tree", "-rz", "--full-tree", "HEAD"],
        capture_output=True, check=False,
    )
    if result.returncode:
        raise ValueError("cannot inspect HEAD Git tree")
    entries: dict[str, tuple[str, str]] = {}
    for entry in result.stdout.split(b"\0"):
        if not entry:
            continue
        try:
            info, rawpath = entry.split(b"\t", 1)
            mode, objtype, sha = info.decode("ascii").split(" ")
            path = rawpath.decode("utf-8")
        except (UnicodeDecodeError, ValueError) as exc:
            raise ValueError("cannot decode Git tree record") from exc
        if objtype != "blob" or mode not in ("100644", "100755"):
            raise ValueError("unsupported tracked object: " + path)
        entries[path] = (mode, sha)
    return entries


def safe_path(name: str) -> Path:
    posix = PurePosixPath(name)
    if (not name or name.startswith("/") or "\\" in name or
            any(part in ("", ".", "..") for part in name.split("/")) or
            str(posix) != name):
        raise ValueError("unsafe manifest path: " + name)
    path = ROOT / name
    if path.is_symlink() or not path.is_file():
        raise ValueError("missing, symbolic, or non-regular file: " + name)
    if not path.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("manifest file escapes checkout: " + name)
    return path


def verification_branches(manifest: dict[str, Any]) -> tuple[str, ...]:
    """Require the reviewed feature/main release branch allowlist.

    Strict mode checks the *branch*, never a creation-time commit SHA: merge
    commits and squash merges have different commit IDs but identical content.
    """
    configured = manifest.get("allowed_branches")
    if not isinstance(configured, list) or tuple(configured) != RELEASE_BRANCHES:
        raise ValueError("source manifest release-branch allowlist mismatch")
    if manifest.get("branch") != RELEASE_BRANCHES[0]:
        raise ValueError("source snapshot provenance branch mismatch")
    return tuple(configured)


def source_report(*, strict: bool) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    checked = 0
    manifest_head = ""
    branch_name = ""
    try:
        root = Path(git("rev-parse", "--show-toplevel")).resolve()
        if root != ROOT.resolve():
            errors.append("verifier location differs from Git checkout root")
        manifest_path = safe_path(MANIFEST_RELPATH)
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        if data.get("schema_version") != 1 or data.get("manifest_id") != EXPECTED_ID:
            raise ValueError("unknown source-state manifest schema/identity")
        if data.get("repository") != EXPECTED_REPO:
            raise ValueError("repository identity mismatch")
        if data.get("validation_at_creation", {}).get("host_runtime") != "NOT_OBSERVED":
            raise ValueError("source manifest must not assert host verification")
        if data.get("validation_at_creation", {}).get("tests") != "NOT_RUN":
            raise ValueError("source manifest must not assert tests passed")
        branches = verification_branches(data)
        files = data.get("files")
        if not isinstance(files, list) or not files:
            raise ValueError("source manifest has no file inventory")
        manifest_head = git("rev-parse", "HEAD")
        branch_name = git("symbolic-ref", "--quiet", "--short", "HEAD")
        if strict and branch_name not in branches:
            errors.append(f"wrong branch: {branch_name}; allowed: {', '.join(branches)}")
        origin = git("remote", "get-url", "origin")
        clean_origin = origin.removesuffix(".git")
        repo_suffix = "/" + EXPECTED_REPO
        if not (clean_origin.endswith(repo_suffix) and
                (clean_origin.startswith("https://github.com/") or
                 clean_origin.startswith("git@github.com:") or
                 clean_origin.startswith("ssh://git@github.com/"))):
            errors.append("origin is not the expected personal fork; never pull/alter legacy checkout")
        tracked = committed_files()
        self_entry = tracked.pop(MANIFEST_RELPATH, None)
        if self_entry is None or self_entry[0] != "100644":
            errors.append("source-state manifest is not tracked as ordinary file")
        elif git_blob(manifest_path) != self_entry[1]:
            errors.append("source-state manifest differs from Git HEAD")
        expected: dict[str, tuple[str, str]] = {}
        for item in files:
            if not isinstance(item, dict):
                raise ValueError("invalid file inventory entry")
            name, mode, sha = item.get("path"), item.get("mode"), item.get("blob_sha")
            if not isinstance(name, str) or not isinstance(mode, str) or not isinstance(sha, str):
                raise ValueError("invalid source inventory shape")
            if name == MANIFEST_RELPATH or name in expected or not HEX40.fullmatch(sha):
                raise ValueError("duplicate, circular or invalid source inventory record: " + name)
            if mode not in ("100644", "100755"):
                raise ValueError("unsupported source file mode: " + name)
            expected[name] = (mode, sha)
        if expected != tracked:
            missing = sorted(set(expected) - set(tracked))
            unexpected = sorted(set(tracked) - set(expected))
            changed = sorted(name for name in expected.keys() & tracked.keys()
                             if expected[name] != tracked[name])
            errors.extend(f"manifest path absent in HEAD: {s}" for s in missing)
            errors.extend(f"unmanifested tracked path in HEAD: {s}" for s in unexpected)
            errors.extend(f"HEAD blob/mode differs from manifest: {s}" for s in changed)
        for name, (mode, sha) in expected.items():
            try:
                path = safe_path(name)
                actual = git_blob(path)
                if actual != sha:
                    errors.append("working-tree blob differs from manifest: " + name)
                if mode == "100755" and not (path.stat().st_mode & stat.S_IXUSR):
                    errors.append("executable bit missing in working tree: " + name)
                checked += 1
            except (OSError, ValueError) as exc:
                errors.append(str(exc))
        # Untracked cache, local state, logs are intentionally not inspected.
        warnings.append("Untracked/ignored files, model payload, Docker and runtime are NOT verified")
        # A merge/squash results in a new commit SHA. Comparing that SHA to a
        # creation parent is meaningless; source content and modes are checked above.
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(str(exc))
    return {
        "result": "PASS_SOURCE_ONLY" if not errors else "FAIL",
        "branch": branch_name, "head": manifest_head, "checked_source_files": checked,
        "errors": errors, "notes": warnings,
        "runtime_checked": False, "unit_tests_run": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true",
                        help="Require approved feature/main branch; always enforce file hashes and fork origin")
    parser.add_argument("--json", action="store_true", help="Machine-readable report on stdout")
    options = parser.parse_args()
    result = source_report(strict=options.strict)
    if options.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{result['result']}: {result['checked_source_files']} tracked file(s)")
        print(f"  branch={result['branch']} HEAD={result['head']}")
        for error in result["errors"]:
            print("  ERROR: " + error, file=sys.stderr)
        for note in result["notes"]:
            print("  NOTE: " + note)
    return 0 if result["result"] == "PASS_SOURCE_ONLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
