"""Phase 5: pinned blazux patch *preflight*, installed preview source-only.

No imports of installed vLLM, no mutations, no GPU, no model weights.  A
passing preflight DOES NOT authorize patching, performance claims or serving.
Pinned blazux: 8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from pathlib import Path

try:
    from .phase5_preview_abi_audit import _safe_read
except ImportError:  # invoked as: python3 src/phase5_patch_readiness.py
    from phase5_preview_abi_audit import _safe_read

PIN = "8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa"
PATHS = {
    "mamba": "v1/worker/gpu/model_states/mamba_hybrid.py",
    "scheduler": "v1/core/sched/scheduler.py",
    "parser_engine": "parser/engine/parser_engine.py",
    "qwen3": "parser/qwen3.py",
    "adapters": "parser/engine/adapters.py",
    "abstract_parser": "parser/abstract_parser.py",
    "stream": "parser/engine/streaming_parser_engine.py",
    "config": "parser/engine/parser_engine_config.py",
    "responses_protocol": "entrypoints/openai/responses/protocol.py",
    "responses_serving": "entrypoints/openai/responses/serving.py",
    "mtp_nvidia": "models/qwen3_8_flash_next/nvidia/mtp.py",
    "ple_nvidia": "models/qwen3_8_flash_next/nvidia/ple_layer.py",
}
ANCHOR_FIELDS = {
    "mamba": (
        "self.cache_config.block_size",
        "self.cache_config.mamba_block_size",
        "num_computed_tokens",
    ),
    "scheduler": (
        "block_size = self.cache_config.block_size",
        "block_size = self.block_size",
        "The last block-aligned position whose state can be cached.",
    ),
    "parser_engine": (
        "_compute_arg_delta", "_flush_arg_converter",
        "_normalize_tool_arguments", "_arguments_block_emission",
        "_skip_incomplete_tool_slot", "_buffer_ambiguous_arguments",
    ),
    "qwen3": (
        "_check_skip_tool_parsing", "_normalize_tool_arguments",
        "_schema_for_tool",
    ),
    "adapters": (
        "prepare_tool_argument_schema", "has_invalid_tool_arguments",
        "has_rejected_tool_calls",
    ),
    "abstract_parser": (
        "has_invalid_tool_arguments", "prepare_tool_argument_schema",
        "has_rejected_tool_calls",
    ),
    "stream": ("_marker_is_literal", "feed", "finish"),
    "config": ("guard_literal_tool_markers",),
    "responses_protocol": (
        "ResponseFailedEvent", "ResponseIncompleteEvent",
        "ResponseCompletedEvent",
    ),
    "responses_serving": (
        "response.failed", "response.incomplete",
        "_make_failed_response_event", "_process_simple_streaming_events",
    ),
    "mtp_nvidia": (
        "Qwen3_8FlashNextMTP", "compute_logits", "self.lm_head",
        "self.logits_processor", "load_weights",
    ),
    "ple_nvidia": ("Qwen3_8FlashNextPLELayer", "NGramEmbedding"),
}


def _class_methods(tree: ast.Module, clsname: str, method: str) -> list[dict]:
    records: list[dict] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != clsname:
            continue
        for child in node.body:
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) or child.name != method:
                continue
            ref_names = sorted({
                obj.attr for obj in ast.walk(child)
                if isinstance(obj, ast.Attribute) and obj.attr in (
                    "mamba_block_size", "block_size", "lm_head",
                    "logits_processor", "index_select", "compute_logits",
                )
            })
            records.append({
                "class": clsname,
                "method": method,
                "lineno": child.lineno,
                "end_lineno": child.end_lineno,
                "signature": [v.arg for v in (
                    child.args.posonlyargs + child.args.args + child.args.kwonlyargs
                )],
                "ast_sha256": hashlib.sha256(ast.dump(
                    child, include_attributes=False
                ).encode()).hexdigest(),
                "selected_attribute_names": ref_names,
            })
    return records


METHODS = {
    "mamba": ("MambaHybridModelState", ("add_request",)),
    "scheduler": ("Scheduler", ("_mamba_block_aligned_split", "_get_local_prefix_cache_hit")),
    "parser_engine": ("ParserEngine", (
        "_handle_tool_end", "_compute_arg_delta",
        "_normalize_tool_arguments", "_arguments_block_emission",
        "_skip_incomplete_tool_slot",
    )),
    "qwen3": ("Qwen3Parser", (
        "_check_skip_tool_parsing", "_normalize_tool_arguments",
    )),
    "stream": ("StreamingParserEngine", ("feed", "finish", "_marker_is_literal")),
    "responses_serving": ("OpenAIServingResponses", (
        "_process_simple_streaming_events", "_make_failed_response_event",
    )),
    "mtp_nvidia": ("Qwen3_8FlashNextMTP", ("compute_logits", "load_weights")),
    "ple_nvidia": ("Qwen3_8FlashNextPLELayer", ("forward",)),
}


def inspect_source_tree(root: Path) -> dict:
    """Read bounded source and emit fingerprints, never raw code or local paths."""
    files: dict[str, dict] = {}
    for label, rel in PATHS.items():
        data, state = _safe_read(root, root / rel)
        if data is None:
            files[label] = {"state": state}
            continue
        sha = hashlib.sha256(data).hexdigest()
        try:
            source = data.decode("utf-8")
            parsed = ast.parse(source)
        except (UnicodeError, SyntaxError, ValueError):
            files[label] = {"state": "UNPARSEABLE", "sha256": sha}
            continue
        anchors = {anchor: source.count(anchor) for anchor in ANCHOR_FIELDS.get(label, ())}
        methods = []
        if label in METHODS:
            cls, names = METHODS[label]
            for name in names:
                methods.extend(_class_methods(parsed, cls, name))
        files[label] = {
            "state": "PARSEABLE_ONLY",
            "sha256": sha,
            "anchor_counts": anchors,
            "method_fingerprints": methods,
        }
    decisions = classify_patch_preflight(files)
    return {
        "status": "SOURCE_ONLY_NOT_PATCH_OR_ABI_CERTIFIED",
        "pinned_blazux": PIN,
        "components": files,
        "preflight": decisions,
    }


def classify_patch_preflight(files: dict[str, dict]) -> dict[str, dict]:
    """Conservative preflight, never produces an APPLY_APPROVED status."""
    def count(label: str, anchor: str) -> int:
        x = files.get(label, {})
        return int(x.get("anchor_counts", {}).get(anchor, 0))

    def present(label: str) -> bool:
        return files.get(label, {}).get("state") == "PARSEABLE_ONLY"

    def decision(status: str, explanation: str, dependencies: list[str]) -> dict:
        return {"status": status, "reason": explanation, "requires": dependencies}

    if present("mamba") and present("scheduler"):
        legacy = count("mamba", "self.cache_config.block_size") > 0
        ready_field = count("mamba", "self.cache_config.mamba_block_size") > 0
        schedule_legacy = count("scheduler", "block_size = self.cache_config.block_size") > 0
        mamba = decision(
            "SOURCE_PREIMAGE_CANDIDATE_UNSAFE_TO_APPLY" if legacy and schedule_legacy
            else "PREIMAGE_MISMATCH_OR_NATIVE_REVIEW",
            "Legacy expressions are hints; ensure cache_config.mamba_block_size is "
            "actually created and scheduler self.block_size is the correct LCM. "
            "Field reference observed=" + str(ready_field),
            ["cache_config creation", "group LCM semantics", "state slot restore"],
        )
    else:
        mamba = decision("SOURCE_MISSING_OR_UNPARSEABLE",
                         "Mamba/scheduler source unavailable", ["source files"])

    schema_files = ("parser_engine", "qwen3", "adapters",
                    "abstract_parser", "responses_serving")
    schema = decision(
        "MULTI_FILE_PATCH_PREREQUISITES_UNVERIFIED" if all(map(present, schema_files))
        else "SOURCE_MISSING_OR_UNPARSEABLE",
        "Pinned argument-schema patch spans ParserEngine, Qwen3, adapters, "
        "abstract parser, Responses and a NEW validation module. Missing helper "
        "does not mean the patch is safe or trivially portable.",
        ["exact patch hunk preimages", "parser factory", "JSON schema dependencies",
         "Responses serving context", "streaming parser lifecycle"],
    )
    marker = decision(
        "MULTI_FILE_PATCH_PREREQUISITES_UNVERIFIED"
        if present("stream") and present("config") else "SOURCE_MISSING_OR_UNPARSEABLE",
        "Literal-marker patch depends on parser stream/config and token-ID "
        "lifecycle, not merely a matching function name.",
        ["literal token matching", "parser config transport", "partial tool tokens"],
    )
    responses = decision(
        "PROTOCOL_AND_SERVING_COMPATIBILITY_UNVERIFIED"
        if present("responses_protocol") and present("responses_serving")
        else "SOURCE_MISSING_OR_UNPARSEABLE",
        "Failed/incomplete terminal event classes and serving exception-to-SSE "
        "wire conversion must be reviewed together.",
        ["OpenAI types", "event protocol union", "HTTP streaming error contract"],
    )
    if present("mtp_nvidia"):
        method_names = {
            m["method"] for m in files["mtp_nvidia"]["method_fingerprints"]
        }
        mtp_status = (
            "MTP_COMPUTE_LOGITS_HOOK_CANDIDATE_NOT_APPROVED"
            if {"compute_logits", "load_weights"} <= method_names
            else "MTP_ABI_SIGNATURE_INCOMPLETE"
        )
    else:
        mtp_status = "MTP_SOURCE_MISSING_OR_UNPARSEABLE"
    mtp = decision(
        mtp_status,
        "Pinned reduced-draft hook assumes shared lm_head.weight and logits "
        "processor vocabulary, and alters draft proposals. Does not establish "
        "weight-loader/TP shard shape, tokenizer IDs or target acceptance.",
        ["lm_head sharing", "weight shapes/dtype", "sampler",
         "EOS/non-Latin/tool token coverage", "acceptance and target parity"],
    )
    return {
        "mamba_scheduler": mamba,
        "tool_argument_schema": schema,
        "tool_literal_marker": marker,
        "responses_terminal": responses,
        "mtp_reduced_draft_vocabulary": mtp,
    }


def main() -> None:
    spec = importlib.util.find_spec("vllm")
    if spec is None or not spec.submodule_search_locations:
        raise SystemExit("BLOCKED: installed vLLM package root not found")
    roots = list(spec.submodule_search_locations)
    if len(roots) != 1 or not Path(roots[0]).is_dir():
        raise SystemExit("BLOCKED: vLLM package root ambiguous or absent")
    result = inspect_source_tree(Path(roots[0]))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    print("PHASE5_PATCH_PREFLIGHT_SOURCE_ONLY_DONE_NO_APPLY_APPROVAL")


if __name__ == "__main__":
    main()
