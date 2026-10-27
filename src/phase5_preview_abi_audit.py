"""Read-only ABI *triage* for an installed vLLM preview (not ABI certification).

No vLLM import, model import, CUDA, pip, filesystem mutations, or code patches.
A model candidate filename or matched function name is not proof of compatibility.
The blazux anchor hints refer to pinned upstream commit
8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa, not current upstream HEAD.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import re
from pathlib import Path

COMPONENTS = {
    "mamba": "v1/worker/gpu/model_states/mamba_hybrid.py",
    "scheduler": "v1/core/sched/scheduler.py",
    "parser_engine": "parser/engine/parser_engine.py",
    "parser_qwen3": "parser/qwen3.py",
    "streaming_parser": "parser/engine/streaming_parser_engine.py",
    "parser_config": "parser/engine/parser_engine_config.py",
    "responses_serving": "entrypoints/openai/responses/serving.py",
    "responses_protocol": "entrypoints/openai/responses/protocol.py",
}

# These are observed from the user's Phase 5 DGX log, not ground-truth hashes
# for arbitrary vLLM installations. Drift must be reviewed, never auto-fixed.
PREVIOUS_SHA256 = {
    "mamba": "2e65f1da0a440f11a784bd36afe9206a7a2f674d522c047b838ad604e4c6acc0",
    "scheduler": "c710f49e41e974e5b7b8f1cd2f5fb9722523f4da0165252e16351199ebd03124",
    "parser_engine": "f837bd5ae7bf759732a7d829209f93444b5692746d981509630c9bd3fcb39edb",
    "parser_qwen3": "8a7ee658322de7b736ea5b0f802d70dd07a124b5878b4f8ad2f99eca8e1d35fb",
    "streaming_parser": "d00aba98ad26a2593e022a1faf5d048348d892822f75be40d19cf1dd522570f2",
    "responses_serving": "d5fdb9ca62fa767d6feb61f6b3f5280f288051eea8605d27afa698cc00067968",
}

# AST names are hints. They are deliberately not called, executed or patched.
WANTED_METHODS = {
    "mamba": ("MambaHybridModelState", ("add_request", "preprocess_state", "postprocess_state")),
    "scheduler": ("Scheduler", ("_mamba_block_aligned_split", "_get_local_prefix_cache_hit")),
    "parser_engine": ("ParserEngine", ("_handle_tool_end", "_normalize_tool_arguments",
                                      "_arguments_block_emission", "_skip_incomplete_tool_slot")),
    "parser_qwen3": ("Qwen3Parser", ("_check_skip_tool_parsing", "extract_reasoning")),
    "streaming_parser": ("StreamingParserEngine", ("feed", "finish", "_marker_is_literal")),
    "responses_serving": ("OpenAIServingResponses",
                          ("_process_simple_streaming_events", "_make_failed_response_event")),
}
MAX_FILE_BYTES = 2_000_000
MAX_MODEL_PY_VISITS = 3000
MAX_MODEL_CANDIDATES = 32


def _safe_read(root: Path, path: Path) -> tuple[bytes, str] | tuple[None, str]:
    """Read only real files beneath root; reject symlinks, large/invalid files."""
    if path.is_symlink():
        return None, "SYMLINK_IGNORED"
    try:
        if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
            return None, "ABSENT_OR_OUTSIDE_ROOT"
        if path.stat().st_size > MAX_FILE_BYTES:
            return None, "TOO_LARGE_FOR_AUDIT"
        return path.read_bytes(), "READ_ONLY"
    except (OSError, ValueError):
        return None, "UNREADABLE"


def _analyze_python(root: Path, path: Path, label: str) -> dict:
    data, status = _safe_read(root, path)
    if data is None:
        return {"state": status}
    sha = hashlib.sha256(data).hexdigest()
    try:
        text = data.decode("utf-8")
        tree = ast.parse(text, filename=label)
    except (SyntaxError, ValueError, UnicodeError):
        return {"state": "UNPARSEABLE", "sha256": sha}
    classes = {
        node.name: node
        for node in tree.body if isinstance(node, ast.ClassDef)
    }
    result: dict = {
        "state": "PRESENT_SOURCE_PARSEABLE",
        "sha256": sha,
        "classes": sorted(classes),
    }
    if label == "model_candidate":
        # MTP/PLE model classes may live in relocated Qwen4Exp modules.
        # Extract signatures only; never instantiate or call these classes.
        result["mtp_ple_candidate_methods"] = {
            cls: {
                fn.name: [a.arg for a in fn.args.posonlyargs + fn.args.args
                          + fn.args.kwonlyargs]
                for fn in node.body
                if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
                and fn.name in ("compute_logits", "forward", "load_weights",
                                "_load_weights", "get_input_embeddings")
            }
            for cls, node in classes.items()
            if "mtp" in cls.lower() or "ple" in cls.lower()
        }
    if label in PREVIOUS_SHA256:
        result["matches_previous_dgx_sha"] = sha == PREVIOUS_SHA256[label]
    if label in WANTED_METHODS:
        cls, methods = WANTED_METHODS[label]
        node = classes.get(cls)
        found = {}
        if node:
            found = {
                item.name: {
                    "lineno": item.lineno,
                    "args": [a.arg for a in item.args.posonlyargs + item.args.args
                             + item.args.kwonlyargs],
                }
                for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
        result["target_class_present"] = bool(node)
        result["target_method_signatures"] = {
            name: found.get(name) for name in methods
        }
        result["missing_target_methods"] = [x for x in methods if x not in found]
    # These flags identify source text anchors, NEVER runtime behavior.
    if label == "mamba":
        result["blazux_mamba_anchor_hints"] = {
            "mamba_block_field": "mamba_block_size" in text,
            "legacy_small_block_expression": bool(re.search(
                r"num_computed_tokens\s*-\s*1\)\s*//\s*self\.cache_config\.block_size",
                text,
            )),
            "direct_mamba_block_expression": bool(re.search(
                r"num_computed_tokens\s*-\s*1\)\s*//\s*(?:self\.cache_config\.)?mamba_block_size",
                text,
            )),
        }
    elif label == "scheduler":
        result["blazux_scheduler_anchor_hints"] = {
            "mamba_split_method": "_mamba_block_aligned_split" in text,
            "legacy_cache_block_assignment": "block_size = self.cache_config.block_size" in text,
            "scheduler_block_assignment": "block_size = self.block_size" in text,
        }
    elif label == "parser_engine":
        result["blazux_tool_schema_anchor_hints"] = {
            k: k in text for k in ("_normalize_tool_arguments",
                                    "_arguments_block_emission",
                                    "_skip_incomplete_tool_slot",
                                    "_buffer_ambiguous_arguments")
        }
    elif label == "parser_config":
        result["blazux_literal_tool_marker_anchor"] = "guard_literal_tool_markers" in text
    elif label == "responses_serving":
        result["blazux_responses_terminal_hints"] = {
            k: k in text for k in ("response.failed", "response.incomplete",
                                    "_make_failed_response_event")
        }
    return result


def _candidate_name(path: Path) -> bool:
    """Conservative model-directory selection; not an inferred model ID."""
    if path.suffix != ".py":
        return False
    pieces = [p.lower() for p in path.parts]
    if any("qwen" in x for x in pieces):
        return path.name in ("mtp.py", "ple_layer.py", "model.py") or (
            "qwen" in path.name.lower()
        )
    return path.stem in ("mtp", "ple_layer")


def _model_candidates(root: Path) -> dict:
    files = []
    visited = 0
    for relative in ("model_executor/models", "models"):
        directory = root / relative
        if not directory.is_dir() or directory.is_symlink():
            continue
        for path in directory.rglob("*.py"):
            visited += 1
            if visited > MAX_MODEL_PY_VISITS:
                return {"state": "SCAN_LIMIT_REACHED", "visited": visited,
                        "candidates": []}
            if _candidate_name(path.relative_to(root)):
                files.append(path)
    # Likely model family first.  A hard limit must not silently exclude
    # qwen4_exp/nvidia/mtp.py after many unrelated qwen* modules.
    def priority(path: Path) -> tuple[int, str]:
        rel = str(path.relative_to(root)).lower()
        order = (0 if "qwen4_exp" in rel else
                 1 if "qwen3_8" in rel or "qwen38" in rel else
                 2 if "qwen" in rel else 3)
        return order, rel

    files.sort(key=priority)
    candidates = []
    for path in files[:MAX_MODEL_CANDIDATES]:
        relative_path = str(path.relative_to(root))
        record = _analyze_python(root, path, "model_candidate")
        candidates.append({"relative_path": relative_path, **record})
    state = ("CANDIDATE_LIMIT_REACHED" if len(files) > MAX_MODEL_CANDIDATES
             else "SCANNED_READ_ONLY")
    return {"state": state, "visited": visited,
            "matched_file_count": len(files), "candidates": candidates}


def audit_tree(root: Path) -> dict:
    """Auditable, synthetic-testable entrypoint. Does not import vLLM."""
    if not root.is_dir() or root.is_symlink():
        return {"package": "NOT_A_DIRECTORY", "components": {},
                "model_search": {"state": "NOT_RUN"}}
    root = root.resolve()
    components = {
        label: _analyze_python(root, root / relative, label)
        for label, relative in COMPONENTS.items()
    }
    search = _model_candidates(root)
    return {
        "package": "SOURCE_TREE_ONLY_NOT_ABI_CERTIFIED",
        "components": components,
        "model_search": search,
    }


def main() -> None:
    spec = importlib.util.find_spec("vllm")
    if spec is None or not spec.submodule_search_locations:
        output = {"package": "VLLM_NOT_FOUND", "components": {}}
    else:
        roots = list(spec.submodule_search_locations)
        output = audit_tree(Path(roots[0])) if len(roots) == 1 else {
            "package": "AMBIGUOUS_VLLM_ROOTS", "components": {}
        }
    print(json.dumps(output, sort_keys=True, ensure_ascii=False))
    print("PHASE5_PREVIEW_ABI_SOURCE_AUDIT_DONE_NOT_COMPATIBILITY_CERTIFIED")


if __name__ == "__main__":
    main()
