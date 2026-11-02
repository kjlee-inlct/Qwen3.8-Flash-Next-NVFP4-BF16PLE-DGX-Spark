"""Validate the original Blazux reduced-MTP ID asset against Orcarouter.

Pinned Apache-2.0 upstream data; only CPU/std-lib parsing and exact local
tokenizer/config metadata are used. No corpus, model, Docker or GPU required.
Opt-in stage writes a *private candidate*, never a serving asset.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile

from src.p2_mtp_draft_vocab import DraftVocab, DraftVocabError, FULL_VOCAB_SIZE, PROPOSED_DRAFT_SIZE
from src.p2_mtp_vocab_artifact import (
    Blocked, MAX_TOKENIZER_BYTES, _read_plain_file, _tokenizer_added_ids,
    npy_int32,
)
from src.p2_token_frequency import (
    MAX_CONFIG_BYTES, TOKENIZER_AUDITED_SHA256, special_ids,
)

UPSTREAM_REPO = "blazux/qwen3.8-Flash-DGX"
UPSTREAM_COMMIT = "b0aa8b77604139557169387b2fa8386355d8b651"
UPSTREAM_PATH = "src/draft_vocab_65536.npy"
UPSTREAM_GIT_BLOB_SHA = "2b94340a3ca0985a7494af369ac82536d61411de"
ASSET_RELATIVE = Path("assets/blazux/draft_vocab_65536.npy")
NPY_LENGTH = 262272
NPY_MAGIC = b"\x93NUMPY\x01\x00"
# A fixed recipe view already audited on the DGX (source itself is read-only).
RECIPE_RELATIVE = Path(
    "Workspace/llm/yslab-qwen38-bf16ple-dgx-spark/recipe-views/"
    "orca-uncensored-bf16-mtp/ee5b6b553f1226d2"
)


def git_blob_sha256_agnostic(data: bytes) -> str:
    """Git's SHA-1 *object* identity, independent of host git installation."""
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def parse_npy(data: bytes, *, expected_blob: str = UPSTREAM_GIT_BLOB_SHA) -> tuple[int, ...]:
    if len(data) != NPY_LENGTH or git_blob_sha256_agnostic(data) != expected_blob:
        raise Blocked("PINNED_UPSTREAM_DRAFT_BLOB_MISMATCH")
    if data[:8] != NPY_MAGIC:
        raise Blocked("UPSTREAM_DRAFT_NUMPY_VERSION_INVALID")
    header_len = struct.unpack_from("<H", data, 8)[0]
    offset = 10 + header_len
    if (offset != 128 or header_len <= 0 or offset > len(data)
            or not data[10:offset].endswith(b"\n")):
        raise Blocked("UPSTREAM_DRAFT_NUMPY_HEADER_INVALID")
    try:
        header = ast.literal_eval(data[10:offset].decode("ascii").strip())
    except (SyntaxError, UnicodeError, ValueError, TypeError):
        raise Blocked("UPSTREAM_DRAFT_HEADER_UNSAFE") from None
    if (not isinstance(header, dict)
            or header != {"descr": "<i4", "fortran_order": False,
                          "shape": (PROPOSED_DRAFT_SIZE,)}):
        raise Blocked("UPSTREAM_DRAFT_DTYPE_SHAPE_INVALID")
    if len(data) - offset != 4 * PROPOSED_DRAFT_SIZE:
        raise Blocked("UPSTREAM_DRAFT_NPY_PAYLOAD_INVALID")
    ids = struct.unpack_from("<" + "i" * PROPOSED_DRAFT_SIZE, data, offset)
    if (ids[:256] != tuple(range(256))
            or any(ids[i] <= ids[i-1] for i in range(1, len(ids)))
            or ids[0] < 0 or ids[-1] >= FULL_VOCAB_SIZE):
        raise Blocked("UPSTREAM_DRAFT_IDS_INVALID")
    if npy_int32(ids) != data:
        raise Blocked("UPSTREAM_DRAFT_NPY_NONCANONICAL")
    return ids


