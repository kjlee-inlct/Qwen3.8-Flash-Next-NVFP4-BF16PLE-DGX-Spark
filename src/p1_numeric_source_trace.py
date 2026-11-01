"""Read-only P1 numeric path locator for the EXACT installed original Preview.

This is not a GPU probe or an inference test. It emits AST locations and SHA256
of installed vLLM Python sources to anchor a later isolated logits/logprob tap.
No module from vLLM or torch is imported. No Docker run/exec or writes are made.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import re
import subprocess
import sys
import tarfile

from src import p1_legacy_service_window as legacy
from src import p1_preview_qsa_exact_topk as qsa

ORIGINAL_ID = "3fc5a3d5be1d52595602287acd87895220219bad050484251ac0408a163ffc45"
ORIGINAL_IMAGE = "sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a"
PACKAGE_ROOT = "/usr/local/lib/python3.12/dist-packages/"
MAX_ARCHIVE_BYTES = 4_000_000
MAX_SOURCE_BYTES = 2_000_000
MAX_LOCATIONS = 48

# Fixed source candidates, not assertions that these are the runtime entrypoints.
# Missing/renamed paths must be reported, not guessed from current upstream main.
SOURCES = {
    "runner": "vllm/v1/worker/gpu_model_runner.py",
    "sampler": "vllm/v1/sample/sampler.py",
    "engine_logprobs": "vllm/v1/engine/logprobs.py",
    "output_processor": "vllm/v1/engine/output_processor.py",
    "chat_api": "vllm/entrypoints/openai/serving_chat.py",
    "model": "vllm/models/qwen3_8_flash_next/nvidia/model.py",
    "logits_processor": "vllm/model_executor/layers/logits_processor.py",
}
INTEREST = re.compile(
    r"(compute_logits|log[_]?softmax|logprobs?|sample|execute_model|"
    r"process_outputs|forward|chat_completion)", re.IGNORECASE
)


class Blocked(RuntimeError):
    """Reason only: never include Docker output, prompt or model data."""


def safe_source_path(path: str) -> str:
    if (path not in SOURCES.values() or not path.endswith(".py")
            or ".." in path.split("/") or path.startswith("/")):
        raise Blocked("SOURCE_NOT_ALLOWLISTED")
    return PACKAGE_ROOT + path


def extract_python_tar(raw: bytes) -> bytes:
    """Read one regular-file Docker-cp member in memory, never extract to disk."""
    if not 0 < len(raw) <= MAX_ARCHIVE_BYTES:
        raise Blocked("ARCHIVE_SIZE_INVALID")
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
            members = [m for m in archive.getmembers() if m.isfile()]
            if len(members) != 1 or not 0 < members[0].size <= MAX_SOURCE_BYTES:
                raise Blocked("ARCHIVE_MEMBERS_INVALID")
            member = members[0]
            if member.issym() or member.islnk() or not member.name.endswith(".py"):
                raise Blocked("ARCHIVE_FILE_INVALID")
            stream = archive.extractfile(member)
            if stream is None:
                raise Blocked("ARCHIVE_READ_INVALID")
            data = stream.read(MAX_SOURCE_BYTES + 1)
            if len(data) != member.size:
                raise Blocked("ARCHIVE_LENGTH_INVALID")
            return data
    except (tarfile.TarError, OSError, EOFError):
        raise Blocked("ARCHIVE_INVALID") from None


def _run_docker_cp(path: str) -> bytes:
    try:
        result = subprocess.run(
            ["docker", "cp", legacy.NAME + ":" + safe_source_path(path), "-"],
            capture_output=True, check=False, timeout=25,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise Blocked("DOCKER_CP_UNAVAILABLE") from None
    if result.returncode != 0:
        raise Blocked("DOCKER_CP_SOURCE_MISSING") from None
    return extract_python_tar(result.stdout)


def locate_symbols(raw: bytes) -> dict:
    """AST locations only. Call names do not by themselves prove call order."""
    if len(raw) > MAX_SOURCE_BYTES:
        raise Blocked("SOURCE_OVERSIZE")
    try:
        tree = ast.parse(raw.decode("utf-8"))
    except (UnicodeError, SyntaxError):
        raise Blocked("SOURCE_SYNTAX_INVALID") from None

    class Visitor(ast.NodeVisitor):
        def __init__(self):
            self.scope: list[str] = []
            self.locations: list[dict] = []
            self.total = 0

        def record(self, kind: str, name: str, line: int):
            self.total += 1
            if len(self.locations) < MAX_LOCATIONS:
                self.locations.append({
                    "kind": kind, "scope": ".".join(self.scope) or "<module>",
                    "name": name[:160], "line": line,
                })

        def visit_ClassDef(self, node):
            self.scope.append(node.name)
            self.generic_visit(node)
            self.scope.pop()

        def visit_FunctionDef(self, node):
            if INTEREST.search(node.name):
                self.record("def", node.name, node.lineno)
            self.scope.append(node.name)
            self.generic_visit(node)
            self.scope.pop()

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Call(self, node):
            fn = ast.unparse(node.func)
            if INTEREST.search(fn):
                self.record("call", fn, node.lineno)
            self.generic_visit(node)

    visitor = Visitor()
    visitor.visit(tree)
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "locations": sorted(visitor.locations, key=lambda r: (r["line"], r["kind"])),
        "total_matched_locations": visitor.total,
        "locations_truncated": visitor.total > MAX_LOCATIONS,
    }


def original_identity() -> tuple[str, str, str]:
    try:
        data = legacy.inspect("container", legacy.NAME)
    except (OSError, ValueError, KeyError, TypeError, legacy.Blocked):
        raise Blocked("ORIGINAL_INSPECT_UNAVAILABLE") from None
    state = data.get("State") or {}
    if (data.get("Id") != ORIGINAL_ID or data.get("Image") != ORIGINAL_IMAGE
            or state.get("Running") is not True
            or state.get("Status") != "running"
            or not isinstance(state.get("StartedAt"), str)
            or not state["StartedAt"]):
        raise Blocked("ORIGINAL_ID_IMAGE_OR_RUNNING_DRIFT")
    return data["Id"], data["Image"], state["StartedAt"]


def inspect_original() -> dict:
    before = original_identity()
    files: dict[str, dict] = {}
    missing: list[str] = []
    try:
        for label, path in SOURCES.items():
            try:
                raw = _run_docker_cp(path)
                files[label] = {"path": path, **locate_symbols(raw)}
            except Blocked as exc:
                if str(exc) == "DOCKER_CP_SOURCE_MISSING":
                    missing.append(path)
                else:
                    raise
    finally:
        # The original is never stopped/restarted. Fail even if only the
        # StartedAt changed during what should have been a passive inspection.
        if original_identity() != before:
            raise Blocked("ORIGINAL_ID_OR_START_TIME_CHANGED") from None

    return {
        "status": "READ_ONLY_PREVIEW_NUMERIC_SOURCE_LOCATIONS",
        "original_image_id_matches_pin": True,
        "original_same_id_running_unchanged": True,
        "source_files_read": len(files),
        "source_files_missing": missing,
        "files": files,
        "runtime_call_path_verified": False,
        "raw_logits_or_logprob_measured": False,
        "gpu_or_api_executed": False,
        "next_decision": (
            "Anchor candidate-only raw logits and pre-API logprob taps to "
            "verified source SHA and exact function; no patch to original."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--expected-head", required=True)
    p.add_argument("--confirm-original-id", required=True)
    p.add_argument("--inspect-original", action="store_true", required=True)
    args = p.parse_args(argv)
    try:
        if args.confirm_original_id != ORIGINAL_ID:
            raise Blocked("ORIGINAL_ID_CONFIRMATION_MISMATCH")
        qsa.preflight(args.expected_head)
        result = inspect_original()
        print(json.dumps(result, ensure_ascii=True, sort_keys=True))
        return 0 if not result["source_files_missing"] else 2
    except (Blocked, qsa.Blocked, OSError, ValueError, KeyError, TypeError):
        print("P1_NUMERIC_SOURCE_TRACE_BLOCKED_OR_INCOMPLETE", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
