"""Stage upstream blazux Tool/Responses code against *pinned Preview source* in tmp.

NO import of vllm, model, CUDA, GPU, service or server endpoint.  NO patch
of installed source, no container exec, no network, no generated overlay kept.
The upstream patch family targets vLLM 0.32: a successful temp source rebase is
only SOURCE_STAGED, never CPU parser/API behavior or deployment certification.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PATCHES = (
    ("qwen-tool-preamble.patch", "e4b14c758a74ace9a7363bb28368515af08e8b70"),
    ("qwen-tool-marker-guard.patch", "aba9e03608c9cb0a85b3992383dcd491a01a0ac3"),
    ("qwen-safe-output.patch", "569b2c7365d58e888f7d586cb39605ff745957d4"),
    ("qwen-tool-argument-schema.patch", "deeba34bf816d25b558ac76c200f8adba4293097"),
)
PATCH_DIR = Path(__file__).resolve().parent / "preview_p1_patches"
# These SHA256 hashes come from the user's actual DGX Preview-source audit,
# not from blazux's v0.32 source. Any version drift blocks staging.
PINNED_PREIMAGES = {
    "vllm/parser/engine/parser_engine.py": "f837bd5ae7bf759732a7d829209f93444b5692746d981509630c9bd3fcb39edb",
    "vllm/parser/qwen3.py": "8a7ee658322de7b736ea5b0f802d70dd07a124b5878b4f8ad2f99eca8e1d35fb",
    "vllm/parser/engine/streaming_parser_engine.py": "d00aba98ad26a2593e022a1faf5d048348d892822f75be40d19cf1dd522570f2",
    "vllm/parser/engine/parser_engine_config.py": "f7350e0ca9124001684f1f874ee72bf6a34932d3e4b84cc84567bbccf2f3e4b9",
    "vllm/entrypoints/openai/responses/serving.py": "d5fdb9ca62fa767d6feb61f6b3f5280f288051eea8605d27afa698cc00067968",
    "vllm/entrypoints/openai/responses/protocol.py": "7a853679f2488f2483dc0dd8352d5dfe91ed844e99ba970a5d3b95fa6b703db3",
}
ALLOWED_FILES = frozenset({
    "vllm/parser/engine/parser_engine.py",
    "vllm/parser/engine/parser_engine_config.py",
    "vllm/parser/engine/streaming_parser_engine.py",
    "vllm/parser/engine/argument_validation.py",
    "vllm/parser/engine/adapters.py",
    "vllm/parser/abstract_parser.py",
    "vllm/parser/qwen3.py",
    "vllm/parser/nemotron_v3.py",
    "vllm/entrypoints/openai/responses/protocol.py",
    "vllm/entrypoints/openai/responses/serving.py",
})
NEW_FILE = "vllm/parser/engine/argument_validation.py"
MAX_PATCH_BYTES = 100_000
MAX_SOURCE_BYTES = 2_000_000


class StageBlocked(RuntimeError):
    """A safety or source-compatibility gate failed (no deployment attempted)."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def parse_patch_files(data: bytes) -> set[str]:
    """Reject any patch path, new-file operation, or binary outside the allowlist."""
    if len(data) > MAX_PATCH_BYTES or not data:
        raise StageBlocked("INVALID_PATCH_SIZE")
    try:
        lines = data.decode("utf-8").splitlines()
    except UnicodeError as exc:
        raise StageBlocked("INVALID_PATCH_ENCODING") from exc
    if any(line.startswith(("GIT binary patch", "Binary files ", "rename ",
                            "copy ", "diff --git ", "new file mode ",
                            "deleted file mode ", "Index: ")) for line in lines):
        raise StageBlocked("FORBIDDEN_PATCH_FORMAT")
    old = None
    touched = set()
    for line in lines:
        if line.startswith("--- "):
            if old is not None:
                raise StageBlocked("MALFORMED_PATCH_HEADER")
            old = line[4:]
        elif line.startswith("+++ "):
            if old is None:
                raise StageBlocked("MALFORMED_PATCH_HEADER")
            new = line[4:]
            if not new.startswith("b/"):
                raise StageBlocked("FORBIDDEN_PATCH_PATH")
            path = new[2:]
            if path not in ALLOWED_FILES or (
                old != "a/" + path and not (old == "/dev/null" and path == NEW_FILE)
            ):
                raise StageBlocked("FORBIDDEN_PATCH_PATH")
            touched.add(path)
            old = None
    if old is not None or not touched or not any(line.startswith("@@ ") for line in lines):
        raise StageBlocked("MALFORMED_PATCH")
    return touched


