"""Phase 5 read-only AST dependency trace for the pinned blazux source gate.

Inspect actual installed preview vLLM; NO vLLM import, patch, weight read,
runtime call, network or GPU. Expression strings are CONSTANT-REDACTED and
bounded. This is *evidence for a human code review*, not compatibility proof.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from pathlib import Path

try:
    from .phase5_patch_readiness import PATHS, PIN
    from .phase5_preview_abi_audit import _safe_read
except ImportError:  # direct Python execution in isolated CPU container
    from phase5_patch_readiness import PATHS, PIN
    from phase5_preview_abi_audit import _safe_read

# Deliberately scoped. No recursive reading of checkpoints, HF cache, Docker.
SCAN_DIRS = ("config", "v1")
MAX_SCAN_FILES = 1600
MAX_SCAN_BYTES = 24 * 1024 * 1024
MAX_DEFINITION_SITES = 48
MAX_CALLS = 36
MAX_EXPR_CHARS = 160

METHODS = {
    "mamba": ("MambaHybridModelState", ("add_request", "preprocess_state",
                                           "postprocess_state")),
    "scheduler": ("Scheduler", (
        "__init__", "_mamba_block_aligned_split", "_get_local_prefix_cache_hit",
    )),
    "parser_engine": ("ParserEngine", ("_handle_tool_end", "_compute_arg_delta",
                                       "_flush_arg_converter", "_buffer_ambiguous_arguments")),
    "qwen3": ("Qwen3Parser", ("extract_reasoning", "_check_skip_tool_parsing",
                             "_normalize_tool_arguments")),
    "stream": ("StreamingParserEngine", ("feed", "finish")),
    "responses_serving": ("OpenAIServingResponses", (
        "_process_simple_streaming_events", "_make_failed_response_event")),
    "mtp_nvidia": ("Qwen3_8FlashNextMTP", (
        "__init__", "compute_logits", "forward", "load_weights",
    )),
    "ple_nvidia": ("Qwen3_8FlashNextPLELayer", ("forward",)),
}
WATCHED_ATTRS = {
    "block_size", "mamba_block_size", "num_computed_tokens", "cache_config",
    "lm_head", "logits_processor", "weight", "org_vocab_size",
    "spec_step_idx",
}


class _RedactConstants(ast.NodeTransformer):
    def visit_Constant(self, node: ast.Constant) -> ast.Constant:
        if isinstance(node.value, (str, bytes)):
            return ast.copy_location(ast.Constant(value="<redacted>"), node)
        if isinstance(node.value, (int, float, complex)) and not isinstance(
            node.value, bool
        ):
            return ast.copy_location(ast.Constant(value="<number>"), node)
        return node


def _shape(node: ast.AST) -> str:
    """Bounded AST shape; never output string literals or numeric constants."""
    try:
        copy = ast.fix_missing_locations(
            _RedactConstants().visit(ast.parse(ast.unparse(node), mode="eval"))
        )
        s = ast.unparse(copy)
    except (SyntaxError, ValueError, TypeError, AttributeError):
        return "<not_representable>"
    return s[:MAX_EXPR_CHARS] + ("..." if len(s) > MAX_EXPR_CHARS else "")


def _qualified_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _qualified_name(node.value)
        return (prefix + "." if prefix else "") + node.attr
    return ""


def _class_method(tree: ast.Module, class_name: str, method_name: str):
    for cls in tree.body:
        if isinstance(cls, ast.ClassDef) and cls.name == class_name:
            for method in cls.body:
                if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                    method.name == method_name
                ):
                    return method
    return None


def _method_trace(method: ast.FunctionDef | ast.AsyncFunctionDef) -> dict:
    divisions: list[dict] = []
    assignments: list[dict] = []
    call_names: set[str] = set()
    attributes: set[str] = set()
    returned_shapes: list[str] = []
    for node in ast.walk(method):
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.FloorDiv, ast.Mod)):
            if len(divisions) < 12:
                divisions.append({
                    "line": node.lineno,
                    "kind": "floor_div" if isinstance(node.op, ast.FloorDiv) else "mod",
                    "left": _shape(node.left),
                    "right": _shape(node.right),
                })
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = (
                node.targets if isinstance(node, ast.Assign) else [node.target]
            )
            for target in targets:
                name = _qualified_name(target)
                if (name in ("block_size", "self.block_size", "self.lm_head",
                             "self.logits_processor", "self.cache_config",
                             "mamba_block_size", "self.mamba_block_size")
                        or name.endswith(".mamba_block_size")):
                    if len(assignments) < 18:
                        assignments.append({
                            "line": node.lineno,
                            "target": name,
                            "value_shape": _shape(node.value),
                        })
        elif isinstance(node, ast.Return) and node.value is not None:
            if len(returned_shapes) < 8:
                returned_shapes.append(_shape(node.value))
        elif isinstance(node, ast.Call):
            name = _qualified_name(node.func)
            if name and len(call_names) < MAX_CALLS:
                call_names.add(name)
        elif isinstance(node, ast.Attribute) and node.attr in WATCHED_ATTRS:
            attributes.add(_qualified_name(node))
    return {
        "line_start": method.lineno,
        "line_end": method.end_lineno,
        "signature": [a.arg for a in (
            method.args.posonlyargs + method.args.args + method.args.kwonlyargs
        )],
        "floor_div_or_mod": divisions,
        "watched_assignments": assignments,
        "calls": sorted(call_names),
        "return_expression_shapes": returned_shapes,
        "watched_attributes": sorted(attributes)[:36],
    }


def _component_traces(root: Path) -> dict:
    result = {}
    for key, (cls, method_names) in METHODS.items():
        data, state = _safe_read(root, root / PATHS[key])
        if data is None:
            result[key] = {"state": state}
            continue
        sha = hashlib.sha256(data).hexdigest()
        try:
            tree = ast.parse(data.decode("utf-8"))
        except (UnicodeError, SyntaxError, ValueError):
            result[key] = {"state": "UNPARSEABLE", "sha256": sha}
            continue
        methods = {}
        for name in method_names:
            node = _class_method(tree, cls, name)
            methods[name] = _method_trace(node) if node else None
        result[key] = {
            "state": "PARSEABLE_ONLY", "sha256": sha,
            "class": cls, "methods": methods,
        }
    return result


def _definition_sites(tree: ast.Module, relative: str, limit: int) -> list[dict]:
    """Exact AST attribute/name stores; no inference from read-only accesses."""
    sites = []
    for node in ast.walk(tree):
        if len(sites) >= limit:
            break
        if isinstance(node, (ast.Attribute, ast.Name)):
            field = node.attr if isinstance(node, ast.Attribute) else node.id
            if field != "mamba_block_size":
                continue
            kind = "STORE" if isinstance(node.ctx, ast.Store) else "LOAD"
            sites.append({
                "relative_path": relative, "line": node.lineno,
                "kind": kind, "target": _qualified_name(node),
            })
    return sites


def scan_mamba_field(root: Path) -> dict:
    """Bounded import-free search of config and v1 source trees.

    Scan can be incomplete due to file/byte limit. A STORE is merely an
    assignment occurrence; it does not prove a populated config at runtime.
    """
    candidates: list[Path] = []
    for directory in SCAN_DIRS:
        folder = root / directory
        if not folder.is_dir() or folder.is_symlink():
            continue
        candidates.extend(sorted(folder.rglob("*.py")))
    if len(candidates) > MAX_SCAN_FILES:
        return {"state": "FILE_LIMIT_EXCEEDED",
                "files_matched": len(candidates), "sites": []}
    total = 0
    visited = 0
    sites: list[dict] = []
    unreadable = 0
    for path in candidates:
        data, state = _safe_read(root, path)
        if data is None:
            unreadable += 1
            continue
        total += len(data)
        if total > MAX_SCAN_BYTES:
            return {"state": "BYTE_LIMIT_EXCEEDED", "files_visited": visited,
                    "bytes_read": total, "sites": sites, "unreadable": unreadable}
        visited += 1
        # Cheap filter; only parse source mentioning the exact field token.
        if b"mamba_block_size" not in data:
            continue
        try:
            tree = ast.parse(data.decode("utf-8"))
        except (UnicodeError, ValueError, SyntaxError):
            unreadable += 1
            continue
        relative = str(path.relative_to(root))
        new_sites = _definition_sites(tree, relative, MAX_DEFINITION_SITES-len(sites))
        sites.extend(new_sites)
        if len(sites) >= MAX_DEFINITION_SITES:
            return {"state": "SITE_LIMIT_EXCEEDED", "files_visited": visited,
                    "bytes_read": total, "sites": sites, "unreadable": unreadable}
    return {"state": "SCANNED_READ_ONLY" if unreadable == 0 else
            "SCANNED_WITH_UNREADABLE_FILES", "files_visited": visited,
            "bytes_read": total, "sites": sites, "unreadable": unreadable}


def inspect(root: Path) -> dict:
    if not root.is_dir() or root.is_symlink():
        return {"status": "INVALID_PACKAGE_ROOT", "not_patch_approved": True}
    root = root.resolve()
    return {
        "status": "AST_DEPENDENCY_EVIDENCE_ONLY_NOT_SEMANTIC_OR_ABI_CERTIFIED",
        "pinned_blazux": PIN,
        "not_patch_approved": True,
        "components": _component_traces(root),
        "mamba_field_scan": scan_mamba_field(root),
        "next_gates": [
            "cache_config field provenance and group LCM/state slot lifecycle",
            "tool parser/Responses streaming partial args and terminal SSE",
            "MTP lm_head owner/shard/target vocab/acceptance",
        ],
    }


def main() -> None:
    spec = importlib.util.find_spec("vllm")
    if spec is None or not spec.submodule_search_locations:
        raise SystemExit("BLOCKED: installed vLLM package root missing")
    roots = list(spec.submodule_search_locations)
    if len(roots) != 1:
        raise SystemExit("BLOCKED: ambiguous vLLM package roots")
    result = inspect(Path(roots[0]))
    if result["status"] == "INVALID_PACKAGE_ROOT":
        raise SystemExit("BLOCKED: invalid vLLM source root")
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    print("PHASE5_DEPENDENCY_TRACE_DONE_NOT_PATCH_APPROVED")


if __name__ == "__main__":
    main()
