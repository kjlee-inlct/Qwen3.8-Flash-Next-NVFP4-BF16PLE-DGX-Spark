"""P2 local token-count -> SHA-pinned 65,536-ID NumPy artifact (stdlib only).

No model loading, tokenizer execution, Docker, GPU, HTTP, filesystem search,
checkpoint edits or runtime enabling. Input is pre-tokenized aggregate counts,
NOT text/prompts. No production ID list is inferred without these inputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import sys
import tempfile

from src.p2_mtp_draft_vocab import FULL_VOCAB_SIZE, PROPOSED_DRAFT_SIZE, DraftVocabError
from src.p2_mtp_vocab_selection import select_draft_vocab, coverage

COUNTS_SCHEMA = "P2_TOKEN_COUNTS_V1"
MAX_COUNTS_BYTES = 8 * 1024 * 1024
MAX_TOKENIZER_BYTES = 80 * 1024 * 1024
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
MAX_COUNT = (1 << 63) - 1


class Blocked(ValueError):
    pass


def _read_plain_file(path: Path, max_bytes: int, *, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise Blocked(label + "_FILE_REQUIRED_NO_SYMLINK")
    size = path.stat().st_size
    if not 0 < size <= max_bytes:
        raise Blocked(label + "_BOUNDED_SIZE_REQUIRED")
    data = path.read_bytes()
    if len(data) != size:
        raise Blocked(label + "_READ_LENGTH_DRIFT")
    return data


def _json_object(raw: bytes, *, label: str) -> dict:
    def unique_pairs(pairs):
        obj = {}
        for name, value in pairs:
            if name in obj:
                raise Blocked(label + "_DUPLICATE_JSON_KEY")
            obj[name] = value
        return obj

    try:
        value = json.loads(raw, object_pairs_hook=unique_pairs)
    except Blocked:
        raise
    except (UnicodeError, ValueError, TypeError):
        raise Blocked(label + "_INVALID_JSON") from None
    if not isinstance(value, dict):
        raise Blocked(label + "_OBJECT_REQUIRED")
    return value


def _tokenizer_added_ids(raw: bytes) -> tuple[tuple[int, ...], tuple[int, ...]]:
    obj = _json_object(raw, label="TOKENIZER")
    tokens = obj.get("added_tokens")
    if not isinstance(tokens, list):
        raise Blocked("TOKENIZER_ADDED_TOKENS_NOT_PROVEN")
    seen = set()
    specials = set()
    for item in tokens:
        if (not isinstance(item, dict) or type(item.get("id")) is not int
                or not 0 <= item["id"] < FULL_VOCAB_SIZE
                or type(item.get("special")) is not bool):
            raise Blocked("TOKENIZER_ADDED_TOKENS_INVALID")
        tid = item["id"]
        if tid in seen:
            raise Blocked("TOKENIZER_ADDED_TOKEN_DUPLICATE")
        seen.add(tid)
        if item["special"]:
            specials.add(tid)
    if not specials:
        raise Blocked("TOKENIZER_SPECIAL_IDS_NOT_PROVEN")
    return tuple(sorted(seen)), tuple(sorted(specials))


def parse_inputs(counts_raw: bytes, tokenizer_raw: bytes):
    data = _json_object(counts_raw, label="COUNTS")
    if set(data) != {"schema", "tokenizer_sha256", "token_counts", "special_token_ids"}:
        raise Blocked("COUNTS_SCHEMA_FIELDS_INVALID")
    if data["schema"] != COUNTS_SCHEMA:
        raise Blocked("COUNTS_SCHEMA_VERSION_INVALID")
    sha = data["tokenizer_sha256"]
    if (not isinstance(sha, str) or not HEX64.fullmatch(sha)
            or hashlib.sha256(tokenizer_raw).hexdigest() != sha):
        raise Blocked("TOKENIZER_EXACT_SHA_MISMATCH")
    added, tokenizer_specials = _tokenizer_added_ids(tokenizer_raw)
    external_specials = data["special_token_ids"]
    if (not isinstance(external_specials, list) or not external_specials
            or any(type(t) is not int or not 0 <= t < FULL_VOCAB_SIZE
                   for t in external_specials)):
        raise Blocked("SPECIAL_IDS_REQUIRED")
    # Extra special IDs can include tokenizer-config control markers. Their
    # provenance is caller supplied; the receipt never certifies correctness.
    raw_counts = data["token_counts"]
    if (not isinstance(raw_counts, dict) or not raw_counts
            or len(raw_counts) > FULL_VOCAB_SIZE):
        raise Blocked("COUNTS_NONEMPTY_MAP_REQUIRED")
    counts = {}
    for raw_id, value in raw_counts.items():
        if (not isinstance(raw_id, str) or not raw_id.isascii()
                or not raw_id.isdecimal() or (len(raw_id) > 1 and raw_id[0] == "0")
                or type(value) is not int or not 0 < value <= MAX_COUNT):
            raise Blocked("COUNTS_ID_OR_VALUE_INVALID")
        tid = int(raw_id)
        if not 0 <= tid < FULL_VOCAB_SIZE:
            raise Blocked("COUNTS_ID_OUT_OF_RANGE")
        counts[tid] = value
    if sum(counts.values()) > MAX_COUNT:
        raise Blocked("COUNTS_TOTAL_OVERFLOW")
    specials = set(external_specials) | set(tokenizer_specials)
    vocab = select_draft_vocab(
        counts, special_ids=specials, added_ids=added,
        full_size=FULL_VOCAB_SIZE, draft_size=PROPOSED_DRAFT_SIZE,
        byte_fallback_count=256,
    )
    return vocab, counts, {
        "tokenizer_added_id_count": len(added),
        "tokenizer_special_id_count": len(tokenizer_specials),
        "supplied_special_id_count": len(set(external_specials)),
    }


def npy_int32(ids: tuple[int, ...]) -> bytes:
    """Produce exactly the NumPy 1.0 little-endian int32 1-D format."""
    if (len(ids) != PROPOSED_DRAFT_SIZE
            or any(type(i) is not int or not 0 <= i < FULL_VOCAB_SIZE for i in ids)
            or tuple(sorted(set(ids))) != ids
            or ids[:256] != tuple(range(256))):
        raise Blocked("NPY_IDS_CONTRACT_INVALID")
    header = "{'descr': '<i4', 'fortran_order': False, 'shape': (65536,), }"
    prefix_len = 10  # magic + version + 2-byte header length
    padding = (-(prefix_len + len(header) + 1)) % 16
    payload_header = (header + " " * padding + "\n").encode("ascii")
    if len(payload_header) > 65535:
        raise Blocked("NPY_HEADER_TOO_LONG")
    return (
        b"\x93NUMPY\x01\x00"
        + struct.pack("<H", len(payload_header))
        + payload_header
        + struct.pack("<" + "i" * len(ids), *ids)
    )


def build(counts_path: Path, tokenizer_path: Path, output_parent: Path) -> dict:
    if os.geteuid() == 0:
        raise Blocked("ROOT_FORBIDDEN")
    # /tmp is permitted for private candidate artifacts; do not create or
    # overwrite files inside any checkout, tokenizer/model/cache directory.
    if output_parent.is_symlink() or not output_parent.is_dir():
        raise Blocked("OUTPUT_PARENT_REQUIRED_NO_SYMLINK")
    parent = output_parent.resolve(strict=True)
    if parent != Path("/tmp") and Path("/tmp") not in parent.parents:
        raise Blocked("OUTPUT_MUST_BE_IN_TMP")
    counts_raw = _read_plain_file(counts_path, MAX_COUNTS_BYTES, label="COUNTS")
    tokenizer_raw = _read_plain_file(tokenizer_path, MAX_TOKENIZER_BYTES, label="TOKENIZER")
    if counts_path.resolve() == tokenizer_path.resolve():
        raise Blocked("TOKENIZER_AND_COUNTS_MUST_DIFFER")
    vocab, counts, stats = parse_inputs(counts_raw, tokenizer_raw)
    content = npy_int32(vocab.draft_to_full)
    hash_value = hashlib.sha256(content).hexdigest()
    coverage_fraction = coverage(counts, vocab)
    receipt = {
        "status": "P2_DRAFT_VOCAB_PRIVATE_ARTIFACT_CREATED_NOT_DEPLOYABLE",
        "schema": "P2_DRAFT_VOCAB_RECEIPT_V1",
        "npy_sha256": hash_value,
        "npy_filename": "ids.npy",
        "tokenizer_sha256": hashlib.sha256(tokenizer_raw).hexdigest(),
        "token_counts_sha256": hashlib.sha256(counts_raw).hexdigest(),
        "draft_mapping_fingerprint": vocab.fingerprint,
        "target_vocab_size": FULL_VOCAB_SIZE,
        "draft_vocab_size": PROPOSED_DRAFT_SIZE,
        "token_frequency_count": len(counts),
        "token_frequency_total": sum(counts.values()),
        "aggregate_count_coverage": coverage_fraction,
        "candidate_opt_in_path_env": "VLLM_P2_DRAFT_VOCAB",
        "candidate_opt_in_hash_env": "VLLM_P2_DRAFT_VOCAB_SHA256",
        "required_ids_included": True,
        "corpus_representativeness_verified": False,
        "tokenizer_specials_complete_verified": False,
        "native_mtp_runtime_verified": False,
        "candidate_gpu_or_api_executed": False,
        **stats,
    }
    folder = Path(tempfile.mkdtemp(prefix="p2-draft-vocab-", dir=str(parent)))
    try:
        folder.chmod(0o700)
        for name, contents in (
            ("ids.npy", content),
            ("receipt.json", (json.dumps(receipt, sort_keys=True, indent=2) + "\n").encode()),
        ):
            fd = os.open(folder / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            try:
                with os.fdopen(fd, "wb") as out:
                    out.write(contents)
            except BaseException:
                raise
        if hashlib.sha256((folder / "ids.npy").read_bytes()).hexdigest() != hash_value:
            raise Blocked("NPY_WRITE_VERIFICATION_FAILED")
    except BaseException:
        shutil.rmtree(folder)
        raise
    return {**receipt, "private_directory": str(folder)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--counts-json", type=Path, required=True)
    parser.add_argument("--tokenizer-json", type=Path, required=True)
    parser.add_argument("--output-parent", type=Path, default=Path("/tmp"))
    args = parser.parse_args(argv)
    try:
        print(json.dumps(build(args.counts_json, args.tokenizer_json,
                               args.output_parent), sort_keys=True))
        return 0
    except (Blocked, DraftVocabError, OSError, ValueError, TypeError,
            OverflowError, MemoryError):
        print("P2_DRAFT_VOCAB_ARTIFACT_BLOCKED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
