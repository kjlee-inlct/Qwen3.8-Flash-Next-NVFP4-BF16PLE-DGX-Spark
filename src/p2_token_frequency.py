"""Offline Orcarouter token-ID frequencies from explicitly authorized files.

No corpus discovery, text export, Docker, GPU, network, HTTP or runtime changes.
Only the caller-provided tokenizer.json is loaded by Python tokenizers.
Output: a private /tmp aggregate for the existing P2 vocabulary builder.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
from typing import Any

from src.p2_mtp_vocab_artifact import (
    Blocked, FULL_VOCAB_SIZE, MAX_COUNT, MAX_TOKENIZER_BYTES,
    _json_object, _read_plain_file, parse_inputs,
)

TOKENIZER_AUDITED_SHA256 = "06b9509352d2af50381ab2247e083b80d32d5c0aba91c272ca9ff729b6a0e523"
DOMAINS = frozenset(("ko", "en", "code", "technical", "tool"))
MAX_CONFIG_BYTES = 8 * 1024 * 1024
MAX_CORPUS_BYTES = 1024 * 1024 * 1024
MAX_LINE_BYTES = 2 * 1024 * 1024
MAX_RECORDS = 1_000_000
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
SPECIAL_KEYS = frozenset((
    "bos_token", "eos_token", "unk_token", "pad_token", "sep_token",
    "cls_token", "mask_token", "additional_special_tokens",
))


def _token_content(value: Any) -> str:
    if isinstance(value, str) and value:
        return value
    if isinstance(value, dict) and isinstance(value.get("content"), str) and value["content"]:
        return value["content"]
    raise Blocked("TOKENIZER_CONFIG_SPECIAL_CONTENT_INVALID")


def special_ids(tokenizer_raw: bytes, config_raw: bytes) -> tuple[set[int], set[int]]:
    """Resolve config specials against declared tokenizer IDs, never head padding."""
    tokenizer = _json_object(tokenizer_raw, label="TOKENIZER")
    config = _json_object(config_raw, label="TOKENIZER_CONFIG")
    model = tokenizer.get("model")
    vocab = model.get("vocab") if isinstance(model, dict) else None
    if not isinstance(vocab, dict) or not vocab:
        raise Blocked("TOKENIZER_VOCAB_UNAVAILABLE")
    names: dict[str, int] = {}
    declared: set[int] = set()
    for token, tid in vocab.items():
        if not isinstance(token, str) or type(tid) is not int or not 0 <= tid < FULL_VOCAB_SIZE or tid in declared:
            raise Blocked("TOKENIZER_VOCAB_INVALID")
        names[token] = tid
        declared.add(tid)
    added = tokenizer.get("added_tokens")
    if not isinstance(added, list) or not added:
        raise Blocked("TOKENIZER_ADDED_TOKENS_REQUIRED")
    specials: set[int] = set()
    for item in added:
        if (not isinstance(item, dict) or type(item.get("id")) is not int
                or type(item.get("special")) is not bool
                or not isinstance(item.get("content"), str) or not item["content"]
                or not 0 <= item["id"] < FULL_VOCAB_SIZE):
            raise Blocked("TOKENIZER_ADDED_METADATA_INVALID")
        tid, name = item["id"], item["content"]
        if (name in names and names[name] != tid) or (tid in declared and names.get(name) != tid):
            raise Blocked("TOKENIZER_ADDED_ID_COLLISION")
        names[name] = tid
        declared.add(tid)
        if item["special"]:
            specials.add(tid)
    decoder = config.get("added_tokens_decoder", {})
    if not isinstance(decoder, dict):
        raise Blocked("TOKENIZER_CONFIG_DECODER_INVALID")
    for key, item in decoder.items():
        if (not isinstance(key, str) or not key.isascii() or not key.isdecimal()
                or (len(key) > 1 and key[0] == "0") or not isinstance(item, dict)
                or type(item.get("special")) is not bool):
            raise Blocked("TOKENIZER_CONFIG_DECODER_INVALID")
        tid = int(key)
        if tid not in declared or names.get(_token_content(item)) != tid:
            raise Blocked("TOKENIZER_CONFIG_DECODER_MISMATCH")
        if item["special"]:
            specials.add(tid)
    config_tokens: set[int] = set()
    for key in SPECIAL_KEYS:
        value = config.get(key)
        if value is None:
            continue
        values = value if key == "additional_special_tokens" else [value]
        if not isinstance(values, list):
            raise Blocked("TOKENIZER_CONFIG_SPECIAL_LIST_INVALID")
        for item in values:
            name = _token_content(item)
            if name not in names:
                raise Blocked("TOKENIZER_CONFIG_SPECIAL_UNDECLARED")
            config_tokens.add(names[name])
    if not specials or not config_tokens:
        raise Blocked("TOKENIZER_CONFIG_SPECIALS_NOT_PROVEN")
    return declared, specials | config_tokens


def _check_corpus(path: Path) -> int:
    if path.is_symlink() or not path.is_file():
        raise Blocked("CORPUS_REGULAR_FILE_REQUIRED_NO_SYMLINK")
    s = path.stat()
    if not stat.S_ISREG(s.st_mode) or not 0 < s.st_size <= MAX_CORPUS_BYTES:
        raise Blocked("CORPUS_SIZE_NOT_BOUNDED")
    return s.st_size


def count_records(corpora: list[tuple[str, Path]], tokenizer: Any,
                  declared_ids: set[int], *,
                  text_files: list[tuple[str, Path]] | None = None
                  ) -> tuple[dict[int, int], list[dict]]:
    """Count explicitly named JSONL records or whole UTF-8 text documents.

    A text file is encoded as *one* document, preserving cross-line token
    boundaries. Large text documents are rejected, never silently chunked.
    """
    sources = [(d, p, "jsonl") for d, p in corpora]
    sources.extend((d, p, "text") for d, p in (text_files or []))
    if not sources or len(sources) > 20:
        raise Blocked("CORPORA_REQUIRED_MAX20")
    totals: Counter[int] = Counter()
    total_all_tokens = 0
    receipts: list[dict] = []
    seen_paths: set[Path] = set()
    for domain, path, source_format in sources:
        if domain not in DOMAINS:
            raise Blocked("UNRECOGNIZED_DOMAIN")
        p = path.resolve(strict=True)
        if p in seen_paths:
            raise Blocked("CORPUS_DUPLICATE_PATH")
        seen_paths.add(p)
        expected_size = _check_corpus(path)
        if source_format == "text" and expected_size > MAX_LINE_BYTES:
            raise Blocked("TEXT_DOCUMENT_TOO_LARGE")
        sha = hashlib.sha256()
        records, tokens, bytes_seen = 0, 0, 0

        def consume(value: str) -> None:
            nonlocal total_all_tokens, tokens
            try:
                ids = tokenizer.encode(value, add_special_tokens=False).ids
            except Exception:
                raise Blocked("TOKENIZER_ENCODING_FAILED") from None
            if not isinstance(ids, list) or not ids:
                raise Blocked("TOKENIZER_EMPTY_OUTPUT")
            for tid in ids:
                if type(tid) is not int or tid not in declared_ids:
                    raise Blocked("TOKENIZER_RETURNED_UNDECLARED_ID")
                totals[tid] += 1
                tokens += 1
                total_all_tokens += 1
                if tokens > MAX_COUNT or total_all_tokens > MAX_COUNT:
                    raise Blocked("COUNT_OVERFLOW")

        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, "rb") as stream:
            st = os.fstat(stream.fileno())
            if not stat.S_ISREG(st.st_mode) or st.st_size != expected_size:
                raise Blocked("CORPUS_CHANGED_AT_OPEN")
            if source_format == "text":
                raw = stream.read(MAX_LINE_BYTES + 1)
                bytes_seen = len(raw)
                if bytes_seen != expected_size:
                    raise Blocked("TEXT_DOCUMENT_CHANGED")
                sha.update(raw)
                try:
                    value = raw.decode("utf-8")
                except UnicodeDecodeError:
                    raise Blocked("TEXT_DOCUMENT_INVALID_UTF8") from None
                if not value.strip():
                    raise Blocked("TEXT_DOCUMENT_EMPTY")
                records = 1
                consume(value)
            else:
                for raw in stream:
                    bytes_seen += len(raw)
                    if len(raw) > MAX_LINE_BYTES or bytes_seen > MAX_CORPUS_BYTES:
                        raise Blocked("CORPUS_RECORD_TOO_LARGE")
                    sha.update(raw)
                    records += 1
                    if records > MAX_RECORDS:
                        raise Blocked("CORPUS_TOO_MANY_RECORDS")
                    record = _json_object(raw, label="CORPUS_RECORD")
                    if (set(record) != {"text"} or not isinstance(record["text"], str)
                            or not record["text"]):
                        raise Blocked("CORPUS_TEXT_FIELD_REQUIRED")
                    consume(record["text"])
            if bytes_seen != expected_size or path.stat().st_size != expected_size:
                raise Blocked("CORPUS_READ_SIZE_CHANGED")
        receipts.append({"domain": domain, "format": source_format,
                         "records": records, "tokens": tokens,
                         "bytes": bytes_seen, "corpus_sha256": sha.hexdigest()})
    if not totals:
        raise Blocked("COUNTS_EMPTY")
    return dict(totals), receipts


def _prepare_tokenizer(tokenizer_path: Path, config_path: Path, *,
                       tokenizer_factory=None):
    tokenizer_raw = _read_plain_file(tokenizer_path, MAX_TOKENIZER_BYTES,
                                     label="TOKENIZER")
    digest = hashlib.sha256(tokenizer_raw).hexdigest()
    if digest != TOKENIZER_AUDITED_SHA256:
        raise Blocked("TOKENIZER_AUDITED_SHA_MISMATCH")
    config_raw = _read_plain_file(config_path, MAX_CONFIG_BYTES,
                                  label="TOKENIZER_CONFIG")
    declared_ids, required_specials = special_ids(tokenizer_raw, config_raw)
    if tokenizer_factory is None:
        try:
            from tokenizers import Tokenizer
        except ImportError:
            raise Blocked("TOKENIZERS_PACKAGE_NOT_INSTALLED_OFFLINE") from None
        tokenizer_factory = Tokenizer.from_file
    try:
        tokenizer = tokenizer_factory(str(tokenizer_path))
    except Exception:
        raise Blocked("TOKENIZER_LOADING_FAILED") from None
    return tokenizer_raw, digest, config_raw, declared_ids, required_specials, tokenizer


def probe(tokenizer_path: Path, config_path: Path, *,
          tokenizer_factory=None) -> dict:
    """Real local tokenizer CPU encode, no corpus or output files."""
    (_, digest, config, declared, required,
     tokenizer) = _prepare_tokenizer(tokenizer_path, config_path,
                                     tokenizer_factory=tokenizer_factory)
    try:
        ids = tokenizer.encode("P2 offline tokenizer probe", add_special_tokens=False).ids
    except Exception:
        raise Blocked("TOKENIZER_PROBE_ENCODING_FAILED") from None
    if (not isinstance(ids, list) or not ids
            or any(type(tid) is not int or tid not in declared for tid in ids)):
        raise Blocked("TOKENIZER_PROBE_IDS_INVALID")
    return {"status": "P2_TOKENIZER_LOCAL_CPU_ENCODER_VERIFIED_SOURCE_ONLY",
            "tokenizer_sha256": digest,
            "tokenizer_config_sha256": hashlib.sha256(config).hexdigest(),
            "declared_ids": len(declared),
            "required_special_ids": len(required),
            "synthetic_probe_token_count": len(ids),
            "actual_corpus_counted": False, "gpu_api_model_executed": False}


def count(corpora: list[tuple[str, Path]], tokenizer_path: Path,
          config_path: Path, output_parent: Path, *,
          tokenizer_factory=None,
          text_files: list[tuple[str, Path]] | None = None) -> dict:
    if os.geteuid() == 0:
        raise Blocked("ROOT_FORBIDDEN")
    if output_parent.is_symlink() or not output_parent.is_dir():
        raise Blocked("OUTPUT_PARENT_REQUIRED")
    parent = output_parent.resolve(strict=True)
    if parent != Path("/tmp") and Path("/tmp") not in parent.parents:
        raise Blocked("OUTPUT_MUST_BE_IN_TMP")
    (tokenizer_raw, digest, config_raw, declared_ids, required_specials,
     tokenizer) = _prepare_tokenizer(tokenizer_path, config_path,
                                     tokenizer_factory=tokenizer_factory)
    totals, corp_receipts = count_records(corpora, tokenizer, declared_ids,
                                         text_files=text_files)
    payload = {"schema": "P2_TOKEN_COUNTS_V1", "tokenizer_sha256": digest,
               "token_counts": {str(k): totals[k] for k in sorted(totals)},
               "special_token_ids": sorted(required_specials)}
    data = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    if len(data) > 8 * 1024 * 1024:
        raise Blocked("COUNTS_ARTIFACT_TOO_LARGE")
    # Validate the actual legacy .npy-builder input contract before writing.
    parse_inputs(data, tokenizer_raw)
    result = {"status": "P2_OFFLINE_ACTUAL_CORPUS_TOKEN_COUNTS_CREATED_NOT_DEPLOYED",
              "schema": "P2_TOKEN_COUNT_RECEIPT_V1",
              "tokenizer_sha256": digest,
              "tokenizer_config_sha256": hashlib.sha256(config_raw).hexdigest(),
              "token_counts_sha256": hashlib.sha256(data).hexdigest(),
              "distinct_counted_ids": len(totals),
              "declared_tokenizer_ids": len(declared_ids),
              "target_head_rows": FULL_VOCAB_SIZE,
              "required_special_ids": len(required_specials),
              "total_counted_tokens": sum(totals.values()),
              "inputs": corp_receipts,
              "source": "OPERATOR_SUPPLIED_EXPLICIT_LOCAL_CORPORA_ONLY",
              "corpus_rights_and_representativeness_verified": False,
              "runtime_tokenizer_mount_verified": False,
              "gpu_api_model_executed": False}
    folder = Path(tempfile.mkdtemp(prefix="p2-token-counts-", dir=str(parent)))
    folder.chmod(0o700)
    try:
        for name, content in (("counts.json", data),
                              ("receipt.json", (json.dumps(result, sort_keys=True, indent=2) + "\n").encode())):
            fd = os.open(folder / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "wb") as output:
                output.write(content)
        if hashlib.sha256((folder / "counts.json").read_bytes()).hexdigest() != result["token_counts_sha256"]:
            raise Blocked("COUNTS_WRITE_VERIFICATION_FAILED")
    except BaseException:
        for name in ("counts.json", "receipt.json"):
            (folder / name).unlink(missing_ok=True)
        folder.rmdir()
        raise
    return {**result, "private_directory": str(folder),
            "counts_file": str(folder / "counts.json")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tokenizer-json", type=Path, required=True)
    parser.add_argument("--tokenizer-config", type=Path, required=True)
    parser.add_argument("--probe", action="store_true",
                        help="Read-only CPU tokenizer/config check, no corpus")
    parser.add_argument("--corpus", nargs=2, action="append",
                        metavar=("DOMAIN", "JSONL"), default=[])
    parser.add_argument("--text", nargs=2, action="append",
                        metavar=("DOMAIN", "UTF8_FILE"), default=[])
    parser.add_argument("--output-parent", type=Path, default=Path("/tmp"))
    args = parser.parse_args(argv)
    try:
        if args.probe:
            if args.corpus or args.text:
                raise Blocked("PROBE_REJECTS_CORPUS")
            print(json.dumps(probe(args.tokenizer_json, args.tokenizer_config),
                             sort_keys=True))
        else:
            if not args.corpus and not args.text:
                raise Blocked("EXPLICIT_CORPUS_REQUIRED")
            inputs = [(domain, Path(path)) for domain, path in args.corpus]
            plain = [(domain, Path(path)) for domain, path in args.text]
            print(json.dumps(count(inputs, args.tokenizer_json,
                                   args.tokenizer_config, args.output_parent,
                                   text_files=plain), sort_keys=True))
        return 0
    except Blocked as exc:
        # Never echo tokenizer names, corpus content, paths or exception details.
        # Our own error codes are uppercase ASCII; fail closed for anything else.
        raw = str(exc)
        reason = (raw if re.fullmatch(r"[A-Z][A-Z0-9_]{2,95}", raw)
                  else "UNCLASSIFIED_BLOCKED")
        print(f"P2_OFFLINE_TOKEN_COUNTS_BLOCKED REASON={reason}",
              file=sys.stderr)
        return 2
    except FileNotFoundError:
        print("P2_OFFLINE_TOKEN_COUNTS_BLOCKED REASON=INPUT_FILE_MISSING",
              file=sys.stderr)
        return 2
    except PermissionError:
        print("P2_OFFLINE_TOKEN_COUNTS_BLOCKED REASON=INPUT_PERMISSION_DENIED",
              file=sys.stderr)
        return 2
    except (OSError, ValueError, TypeError, KeyError, OverflowError,
            MemoryError):
        print("P2_OFFLINE_TOKEN_COUNTS_BLOCKED REASON=UNCLASSIFIED_RUNTIME_FAILURE",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
