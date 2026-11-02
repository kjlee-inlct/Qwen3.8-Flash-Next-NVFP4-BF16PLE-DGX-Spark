"""Read-only P2 Orcarouter target/recipe tokenizer identity and ID inventory.

No Docker, GPU, tokenizer encoding, corpus discovery, network, model loading,
asset creation or writes. These file bytes alone do NOT prove active runtime
mounts, special-token completeness, or corpus coverage.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from src.p2_mtp_vocab_artifact import (
    MAX_TOKENIZER_BYTES, Blocked, _json_object, FULL_VOCAB_SIZE,
)


def _read_tokenizer(path: Path, *, recipe: bool) -> bytes:
    # HF snapshot tokenizer.json may be a symlink into the Hub blobs/ store.
    # The generated recipe view should instead be a real metadata copy.
    if recipe and path.is_symlink():
        raise Blocked("RECIPE_METADATA_MUST_BE_COPY_NOT_SYMLINK")
    try:
        actual = path.resolve(strict=True)
        if not actual.is_file() or not 0 < actual.stat().st_size <= MAX_TOKENIZER_BYTES:
            raise Blocked("TOKENIZER_MISSING_OR_UNBOUNDED")
        with actual.open("rb") as f:
            data = f.read(MAX_TOKENIZER_BYTES + 1)
        if len(data) != actual.stat().st_size:
            raise Blocked("TOKENIZER_READ_LENGTH_DRIFT")
        return data
    except (OSError, RuntimeError):
        raise Blocked("TOKENIZER_UNAVAILABLE") from None


def _ids(data: bytes) -> dict:
    doc = _json_object(data, label="TOKENIZER")
    model = doc.get("model")
    if not isinstance(model, dict) or not isinstance(model.get("vocab"), dict):
        raise Blocked("TOKENIZER_MODEL_VOCAB_NOT_PROVEN")
    vocab = model["vocab"]
    if not vocab:
        raise Blocked("TOKENIZER_EMPTY_MODEL_VOCAB")
    ids = list(vocab.values())
    if (any(type(v) is not int or not 0 <= v < FULL_VOCAB_SIZE for v in ids)
            or len(set(ids)) != len(ids)):
        raise Blocked("TOKENIZER_MODEL_VOCAB_IDS_INVALID")
    added = doc.get("added_tokens")
    if not isinstance(added, list) or not added:
        raise Blocked("TOKENIZER_ADDED_METADATA_MISSING")
    added_ids = []
    marked_special = []
    for item in added:
        if (not isinstance(item, dict)
                or type(item.get("id")) is not int
                or not 0 <= item["id"] < FULL_VOCAB_SIZE
                or type(item.get("special")) is not bool):
            raise Blocked("TOKENIZER_ADDED_ENTRY_INVALID")
        added_ids.append(item["id"])
        if item["special"]:
            marked_special.append(item["id"])
    if not marked_special or len(set(added_ids)) != len(added_ids):
        raise Blocked("TOKENIZER_SPECIAL_OR_ADDED_ID_INVALID")
    declared = set(ids) | set(added_ids)
    return {
        "model_vocab_ids": len(ids),
        "added_token_ids": len(added_ids),
        "marked_special_ids": len(marked_special),
        "distinct_declared_ids": len(declared),
        "min_declared_id": min(declared),
        "max_declared_id": max(declared),
        "ids_within_expected_target_head": max(declared) < FULL_VOCAB_SIZE,
        "fully_covers_all_target_head_ids": (
            len(declared) == FULL_VOCAB_SIZE and min(declared) == 0
            and max(declared) == FULL_VOCAB_SIZE - 1
        ),
        "special_token_ids": sorted(set(marked_special)),
        "added_token_id_count_in_model_vocab": len(set(ids) & set(added_ids)),
    }


def audit_pair(recipe: Path, source: Path) -> dict:
    if recipe.resolve(strict=True) == source.resolve(strict=True):
        raise Blocked("TOKENIZERS_SAME_FILE_NO_INDEPENDENT_PROVENANCE")
    left = _read_tokenizer(recipe, recipe=True)
    right = _read_tokenizer(source, recipe=False)
    sha_left = hashlib.sha256(left).hexdigest()
    sha_right = hashlib.sha256(right).hexdigest()
    if sha_left != sha_right or left != right:
        raise Blocked("RECIPE_ORCAROUTER_TOKENIZER_BYTES_MISMATCH")
    inventory = _ids(left)
    if not inventory["ids_within_expected_target_head"]:
        raise Blocked("TOKEN_IDS_EXCEED_MODEL_HEAD")
    return {
        "status": "P2_RECIPE_ORCAROUTER_TOKENIZER_EXACT_MATCH_SOURCE_ONLY",
        "sha256": sha_left,
        "recipe_metadata_copy_verified": True,
        "original_snapshot_bytes_match": True,
        "target_head_vocab_rows": FULL_VOCAB_SIZE,
        "inventory": inventory,
        "active_container_mount_proven": False,
        "tokenizer_config_specials_verified": False,
        "actual_domain_token_counts_available": False,
        "deployment_or_gpu_executed": False,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--recipe-tokenizer", type=Path, required=True)
    p.add_argument("--orcarouter-snapshot-tokenizer", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        print(json.dumps(audit_pair(a.recipe_tokenizer,
                                   a.orcarouter_snapshot_tokenizer),
                         sort_keys=True))
        return 0
    except (Blocked, OSError, RuntimeError, ValueError, TypeError):
        print("P2_TOKENIZER_SOURCE_IDENTITY_BLOCKED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
