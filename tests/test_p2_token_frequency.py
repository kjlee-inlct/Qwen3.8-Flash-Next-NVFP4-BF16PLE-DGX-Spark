"""stdlib-only synthetic contracts; no real user corpus or tokenizer package."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src import p2_token_frequency as freq


def fixture() -> tuple[bytes, bytes]:
    tokenizer = {"model": {"vocab": {"a": 0, "b": 1, "c": 2}},
                 "added_tokens": [{"id": 3, "content": "<|eos|>", "special": True},
                                  {"id": 4, "content": "<|tool|>", "special": True}]}
    config = {"eos_token": "<|eos|>", "additional_special_tokens": ["<|tool|>"],
              "added_tokens_decoder": {"3": {"content": "<|eos|>", "special": True},
                                       "4": {"content": "<|tool|>", "special": True}}}
    return json.dumps(tokenizer).encode(), json.dumps(config).encode()


class FakeTokenizer:
    def encode(self, text: str, *, add_special_tokens: bool):
        if add_special_tokens:
            raise AssertionError("implicit specials forbidden")
        return type("Encoding", (), {"ids": [0 if c == "a" else 1 for c in text]})()


class TokenFrequencyTests(unittest.TestCase):
    def test_config_special_ids_and_unallocated_rows_not_selected(self):
        t, c = fixture()
        declared, required = freq.special_ids(t, c)
        self.assertEqual(declared, set(range(5)))
        self.assertEqual(required, {3, 4})
        self.assertNotIn(248319, declared)

    def test_config_special_unknown_or_mismatched_decoder_blocks(self):
        t, c = fixture()
        for edited in (dict(eos_token="NOT_DECLARED"),
                       dict(added_tokens_decoder={"3": {"content": "<|tool|>", "special": True}}),
                       dict(additional_special_tokens="wrong type")):
            d = json.loads(c)
            d.update(edited)
            with self.subTest(edited=edited), self.assertRaises(freq.Blocked):
                freq.special_ids(t, json.dumps(d).encode())

    def test_duplicate_ids_and_invalid_bool_rejected(self):
        t, c = fixture()
        for field in ({"model": {"vocab": {"a": 0, "b": 0}}},
                      {"added_tokens": [{"id": True, "content": "x", "special": True}]}):
            d = json.loads(t)
            d.update(field)
            with self.assertRaises(freq.Blocked):
                freq.special_ids(json.dumps(d).encode(), c)

    def test_count_records_combines_domains_without_logging_raw_text(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as td:
            p1, p2 = Path(td)/"en.jsonl", Path(td)/"tool.jsonl"
            p1.write_text('{"text":"aba"}\n{"text":"bb"}\n')
            p2.write_text('{"text":"a"}\n')
            result, receipt = freq.count_records([("en", p1), ("tool", p2)], FakeTokenizer(), set(range(5)))
            self.assertEqual(result, {0: 3, 1: 3})
            self.assertEqual([r["tokens"] for r in receipt], [5, 1])
            self.assertNotIn('aba', json.dumps(receipt))
            self.assertTrue(all(len(r["corpus_sha256"]) == 64 for r in receipt))

    def test_reject_bad_domain_duplicate_paths_and_undeclared_ids(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as td:
            p = Path(td)/"sample.jsonl"
            p.write_text('{"text":"a"}\n')
            for corpora in ([('unknown', p)], [('ko', p), ('en', p)]):
                with self.assertRaises(freq.Blocked):
                    freq.count_records(corpora, FakeTokenizer(), {0, 1})
            with self.assertRaisesRegex(freq.Blocked, "UNDECLARED"):
                freq.count_records([('ko', p)], FakeTokenizer(), {2})

    def test_invalid_jsonl_duplicate_key_empty_text_and_metadata_blocked(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as td:
            p = Path(td)/"sample.jsonl"
            for raw in ('{"text":""}\n', '{"text":"a","prompt":"hidden"}\n',
                        '{"text":"a","text":"b"}\n', '{BROKEN}\n'):
                p.write_text(raw)
                with self.subTest(raw=raw), self.assertRaises(freq.Blocked):
                    freq.count_records([('code', p)], FakeTokenizer(), {0, 1})

    def test_symlink_corpus_forbidden(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as td:
            p = Path(td)/"sample.jsonl"
            s = Path(td)/"alias.jsonl"
            p.write_text('{"text":"a"}\n')
            s.symlink_to(p)
            with self.assertRaisesRegex(freq.Blocked, "SYMLINK"):
                freq.count_records([('ko', s)], FakeTokenizer(), {0, 1})

    def test_full_private_counts_artifact_no_raw_corpus_and_no_deployment(self):
        t, c = fixture()
        with tempfile.TemporaryDirectory(dir="/tmp") as td:
            root = Path(td)
            tokenizer, config, corpus = root/"tokenizer.json", root/"tokenizer_config.json", root/"corpus.jsonl"
            tokenizer.write_bytes(t)
            config.write_bytes(c)
            corpus.write_text('{"text":"abba"}\n')
            with patch.object(freq.os, "geteuid", return_value=1000), \
                 patch.object(freq, "TOKENIZER_AUDITED_SHA256", hashlib.sha256(t).hexdigest()):
                r = freq.count([('en', corpus)], tokenizer, config, root,
                               tokenizer_factory=lambda _: FakeTokenizer())
            folder = Path(r['private_directory'])
            self.assertEqual(folder.stat().st_mode & 0o777, 0o700)
            self.assertEqual((folder/'counts.json').stat().st_mode & 0o777, 0o600)
            self.assertEqual((folder/'receipt.json').stat().st_mode & 0o777, 0o600)
            data = json.loads((folder/'counts.json').read_text())
            self.assertEqual(data['special_token_ids'], [3, 4])
            self.assertEqual(data['token_counts'], {'0': 2, '1': 2})
            self.assertEqual(data['tokenizer_sha256'], hashlib.sha256(t).hexdigest())
            self.assertFalse(r['gpu_api_model_executed'])
            self.assertNotIn('abba', (folder/'receipt.json').read_text())

    def test_encode_error_is_classified_without_echoing_corpus(self):
        class BrokenTokenizer:
            def encode(self, text: str, *, add_special_tokens: bool):
                raise RuntimeError("sensitive input should not leak")

        with tempfile.TemporaryDirectory(dir="/tmp") as td:
            p = Path(td) / "corpus.jsonl"
            p.write_text('{"text":"sensitive input"}\\n'.replace("\\n", "\n"))
            with self.assertRaisesRegex(freq.Blocked, "^TOKENIZER_ENCODING_FAILED$"):
                freq.count_records([("ko", p)], BrokenTokenizer(), {0, 1})

    def test_wrong_source_sha_refuses_creation(self):
        t, c = fixture()
        with tempfile.TemporaryDirectory(dir="/tmp") as td:
            root = Path(td)
            (root/'t').write_bytes(t)
            (root/'c').write_bytes(c)
            (root/'data').write_text('{"text":"a"}\n')
            with patch.object(freq.os, "geteuid", return_value=1000):
                with self.assertRaisesRegex(freq.Blocked, "AUDITED_SHA"):
                    freq.count([('en', root/'data')], root/'t', root/'c', root,
                               tokenizer_factory=lambda _: FakeTokenizer())
            self.assertFalse(list(root.glob('p2-token-counts-*')))

    def test_root_and_outside_tmp_blocked(self):
        t, c = fixture()
        with tempfile.TemporaryDirectory(dir="/tmp") as td:
            root = Path(td)
            with patch.object(freq.os, "geteuid", return_value=0):
                with self.assertRaisesRegex(freq.Blocked, "ROOT_FORBIDDEN"):
                    freq.count([], root/'missing', root/'missing', root)
            with patch.object(freq.os, "geteuid", return_value=1000):
                with self.assertRaisesRegex(freq.Blocked, "OUTPUT_MUST_BE_IN_TMP"):
                    freq.count([], root/'missing', root/'missing', Path('/usr'))


if __name__ == '__main__':
    unittest.main()
