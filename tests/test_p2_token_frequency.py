"""stdlib-only synthetic contracts; no real user corpus or tokenizer package."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stderr
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


    def test_plain_text_file_is_one_document_including_line_breaks(self):
        class CaptureTokenizer:
            def __init__(self):
                self.texts = []
            def encode(self, text: str, *, add_special_tokens: bool):
                self.texts.append(text)
                return type("Encoding", (), {"ids": [0, 1, 0]})()

        with tempfile.TemporaryDirectory(dir="/tmp") as td:
            p = Path(td) / "approved.md"
            p.write_text("a\nb\n", encoding="utf-8")
            engine = CaptureTokenizer()
            counts, records = freq.count_records([], engine, {0, 1},
                                                   text_files=[("technical", p)])
            self.assertEqual(engine.texts, ["a\nb\n"])
            self.assertEqual(counts, {0: 2, 1: 1})
            self.assertEqual(records[0]["format"], "text")
            self.assertEqual((records[0]["records"], records[0]["tokens"]), (1, 3))

    def test_plain_text_invalid_utf8_oversized_and_symlink_blocked(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as td:
            p = Path(td) / "approved.txt"
            p.write_bytes(b"\xff\xfe")
            with self.assertRaisesRegex(freq.Blocked, "INVALID_UTF8"):
                freq.count_records([], FakeTokenizer(), {0, 1},
                                   text_files=[("en", p)])
            p.write_text("a" * (freq.MAX_LINE_BYTES + 1))
            with self.assertRaisesRegex(freq.Blocked, "TOO_LARGE"):
                freq.count_records([], FakeTokenizer(), {0, 1},
                                   text_files=[("en", p)])
            p.write_text("aba")
            alias = Path(td) / "alias.txt"
            alias.symlink_to(p)
            with self.assertRaisesRegex(freq.Blocked, "SYMLINK"):
                freq.count_records([], FakeTokenizer(), {0, 1},
                                   text_files=[("en", alias)])

    def test_mixed_text_and_jsonl_rejects_duplicate_file(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as td:
            p = Path(td) / "corpus.jsonl"
            p.write_text('{"text":"a"}\n')
            with self.assertRaisesRegex(freq.Blocked, "DUPLICATE_PATH"):
                freq.count_records([("ko", p)], FakeTokenizer(), {0, 1},
                                   text_files=[("code", p)])

    def test_probe_exact_source_and_fixed_cpu_encoding(self):
        t, c = fixture()
        with tempfile.TemporaryDirectory(dir="/tmp") as td:
            root = Path(td)
            (root / "tokenizer.json").write_bytes(t)
            (root / "tokenizer_config.json").write_bytes(c)
            with patch.object(freq, "TOKENIZER_AUDITED_SHA256", hashlib.sha256(t).hexdigest()):
                r = freq.probe(root / "tokenizer.json", root / "tokenizer_config.json",
                               tokenizer_factory=lambda _: FakeTokenizer())
            self.assertEqual(r["declared_ids"], 5)
            self.assertGreater(r["synthetic_probe_token_count"], 0)
            self.assertFalse(r["actual_corpus_counted"])
            self.assertFalse(list(root.glob("p2-token-counts-*")))

    def test_count_plain_text_artifact_uses_same_builder_contract(self):
        t, c = fixture()
        with tempfile.TemporaryDirectory(dir="/tmp") as td:
            root = Path(td)
            tp, cp, txt = root / "tokenizer.json", root / "tokenizer_config.json", root / "source.py"
            tp.write_bytes(t)
            cp.write_bytes(c)
            txt.write_text("aba\n")
            with patch.object(freq.os, "geteuid", return_value=1000), \
                 patch.object(freq, "TOKENIZER_AUDITED_SHA256", hashlib.sha256(t).hexdigest()):
                result = freq.count([], tp, cp, root,
                                    tokenizer_factory=lambda _: FakeTokenizer(),
                                    text_files=[("code", txt)])
            written = json.loads(Path(result["counts_file"]).read_text())
            self.assertEqual(written["token_counts"], {"0": 2, "1": 2})
            self.assertEqual(written["special_token_ids"], [3, 4])
            self.assertEqual(result["inputs"][0]["format"], "text")
            self.assertFalse(result["corpus_rights_and_representativeness_verified"])


    def test_probe_blocker_reports_safe_reason_code_without_paths(self):
        buffer = io.StringIO()
        args = ["--tokenizer-json", "/not/a/real/private/model/path",
                "--tokenizer-config", "/not/a/real/private/config/path", "--probe"]
        with patch.object(freq, "probe", side_effect=freq.Blocked(
                "TOKENIZERS_PACKAGE_NOT_INSTALLED_OFFLINE")):
            with redirect_stderr(buffer):
                rc = freq.main(args)
        self.assertEqual(rc, 2)
        self.assertEqual(buffer.getvalue().strip(),
                         "P2_OFFLINE_TOKEN_COUNTS_BLOCKED REASON="
                         "TOKENIZERS_PACKAGE_NOT_INSTALLED_OFFLINE")
        self.assertNotIn("/not/a/real", buffer.getvalue())

    def test_probe_blocker_redacts_unexpected_reason_content(self):
        secret = "sensitive/text from the tokenizer config"
        buffer = io.StringIO()
        with patch.object(freq, "probe", side_effect=freq.Blocked(secret)):
            with redirect_stderr(buffer):
                rc = freq.main(["--tokenizer-json", "/private/sensitive",
                                "--tokenizer-config", "/private/confidential",
                                "--probe"])
        self.assertEqual(rc, 2)
        self.assertIn("REASON=UNCLASSIFIED_BLOCKED", buffer.getvalue())
        self.assertNotIn(secret, buffer.getvalue())
        self.assertNotIn("/private", buffer.getvalue())

    def test_probe_os_error_is_classified_without_exception_details(self):
        buffer = io.StringIO()
        with patch.object(freq, "probe", side_effect=PermissionError(
                "secret source path cannot be opened")):
            with redirect_stderr(buffer):
                rc = freq.main(["--tokenizer-json", "/secret/one",
                                "--tokenizer-config", "/secret/two", "--probe"])
        self.assertEqual(rc, 2)
        self.assertEqual(buffer.getvalue().strip(),
                         "P2_OFFLINE_TOKEN_COUNTS_BLOCKED "
                         "REASON=INPUT_PERMISSION_DENIED")

    def test_real_file_missing_config_yields_actionable_safe_reason(self):
        tokenizer_raw, _ = fixture()
        with tempfile.TemporaryDirectory(dir="/tmp") as td:
            file = Path(td) / "tokenizer.json"
            file.write_bytes(tokenizer_raw)
            buffer = io.StringIO()
            with patch.object(freq, "TOKENIZER_AUDITED_SHA256",
                              hashlib.sha256(tokenizer_raw).hexdigest()):
                with redirect_stderr(buffer):
                    rc = freq.main(["--tokenizer-json", str(file),
                                    "--tokenizer-config",
                                    str(Path(td) / "missing_config.json"), "--probe"])
            self.assertEqual(rc, 2)
            self.assertIn("REASON=TOKENIZER_CONFIG_FILE_REQUIRED_NO_SYMLINK",
                          buffer.getvalue())
            self.assertNotIn(td, buffer.getvalue())


if __name__ == '__main__':
    unittest.main()
