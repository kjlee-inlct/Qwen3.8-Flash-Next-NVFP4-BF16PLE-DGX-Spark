"""P2 minimal numeric-only candidate: focused source-only safety tests."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from src import p2_numeric_minimal_candidate as minimal


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class MinimalNumericCandidateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="p2-functional-bundle-", dir="/tmp")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.root.chmod(0o700)
        self.contents = {}
        for name in minimal.PIN_SOURCE_HASHES:
            if name == "sampler.py":
                value = (minimal.witness.MARKER + "\n"
                         + 'VLLM_P2_NUMERIC_WITNESS", "0"\n').encode()
            else:
                value = ("synthetic-" + name).encode()
            self.contents[name] = value
        self.contents["Dockerfile"] = minimal.bundle.dockerfile(
            include_mtp=True, include_upstream_draft=True).encode()
        for name, value in self.contents.items():
            f = self.root / name
            f.write_bytes(value)
            f.chmod(0o600)

    def pins(self):
        return patch.dict(minimal.PIN_SOURCE_HASHES, {
            name: digest(self.contents[name])
            for name in minimal.PIN_SOURCE_HASHES
        }, clear=True)

    @staticmethod
    def fake_guard():
        return {"original_id_verified": True,
                "original_image_verified": True,
                "baseline_prefix": "OFF",
                "baseline_mtp": 2,
                "future_numeric_candidate_prefix": "OFF",
                "future_numeric_candidate_mtp": 0,
                "prepared_command_not_executed": True}

    def test_staged_real_bundle_layout_accepts_only_when_sha_verified(self):
        with self.pins():
            self.assertEqual(minimal.source_stage(self.root),
                             self.contents["sampler.py"])

    def test_stage_edited_sampler_fails_closed(self):
        with self.pins():
            (self.root / "sampler.py").write_bytes(self.contents["sampler.py"] + b"\n# edit")
            with self.assertRaisesRegex(minimal.Blocked, "PINNED_SHA_DRIFT"):
                minimal.source_stage(self.root)

    def test_stage_extraneous_source_and_permissions_block(self):
        with self.pins():
            extra = self.root / "unreviewed.py"
            extra.write_text("pass")
            with self.assertRaisesRegex(minimal.Blocked, "FILE_SET_DRIFT"):
                minimal.source_stage(self.root)
            extra.unlink()
            (self.root / "sampler.py").chmod(0o644)
            with self.assertRaisesRegex(minimal.Blocked, "MODE_OR_SIZE_DRIFT"):
                minimal.source_stage(self.root)

    def test_stage_symlink_and_wrong_dockerfile_block(self):
        with self.pins():
            (self.root / "Dockerfile").write_text("FROM unsafe\n")
            with self.assertRaisesRegex(minimal.Blocked, "DOCKERFILE_DRIFT"):
                minimal.source_stage(self.root)
            (self.root / "Dockerfile").unlink()
            (self.root / "Dockerfile").symlink_to(self.root / "sampler.py")
            with self.assertRaisesRegex(minimal.Blocked, "NOT_REGULAR"):
                minimal.source_stage(self.root)

    def test_numeric_recipe_has_one_source_copy_no_build_or_model_action(self):
        raw = minimal.numeric_only_dockerfile().decode()
        self.assertEqual(raw.count("COPY "), 1)
        self.assertIn("sampler.py " + minimal.bundle.SAMPLER_DEST, raw)
        self.assertIn("VLLM_P2_NUMERIC_WITNESS=0", raw)
        self.assertIn("VLLM_PLE_UNIQUE_H2D=0", raw)
        self.assertIn("VLLM_P2_DRAFT_VOCAB= ", raw)
        self.assertNotIn("mtp.py", raw)
        self.assertNotIn("draft_vocab_65536.npy", raw)
        self.assertNotIn("vllm_ple_mmap.py", raw)
        self.assertNotIn("\nRUN ", raw)
        self.assertNotIn("docker run", raw)

    def test_plan_reads_identity_twice_and_claims_no_gpu_certification(self):
        with self.pins(), \
             patch.object(minimal.trace, "original_identity",
                          return_value=("id", "image", "started")) as identity, \
             patch.object(minimal.legacy, "inspect",
                          return_value={"Id": minimal.trace.ORIGINAL_IMAGE}) as inspect:
            report, data = minimal.plan(self.root, guard=self.fake_guard)
        self.assertEqual(identity.call_count, 2)
        inspect.assert_called_once_with("image", minimal.legacy.IMAGE_TAG)
        self.assertEqual(data, self.contents["sampler.py"])
        self.assertEqual(report["sampler_sha256"], digest(data))
        self.assertFalse(report["gpu_window_authorized"])
        self.assertFalse(report["resource_headroom_certified"])
        self.assertFalse(report["first_divergence_measured"])
        self.assertFalse(report["strict_numeric_resolved"])
        self.assertTrue(report["future_execution_requires_separate_approved_gpu_window"])

    def test_identity_drift_blocks_without_private_output(self):
        with self.pins(), \
             patch.object(minimal.trace, "original_identity", side_effect=[
                 ("id", "image", "before"), ("id", "image", "after")
             ]), \
             patch.object(minimal.legacy, "inspect",
                          return_value={"Id": minimal.trace.ORIGINAL_IMAGE}), \
             patch.object(minimal.tempfile, "mkdtemp") as maker:
            with self.assertRaisesRegex(minimal.Blocked, "START_TIME_CHANGED"):
                minimal.prepare(self.root, guard=self.fake_guard)
        maker.assert_not_called()

    def test_numeric_minimal_private_stage_off_no_side_effects(self):
        with self.pins(), \
             patch.object(minimal.trace, "original_identity",
                          return_value=("id", "image", "started")) as identity, \
             patch.object(minimal.legacy, "inspect",
                          return_value={"Id": minimal.trace.ORIGINAL_IMAGE}):
            report = minimal.prepare(self.root, guard=self.fake_guard)
        identity.assert_called()
        folder = Path(report["private_directory"])
        self.addCleanup(lambda: __import__("shutil").rmtree(folder))
        self.assertTrue(folder.name.startswith(minimal.SINGLE_CANDIDATE_PREFIX))
        self.assertEqual(stat.S_IMODE(folder.stat().st_mode), 0o700)
        self.assertEqual(set(x.name for x in folder.iterdir()),
                         {"sampler.py", "Dockerfile", "receipt.json"})
        for file in folder.iterdir():
            self.assertEqual(stat.S_IMODE(file.stat().st_mode), 0o600)
        self.assertEqual((folder / "sampler.py").read_bytes(),
                         self.contents["sampler.py"])
        self.assertEqual((folder / "Dockerfile").read_bytes(),
                         minimal.numeric_only_dockerfile())
        saved = json.loads((folder / "receipt.json").read_text())
        self.assertEqual(saved["status"], "P2_MINIMAL_NUMERIC_SOURCE_PLAN_NO_GPU_AUTHORIZATION")
        self.assertEqual(report["status"], "P2_MINIMAL_NUMERIC_PRIVATE_SOURCE_STAGED_NOT_BUILT")
        self.assertFalse(report["image_build_authorized"])

    def test_original_contract_is_read_only_and_requires_prefix_off_mtp2(self):
        with patch.object(minimal.legacy, "state_receipt", return_value={"id": minimal.trace.ORIGINAL_ID}), \
             patch.object(minimal.legacy, "inspect", side_effect=[
                 {"Id": minimal.trace.ORIGINAL_ID,
                  "Image": minimal.trace.ORIGINAL_IMAGE,
                  "Config": {"Cmd": ["stock-placeholder"]}},
                 {"Id": minimal.trace.ORIGINAL_IMAGE},
             ]) as inspect, \
             patch.object(minimal.legacy, "verify_identity", return_value="running"), \
             patch.object(minimal.mtp_off, "cmd_without_mtp",
                          return_value=["--no-enable-prefix-caching"]) as cmd:
            report = minimal.read_only_original_guard()
        self.assertEqual(inspect.call_count, 2)
        cmd.assert_called_once_with(["stock-placeholder"])
        self.assertTrue(report["original_id_verified"])
        self.assertTrue(report["prepared_command_not_executed"])
        self.assertEqual(report["future_numeric_candidate_mtp"], 0)

    def test_original_stopped_or_bad_prefix_blocks(self):
        with patch.object(minimal.legacy, "state_receipt", return_value={"id": minimal.trace.ORIGINAL_ID}), \
             patch.object(minimal.legacy, "inspect", side_effect=[
                 {"Id": minimal.trace.ORIGINAL_ID,
                  "Image": minimal.trace.ORIGINAL_IMAGE, "Config": {"Cmd": []}},
                 {"Id": minimal.trace.ORIGINAL_IMAGE},
             ]), \
             patch.object(minimal.legacy, "verify_identity", return_value="exited"):
            with self.assertRaisesRegex(minimal.Blocked, "NOT_SAME_ID_RUNNING"):
                minimal.read_only_original_guard()


if __name__ == "__main__":
    unittest.main()
