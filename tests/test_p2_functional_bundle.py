"""P2 actual combined source-stage contract, no Docker/model/GPU/HTTP use."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

from src import p2_functional_bundle as bundle
from src import p2_numeric_sampler_witness as witness
from tests.test_p2_numeric_sampler_witness import fixture


class P2FunctionalBundleTests(unittest.TestCase):
    def test_ple_code_is_real_optin_module(self):
        source = bundle.checked_ple(bundle.qsa.ROOT)
        self.assertIn(b"def _ple_unique_h2d_lookup(", source)
        self.assertIn(b"index_select(", source)

    def test_two_copy_same_base_default_off(self):
        d = bundle.dockerfile()
        self.assertEqual(d.count("FROM "), 1)
        self.assertTrue(d.startswith("FROM " + bundle.legacy.IMAGE_TAG))
        self.assertEqual(d.count("COPY "), 2)
        self.assertIn("sampler.py " + bundle.SAMPLER_DEST, d)
        self.assertIn("vllm_ple_mmap.py " + bundle.PLE_DEST, d)
        self.assertIn("VLLM_P2_NUMERIC_WITNESS=0", d)
        self.assertIn("VLLM_PLE_UNIQUE_H2D=0", d)
        self.assertNotIn("\nRUN ", d)

    def test_exact_pinned_source_mismatch_blocks_before_stage(self):
        with patch.object(bundle.trace, "original_identity",
                          return_value=("id", "image", "start")), \
             patch.object(bundle, "inspect_local_base_image"), \
             patch.object(bundle.trace, "_run_docker_cp", return_value=b"invalid"), \
             patch.object(bundle.tempfile, "mkdtemp") as created:
            with self.assertRaisesRegex(witness.Blocked, "SHA_DRIFT"):
                bundle.prepare(bundle.qsa.ROOT, probe=lambda: {})
            created.assert_not_called()

    def test_stage_two_real_patches_no_docker_build(self):
        sampler = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            real_mkdtemp = tempfile.mkdtemp
            def mkdtemp(*, prefix, dir):
                self.assertEqual(dir, "/tmp")
                self.assertEqual(prefix, "p2-functional-bundle-")
                return real_mkdtemp(prefix=prefix, dir=tmp)
            with patch.object(bundle.trace, "original_identity",
                              return_value=("id", "image", "start")) as identity, \
                 patch.object(bundle, "inspect_local_base_image"), \
                 patch.object(bundle.trace, "_run_docker_cp", return_value=sampler) as cp, \
                 patch.object(witness, "SOURCE_SHA256",
                              hashlib.sha256(sampler).hexdigest()), \
                 patch.object(bundle.tempfile, "mkdtemp", side_effect=mkdtemp):
                report = bundle.prepare(
                    bundle.qsa.ROOT,
                    probe=lambda: {"status": "MTP_DRAFT_ABI_SOURCE_TRIAGE_ONLY",
                                   "draft_head_slicing_implemented": False},
                )
            identity.assert_called()
            self.assertEqual(identity.call_count, 2)
            cp.assert_called_once_with(bundle.trace.SOURCES["sampler"])
            self.assertEqual(report["status"], "P2_NUMERIC_PLE_CANDIDATE_SOURCE_STAGED_NOT_BUILT")
            self.assertFalse(report["candidate_build_or_gpu_or_api_executed"])
            self.assertFalse(report["mtp"]["draft_head_slicing_implemented"])
            root = Path(report["stage_directory"])
            self.assertEqual(root.stat().st_mode & 0o777, 0o700)
            for name in ("sampler.py", "vllm_ple_mmap.py", "Dockerfile"):
                self.assertEqual((root / name).stat().st_mode & 0o777, 0o600)
            self.assertIn(witness.MARKER, (root / "sampler.py").read_text())
            self.assertEqual(
                hashlib.sha256((root / "vllm_ple_mmap.py").read_bytes()).hexdigest(),
                report["ple_candidate_sha256"],
            )

    def test_identity_change_rejects_before_private_stage(self):
        sampler = fixture()
        with patch.object(bundle.trace, "original_identity", side_effect=[
                 ("id", "img", "start1"), ("id", "img", "start2")]), \
             patch.object(bundle, "inspect_local_base_image"), \
             patch.object(bundle.trace, "_run_docker_cp", return_value=sampler), \
             patch.object(witness, "SOURCE_SHA256",
                          hashlib.sha256(sampler).hexdigest()), \
             patch.object(bundle.tempfile, "mkdtemp") as mkdir:
            with self.assertRaisesRegex(bundle.Blocked, "STARTED_AT_CHANGED"):
                bundle.prepare(bundle.qsa.ROOT, probe=lambda: {})
            mkdir.assert_not_called()

    def test_mtp_abi_source_only_and_absent(self):
        source = b"class Qwen3_8FlashNextMTP:\n    def load_weights(self, weights):\n        pass\n"
        result = bundle.mtp_source_summary(source)
        self.assertEqual(result["sha256"], hashlib.sha256(source).hexdigest())
        self.assertEqual(result["class_signatures"][0]["methods"], ["load_weights"])
        self.assertTrue(result["source_only_not_runtime_abi_pass"])
        with patch.object(bundle, "_read_mtp_source",
                          side_effect=lambda p: source if p == bundle.MTP_SOURCE_CANDIDATES[0]
                          else None):
            report = bundle.read_mtp_abi()
        self.assertFalse(report["draft_head_slicing_implemented"])
        self.assertFalse(report["loader_acceptance_runtime_verified"])
        self.assertEqual(len(report["sources"]), len(bundle.MTP_SOURCE_CANDIDATES))
        with self.assertRaisesRegex(bundle.Blocked, "NOT_ALLOWLISTED"):
            bundle._read_mtp_source("/tmp/secret")

    def test_stage_rejects_wrong_original_id_before_docker(self):
        with patch.object(bundle.qsa, "preflight"), \
             patch.object(bundle, "prepare") as stage:
            rc = bundle.main(["--expected-head", "a"*40, "--stage",
                             "--confirm-original-id", "invalid"])
            self.assertEqual(rc, 2)
            stage.assert_not_called()

    def test_three_copy_source_recipe_is_candidate_only(self):
        d = bundle.dockerfile(include_mtp=True)
        self.assertEqual(d.count("FROM "), 1)
        self.assertEqual(d.count("COPY "), 3)
        self.assertIn("mtp.py " + bundle.trace.PACKAGE_ROOT
                      + bundle.mtp_overlay.SOURCE_FILE, d)
        self.assertIn("VLLM_P2_DRAFT_VOCAB= VLLM_P2_DRAFT_VOCAB_SHA256=", d)
        self.assertNotIn("\nRUN ", d)

    def test_three_source_stage_creates_private_candidate_only(self):
        sampler = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            real_mkdtemp = tempfile.mkdtemp
            def mkdtemp(*, prefix, dir):
                self.assertEqual(dir, "/tmp")
                return real_mkdtemp(prefix=prefix, dir=tmp)
            with patch.object(bundle.trace, "original_identity",
                              return_value=("id", "image", "start")) as identity, \
                 patch.object(bundle, "inspect_local_base_image"), \
                 patch.object(bundle.trace, "_run_docker_cp",
                              return_value=sampler), \
                 patch.object(witness, "SOURCE_SHA256",
                              hashlib.sha256(sampler).hexdigest()), \
                 patch.object(bundle, "_read_mtp_source",
                              return_value=b"class Qwen3_8FlashNextMTP: pass"), \
                 patch.object(bundle.mtp_overlay, "transform",
                              return_value=b"# candidate-only patched MTP"), \
                 patch.object(bundle.tempfile, "mkdtemp", side_effect=mkdtemp):
                r = bundle.prepare(bundle.qsa.ROOT, include_mtp=True,
                                   probe=lambda: {"draft_head_slicing_implemented": False})
            self.assertEqual(identity.call_count, 2)
            self.assertTrue(r["mtp_reduced_vocab_source_included"])
            self.assertTrue(r["mtp_reduced_vocab_default_off"])
            self.assertFalse(r["candidate_build_or_gpu_or_api_executed"])
            self.assertEqual(r["status"],
                             "P2_NUMERIC_PLE_MTP_CANDIDATE_SOURCE_STAGED_NOT_BUILT")
            folder = Path(r["stage_directory"])
            self.assertEqual((folder / "mtp.py").read_bytes(),
                             b"# candidate-only patched MTP")
            self.assertEqual((folder / "Dockerfile").read_text().count("COPY "), 3)
            for name in ("mtp.py", "sampler.py", "vllm_ple_mmap.py", "Dockerfile"):
                self.assertEqual((folder / name).stat().st_mode & 0o777, 0o600)

    def test_check_makes_no_docker_calls(self):
        with patch.object(bundle.qsa, "preflight"), \
             patch.object(bundle.trace, "original_identity") as identity, \
             patch.object(bundle, "inspect_local_base_image") as image, \
             patch.object(bundle, "prepare") as stage:
            rc = bundle.main(["--expected-head", "a"*40, "--check"])
            self.assertEqual(rc, 0)
            identity.assert_not_called()
            image.assert_not_called()
            stage.assert_not_called()


if __name__ == "__main__":
    unittest.main()
