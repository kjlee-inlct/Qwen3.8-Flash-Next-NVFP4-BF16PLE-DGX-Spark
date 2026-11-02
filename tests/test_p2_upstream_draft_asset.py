"""CPU/std-lib only audit of the exact upstream Blazux .npy against Orcarouter."""
from __future__ import annotations

import hashlib
import io
import json
import struct
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src import p2_upstream_draft_asset as up
from src.p2_mtp_vocab_artifact import Blocked
from tests.test_p2_token_frequency import fixture


def gitsha(raw: bytes) -> str:
    return up.git_blob_sha256_agnostic(raw)


def pinned_style_npy(ids: tuple[int, ...]) -> bytes:
    """Build the upstream NumPy 1.0 128-byte header, not local 80-byte variant."""
    header = "{'descr': '<i4', 'fortran_order': False, 'shape': (65536,), }"
    padding = 118 - len(header) - 1
    assert padding >= 0 and len(ids) == 65536
    return (b"\x93NUMPY\x01\x00" + struct.pack("<H", 118)
            + (header + " " * padding + "\n").encode("ascii")
            + struct.pack("<65536i", *ids))


class UpstreamDraftAssetTests(unittest.TestCase):
    def _setup(self, root: Path):
        raw, config = fixture()
        target = root / "t.json"
        conf = root / "c.json"
        target.write_bytes(raw)
        conf.write_bytes(config)
        data = pinned_style_npy(tuple(range(65536)))
        asset = root / "asset.npy"
        asset.write_bytes(data)
        return asset, target, conf, data, hashlib.sha256(raw).hexdigest()

    def _mocks(self):
        return (patch.object(up, "special_ids",
                             return_value=(set(range(65536)), {3, 4})),
                patch.object(up, "_tokenizer_added_ids",
                             return_value=((3, 4), (3, 4))))

    def test_exact_upstream_asset_is_canonical_and_contains_added_range(self):
        real = Path(__file__).resolve().parents[1] / up.ASSET_RELATIVE
        raw = real.read_bytes()
        self.assertEqual(gitsha(raw), up.UPSTREAM_GIT_BLOB_SHA)
        ids = up.parse_npy(raw)
        self.assertEqual(len(ids), 65536)
        self.assertEqual(ids[:256], tuple(range(256)))
        self.assertTrue(set(range(248044, 248077)).issubset(ids))
        self.assertTrue(all(tid < 248077 for tid in ids))

    def test_real_format_and_orcarouter_metadata_contract(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            asset, target, conf, data, sha = self._setup(Path(tmp))
            mock1, mock2 = self._mocks()
            with mock1, mock2:
                receipt = up.audit(asset, target, conf,
                                   expected_blob=gitsha(data), expected_tokenizer=sha)
            self.assertEqual(receipt["selected_ids"], 65536)
            self.assertFalse(receipt["corpus_required"])
            self.assertFalse(receipt["native_mtp_runtime_verified"])
            self.assertEqual(receipt["required_special_ids"], 2)
            self.assertNotIn(tmp, json.dumps(receipt))

    def test_missing_special_or_added_blocks(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            asset, target, conf, data, sha = self._setup(Path(tmp))
            with patch.object(up, "special_ids",
                              return_value=(set(range(65537)), {65536})), \
                 patch.object(up, "_tokenizer_added_ids",
                              return_value=((3, 4), (3, 4))):
                with self.assertRaisesRegex(Blocked, "MISSING_ORCAROUTER_REQUIRED_ID"):
                    up.audit(asset, target, conf, expected_blob=gitsha(data),
                             expected_tokenizer=sha)

    def test_undeclared_or_head_padding_id_blocks(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            asset, target, conf, data, sha = self._setup(Path(tmp))
            with patch.object(up, "special_ids",
                              return_value=(set(range(65535)), {3, 4})), \
                 patch.object(up, "_tokenizer_added_ids",
                              return_value=((3, 4), (3, 4))):
                with self.assertRaisesRegex(Blocked, "UNDECLARED_OR_PADDED_ID"):
                    up.audit(asset, target, conf, expected_blob=gitsha(data),
                             expected_tokenizer=sha)

    def test_tampering_fails_before_tokenizer_io(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            asset, target, conf, data, sha = self._setup(Path(tmp))
            asset.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
            with self.assertRaisesRegex(Blocked, "PINNED_UPSTREAM_DRAFT_BLOB_MISMATCH"):
                up.audit(asset, target, conf,
                         expected_blob=gitsha(data), expected_tokenizer=sha)

    def test_numpy_header_rejects_malformed_bytes_without_evaluation(self):
        raw = bytearray(pinned_style_npy(tuple(range(65536))))
        raw[12] ^= 0x7F
        with self.assertRaises(Blocked):
            up.parse_npy(bytes(raw), expected_blob=gitsha(bytes(raw)))

    def test_private_stage_bytes_and_receipts_not_deployed(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            root = Path(tmp)
            asset, target, conf, data, sha = self._setup(root)
            mock1, mock2 = self._mocks()
            with mock1, mock2, patch.object(up.os, "geteuid", return_value=1000):
                receipt = up.stage(asset, target, conf, output_parent=root,
                                   expected_blob=gitsha(data), expected_tokenizer=sha)
            folder = Path(receipt["private_directory"])
            self.assertEqual(folder.stat().st_mode & 0o777, 0o700)
            self.assertEqual((folder / "ids.npy").stat().st_mode & 0o777, 0o600)
            self.assertEqual((folder / "ids.npy").read_bytes(), data)
            self.assertFalse(receipt["model_or_gpu_executed"])
            self.assertNotIn(str(target), (folder / "receipt.json").read_text())

    def test_root_and_symlinks_fail_closed(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            root = Path(tmp)
            asset, target, conf, data, sha = self._setup(root)
            with patch.object(up.os, "geteuid", return_value=0):
                with self.assertRaisesRegex(Blocked, "ROOT_FORBIDDEN"):
                    up.stage(asset, target, conf, output_parent=root,
                             expected_blob=gitsha(data), expected_tokenizer=sha)
            link = root / "symlink.npy"
            link.symlink_to(asset)
            with self.assertRaisesRegex(Blocked, "SYMLINK"):
                up.audit(link, target, conf,
                         expected_blob=gitsha(data), expected_tokenizer=sha)


if __name__ == "__main__":
    unittest.main()