def audit(asset_path: Path, tokenizer_path: Path, config_path: Path, *,
          expected_blob: str = UPSTREAM_GIT_BLOB_SHA,
          expected_tokenizer: str = TOKENIZER_AUDITED_SHA256) -> dict:
    data = _read_plain_file(asset_path, NPY_LENGTH, label="UPSTREAM_DRAFT")
    ids = parse_npy(data, expected_blob=expected_blob)
    tokenizer_raw = _read_plain_file(tokenizer_path, MAX_TOKENIZER_BYTES,
                                     label="TOKENIZER")
    tokenizer_sha = hashlib.sha256(tokenizer_raw).hexdigest()
    if tokenizer_sha != expected_tokenizer:
        raise Blocked("ORCAROUTER_TOKENIZER_SOURCE_SHA_DRIFT")
    config_raw = _read_plain_file(config_path, MAX_CONFIG_BYTES,
                                  label="TOKENIZER_CONFIG")
    declared, required_special = special_ids(tokenizer_raw, config_raw)
    added, _ = _tokenizer_added_ids(tokenizer_raw)
    retained = set(ids)
    if not retained.issubset(declared):
        raise Blocked("UPSTREAM_DRAFT_CONTAINS_UNDECLARED_OR_PADDED_ID")
    mandatory = set(range(256)) | set(added) | required_special
    if not mandatory.issubset(retained):
        raise Blocked("UPSTREAM_DRAFT_MISSING_ORCAROUTER_REQUIRED_ID")
    vocab = DraftVocab.validate(
        ids, target_size=FULL_VOCAB_SIZE, draft_size=PROPOSED_DRAFT_SIZE,
        required_token_ids=mandatory)
    return {
        "status": "P2_ORCAROUTER_UPSTREAM_DRAFT_COMPATIBLE_CPU_SOURCE_ONLY",
        "upstream_repo": UPSTREAM_REPO,
        "upstream_commit": UPSTREAM_COMMIT,
        "upstream_git_blob_sha": expected_blob,
        "upstream_npy_sha256": hashlib.sha256(data).hexdigest(),
        "orcarouter_tokenizer_sha256": tokenizer_sha,
        "orcarouter_config_sha256": hashlib.sha256(config_raw).hexdigest(),
        "draft_mapping_fingerprint": vocab.fingerprint,
        "selected_ids": len(ids),
        "declared_tokenizer_ids": len(declared),
        "required_special_ids": len(required_special),
        "required_added_ids": len(added),
        "unallocated_head_rows_selected": 0,
        "source": "PINNED_APACHE_2_0_BLAZUX_PREBUILT_NOT_LOCAL_CORPUS",
        "corpus_required": False,
        "model_or_gpu_executed": False,
        "native_mtp_runtime_verified": False,
        "strict_numeric_resolved": False,
        "runtime_or_quality_approved": False,
    }


def stage(asset_path: Path, tokenizer_path: Path, config_path: Path, *,
          output_parent: Path = Path("/tmp"),
          expected_blob: str = UPSTREAM_GIT_BLOB_SHA,
          expected_tokenizer: str = TOKENIZER_AUDITED_SHA256) -> dict:
    if os.geteuid() == 0:
        raise Blocked("ROOT_FORBIDDEN")
    if output_parent.is_symlink() or not output_parent.is_dir():
        raise Blocked("OUTPUT_PARENT_REQUIRED")
    parent = output_parent.resolve(strict=True)
    if parent != Path("/tmp") and Path("/tmp") not in parent.parents:
        raise Blocked("OUTPUT_MUST_BE_IN_TMP")
    receipt = audit(asset_path, tokenizer_path, config_path,
                    expected_blob=expected_blob,
                    expected_tokenizer=expected_tokenizer)
    content = _read_plain_file(asset_path, NPY_LENGTH, label="UPSTREAM_DRAFT")
    if hashlib.sha256(content).hexdigest() != receipt["upstream_npy_sha256"]:
        raise Blocked("UPSTREAM_DRAFT_CHANGED_AFTER_AUDIT")
    folder = Path(tempfile.mkdtemp(prefix="p2-upstream-draft-", dir=str(parent)))
    try:
        folder.chmod(0o700)
        for name, payload in (
            ("ids.npy", content),
            ("receipt.json", (json.dumps(receipt, sort_keys=True, indent=2) + "\n").encode()),
        ):
            with os.fdopen(os.open(folder / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                                  0o600), "wb") as stream:
                stream.write(payload)
        if hashlib.sha256((folder / "ids.npy").read_bytes()).hexdigest() != receipt["upstream_npy_sha256"]:
            raise Blocked("STAGED_DRAFT_SHA_MISMATCH")
    except BaseException:
        shutil.rmtree(folder)
        raise
    return {**receipt,
            "status": "P2_ORCAROUTER_PINNED_DRAFT_PRIVATE_CANDIDATE_NOT_DEPLOYED",
            "private_directory": str(folder),
            "ids_file": str(folder / "ids.npy"),
            "receipt_file": str(folder / "receipt.json")}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--audit", action="store_true")
    mode.add_argument("--stage", action="store_true")
    p.add_argument("--asset", type=Path, required=True)
    p.add_argument("--tokenizer-json", type=Path, required=True)
    p.add_argument("--tokenizer-config", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        result = (stage(args.asset, args.tokenizer_json, args.tokenizer_config)
                  if args.stage else audit(args.asset, args.tokenizer_json,
                                           args.tokenizer_config))
        print(json.dumps(result, sort_keys=True))
        return 0
    except Blocked as exc:
        # All our failure codes are static, uppercase ASCII; never output a path.
        import re
        raw = str(exc)
        reason = raw if re.fullmatch(r"[A-Z][A-Z0-9_]{2,95}", raw) else "UNCLASSIFIED_BLOCKED"
        print("P2_UPSTREAM_DRAFT_BLOCKED REASON=" + reason, file=sys.stderr)
        return 2
    except (DraftVocabError, OSError, ValueError, TypeError, KeyError, MemoryError):
        print("P2_UPSTREAM_DRAFT_BLOCKED REASON=UNCLASSIFIED_INPUT_FAILURE",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
