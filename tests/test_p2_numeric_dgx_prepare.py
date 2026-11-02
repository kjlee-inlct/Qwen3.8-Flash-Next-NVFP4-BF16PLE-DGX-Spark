"""Offline fail-closed DGX stage tests. Never call Docker, GPU or HTTP."""
from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src import p2_numeric_dgx_prepare as prep
from src import p2_numeric_sampler_witness as witness
from tests.test_p2_numeric_sampler_witness import fixture


class PrepareTests(unittest.TestCase):
    def test_dockerfile_one_copy_parent_and_default_off(self):
        df = prep.dockerfile()
        self.assertEqual(df.count("COPY "), 1)
        self.assertEqual(df.count("FROM "), 1)
        self.assertTrue(df.startswith("FROM " + prep.legacy.IMAGE_TAG))
        self.assertIn("ENV VLLM_P2_NUMERIC_WITNESS=0\n", df)
        self.assertNotIn("RUN ", df)

    def test_check_mode_never_calls_docker(self):
        with patch.object(prep.qsa, "preflight") as preflight, \
             patch.object(prep, "stage") as staged, \
             patch.object(prep.source_trace, "original_identity") as identity:
            self.assertEqual(prep.main(["--expected-head", "a"*40, "--check"]), 0)
            preflight.assert_called_once_with("a"*40)
            staged.assert_not_called()
            identity.assert_not_called()

    def test_stage_requires_full_original_id_before_access(self):
        with patch.object(prep.qsa, "preflight"), \
             patch.object(prep, "stage") as staged:
            self.assertEqual(prep.main(["--expected-head", "a"*40,
                                       "--stage", "--confirm-original-id", "wrong"]), 2)
            staged.assert_not_called()

    def test_original_image_mismatch_fails_closed(self):
        with patch.object(prep.legacy, "inspect", return_value={"Id": "sha256:bad"}):
            with self.assertRaisesRegex(prep.Blocked, "ORIGINAL_IMAGE_TAG_ID_DRIFT"):
                prep.verify_original_image()

    def test_pinned_source_stage_writes_only_private_files(self):
        raw = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            real_mkdtemp = tempfile.mkdtemp
            def mkdtemp(*, prefix, dir):
                self.assertEqual(dir, "/tmp")
                return real_mkdtemp(prefix=prefix, dir=tmp)
            with patch.object(prep.source_trace, "original_identity", return_value=("id", "image", "started")) as identity, \
                 patch.object(prep, "verify_original_image"), \
                 patch.object(prep.source_trace, "_run_docker_cp", return_value=raw) as cp, \
                 patch.object(witness, "SOURCE_SHA256", hashlib.sha256(raw).hexdigest()), \
                 patch.object(prep.tempfile, "mkdtemp", side_effect=mkdtemp):
                report = prep.stage()
            self.assertEqual(identity.call_count, 2)
            cp.assert_called_once_with(prep.source_trace.SOURCES["sampler"])
            self.assertEqual(report["status"], "P2_WITNESS_SOURCE_STAGED_NOT_BUILT_NOT_RUN")
            folder = Path(report["stage_directory"])
            self.assertTrue((folder / "sampler.py").exists())
            self.assertIn(witness.MARKER, (folder / "sampler.py").read_text())
            self.assertEqual((folder.stat().st_mode & 0o777), 0o700)
            self.assertEqual(((folder / "sampler.py").stat().st_mode & 0o777), 0o600)
            self.assertTrue(report["witness_default_off"])
            self.assertFalse(report["docker_build_run_gpu_api_executed"])

    def test_source_sha_drift_fails_before_writing_stage(self):
        with patch.object(prep.source_trace, "original_identity", return_value=("id", "image", "started")), \
             patch.object(prep, "verify_original_image"), \
             patch.object(prep.source_trace, "_run_docker_cp", return_value=b"not a pinned source"), \
             patch.object(prep.tempfile, "mkdtemp") as mkdir:
            with self.assertRaisesRegex(witness.Blocked, "SHA_DRIFT"):
                prep.stage()
            mkdir.assert_not_called()

    def test_original_start_time_drift_blocks_stage(self):
        raw = fixture()
        with patch.object(prep.source_trace, "original_identity", side_effect=[("a", "b", "start1"), ("a", "b", "start2")]), \
             patch.object(prep, "verify_original_image"), \
             patch.object(prep.source_trace, "_run_docker_cp", return_value=raw), \
             patch.object(witness, "SOURCE_SHA256", hashlib.sha256(raw).hexdigest()), \
             patch.object(prep.tempfile, "mkdtemp") as mkdir:
            with self.assertRaisesRegex(prep.Blocked, "ORIGINAL_ID_OR_STARTED_AT_CHANGED"):
                prep.stage()
            mkdir.assert_not_called()


if __name__ == "__main__":
    unittest.main()
