"""Phase 5: narrow, import-free source-only Scheduler block-size flow triage.

This inspects ONLY a fixed set of installed preview vLLM .py files, never
imports vLLM or model code, changes files, reads weights, or invokes GPU.
An AST chain is a syntactic candidate, NOT proven runtime equivalence or
permission to apply any blazux patch.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from pathlib import Path

try:
    from .phase5_dependency_trace import _shape, _qualified_name, _method_trace
    from .phase5_patch_readiness import PIN
    from .phase5_preview_abi_audit import _safe_read
except ImportError:
    from phase5_dependency_trace import _shape, _qualified_name, _method_trace
    from phase5_patch_readiness import PIN
    from phase5_preview_abi_audit import _safe_read

PATHS = {
    "engine_core": "v1/engine/core.py",
    "kv_utils": "v1/core/kv_cache_utils.py",
    "scheduler": "v1/core/sched/scheduler.py",
    "mamba_worker": "v1/worker/gpu/model_states/mamba_hybrid.py",
    "mamba_backend": "v1/attention/backends/mamba_attn.py",
    "cache_config": "config/cache.py",
}
WATCHED_NAMES = frozenset({
    "scheduler_block_size", "hash_block_size", "group_block_sizes",
    "hashing_sizes", "block_size", "mamba_block_size",
    "self.block_size", "self.hash_block_size",
    "self.cache_config.block_size", "self.cache_config.mamba_block_size",
})
WATCHED_CALLEES = frozenset({
    "resolve_kv_cache_block_sizes", "Scheduler", "lcm", "gcd",
})
MAX_METHODS = 32
MAX_RECORDS = 64
MAX_SHAPE = 160


def _target_names(node: ast.AST) -> list[str]:
    if isinstance(node, (ast.Tuple, ast.List)):
        return [name for part in node.elts for name in _target_names(part)]
    name = _qualified_name(node)
    return [name] if name else []


def _imports(tree: ast.Module) -> dict[str, str]:
    """Static source import declarations; not a full Python binder."""
    found: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                if alias.name != "*":
                    found[alias.asname or alias.name] = (
                        f"{module}.{alias.name}"
                    )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                found[alias.asname or alias.name.split(".")[0]] = alias.name
    return found


def _method_matches(method: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(
        isinstance(x, ast.Name) and x.id in (
            "scheduler_block_size", "hash_block_size",
            "resolve_kv_cache_block_sizes",
        )
        for x in ast.walk(method)
    ) or any(
        isinstance(x, ast.Call) and _qualified_name(x.func).rsplit(".", 1)[-1]
        in ("Scheduler", "resolve_kv_cache_block_sizes")
        for x in ast.walk(method)
    )


def _bounded_append(items: list, item: dict, warnings: list[str],
                    label: str) -> None:
    if len(items) < MAX_RECORDS:
        items.append(item)
    elif label not in warnings:
        warnings.append(label)


def _trace_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict:
    assignments: list[dict] = []
    calls: list[dict] = []
    returns: list[dict] = []
    warnings: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
            targets = (child.targets if isinstance(child, ast.Assign)
                       else [child.target])
            names = [n for target in targets for n in _target_names(target)]
            value = child.value
            vcall = _qualified_name(value.func) if isinstance(value, ast.Call) else ""
            if (any(x in WATCHED_NAMES for x in names)
                    or vcall.rsplit(".", 1)[-1] in WATCHED_CALLEES
                    or any("block_size" in x for x in names)):
                _bounded_append(assignments, {
                    "line": child.lineno,
                    "targets": names[:12],
                    "value_shape": _shape(value)[:MAX_SHAPE],
                    "callee_if_call": vcall,
                }, warnings, "ASSIGNMENT_CAP")
        elif isinstance(child, ast.Call):
            callee = _qualified_name(child.func)
            name = callee.rsplit(".", 1)[-1]
            is_group_append = (
                isinstance(child.func, ast.Attribute)
                and child.func.attr == "append"
                and _qualified_name(child.func.value) in (
                    "group_block_sizes", "hashing_sizes"
                )
            )
            if name in WATCHED_CALLEES or is_group_append:
                _bounded_append(calls, {
                    "line": child.lineno, "callee": callee,
                    "args": [_shape(x)[:MAX_SHAPE] for x in child.args[:10]],
                    "kwargs": {x.arg: _shape(x.value)[:MAX_SHAPE]
                               for x in child.keywords if x.arg in
                               ("block_size", "hash_block_size")},
                    "has_kw_unpack": any(x.arg is None for x in child.keywords),
                }, warnings, "CALL_CAP")
        elif isinstance(child, ast.Return) and child.value is not None:
            _bounded_append(returns, {
                "line": child.lineno, "value_shape": _shape(child.value)[:MAX_SHAPE],
                "names": _target_names(child.value),
            }, warnings, "RETURN_CAP")
    return {
        "line_start": node.lineno, "line_end": node.end_lineno,
        "signature": [x.arg for x in (node.args.posonlyargs
                                     + node.args.args + node.args.kwonlyargs)],
        "assignments": assignments, "calls": calls,
        "returns": returns, "limits": warnings,
    }


def _named_function(tree: ast.Module, name: str):
    return next((node for node in tree.body
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and node.name == name), None)


def _class_methods(tree: ast.Module, class_name: str):
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return [x for x in node.body if isinstance(
                x, (ast.FunctionDef, ast.AsyncFunctionDef))]
    return []


def _inspect_file(root: Path, label: str, relative: str) -> dict:
    data, status = _safe_read(root, root / relative)
    if data is None:
        return {"state": status, "relative_path": relative}
    sha = hashlib.sha256(data).hexdigest()
    try:
        tree = ast.parse(data.decode("utf-8"))
    except (UnicodeError, ValueError, SyntaxError):
        return {"state": "UNPARSEABLE", "relative_path": relative, "sha256": sha}
    result = {
        "state": "PARSEABLE_ONLY", "relative_path": relative,
        "sha256": sha,
    }
    if label == "engine_core":
        methods = _class_methods(tree, "EngineCore")
        relevant = [m for m in methods if _method_matches(m)]
        result["imports_of_interest"] = {
            k: v for k, v in _imports(tree).items()
            if (k in ("Scheduler", "resolve_kv_cache_block_sizes")
                or v.endswith((".Scheduler", ".resolve_kv_cache_block_sizes")))
        }
        result["methods"] = {
            m.name: _trace_function(m) for m in relevant[:MAX_METHODS]
        }
        result["method_limit"] = len(relevant) > MAX_METHODS
    elif label == "kv_utils":
        fn = _named_function(tree, "resolve_kv_cache_block_sizes")
        result["function"] = _trace_function(fn) if fn else None
        result["imports_of_interest"] = {
            k: v for k, v in _imports(tree).items()
            if k in ("math", "lcm", "gcd")
        }
    elif label in ("scheduler", "mamba_worker", "mamba_backend", "cache_config"):
        name, methods = {
            "scheduler": ("Scheduler", ("__init__", "_mamba_block_aligned_split")),
            "mamba_worker": ("MambaHybridModelState",
                             ("add_request", "preprocess_state", "postprocess_state")),
            "mamba_backend": ("BaseMambaAttentionMetadataBuilder",
                              ("_compute_common_metadata",)),
            "cache_config": ("CacheConfig", ("_apply_block_size_default",)),
        }[label]
        found = {m.name: m for m in _class_methods(tree, name)}
        result["method_traces"] = {
            method: (_method_trace(found[method]) if method in found else None)
            for method in methods
        }
    return result


def _static_candidate(files: dict[str, dict]) -> dict:
    """Gate is conservative and explicitly does NOT certify value flow."""
    engine = files["engine_core"]
    kv = files["kv_utils"]
    missing = []
    if engine["state"] != "PARSEABLE_ONLY":
        missing.append("ENGINE_CORE_UNAVAILABLE")
    if kv["state"] != "PARSEABLE_ONLY":
        missing.append("KV_UTILS_UNAVAILABLE")
    if missing:
        return {"status": "INSUFFICIENT_SOURCE", "missing": missing,
                "runtime_flow_proven": False}
    kvfn = kv.get("function")
    methods = engine.get("methods", {})
    engine_traces = list(methods.values())
    imported_resolver = any(
        x.endswith(".kv_cache_utils.resolve_kv_cache_block_sizes")
        for x in engine.get("imports_of_interest", {}).values()
    )
    imported_scheduler = any(
        x.endswith(".sched.scheduler.Scheduler")
        for x in engine.get("imports_of_interest", {}).values()
    )
    has_lcm = bool(kvfn and any(
        "scheduler_block_size" in x["targets"]
        and x["callee_if_call"] in ("math.lcm", "lcm")
        for x in kvfn["assignments"]
    ))
    has_tuple_return = bool(kvfn and any(
        set(("scheduler_block_size", "hash_block_size")) <= set(x["names"])
        for x in kvfn["returns"]
    ))
    has_consumer_assignment = any(
        any("scheduler_block_size" in x["targets"]
            and x["callee_if_call"] in (
                "resolve_kv_cache_block_sizes",
                "kv_cache_utils.resolve_kv_cache_block_sizes",
            ) for x in v["assignments"])
        for v in engine_traces
    )
    has_ctor = any(
        any(x["callee"].rsplit(".", 1)[-1] == "Scheduler"
            and x["kwargs"].get("block_size") == "scheduler_block_size"
            for x in v["calls"])
        for v in engine_traces
    )
    checks = {
        "engine_static_imports_resolver": imported_resolver,
        "engine_static_imports_scheduler": imported_scheduler,
        "kv_scheduler_size_lcm_assignment": has_lcm,
        "kv_function_returns_both_sizes": has_tuple_return,
        "engine_assigns_scheduler_size_from_resolver": has_consumer_assignment,
        "engine_ctor_uses_scheduler_size_variable": has_ctor,
    }
    failures = sorted(k for k, ok in checks.items() if not ok)
    limits = (
        engine.get("method_limit", False) or
        any(v["limits"] for v in engine_traces) or
        (bool(kvfn) and bool(kvfn["limits"]))
    )
    return {
        "status": ("STATIC_CHAIN_CANDIDATE_NOT_RUNTIME_CERTIFIED"
                   if not failures and not limits else
                   "UNRESOLVED_OR_PARTIAL_STATIC_CHAIN"),
        "checks": checks, "missing": failures,
        "bounded_output_truncated": bool(limits),
        "runtime_flow_proven": False,
    }


def inspect(root: Path) -> dict:
    if not root.is_dir() or root.is_symlink():
        return {"status": "INVALID_ROOT", "patch_approved": False}
    root = root.resolve()
    files = {
        label: _inspect_file(root, label, relative)
        for label, relative in PATHS.items()
    }
    return {
        "status": "NARROW_SOURCE_AST_ONLY_NOT_ABI_OR_CACHE_CERTIFIED",
        "pinned_blazux": PIN,
        "patch_approved": False,
        "files": files, "static_chain": _static_candidate(files),
        "next_gate": (
            "Review any unresolved engine assignment/import/return chain; "
            "then correlate actual KV group specs with Mamba seed and "
            "preprocess/postprocess slot alignment using isolated fixtures."
        ),
    }


def main() -> None:
    spec = importlib.util.find_spec("vllm")
    if spec is None or not spec.submodule_search_locations:
        raise SystemExit("BLOCKED: installed vLLM root unavailable")
    roots = list(spec.submodule_search_locations)
    if len(roots) != 1:
        raise SystemExit("BLOCKED: ambiguous installed vLLM root")
    result = inspect(Path(roots[0]))
    if result["status"] != "NARROW_SOURCE_AST_ONLY_NOT_ABI_OR_CACHE_CERTIFIED":
        raise SystemExit("BLOCKED: invalid package root")
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    print("PHASE5_NARROW_BLOCK_FLOW_DONE_NOT_PATCH_APPROVED")


if __name__ == "__main__":
    main()
