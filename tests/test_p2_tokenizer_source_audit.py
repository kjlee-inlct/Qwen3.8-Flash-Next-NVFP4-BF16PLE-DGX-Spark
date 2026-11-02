"""P2 read-only tokenizer source identity checks; synthetic fixtures only."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from src import p2_tokenizer_source_audit as audit


def tokenizer(*, size=6, added=True, special=True):
    value = {"model": {"type": "BPE", "vocab": {
        "synthetic_" + str(i): i for i in range(size)
    }}}
    if added:
        value["added_tokens"] = [{"id": 248319, "special": special,
                                  "content": "<SYNTHETIC>"}]
    return json.dumps(value, sort_keys=True).encode("utf-8")


class SourceIdentityTests(unittest.TestCase):
    def test_matching_distinct_copy_and_snapshot_symlink(self):
        data = tokenizer()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recipe = root / "recipe" / "tokenizer.json"
            original = root / "hub" / "snapshots" / "revision" / "tokenizer.json"
            blob = root / "hub" / "blobs" / "sha"
            recipe.parent.mkdir()
            original.parent.mkdir(parents=True)
            blob.parent.mkdir()
            recipe.write_bytes(data)
            blob.write_bytes(data)
            original.symlink_to(blob)
            record = audit.audit_pair(recipe, original)
            self.assertEqual(record["sha256"], hashlib.sha256(data).hexdigest())
            self.assertEqual(record["status"],
                             "P2_RECIPE_ORCAROUTER_TOKENIZER_EXACT_MATCH_SOURCE_ONLY")
            self.assertFalse(record["active_container_mount_proven"])
            self.assertFalse(record["actual_domain_token_counts_available"])
            inv = record["inventory"]
            self.assertEqual(inv["model_vocab_ids"], 6)
            self.assertEqual(inv["marked_special_ids"], 1)
            self.assertEqual(inv["special_token_ids"], [248319])
            self.assertTrue(inv["ids_within_expected_target_head"])

    def test_mismatched_bytes_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a.json", Path(tmp) / "b.json"
            a.write_bytes(tokenizer())
            b.write_bytes(tokenizer(size=5))
            with self.assertRaisesRegex(audit.Blocked, "BYTES_MISMATCH"):
                audit.audit_pair(a, b)

    def test_same_file_is_not_independent_metadata_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "same.json"
            file.write_bytes(tokenizer())
            with self.assertRaisesRegex(audit.Blocked, "SAME_FILE"):
                audit.audit_pair(file, file)

    def test_recipe_symlink_is_rejected_even_when_bytes_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blob = root / "blob.json"
            recipe = root / "recipe.json"
            original = root / "source.json"
            blob.write_bytes(tokenizer())
            original.write_bytes(tokenizer())
            recipe.symlink_to(blob)
            with self.assertRaisesRegex(audit.Blocked, "COPY_NOT_SYMLINK"):
                audit.audit_pair(recipe, original)

    def test_missing_specials_or_bad_ids_fail_closed(self):
        for data in (tokenizer(added=False), tokenizer(special=False)):
            with self.subTest(raw=data), self.assertRaises(audit.Blocked):
                audit._ids(data)
        d = json.loads(tokenizer())
        d["model"]["vocab"]["invalid"] = 248320
        with self.assertRaisesRegex(audit.Blocked, "MODEL_VOCAB_IDS_INVALID"):
            audit._ids(json.dumps(d).encode())
        d = json.loads(tokenizer())
        d["added_tokens"].append(d["added_tokens"][0])
        with self.assertRaisesRegex(audit.Blocked, "SPECIAL_OR_ADDED_ID_INVALID"):
            audit._ids(json.dumps(d).encode())

    def test_duplicate_json_keys_rejected(self):
        raw = b'{"model":{"vocab":{"a":0,"a":1}},"added_tokens":[{"id":5,"special":true}]}'
        with self.assertRaisesRegex(audit.Blocked, "DUPLICATE_JSON_KEY"):
            audit._ids(raw)


if __name__ == "__main__":
    unittest.main()
