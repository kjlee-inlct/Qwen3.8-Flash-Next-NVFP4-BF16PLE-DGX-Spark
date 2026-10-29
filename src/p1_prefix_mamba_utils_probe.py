"""P1 GPU-free exact-image mamba_utils source ABI inventory.

For diagnostic design ONLY. No runtime hooks, CUDA, source installs or model data.
Reads one bounded installed vLLM Python source file via a disposable, read-only
CPU-only container pinned to the *original* service image digest.
"""
from __future__ import annotations

import argparse
import ast
import base64
import binascii
import hashlib
import json
import re
import sys
from pathlib import Path

# Direct invocation from src/ puts only src on Python's sys.path.
# Resolve this checked-out repo root in both CLI forms.
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

TARGET = "v1/worker/mamba_utils.py"
MAX_SOURCE_BYTES = 400_000
METHODS = (
    "initialize_from_forward_context", "_populate_metadata",
    "run_fused_precopy", "run_fused_postprocess_align",
)
KERNELS = (
    "_copy_mamba_state_block", "precopy_mamba_align_fused_kernel",
    "postprocess_mamba_fused_kernel",
)
# Source-only export; no execution or import of target vLLM module.
_READ_ONLY_EXPORT = (
    "import base64,hashlib,json,pathlib,sys;"
    "p=pathlib.Path(sys.argv[1]);"
    "assert p.name=='mamba_utils.py' and p.is_file() and not p.is_symlink();"
    "assert 0<p.stat().st_size<=400000;"
    "d=p.read_bytes();"
    "assert len(d)<=400000;"
    "print(json.dumps({'sha256':hashlib.sha256(d).hexdigest(),"
    "'source_base64':base64.b64encode(d).decode('ascii')}))"
)


class SourceBlocked(ValueError):
    pass


def cpu_probe_argv(image: str, runtime_user: str, path: str) -> list[str]:
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", image):
        raise SourceBlocked("IMAGE_ID_INVALID")
    if (not path.startswith("/") or not path.endswith("/vllm/" + TARGET)
            or ".." in path):
        raise SourceBlocked("SOURCE_PATH_INVALID")
    argv = [
        "docker", "run", "--rm", "--pull=never", "--runtime=runc",
        "--network=none", "--read-only", "--cap-drop=ALL",
        "--security-opt=no-new-privileges", "--cpus=1",
        "--memory=512m", "--memory-swap=512m", "--pids-limit=64",
        "--env", "NVIDIA_VISIBLE_DEVICES=void",
        "--env", "CUDA_VISIBLE_DEVICES=-1",
        "--env", "PYTHONDONTWRITEBYTECODE=1",
    ]
    if runtime_user:
        if len(runtime_user) > 80 or runtime_user.startswith("-"):
            raise SourceBlocked("RUNTIME_USER_INVALID")
        argv += ["--user", runtime_user]
    argv += ["--entrypoint", "python3", image, "-c", _READ_ONLY_EXPORT, path]
    return argv


def source_from_export(output: str) -> bytes:
    try:
        payload = json.loads(output)
        if not isinstance(payload, dict):
            raise ValueError()
        value = payload["source_base64"]
        digest = payload["sha256"]
        if not isinstance(value, str) or len(value) > MAX_SOURCE_BYTES * 2:
            raise ValueError()
        raw = base64.b64decode(value, validate=True)
        if (not raw or len(raw) > MAX_SOURCE_BYTES
                or hashlib.sha256(raw).hexdigest() != digest):
            raise ValueError()
        return raw
    except (ValueError, TypeError, KeyError, UnicodeError, binascii.Error):
        raise SourceBlocked("SOURCE_EXPORT_SHA_OR_SIZE_INVALID") from None


