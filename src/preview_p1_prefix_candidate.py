"""P1 Prefix-cache: exact-pin Preview-native two-site source patch candidate.

Never modifies installed vLLM. The only executable operation is staging TWO
SHA-pinned Python files into a disposable TemporaryDirectory and checking AST.
It does NOT run vLLM, the scheduler, model, CUDA, HTTP, or live prefix caching.
A patch candidate is NOT approval to install it or correctness certification.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

PREVIEW_PIN = "0.1.dev20073+g8e685d198"
UPSTREAM_PIN = "7e63dbe5761448ea833ed28781c1d32ce0d56f4c"
SPECS = {
    "mamba": (
        "v1/worker/gpu/model_states/mamba_hybrid.py",
        "2e65f1da0a440f11a784bd36afe9206a7a2f674d522c047b838ad604e4c6acc0",
    ),
    "scheduler": (
        "v1/core/sched/scheduler.py",
        "c710f49e41e974e5b7b8f1cd2f5fb9722523f4da0165252e16351199ebd03124",
    ),
}
OLD_WORKER = b"self.cache_config.block_size"
NEW_WORKER = b"self.cache_config.mamba_block_size"
OLD_SCHED = b"self.cache_config.block_size"
NEW_SCHED = b"self.block_size"


class Blocked(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _method(tree: ast.Module, class_name: str, method_name: str) -> ast.FunctionDef:
    classes = [n for n in tree.body
               if isinstance(n, ast.ClassDef) and n.name == class_name]
    if len(classes) != 1:
        raise Blocked("TARGET_CLASS_SHAPE_CHANGED")
    funcs = [n for n in classes[0].body
             if isinstance(n, ast.FunctionDef) and n.name == method_name]
    if len(funcs) != 1:
        raise Blocked("TARGET_METHOD_SHAPE_CHANGED")
    return funcs[0]


def _parse(data: bytes) -> ast.Module:
    try:
        return ast.parse(data.decode("utf-8"))
    except (UnicodeError, SyntaxError, ValueError):
        raise Blocked("SOURCE_UNPARSEABLE") from None


def _divisors(node: ast.AST, rhs: str) -> list[ast.BinOp]:
    return [n for n in ast.walk(node)
            if isinstance(n, ast.BinOp) and isinstance(n.op, ast.FloorDiv)
            and ast.unparse(n.right) == rhs]


def _anchor(label: str, source: bytes) -> ast.expr:
    tree = _parse(source)
    if label == "mamba":
        method = _method(tree, "MambaHybridModelState", "add_request")
        calls = [n for n in ast.walk(method)
                 if isinstance(n, ast.Call)
                 and ast.unparse(n.func) ==
                 "self._mamba_state_idx_gpu[req_index].fill_"]
        if len(calls) != 1:
            raise Blocked("MAMBA_SEED_CALL_DRIFT")
        if not any(isinstance(n, ast.If) and
                   ast.unparse(n.test) == "self._align_mode" and
                   any(call is candidate for statement in n.body
                       for candidate in ast.walk(statement))
                   for n in ast.walk(method) for call in calls):
            raise Blocked("MAMBA_ALIGN_BRANCH_DRIFT")
        matches = _divisors(calls[0], OLD_WORKER.decode())
        if (len(matches) != 1 or
                len(_divisors(method, OLD_WORKER.decode())) != 1):
            raise Blocked("MAMBA_SEED_DIVISOR_DRIFT")
        return matches[0].right
    if label == "scheduler":
        method = _method(tree, "Scheduler", "_mamba_block_aligned_split")
        matches = [n for n in ast.walk(method) if isinstance(n, ast.Assign)
                   and len(n.targets) == 1
                   and isinstance(n.targets[0], ast.Name)
                   and n.targets[0].id == "block_size"
                   and ast.unparse(n.value) == OLD_SCHED.decode()]
        if len(matches) != 1:
            raise Blocked("SCHEDULER_SPLIT_ASSIGNMENT_DRIFT")
        # Refuse multiple assignments that could override the chosen value.
        total = [n for n in ast.walk(method)
                 if isinstance(n, (ast.Assign, ast.AnnAssign))
                 and any(isinstance(t, ast.Name) and t.id == "block_size"
                         for t in (n.targets if isinstance(n, ast.Assign)
                                   else (n.target,)))]
        if len(total) != 1:
            raise Blocked("SCHEDULER_BLOCK_VARIABLE_DRIFT")
        return matches[0].value
    raise Blocked("UNKNOWN_TARGET")


def _replace_expr(source: bytes, expr: ast.expr, old: bytes, new: bytes) -> bytes:
    lines = source.splitlines(keepends=True)
    if (expr.end_lineno != expr.lineno or expr.lineno is None
            or expr.end_col_offset is None or expr.col_offset is None):
        raise Blocked("EXPRESSION_SPAN_CHANGED")
    start = sum(map(len, lines[:expr.lineno - 1])) + expr.col_offset
    end = sum(map(len, lines[:expr.end_lineno - 1])) + expr.end_col_offset
    if source[start:end] != old:
        raise Blocked("EXPRESSION_BYTES_CHANGED")
    return source[:start] + new + source[end:]


def patch_source(label: str, source: bytes, expected_sha: str) -> bytes:
    """Only used with hardcoded SHA pins in the installed-code entrypoint."""
    if label not in SPECS:
        raise Blocked("UNKNOWN_TARGET")
    if _sha(source) != expected_sha:
        raise Blocked("PREVIEW_SOURCE_SHA_DRIFT")
    expr = _anchor(label, source)
    before, after = ((OLD_WORKER, NEW_WORKER) if label == "mamba"
                     else (OLD_SCHED, NEW_SCHED))
    patched = _replace_expr(source, expr, before, after)
    # Exact intended semantic node, source parse, and one-span edit only.
    post = _parse(patched)
    if label == "mamba":
        fn = _method(post, "MambaHybridModelState", "add_request")
        if (len(_divisors(fn, NEW_WORKER.decode())) != 1 or
                _divisors(fn, OLD_WORKER.decode())):
            raise Blocked("MAMBA_POST_PATCH_CONTRACT_FAILED")
    else:
        fn = _method(post, "Scheduler", "_mamba_block_aligned_split")
        assigns = [n for n in ast.walk(fn) if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "block_size"
                           for t in n.targets)]
        if len(assigns) != 1 or ast.unparse(assigns[0].value) != NEW_SCHED.decode():
            raise Blocked("SCHEDULER_POST_PATCH_CONTRACT_FAILED")
    if patched == source:
        raise Blocked("NO_SOURCE_CHANGE")
    return patched


def _installed_root() -> Path:
    spec = importlib.util.find_spec("vllm")  # Never import vLLM or CUDA.
    if spec is None or not spec.submodule_search_locations:
        raise Blocked("PREVIEW_PACKAGE_NOT_FOUND")
    locations = list(spec.submodule_search_locations)
    if len(locations) != 1:
        raise Blocked("PREVIEW_PACKAGE_PATH_AMBIGUOUS")
    root = Path(locations[0])
    if not root.is_dir() or root.is_symlink():
        raise Blocked("PREVIEW_ROOT_UNAVAILABLE")
    return root.resolve()


def _read_pinned(root: Path, label: str) -> bytes:
    relative, digest = SPECS[label]
    file = root / relative
    if file.is_symlink() or not file.is_file() or not file.resolve().is_relative_to(root):
        raise Blocked("PREVIEW_SOURCE_UNAVAILABLE")
    if file.stat().st_size > 2_000_000:
        raise Blocked("PREVIEW_SOURCE_OVERSIZED")
    data = file.read_bytes()
    if _sha(data) != digest:
        raise Blocked("PREVIEW_SOURCE_SHA_DRIFT")
    return data


def verify_installed() -> dict[str, object]:
    root = _installed_root()
    original = {label: _read_pinned(root, label) for label in SPECS}
    patched = {label: patch_source(label, original[label], SPECS[label][1])
               for label in SPECS}
    with tempfile.TemporaryDirectory(prefix="p1-prefix-only-") as folder:
        temp = Path(folder)
        for label, (relative, _) in SPECS.items():
            candidate = temp / relative
            candidate.parent.mkdir(parents=True, exist_ok=True)
            candidate.write_bytes(patched[label])
            if candidate.read_bytes() != patched[label]:
                raise Blocked("TEMP_PATCH_VERIFY_FAILED")
            _parse(candidate.read_bytes())
        # Read original installed paths again: no copy-back and no mutation.
        if any(_read_pinned(root, label) != original[label] for label in SPECS):
            raise Blocked("INSTALLED_SOURCE_CHANGED")
    return {
        "status": "P1_PINNED_PREVIEW_PREFIX_SOURCE_CANDIDATE_STAGED",
        "preview_pin": PREVIEW_PIN,
        "upstream_pin": UPSTREAM_PIN,
        "source_files": 2,
        "candidate_sites": ["mamba_align_seed_divisor",
                            "scheduler_mamba_split_block_size"],
        "installed_package_modified": False,
        "actual_scheduler_or_group_abi_observed": False,
        "actual_cache_hit_or_gpu_executed": False,
        "runtime_prefix_correctness_certified": False,
    }


def main(args: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if args is None else args)
    if argv != ["--verify-installed"]:
        print("STOP: explicit --verify-installed required")
        return 2
    try:
        print(json.dumps(verify_installed(), sort_keys=True))
        print("P1_PREFIX_CANDIDATE_PINNED_PREVIEW_SOURCE_ONLY_PASS_NOT_APPLIED")
        return 0
    except Blocked as exc:
        print(json.dumps({"status": "BLOCKED_NOT_APPLIED",
                          "reason": exc.code}, sort_keys=True))
        return 2
    except (OSError, TypeError, AttributeError):
        print('{"reason": "SOURCE_ACCESS_OR_SHAPE_ERROR", "status": "BLOCKED_NOT_APPLIED"}')
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
