"""P2 private .npy asset: real bytes, SHA, dimensions and fail-closed IO."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from src import p2_mtp_vocab_artifact as artifact


def fake_tokenizer_bytes(*, specials=True) -> bytes:
    tokens = [{"id": 248318, "special": False},
              {"id": 248319, "special": specials}]
    return json.dumps({"model": {"type": "BPE"}, "added_tokens": tokens}).encode()


def input_data(tokenizer: bytes, *, counts=None, special_ids=None) -> bytes:
    return json.dumps({
        "schema": artifact.COUNTS_SCHEMA,
        "tokenizer_sha256": hashlib.sha256(tokenizer).hexdigest(),
        "token_counts": ({"0": 4, "120000": 5000, "248000": 100}
                         if counts is None else counts),
        "special_token_ids": [248319] if special_ids is None else special_ids,
    }).encode()


class VocabArtifactTests(unittest.TestCase):
    def test_actual_npy_v1_bytes_and_sha(self):
        tokens = fake_tokenizer_bytes()
        mapping, counts, meta = artifact.parse_inputs(input_data(tokens), tokens)
        data = artifact.npy_int32(mapping.draft_to_full)
        self.assertEqual(data[:8], b"\x93NUMPY\x01\x00")
        size = struct.unpack("<H", data[8:10])[0]
        self.assertEqual((10 + size) % 16, 0)
        self.assertIn(b"'descr': '<i4'", data[10:10 + size])
        self.assertIn(b"'shape': (65536,)", data[10:10 + size])
        self.assertEqual(len(data), 10 + size + 65536 * 4)
        numbers = struct.unpack("<65536i", data[10 + size:])
        self.assertEqual(numbers, mapping.draft_to_full)
        self.assertEqual(numbers[:256], tuple(range(256)))
        self.assertIn(248319, numbers)
        self.assertIn(248318, numbers)
        self.assertIn(120000, numbers)
        self.assertEqual(meta["tokenizer_added_id_count"], 2)
        self.assertIn(120000, counts)

    def test_reproducible_bytes_and_metadata_independent_of_count_order(self):
        t = fake_tokenizer_bytes()
        a = input_data(t, counts={"120000": 5000, "0": 4})
        b = input_data(t, counts={"0": 4, "120000": 5000})
        va, _, _ = artifact.parse_inputs(a, t)
        vb, _, _ = artifact.parse_inputs(b, t)
        self.assertEqual(artifact.npy_int32(va.draft_to_full),
                         artifact.npy_int32(vb.draft_to_full))

    def test_wrong_tokenizer_sha_and_missing_special_block(self):
        t = fake_tokenizer_bytes()
        wrong = input_data(t).replace(hashlib.sha256(t).hexdigest().encode(), b"0" * 64)
        with self.assertRaisesRegex(artifact.Blocked, "EXACT_SHA_MISMATCH"):
            artifact.parse_inputs(wrong, t)
        with self.assertRaisesRegex(artifact.Blocked, "SPECIAL_IDS_NOT_PROVEN"):
            artifact.parse_inputs(input_data(fake_tokenizer_bytes(specials=False)),
                                  fake_tokenizer_bytes(specials=False))

    def test_count_ranges_zeros_types_and_duplicate_block(self):
        t = fake_tokenizer_bytes()
        for counts in ({"1": 0}, {"1": -3}, {"1": True},
                       {"248320": 10}, {"01": 2}, {"a": 3}):
            with self.subTest(counts=counts), self.assertRaises(artifact.Blocked):
                artifact.parse_inputs(input_data(t, counts=counts), t)
        with self.assertRaisesRegex(artifact.Blocked, "COUNTS_NONEMPTY"):
            artifact.parse_inputs(input_data(t, counts={}), t)

    def test_tampered_mapping_rejected(self):
        with self.assertRaisesRegex(artifact.Blocked, "CONTRACT_INVALID"):
            artifact.npy_int32(tuple(range(1, 65537)))
        with self.assertRaisesRegex(artifact.Blocked, "CONTRACT_INVALID"):
            artifact.npy_int32(tuple(range(65535)) + (65534,))

    def test_private_output_is_real_and_not_deployable(self):
        t = fake_tokenizer_bytes()
        with tempfile.TemporaryDirectory(dir="/tmp", prefix="p2-asset-fixture-") as td:
            root = Path(td)
            counts = root / "counts.json"
            tokenizer = root / "tokenizer.json"
            counts.write_bytes(input_data(t))
            tokenizer.write_bytes(t)
            with patch.object(artifact.os, "geteuid", return_value=1000):
                result = artifact.build(counts, tokenizer, root)
            folder = Path(result["private_directory"])
            self.assertEqual(folder.parent, root)
            self.assertEqual(folder.stat().st_mode & 0o777, 0o700)
            for name in ("ids.npy", "receipt.json"):
                self.assertEqual((folder / name).stat().st_mode & 0o777, 0o600)
            raw = (folder / "ids.npy").read_bytes()
            self.assertEqual(result["npy_sha256"], hashlib.sha256(raw).hexdigest())
            self.assertFalse(result["native_mtp_runtime_verified"])
            self.assertFalse(result["corpus_representativeness_verified"])
            receipt = json.loads((folder / "receipt.json").read_text())
            self.assertEqual(receipt["npy_sha256"], result["npy_sha256"])
            self.assertNotIn("private_directory", receipt)

    def test_non_tmp_output_and_root_forbidden(self):
        t = fake_tokenizer_bytes()
        with tempfile.TemporaryDirectory(dir="/tmp") as td:
            counts, tokenizer = Path(td) / "c.json", Path(td) / "t.json"
            counts.write_bytes(input_data(t))
            tokenizer.write_bytes(t)
            with patch.object(artifact.os, "geteuid", return_value=0):
                with self.assertRaisesRegex(artifact.Blocked, "ROOT_FORBIDDEN"):
                    artifact.build(counts, tokenizer, Path(td))
            with patch.object(artifact.os, "geteuid", return_value=1000):
                with self.assertRaisesRegex(artifact.Blocked, "OUTPUT_MUST_BE_IN_TMP"):
                    artifact.build(counts, tokenizer, Path("/usr"))

    def test_fail_closed_duplicate_or_unexpected_json_fields(self):
        t = fake_tokenizer_bytes()
        d = json.loads(input_data(t))
        d["unexpected"] = True
        with self.assertRaisesRegex(artifact.Blocked, "SCHEMA_FIELDS_INVALID"):
            artifact.parse_inputs(json.dumps(d).encode(), t)
        d.pop("unexpected")
        d["token_counts"] = {"0": 9223372036854775808}
        with self.assertRaisesRegex(artifact.Blocked, "COUNTS_ID_OR_VALUE_INVALID"):
            artifact.parse_inputs(json.dumps(d).encode(), t)

    def test_duplicate_json_key_fails_closed_without_overriding_counts(self):
        t = fake_tokenizer_bytes()
        duplicated = (
            b'{"schema":"P2_TOKEN_COUNTS_V1","schema":"P2_TOKEN_COUNTS_V1",'
            + b'"tokenizer_sha256":"' + hashlib.sha256(t).hexdigest().encode()
            + b'","token_counts":{"0":3},"special_token_ids":[248319]}'
        )
        with self.assertRaisesRegex(artifact.Blocked, "DUPLICATE_JSON_KEY"):
            artifact.parse_inputs(duplicated, t)

    def test_schema_rejects_missing_tokenizer_added_metadata(self):
        t = b'{"model":{"type":"BPE"}}'
        with self.assertRaisesRegex(artifact.Blocked, "ADDED_TOKENS_NOT_PROVEN"):
            artifact.parse_inputs(input_data(t), t)


if __name__ == "__main__":
    unittest.main()