def inspect_source(raw: bytes) -> dict:
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_SOURCE_BYTES:
        raise SourceBlocked("SOURCE_INVALID_SIZE")
    try:
        source = raw.decode("utf-8")
        tree = ast.parse(source)
    except (SyntaxError, UnicodeError, ValueError):
        raise SourceBlocked("SOURCE_UNPARSEABLE") from None
    classes = [node for node in tree.body
               if isinstance(node, ast.ClassDef)
               and node.name == "MambaSpecDecodeGPUContext"]
    if len(classes) != 1:
        raise SourceBlocked("MAMBA_GPU_CONTEXT_CLASS_DRIFT")
    klass = classes[0]
    result: dict = {
        "status": "PINNED_IMAGE_MAMBA_UTILS_SOURCE_ABI_ONLY_NOT_GPU",
        "installed_source_sha256": hashlib.sha256(raw).hexdigest(),
        "read_only": True, "gpu_model_loaded": False,
        "source_runtime_state_reuse_verified": False,
        "methods": {}, "kernels": {},
    }
    lines = source.splitlines()
    for name in METHODS + KERNELS:
        parent = klass.body if name in METHODS else tree.body
        matches = [node for node in parent
                   if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and node.name == name]
        if len(matches) != 1:
            raise SourceBlocked("MAMBA_GPU_SYMBOL_DRIFT_" + name)
        fn = matches[0]
        calls = sorted({ast.unparse(node.func) for node in ast.walk(fn)
                        if isinstance(node, ast.Call)})
        attrs = sorted({node.attr for node in ast.walk(fn)
                        if isinstance(node, ast.Attribute)})
        info = {
            "first_line": fn.lineno, "last_line": fn.end_lineno,
            "args": [x.arg for x in fn.args.posonlyargs + fn.args.args],
            "calls": calls[:80], "attrs": attrs[:100],
            "source": [f"{i}: {lines[i - 1]}"
                       for i in range(fn.lineno, fn.end_lineno + 1)],
        }
        result["methods" if name in METHODS else "kernels"][name] = info
    # Check actual installed callback paths; no import of target vLLM code.
    pre = result["methods"]["run_fused_precopy"]
    post = result["methods"]["run_fused_postprocess_align"]
    if (not any("precopy_mamba_align_fused_kernel" in c for c in pre["calls"]) or
            not any("postprocess_mamba_fused_kernel" in c for c in post["calls"])):
        raise SourceBlocked("MAMBA_FUSED_KERNEL_CALL_SITES_DRIFT")
    return result


def inspect_installed_image() -> dict:
    # Existing preflight verifies branch, exact original image / container
    # identity, candidate absence, host stage hashes and worker/sched source.
    from src import p1_prefix_gpu_window as window
    try:
        _, original, _, _, _, _ = window.preflight()
        runtime_user = (original.get("Config") or {}).get("User") or ""
        root = window.probe_vllm_root(runtime_user)
        argv = cpu_probe_argv(window.IMAGE, runtime_user, root + "/" + TARGET)
        output = window.checked(argv, timeout=90)
    except (window.Blocked, window.legacy.Blocked):
        # preflight() delegates Docker/state identity checks to the legacy
        # service module, whose Blocked type is intentionally distinct.
        # An unavailable Docker daemon must remain a bounded CPU-only block
        # (exit 2), not an uncaught exception/traceback (exit 1).
        raise SourceBlocked("PINNED_IMAGE_CPU_PREFLIGHT_OR_PROBE_BLOCKED") from None
    report = inspect_source(source_from_export(output))
    report["source_path_relative"] = TARGET
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inspect-image", action="store_true", required=True)
    ap.add_argument("--show-source", action="store_true")
    args = ap.parse_args(argv)
    try:
        report = inspect_installed_image()
    except (SourceBlocked, OSError, ValueError) as exc:
        reason = str(exc) if isinstance(exc, SourceBlocked) else "CPU_SOURCE_PROBE_UNAVAILABLE"
        print(json.dumps({"status": "BLOCKED_NO_GPU", "reason": reason}))
        return 2
    details = report.pop("methods"), report.pop("kernels")
    print(json.dumps(report, sort_keys=True))
    for title, section in zip(("METHOD", "KERNEL"), details):
        for name, meta in section.items():
            print("=== %s: %s (%s-%s) ===" %
                  (title, name, meta["first_line"], meta["last_line"]))
            print(json.dumps({"args": meta["args"], "calls": meta["calls"],
                              "attrs": meta["attrs"]}, sort_keys=True))
            if args.show_source:
                for line in meta["source"]:
                    print(line)
    print("P1_PINNED_IMAGE_MAMBA_UTILS_CPU_SOURCE_ONLY_PASS_NO_GPU")
    return 0


if __name__ == "__main__":
    sys.exit(main())