def read_patch_bundle(directory: Path = PATCH_DIR) -> tuple[list[bytes], set[str]]:
    """Exact upstream Git blob identity; allows neither replacements nor symlinks."""
    payloads = []
    touched = set()
    for name, sha in PATCHES:
        path = directory / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_PATCH_BYTES:
            raise StageBlocked("PATCH_MISSING_OR_UNSAFE")
        data = path.read_bytes()
        if git_blob_sha(data) != sha:
            raise StageBlocked("PATCH_BLOB_DRIFT")
        touched.update(parse_patch_files(data))
        payloads.append(data)
    if not set(PINNED_PREIMAGES).issubset(touched) or NEW_FILE not in touched:
        raise StageBlocked("INCOMPLETE_PATCH_FAMILY")
    return payloads, touched


def find_installed_preview() -> Path:
    """find_spec of top-level package only: never import vllm or model."""
    spec = importlib.util.find_spec("vllm")
    if spec is None or not spec.submodule_search_locations:
        raise StageBlocked("INSTALLED_VLLM_NOT_FOUND")
    roots = list(spec.submodule_search_locations)
    if len(roots) != 1:
        raise StageBlocked("AMBIGUOUS_VLLM_ROOT")
    root = Path(roots[0])
    if root.is_symlink() or not root.is_dir():
        raise StageBlocked("UNSAFE_VLLM_ROOT")
    return root.parent


def validate_preview_pins() -> None:
    """Catch malformed static pins before blaming actual Preview source drift."""
    for pin in PINNED_PREIMAGES.values():
        if len(pin) != 64 or any(c not in "0123456789abcdef" for c in pin):
            raise StageBlocked("INVALID_PREVIEW_SHA_PIN")


def read_preview_sources(site: Path, touched: set[str]) -> dict[str, bytes]:
    """Snapshot only exact allowlisted Python files, with strict pinned hashes."""
    validate_preview_pins()
    files = {}
    package = site / "vllm"
    if package.is_symlink() or not package.is_dir():
        raise StageBlocked("UNSAFE_VLLM_ROOT")
    for name in sorted(touched):
        path = site / name
        current = package
        for part in Path(name).parts[1:-1]:
            current = current / part
            if current.is_symlink():
                raise StageBlocked("SOURCE_SYMLINK")
        if path.is_symlink():
            raise StageBlocked("SOURCE_SYMLINK")
        if not path.is_file():
            if name == NEW_FILE:
                continue
            raise StageBlocked("SOURCE_MISSING")
        if name == NEW_FILE:  # New upstream patch must not overwrite a live file.
            raise StageBlocked("NEW_FILE_ALREADY_EXISTS")
        if path.stat().st_size > MAX_SOURCE_BYTES:
            raise StageBlocked("SOURCE_TOO_LARGE")
        raw = path.read_bytes()
        expected = PINNED_PREIMAGES.get(name)
        if expected is not None and hashlib.sha256(raw).hexdigest() != expected:
            raise StageBlocked("PREVIEW_SHA_DRIFT")
        try:
            ast.parse(raw, filename=name)
        except (SyntaxError, UnicodeError) as exc:
            raise StageBlocked("PREVIEW_SYNTAX_UNSUPPORTED") from exc
        files[name] = raw
    return files


def _class_method_names(path: Path, class_name: str) -> set[str]:
    root = ast.parse(path.read_bytes())
    for node in root.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {child.name for child in node.body if isinstance(
                child, (ast.FunctionDef, ast.AsyncFunctionDef))}
    return set()


