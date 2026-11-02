"""P2 exact-pinned installed Preview MTP head/loader ABI source audit.

Reads only known Python files from the running original using existing bounded
docker cp. Does not import vLLM, torch, model, or load any weights.
The returned AST names are *hints*; full loader/acceptance ABI remains blocked.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys

from src import p2_functional_bundle as bundle
from src import p1_numeric_source_trace as trace
from src import p1_preview_qsa_exact_topk as qsa

MTPS = {
    "vllm/models/qwen3_8_flash_next/nvidia/mtp.py":
        "d1ee05d4ec35360a9a801f7ef5271e8e4cda458a9c754058899441fa1e7bd0d6",
    "vllm/models/qwen3_8_flash_next/nvidia/model.py":
        "e74a0bf92ed73306ed28366543b00255b23ac7ec3f705b600ff0c8874442f0c6",
    "vllm/v1/spec_decode/eagle.py":
        "b2b1f7d15117b43108be368756d9c6e9334d9415a070e46178e18bb7c6476378",
}
OPTIONAL_UNVERIFIED = "vllm/models/qwen4_exp.py"
CORE_CLASSES = ("Qwen3_8FlashNextMultiTokenPredictor",
                "Qwen3_8FlashNextMTP")
METHODS = ("__init__", "compute_logits", "load_weights", "forward")
TAGS = ("lm_head", "logits_processor", "vocab_size", "output_layer",
        "embed_tokens", "embedding", "draft", "target", "mtp", "tied", "quant")


class Blocked(RuntimeError):
    pass


def _limited(values: set[str], cap: int = 48) -> dict:
    result = sorted(values)
    return {"names": result[:cap], "truncated": len(result) > cap}


def source_surface(data: bytes, *, selected: tuple[str, ...] = CORE_CLASSES) -> dict:
    if not 0 < len(data) <= trace.MAX_SOURCE_BYTES:
        raise Blocked("PINNED_SOURCE_SIZE_INVALID")
    try:
        tree = ast.parse(data.decode("utf-8"))
    except (SyntaxError, UnicodeError):
        raise Blocked("PINNED_SOURCE_INVALID_AST") from None
    matches = {}
    for cls in (n for n in tree.body if isinstance(n, ast.ClassDef)):
        if cls.name not in selected:
            continue
        methods = {}
        for fn in (n for n in cls.body
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and n.name in METHODS):
            attrs = set()
            calls = set()
            assigned = set()
            for n in ast.walk(fn):
                if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name):
                    if n.value.id == "self" and any(tag in n.attr.lower() for tag in TAGS):
                        attrs.add("self." + n.attr)
                    if isinstance(n.ctx, ast.Store) and n.value.id == "self":
                        assigned.add("self." + n.attr)
                if isinstance(n, ast.Call):
                    f = n.func
                    if isinstance(f, ast.Attribute):
                        # Only a token representing a method name; not code or args.
                        if any(tag in f.attr.lower() for tag in TAGS) or f.attr in (
                                "load_weights", "compute_logits", "forward", "index_select"):
                            calls.add(f.attr)
                    elif isinstance(f, ast.Name) and any(tag in f.id.lower() for tag in TAGS):
                        calls.add(f.id)
            methods[fn.name] = {
                "args": [x.arg for x in fn.args.posonlyargs + fn.args.args
                         + fn.args.kwonlyargs][:24],
                "referenced_self_attributes": _limited(attrs),
                "assigned_self_attributes": _limited(assigned),
                "selected_call_names": _limited(calls),
                "ast_sha256": hashlib.sha256(ast.dump(fn, include_attributes=False).encode()).hexdigest(),
            }
        matches[cls.name] = methods
    return {
        "sha256": hashlib.sha256(data).hexdigest(),
        "classes": matches,
        "source_hints_only": True,
        "head_ownership_proven": False,
        "draft_logits_remap_verified": False,
        "acceptance_integration_verified": False,
    }


def check_pinned_sources(reader=bundle._read_mtp_source) -> dict:
    report = {}
    for path, pinned in MTPS.items():
        data = reader(path)
        if data is None or hashlib.sha256(data).hexdigest() != pinned:
            raise Blocked("PINNED_INSTALLED_MTP_SOURCE_DRIFT")
        report[path] = source_surface(data)
    optional = reader(OPTIONAL_UNVERIFIED)
    report[OPTIONAL_UNVERIFIED] = {
        "status": "UNVERIFIED_OPTIONAL_SOURCE_NOT_NEEDED_FOR_PINNED_CORE",
        "found": optional is not None,
        "sha256": hashlib.sha256(optional).hexdigest() if optional is not None else None,
    }
    mtp = report["vllm/models/qwen3_8_flash_next/nvidia/mtp.py"]["classes"]
    for cls, methods in (("Qwen3_8FlashNextMultiTokenPredictor",
                          ("__init__", "forward", "load_weights")),
                         ("Qwen3_8FlashNextMTP",
                          ("__init__", "forward", "compute_logits", "load_weights"))):
        if cls not in mtp or any(method not in mtp[cls] for method in methods):
            raise Blocked("PINNED_CORE_MTP_METHOD_ABI_DRIFT")
    return {
        "status": "P2_PINNED_MTP_AST_SURFACE_VERIFIED_NOT_RUNTIME_CONNECTED",
        "pinned_source_files": len(MTPS),
        "source_surfaces": report,
        "reduced_head_wired": False,
        "target_head_immutable": True,
        "runtime_candidate_or_gpu_executed": False,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--expected-head", required=True)
    p.add_argument("--confirm-original-id", required=True)
    p.add_argument("--read-installed", action="store_true", required=True)
    a = p.parse_args(argv)
    try:
        qsa.preflight(a.expected_head)
        if a.confirm_original_id != trace.ORIGINAL_ID:
            raise Blocked("EXACT_ORIGINAL_CONTAINER_ID_REQUIRED")
        before = trace.original_identity()
        try:
            bundle.inspect_local_base_image()
            output = check_pinned_sources()
        finally:
            if trace.original_identity() != before:
                raise Blocked("ORIGINAL_CONTAINER_ID_OR_STARTED_AT_CHANGED") from None
        print(json.dumps(output, sort_keys=True))
        return 0
    except (Blocked, bundle.Blocked, trace.Blocked, qsa.Blocked,
            OSError, ValueError, TypeError, KeyError):
        print("P2_PINNED_MTP_ABI_AUDIT_BLOCKED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
