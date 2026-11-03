"""Read-only P2 witness missing-event source audit, no GPU or service changes.

Distingishes exact source installation and static guard gates from unknown
runtime branch observations. Never asserts a numeric cause from static AST.
Original running container is only accessed by docker inspect + docker cp.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import sys

from src import p1_numeric_source_trace as trace
from src import p1_preview_qsa_exact_topk as qsa
from src import p2_numeric_first_divergence_window as window
from src import p2_numeric_sampler_witness as witness

class AuditBlocked(RuntimeError):
    pass

MAX_STAGE_SOURCE = 2_000_000



def original_forward_flow(raw: bytes) -> dict:
    """Read-only AST-only map of the exact original Sampler.forward's guard sites.

    The only output is variable/AST-node types and source line numbers; not
    executable statements, user prompts, token contents, logits, or tensors.
    The site map does not reveal which branch actually ran on a GPU.
    """
    if not 0 < len(raw) <= MAX_STAGE_SOURCE:
        raise AuditBlocked("SAMPLER_FORWARD_SOURCE_SIZE_INVALID")
    try:
        tree = ast.parse(raw.decode("utf-8"))
    except (UnicodeError, SyntaxError):
        raise AuditBlocked("SAMPLER_FORWARD_SOURCE_AST_INVALID") from None
    interested = {"num_logprobs", "raw_logprobs", "processed_logprobs",
                  "logprobs_mode"}
    functions = [
        n for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and n.name == "forward"
        and any(isinstance(a, ast.Attribute) and a.attr == "max_num_logprobs"
                for a in ast.walk(n))
    ]
    if len(functions) != 1:
        raise AuditBlocked("SAMPLER_FORWARD_AMBIGUOUS")
    fn = functions[0]

    def names(node: ast.AST) -> list[str]:
        return sorted({x.id for x in ast.walk(node)
                       if isinstance(x, ast.Name) and x.id in interested})

    sites = []
    for node in ast.walk(fn):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            target_names = sorted({name for target in targets
                                   for name in names(target)})
            if target_names:
                sites.append({"line": node.lineno, "kind": "assignment",
                              "targets": target_names,
                              "rhs_ast_type": type(node.value).__name__})
        elif isinstance(node, (ast.If, ast.While)):
            target_names = names(node.test)
            if target_names:
                sites.append({"line": node.lineno, "kind": "conditional",
                              "referenced_names": target_names,
                              "test_ast_type": type(node.test).__name__})
    sites.sort(key=lambda entry: (entry["line"], entry["kind"]))
    return {
        "site_count": len(sites),
        "sites": sites[:48],
        "sites_truncated": len(sites) > 48,
        "runtime_assignment_values_observed": False,
        "runtime_branches_observed": False,
        "runtime_worker_process_observed": False,
    }

def audit_source(raw: bytes, staged: bytes) -> dict:
    """Verify full installed original Sampler SHA, patch bytes and guard paths."""
    if hashlib.sha256(raw).hexdigest() != witness.SOURCE_SHA256:
        raise AuditBlocked("ORIGINAL_SAMPLER_SOURCE_SHA_DRIFT")
    expected = witness.transform(raw)
    if staged != expected:
        raise AuditBlocked("STAGED_SAMPLER_DIFFERS_FROM_EXACT_PINNED_TRANSFORM")
    if not 0 < len(staged) <= MAX_STAGE_SOURCE:
        raise AuditBlocked("STAGED_SAMPLER_SIZE_INVALID")
    try:
        tree = ast.parse(staged.decode("utf-8"))
    except (UnicodeError, SyntaxError):
        raise AuditBlocked("STAGED_SAMPLER_AST_INVALID") from None
    guards = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.If)
        and isinstance(n.test, ast.BoolOp)
        and any(isinstance(x, ast.Name) and x.id == "_P2_WITNESS_ENABLED"
                for x in ast.walk(n.test))
    ]
    capture_calls = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and n.func.id == "_p2_witness_capture"
    ]
    emit_calls = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and n.func.id == "_p2_witness_emit"
    ]
    if len(capture_calls) != 1 or len(emit_calls) != 1 or len(guards) != 2:
        raise AuditBlocked("WITNESS_STATIC_GUARD_TOPOLOGY_DRIFT")
    required = (
        'if processed is not None or mode != "raw_logprobs":',
        "if (logits.ndim != 2 or logprobs.ndim != 2 or",
        "if (sampled.ndim != 1 or sampled.shape[0] != 1 or",
        '_P2_WITNESS_ENABLED = _p2_os.environ.get("VLLM_P2_NUMERIC_WITNESS", "0") == "1"',
        '_P2_WITNESS_FILE = "/tmp/p2-numeric-witness.jsonl"',
    )
    if any(entry not in witness.HELPER or entry not in staged.decode("utf-8")
           for entry in required):
        raise AuditBlocked("WITNESS_HELPER_GUARD_MISSING_OR_CHANGED")
    source_lines = staged.decode("utf-8").splitlines()
    return {
        "status": "P2_NUMERIC_WITNESS_STATIC_GATES_VERIFIED_RUNTIME_UNKNOWN",
        "original_sampler_sha256": hashlib.sha256(raw).hexdigest(),
        "staged_sampler_sha256": hashlib.sha256(staged).hexdigest(),
        "exact_original_pinned_transform_matches_stage": True,
        "witness_enable_default_off": True,
        "capture_call_line": capture_calls[0].lineno,
        "emit_call_line": emit_calls[0].lineno,
        "original_sampler_forward_flow": original_forward_flow(raw),
        "runtime_env_candidate_worker_verified": False,
        "runtime_sampler_import_verified": False,
        "runtime_raw_logprobs_branch_verified": False,
        "runtime_num_logprobs_not_none_verified": False,
        "runtime_single_row_shape_verified": False,
        "runtime_processed_logprobs_none_verified": False,
        "static_suppression_conditions": [
            "VLLM_P2_NUMERIC_WITNESS_MUST_BE_1_IN_WORKER",
            "SAMPLER_RAW_LOGPROBS_BRANCH_AND_REQUEST_MAX_LOGPROBS_REQUIRED",
            "SINGLE_ROW_LOGITS_AND_LOGPROBS_REQUIRED",
            "PROCESSED_LOGPROBS_MUST_BE_NONE_FOR_EMISSION",
            "WORKER_PRIVATE_FILE_OR_STDERR_MUST_BE_COLLECTABLE",
        ],
        "numeric_root_cause_located": False,
        "candidate_gpu_or_http_executed": False,
        "original_modified": False,
        "note": "Static reachability only; actual missing-event cause remains unknown",
    }


def read_only_audit(stage: Path) -> dict:
    before = trace.original_identity()
    try:
        window.verify_minimal_stage(stage)
        # Read original *running* container's installed Python source;
        # neither execute a command inside it nor change files.
        raw = trace._run_docker_cp(trace.SOURCES["sampler"])
        f = stage / "sampler.py"
        if f.is_symlink() or not f.is_file():
            raise AuditBlocked("SAMPLER_STAGE_UNSAFE")
        staged = f.read_bytes()
        report = audit_source(raw, staged)
    finally:
        if trace.original_identity() != before:
            raise AuditBlocked("ORIGINAL_STARTED_AT_DRIFT_DURING_READ_ONLY_AUDIT")
    report.update({
        "original_same_id_running_verified": True,
        "stage_read_only_verified": True,
        "service_stop_or_restart_performed": False,
    })
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--stage", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        qsa.preflight(args.expected_head)
        result = read_only_audit(args.stage)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (AuditBlocked, witness.Blocked, window.Blocked, trace.Blocked,
            qsa.Blocked, OSError, ValueError, KeyError, TypeError):
        print("P2_NUMERIC_WITNESS_STATIC_AUDIT_BLOCKED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
