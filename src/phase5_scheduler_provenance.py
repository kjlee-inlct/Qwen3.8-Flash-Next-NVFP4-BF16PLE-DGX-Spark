"""Read-only Phase 5 Scheduler block-size provenance, not a runtime/patch test.

No vLLM imports, installs, monkeypatch, checkpoint access or GPU.  Only
bounded, constant-redacted AST from installed vLLM Python source is used.
Direct Scheduler() calls are *name-based candidates*, not resolved imports.
Dynamic scheduler_cls() calls cannot be proven to construct Scheduler.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from pathlib import Path

try:
    from .phase5_dependency_trace import _shape, _qualified_name, _class_method, _method_trace
    from .phase5_patch_readiness import PATHS, PIN
    from .phase5_preview_abi_audit import _safe_read
except ImportError:
    from phase5_dependency_trace import _shape, _qualified_name, _class_method, _method_trace
    from phase5_patch_readiness import PATHS, PIN
    from phase5_preview_abi_audit import _safe_read

SCAN_DIRS = ("config", "v1")
MAX_FILES = 1600
MAX_BYTES = 24 * 1024 * 1024
MAX_CALL_SITES = 48
MAX_ASSIGN_SITES = 64
MAX_FIELD_SITES = 40
DYNAMIC_CTOR_NAMES = frozenset((
    "scheduler_cls", "scheduler_class", "scheduler_cls_obj",
    "scheduler_type", "scheduler_factory", "scheduler_impl",
))
WATCHED_TARGETS = frozenset((
    "block_size", "hash_block_size", "mamba_block_size",
    "self.block_size", "self.hash_block_size",
    "self.mamba_block_size", "self.cache_config.mamba_block_size",
    "scheduler_cls", "scheduler_class", "scheduler_cls_obj",
))


def _scope(name_stack: list[str]) -> str:
    return ".".join(name_stack)[:160]


class EvidenceVisitor(ast.NodeVisitor):
    def __init__(self, relative: str):
        self.relative = relative
        self.scope: list[str] = []
        self.calls: list[dict] = []
        self.assignments: list[dict] = []
        self.field_sites: list[dict] = []
        self.truncated = False

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node: ast.Call) -> None:
        callee = _qualified_name(node.func)
        tail = callee.rsplit(".", 1)[-1]
        is_direct = tail == "Scheduler"
        is_dynamic = tail in DYNAMIC_CTOR_NAMES
        if is_direct or is_dynamic:
            if len(self.calls) >= MAX_CALL_SITES:
                self.truncated = True
            else:
                keywords = {
                    kw.arg: _shape(kw.value)
                    for kw in node.keywords
                    if kw.arg in ("block_size", "hash_block_size")
                }
                args = [_shape(x) for x in node.args[:6]]
                # Scheduler.__init__ signature observed on user's DGX:
                # (self, vllm_config, kv_cache_config,
                #  structured_output_manager, block_size, hash_block_size, ...).
                # This position is a HINT until the live source signature
                # and import binding have both been verified.
                block_arg = (keywords.get("block_size") or
                             (args[3] if is_direct and len(args) > 3 else None))
                hash_arg = (keywords.get("hash_block_size") or
                            (args[4] if is_direct and len(args) > 4 else None))
                self.calls.append({
                    "relative_path": self.relative,
                    "line": node.lineno,
                    "scope": _scope(self.scope),
                    "callee": callee,
                    "kind": ("NAME_MATCH_SCHEDULER_NOT_RESOLVED"
                             if is_direct else "DYNAMIC_CTOR_UNRESOLVED"),
                    "block_size_expr_candidate": block_arg,
                    "hash_block_size_expr_candidate": hash_arg,
                    "keywords": keywords,
                    "positional_arg_shapes": args,
                    "has_keyword_unpack": any(k.arg is None for k in node.keywords),
                })
        self.generic_visit(node)

    def _assignment(self, target: ast.AST, value: ast.AST | None, line: int) -> None:
        name = _qualified_name(target)
        call_name = _qualified_name(value.func) if isinstance(value, ast.Call) else ""
        if name not in WATCHED_TARGETS and not name.endswith(".mamba_block_size") and not (
            call_name.rsplit(".", 1)[-1] in ("lcm", "compute_lcm", "math_lcm")
        ):
            return
        if len(self.assignments) >= MAX_ASSIGN_SITES:
            self.truncated = True
            return
        self.assignments.append({
            "relative_path": self.relative,
            "line": line,
            "scope": _scope(self.scope),
            "target": name,
            "expression_shape": _shape(value) if value is not None else "<none>",
            "lcmlike_call": call_name.rsplit(".", 1)[-1] in (
                "lcm", "compute_lcm", "math_lcm"
            ),
        })

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if isinstance(target, (ast.Name, ast.Attribute)):
                self._assignment(target, node.value, node.lineno)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self._assignment(node.target, node.value, node.lineno)
        self.generic_visit(node)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self._assignment(node.target, node.value, node.lineno)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr == "mamba_block_size":
            if len(self.field_sites) >= MAX_FIELD_SITES:
                self.truncated = True
            else:
                self.field_sites.append({
                    "relative_path": self.relative, "line": node.lineno,
                    "scope": _scope(self.scope),
                    "kind": "STORE" if isinstance(node.ctx, ast.Store) else "LOAD",
                    "reference": _qualified_name(node),
                })
        self.generic_visit(node)


def _core_methods(root: Path) -> dict:
    out = {}
    for label, cls, funcs in (
        ("scheduler", "Scheduler", ("__init__", "_mamba_block_aligned_split",
                                    "_get_local_prefix_cache_hit")),
        ("mamba", "MambaHybridModelState", ("add_request", "preprocess_state",
                                           "postprocess_state")),
    ):
        data, status = _safe_read(root, root / PATHS[label])
        if data is None:
            out[label] = {"state": status}
            continue
        try:
            tree = ast.parse(data.decode("utf-8"))
        except (UnicodeError, ValueError, SyntaxError):
            out[label] = {"state": "UNPARSEABLE"}
            continue
        out[label] = {
            "state": "PARSEABLE_ONLY",
            "sha256": hashlib.sha256(data).hexdigest(),
            "methods": {
                f: (_method_trace(node) if (node := _class_method(tree, cls, f))
                    else None)
                for f in funcs
            },
        }
    return out


def inspect(root: Path) -> dict:
    if not root.is_dir() or root.is_symlink():
        return {"status": "INVALID_ROOT", "patch_approved": False}
    root = root.resolve()
    candidates = []
    for sub in SCAN_DIRS:
        directory = root / sub
        if directory.is_dir() and not directory.is_symlink():
            candidates.extend(sorted(directory.rglob("*.py")))
    candidates = sorted(set(candidates))
    complete = len(candidates) <= MAX_FILES
    calls: list[dict] = []
    assignments: list[dict] = []
    fields: list[dict] = []
    unreadable = 0
    visited = 0
    nbytes = 0
    exceeded: list[str] = []
    if not complete:
        exceeded.append("FILE_LIMIT")
    for path in candidates[:MAX_FILES]:
        data, state = _safe_read(root, path)
        if data is None:
            unreadable += 1
            continue
        if nbytes + len(data) > MAX_BYTES:
            complete = False
            exceeded.append("BYTE_LIMIT")
            break
        nbytes += len(data)
        visited += 1
        if not any(token in data for token in (
            b"Scheduler", b"scheduler_cls", b"scheduler_class",
            b"scheduler_type", b"scheduler_factory", b"scheduler_impl",
            b"block_size", b"lcm",
        )):
            continue
        try:
            tree = ast.parse(data.decode("utf-8"))
        except (SyntaxError, ValueError, UnicodeError):
            unreadable += 1
            continue
        v = EvidenceVisitor(str(path.relative_to(root)))
        v.visit(tree)
        # Reserve one global slice per kind rather than accidentally presenting
        # a fully populated call list as a complete package scan.
        for dest, src, bound, label in (
            (calls, v.calls, MAX_CALL_SITES, "CALL_SITE_LIMIT"),
            (assignments, v.assignments, MAX_ASSIGN_SITES, "ASSIGN_SITE_LIMIT"),
            (fields, v.field_sites, MAX_FIELD_SITES, "FIELD_SITE_LIMIT"),
        ):
            if len(dest) + len(src) > bound:
                complete = False
                if label not in exceeded:
                    exceeded.append(label)
            dest.extend(src[:max(bound-len(dest), 0)])
        if v.truncated:
            complete = False
            if "PER_FILE_LIMIT" not in exceeded:
                exceeded.append("PER_FILE_LIMIT")
    if unreadable:
        complete = False
        exceeded.append("UNREADABLE_OR_UNPARSEABLE")
    core = _core_methods(root)
    direct = sum(c["kind"] == "NAME_MATCH_SCHEDULER_NOT_RESOLVED" for c in calls)
    dynamic = sum(c["kind"] == "DYNAMIC_CTOR_UNRESOLVED" for c in calls)
    return {
        "status": "SOURCE_EVIDENCE_ONLY_NOT_BLOCK_SIZE_PROVEN",
        "pinned_blazux": PIN,
        "patch_approved": False,
        "scan": {
            "state": "COMPLETE_IN_SCANNED_SCOPE" if complete else "PARTIAL",
            "directories": list(SCAN_DIRS),
            "candidate_py_files": len(candidates),
            "visited": visited,
            "bytes": nbytes,
            "unreadable_or_unparseable": unreadable,
            "limits": sorted(set(exceeded)),
        },
        "scheduler_constructor_candidates": {
            "direct_name_matches": direct,
            "dynamic_unresolved": dynamic,
            "sites": calls,
        },
        "block_assignments": assignments,
        "mamba_field_references": fields,
        "core_method_traces": core,
        "next_gate": (
            "Resolve Scheduler factory/class binding and block_size caller; "
            "check hybrid group LCM and Mamba state slot before any patch."
        ),
    }


def main() -> None:
    spec = importlib.util.find_spec("vllm")
    if spec is None or not spec.submodule_search_locations:
        raise SystemExit("BLOCKED: installed vLLM source root unavailable")
    roots = list(spec.submodule_search_locations)
    if len(roots) != 1:
        raise SystemExit("BLOCKED: ambiguous installed vLLM source roots")
    result = inspect(Path(roots[0]))
    if result["status"] != "SOURCE_EVIDENCE_ONLY_NOT_BLOCK_SIZE_PROVEN":
        raise SystemExit("BLOCKED: invalid vLLM source root")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    print("PHASE5_SCHEDULER_PROVENANCE_SOURCE_ONLY_DONE_NOT_PATCH_APPROVED")


if __name__ == "__main__":
    main()
