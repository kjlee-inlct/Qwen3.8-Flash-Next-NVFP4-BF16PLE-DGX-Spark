"""Read-only installed vLLM source/ABI *inventory*, without importing vLLM.

This inventories file SHA256 and relevant class/function names, not runtime
compatibility or actual parser/cache behavior. Runs inside a disposable,
network-disabled CPU-only container using its already installed vLLM package.
No model/GPU access, installation, monkeypatch or output file.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from pathlib import Path

COMPONENTS = {
    "mamba_hybrid": "v1/worker/gpu/model_states/mamba_hybrid.py",
    "scheduler": "v1/core/sched/scheduler.py",
    "parser_qwen3": "parser/qwen3.py",
    "parser_engine": "parser/engine/parser_engine.py",
    "streaming_parser": "parser/engine/streaming_parser_engine.py",
    "responses_serving": "entrypoints/openai/responses/serving.py",
    "qwen38_mtp": "model_executor/models/qwen3_8_flash_next/nvidia/mtp.py",
    "qwen38_ple": "model_executor/models/qwen3_8_flash_next/nvidia/ple_layer.py",
}


def inventory() -> dict:
    spec = importlib.util.find_spec("vllm")
    if spec is None or not spec.submodule_search_locations:
        return {"package": "NOT_INSTALLED", "components": {}}
    roots = [Path(p) for p in spec.submodule_search_locations]
    if len(roots) != 1:
        return {"package": "AMBIGUOUS_MULTI_ROOT", "components": {}}
    root = roots[0]
    components = {}
    for label, relative in COMPONENTS.items():
        path = root / relative
        if not path.is_file():
            components[label] = {"state": "ABSENT_OR_RELOCATED"}
            continue
        contents = path.read_bytes()
        try:
            node = ast.parse(contents, filename=relative)
        except (SyntaxError, ValueError, UnicodeError):
            components[label] = {
                "state": "PRESENT_NONPARSEABLE",
                "sha256": hashlib.sha256(contents).hexdigest(),
            }
            continue
        names = sorted({
            item.name
            for item in ast.walk(node)
            if isinstance(item, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        })
        components[label] = {
            "state": "PRESENT_SOURCE_PARSEABLE",
            "sha256": hashlib.sha256(contents).hexdigest(),
            "symbols": names,
        }
    return {"package": "LOCATED_READ_ONLY", "components": components}


if __name__ == "__main__":
    result = inventory()
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    print("PHASE5_VLLM_SOURCE_INVENTORY_DONE_NOT_ABI_CERTIFIED")