def check_implemented_hooks(root: Path) -> None:
    """Check actual patched Python AST, not synthetic stand-ins for vLLM."""
    requirements = {
        ("vllm/parser/engine/parser_engine.py", "ParserEngine"): {
            "_normalize_tool_arguments", "_arguments_block_emission",
            "_skip_incomplete_tool_slot", "_buffer_ambiguous_arguments"},
        ("vllm/parser/qwen3.py", "Qwen3Parser"): {
            "_normalize_tool_arguments", "_check_skip_tool_parsing"},
        ("vllm/parser/engine/streaming_parser_engine.py", "StreamingParserEngine"): {
            "_marker_is_literal"},
        ("vllm/entrypoints/openai/responses/serving.py", "OpenAIServingResponses"): {
            "_make_failed_response_event"},
    }
    for (name, klass), hooks in requirements.items():
        if not hooks.issubset(_class_method_names(root / name, klass)):
            raise StageBlocked("PATCHED_HOOKS_MISSING")
    arg_tree = ast.parse((root / NEW_FILE).read_bytes())
    functions = {
        n.name for n in arg_tree.body if isinstance(n, ast.FunctionDef)
    }
    if not {"validate_or_unwrap", "find_parameters"}.issubset(functions):
        raise StageBlocked("PATCHED_ARGUMENT_VALIDATOR_MISSING")


def first_rejected_hunk(sandbox: Path) -> str:
    """Reveal only an allowlisted source filename and old line number, never code."""
    for path in sorted(sandbox.rglob("*.rej")):
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_PATCH_BYTES:
            continue
        filename = path.relative_to(sandbox).as_posix()
        if not filename.endswith(".rej") or filename[:-4] not in ALLOWED_FILES:
            continue
        try:
            rejected = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        match = re.search(r"^@@ -(\d+)(?:,\d+)? \+\d+", rejected, re.M)
        # The output is bounded, non-sensitive source locator information.
        return filename[:-4] + (":old_line_" + match.group(1) if match else "")
    return "UNKNOWN_ALLOWLISTED_HUNK"


def stage_preview_bundle(site: Path, directory: Path = PATCH_DIR) -> dict:
    """Apply blazux source to TEMP COPIES only; never import or modify vllm."""
    patches, touched = read_patch_bundle(directory)
    originals = read_preview_sources(site, touched)
    if shutil.which("patch") is None:
        raise StageBlocked("PATCH_EXECUTABLE_UNAVAILABLE")
    with tempfile.TemporaryDirectory(prefix="preview-p1-source-only-") as tmp:
        sandbox = Path(tmp)
        for name, data in originals.items():
            path = sandbox / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        for index, payload in enumerate(patches, 1):
            try:
                result = subprocess.run(
                    ["patch", "--batch", "--forward", "--fuzz=0", "-p1",
                     "--silent", "--no-backup-if-mismatch"],
                    input=payload, cwd=sandbox, capture_output=True,
                    timeout=12, check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise StageBlocked("PATCH_TOOL_FAILED") from exc
            if result.returncode != 0:
                # Do not print patch stdout/stderr or source body; only a public
                # allowlisted relative path and rejected hunk's old line number.
                detail = first_rejected_hunk(sandbox)
                raise StageBlocked(f"PREVIEW_PATCH_{index}_CONTEXT_MISMATCH:{detail}")
        for name in touched:
            path = sandbox / name
            if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_SOURCE_BYTES:
                raise StageBlocked("PATCHED_OUTPUT_MISSING_OR_UNSAFE")
            try:
                ast.parse(path.read_bytes(), filename=name)
            except (SyntaxError, UnicodeError) as exc:
                raise StageBlocked("PATCHED_OUTPUT_SYNTAX_ERROR") from exc
        check_implemented_hooks(sandbox)
        # Source is deliberately deleted at TemporaryDirectory exit.
    return {
        "status": "BLazux_V032_PATCHES_STAGED_IN_TEMP_SOURCE_ONLY",
        "patches_in_order": len(PATCHES),
        "source_files": len(touched),
        "preview_pins_checked": len(PINNED_PREIMAGES),
        "model_gpu_api_run": False,
        "installed_vllm_modified": False,
        "actual_parser_compatibility_verified": False,
        "persisted_overlay": False,
    }


def main(argv: list[str]) -> int:
    if argv != ["--stage-preview-source-only"]:
        print(json.dumps({"status": "BLOCKED", "reason": "EXPLICIT_SOURCE_STAGE_ARG_REQUIRED"}))
        return 2
    try:
        result = stage_preview_bundle(find_installed_preview())
    except StageBlocked as exc:
        print(json.dumps({
            "status": "BLOCKED_NOT_APPLIED", "reason": exc.code,
            "installed_vllm_modified": False,
            "model_gpu_api_run": False,
            "runtime_compatibility_verified": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    print("PREVIEW_P1_TOOL_RESPONSES_TEMP_SOURCE_STAGED_ONLY_NOT_RUNTIME")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
