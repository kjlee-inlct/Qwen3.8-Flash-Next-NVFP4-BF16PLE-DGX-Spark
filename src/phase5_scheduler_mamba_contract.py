"""Phase5 source-only Scheduler factory and Mamba block-unit contract.

READ ONLY: inspect six fixed Python source files inside an installed vLLM
package without importing vLLM. No patching, model files, GPU or networking.
Synthetic slot arithmetic is illustrative, NOT a test of actual CUDA kernels.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from pathlib import Path

try:
    from .phase5_dependency_trace import _qualified_name, _shape
    from .phase5_patch_readiness import PIN
    from .phase5_preview_abi_audit import _safe_read
except ImportError:
    from phase5_dependency_trace import _qualified_name, _shape
    from phase5_patch_readiness import PIN
    from phase5_preview_abi_audit import _safe_read

FILES = {
    "scheduler_config": "config/scheduler.py",
    "engine_core": "v1/engine/core.py",
    "scheduler": "v1/core/sched/scheduler.py",
    "mamba_worker": "v1/worker/gpu/model_states/mamba_hybrid.py",
    "mamba_backend": "v1/attention/backends/mamba_attn.py",
    "cache_config": "config/cache.py",
}
METHODS = {
    "scheduler_config": ("SchedulerConfig", ("get_scheduler_cls",)),
    "engine_core": ("EngineCore", ("__init__",)),
    "scheduler": ("Scheduler", ("__init__", "_mamba_block_aligned_split")),
    "mamba_worker": ("MambaHybridModelState", (
        "add_request", "_get_mamba_group_info",
        "_ensure_align_ctx", "preprocess_state", "postprocess_state")),
    "mamba_backend": ("BaseMambaAttentionMetadataBuilder",
                      ("_compute_common_metadata",)),
    "cache_config": ("CacheConfig", ("__post_init__",)),
}
MAX_EVENTS = 24


def _method(tree: ast.Module, cls: str, name: str):
    for item in tree.body:
        if isinstance(item, ast.ClassDef) and item.name == cls:
            for member in item.body:
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if member.name == name:
                        return member
    return None


def _called(method, name: str) -> bool:
    return method is not None and any(
        isinstance(n, ast.Call) and _qualified_name(n.func) == name
        for n in ast.walk(method)
    )


def _assigned(method, target: str, value_call: str) -> bool:
    if method is None:
        return False
    return any(
        isinstance(n, ast.Assign)
        and any(_qualified_name(t) == target for t in n.targets)
        and isinstance(n.value, ast.Call)
        and _qualified_name(n.value.func) == value_call
        for n in ast.walk(method)
    )


def _uses_keyword(method, call: str, keyword: str, expr: str) -> bool:
    return method is not None and any(
        isinstance(n, ast.Call) and _qualified_name(n.func) == call
        and any(k.arg == keyword and _qualified_name(k.value) == expr
                for k in n.keywords)
        for n in ast.walk(method)
    )


def _has_divisor(method, divisor: str) -> bool:
    return method is not None and any(
        isinstance(n, ast.BinOp) and isinstance(n.op, ast.FloorDiv)
        and _qualified_name(n.right) == divisor
        for n in ast.walk(method)
    )


def _has_assignment(method, target: str, rhs: str) -> bool:
    return method is not None and any(
        isinstance(n, (ast.Assign, ast.AnnAssign))
        and (any(_qualified_name(t) == target for t in n.targets)
             if isinstance(n, ast.Assign)
             else _qualified_name(n.target) == target)
        and n.value is not None and _qualified_name(n.value) == rhs
        for n in ast.walk(method)
    )


def _compares_group_blocks(method) -> bool:
    return method is not None and any(
        isinstance(n, ast.Compare)
        and _qualified_name(n.left) == "spec.block_size"
        and any(_qualified_name(c) == "mamba_spec.block_size"
                for c in n.comparators)
        for n in ast.walk(method)
    )


def _events(method) -> dict:
    if method is None:
        return {"state": "METHOD_ABSENT"}
    matched = []
    count = 0
    # Bounded, constant-redacted expressions: not original source excerpts.
    for n in ast.walk(method):
        target = ""
        if isinstance(n, ast.Return) and n.value is not None:
            target = "return"
            expr = n.value
        elif isinstance(n, ast.Call):
            name = _qualified_name(n.func)
            if not any(k in name for k in (
                "scheduler_cls", "Scheduler", "align", "precopy",
                "postprocess", "mamba_group", "block_size"
            )):
                continue
            target, expr = "call", n
        elif isinstance(n, ast.BinOp) and isinstance(n.op, ast.FloorDiv):
            target, expr = "floor_div", n
        elif isinstance(n, ast.Assign):
            if not any("block_size" in _qualified_name(t) or
                       _qualified_name(t) == "Scheduler" for t in n.targets):
                continue
            target, expr = "assignment", n.value
        else:
            continue
        count += 1
        if len(matched) < MAX_EVENTS:
            matched.append({
                "line": n.lineno, "kind": target,
                "shape": _shape(expr)[:160],
            })
    return {
        "state": "SOURCE_AST_ONLY",
        "line_start": method.lineno,
        "line_end": method.end_lineno,
        "parameters": [
            a.arg for a in method.args.posonlyargs + method.args.args
            + method.args.kwonlyargs
        ],
        "events": matched,
        "events_seen": count,
        "events_truncated": count > MAX_EVENTS,
    }


def _load(root: Path) -> tuple[dict, dict]:
    summaries: dict = {}
    methods: dict = {}
    for label, relative in FILES.items():
        data, state = _safe_read(root, root / relative)
        if data is None:
            summaries[label] = {"state": state, "path": relative}
            methods[label] = {}
            continue
        sha = hashlib.sha256(data).hexdigest()
        try:
            tree = ast.parse(data.decode("utf-8"), filename=relative)
        except (SyntaxError, ValueError, UnicodeError):
            summaries[label] = {
                "state": "UNPARSEABLE", "path": relative, "sha256": sha
            }
            methods[label] = {}
            continue
        cls, wanted = METHODS[label]
        found = {name: _method(tree, cls, name) for name in wanted}
        methods[label] = found
        summaries[label] = {
            "state": "PARSEABLE_ONLY",
            "path": relative,
            "sha256": sha,
            "methods": {name: _events(fn) for name, fn in found.items()},
        }
    return summaries, methods


def synthetic_seed_oracle(
    config_block_size: int,
    mamba_block_size: int,
    computed_positions: tuple[int, ...] = (1, 15, 16, 17, 31, 32, 33, 48, 49, 64),
) -> dict:
    """Illustrates numerator/denominator sensitivity, NOT real slot mapping."""
    if (type(config_block_size) is not int or
            type(mamba_block_size) is not int or
            config_block_size <= 0 or mamba_block_size <= 0):
        raise ValueError("positive integer block sizes required")
    if not computed_positions or len(computed_positions) > 64 or any(
        type(n) is not int or n <= 0 or n > 1_000_000 for n in computed_positions
    ):
        raise ValueError("bounded positive synthetic token positions required")
    different = []
    for n in computed_positions:
        config_index = (n - 1) // config_block_size
        spec_index = (n - 1) // mamba_block_size
        if config_index != spec_index:
            different.append({
                "tokens": n, "config_seed_index": config_index,
                "spec_reference_index": spec_index,
            })
    return {
        "status": "SYNTHETIC_INDEX_ARITHMETIC_ONLY",
        "config_block_size": config_block_size,
        "mamba_block_size": mamba_block_size,
        "positions_checked": len(computed_positions),
        "different_index_positions": different,
        "not_runtime_or_kernel_certification": True,
    }


def inspect(root: Path) -> dict:
    if not root.is_dir() or root.is_symlink():
        return {"status": "INVALID_ROOT", "patch_approved": False}
    summaries, methods = _load(root.resolve())
    factory = methods["scheduler_config"].get("get_scheduler_cls")
    engine = methods["engine_core"].get("__init__")
    worker = methods["mamba_worker"]
    scheduler = methods["scheduler"].get("_mamba_block_aligned_split")
    pre = worker.get("preprocess_state")
    group = worker.get("_get_mamba_group_info")
    post = worker.get("postprocess_state")
    backend = methods["mamba_backend"].get("_compute_common_metadata")
    checks = {
        "scheduler_config_factory_declared": factory is not None,
        "engine_assigns_scheduler_from_config_factory": _assigned(
            engine, "Scheduler", "vllm_config.scheduler_config.get_scheduler_cls"
        ),
        "engine_calls_factory_result_scheduler": _uses_keyword(
            engine, "Scheduler", "block_size", "scheduler_block_size"
        ),
        "mamba_seed_uses_cache_config_block": _has_divisor(
            worker.get("add_request"), "self.cache_config.block_size"
        ),
        "mamba_group_checks_spec_block": _compares_group_blocks(group),
        "mamba_preprocess_uses_group_spec_block": _uses_keyword(
            pre, "preprocess_mamba_align_fused_kernel",
            "MAMBA_BLOCK_SIZE", "mamba_spec.block_size"
        ) or (pre is not None and any(
            isinstance(k, ast.keyword) and k.arg == "MAMBA_BLOCK_SIZE"
            and _qualified_name(k.value) == "mamba_spec.block_size"
            for k in ast.walk(pre)
        )),
        "mamba_align_context_helper_declared": worker.get("_ensure_align_ctx") is not None,
        "mamba_postprocess_fused_hook": _called(
            post, "self._mamba_ctx.run_fused_postprocess_align"
        ),
        "scheduler_align_uses_cache_config_block": _has_assignment(
            scheduler, "block_size", "self.cache_config.block_size"
        ),
        "backend_reads_spec_block": backend is not None and any(
            isinstance(n, ast.Attribute)
            and _qualified_name(n) == "self.kv_cache_spec.block_size"
            for n in ast.walk(backend)
        ),
    }
    absent = sorted(k for k, v in checks.items() if not v)
    return {
        "status": "SOURCE_FACTORY_AND_SLOT_EVIDENCE_ONLY",
        "pinned_blazux": PIN,
        "patch_approved": False,
        "active_scheduler_class_verified": False,
        "actual_config_block_equality_verified": False,
        "state_slot_correctness_verified": False,
        "source_checks": checks,
        "missing_source_checks": absent,
        "file_evidence": summaries,
        "synthetic_oracles": {
            "equal_blocks": synthetic_seed_oracle(16, 16),
            "different_blocks": synthetic_seed_oracle(16, 32),
        },
        "next_gate": (
            "Determine SchedulerConfig factory default/override and actual "
            "MambaSpec vs CacheConfig block values and kernel slot lifecycle "
            "before considering any runtime patch."
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
    if result["status"] != "SOURCE_FACTORY_AND_SLOT_EVIDENCE_ONLY":
        raise SystemExit("BLOCKED: invalid source root")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    print("PHASE5_SCHEDULER_MAMBA_CONTRACT_DONE_NOT_PATCH_APPROVED")


if __name__ == "__main__":
    main()
