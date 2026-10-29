"""P1 Prefix-cache patched source export. No Docker/GPU/model is invoked."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from src import p1_prefix_stage_files as stage


class PrefixStageFilesTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="p1-test-stage-")
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name)

    @staticmethod
    def reader(root, label):
        if str(root) != "/no-gpu-installed":
            raise AssertionError("unexpected root")
        return b"x = 1\n" if label == "mamba" else b"y = 2\n"

    @staticmethod
    def patcher(label, source, expected):
        if expected != stage.candidate.SPECS[label][1]:
            raise AssertionError("wrong source digest pin")
        return b"x = 3\n" if label == "mamba" else b"y = 4\n"

    def test_stage_exports_only_two_fully_patched_files(self):
        with patch.object(stage.candidate, "_installed_root",
                          return_value=Path("/no-gpu-installed")):
            result = stage.stage_files(
                self.output, read=self.reader, patch=self.patcher)
        self.assertEqual(result["files"], 2)
        self.assertEqual(result["status"], "SOURCE_STAGE_ONLY_NOT_INSTALLED")
        self.assertFalse(result["actual_gpu_or_model_run"])
        self.assertEqual(set(p.name for p in self.output.iterdir()),
                         {"mamba_hybrid.py", "scheduler.py"})
        self.assertEqual((self.output / "mamba_hybrid.py").read_bytes(), b"x = 3\n")
        self.assertEqual((self.output / "scheduler.py").read_bytes(), b"y = 4\n")
        for path in self.output.iterdir():
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_refuses_to_overwrite_existing_stage(self):
        (self.output / "mamba_hybrid.py").write_text("original")
        with self.assertRaisesRegex(stage.StageBlocked, "OUTPUT_NOT_EMPTY"):
            stage.stage_files(self.output, read=self.reader, patch=self.patcher)
        self.assertEqual((self.output / "mamba_hybrid.py").read_text(),
                         "original")

    def test_refuses_world_accessible_directory(self):
        os.chmod(self.output, 0o755)
        with self.assertRaisesRegex(stage.StageBlocked,
                                    "OUTPUT_DIRECTORY_NOT_PRIVATE"):
            stage.stage_files(self.output, read=self.reader, patch=self.patcher)

    def test_source_drift_blocks_before_writing(self):
        calls = {"n": 0}
        def reader(root, label):
            calls["n"] += 1
            if calls["n"] > 2 and label == "mamba":
                return b"DRIFT"
            return self.reader(root, label)
        with patch.object(stage.candidate, "_installed_root",
                          return_value=Path("/no-gpu-installed")):
            with self.assertRaisesRegex(stage.StageBlocked,
                                        "INSTALLED_SOURCE_DRIFT"):
                stage.stage_files(self.output, read=reader, patch=self.patcher)
        self.assertFalse(any(self.output.iterdir()))

    def test_main_requires_fixed_stage_path(self):
        self.assertEqual(stage.main([]), 2)
        self.assertEqual(stage.main(["--stage-files", "--output", "/tmp"]), 2)

    def test_stage_wrapper_is_cpu_only_no_model_mount(self):
        script = (Path(__file__).resolve().parents[1] /
                  "scripts/p1-prefix-stage.sh").read_text()
        self.assertIn("NVIDIA_VISIBLE_DEVICES=void", script)
        self.assertIn("CUDA_VISIBLE_DEVICES=-1", script)
        self.assertIn("--network=none", script)
        self.assertIn("--runtime=runc", script)
        self.assertNotIn("--gpus all", script)
        self.assertNotIn("--ipc=host", script)
        self.assertNotIn("--privileged", script)
        self.assertNotIn("docker exec", script)


if __name__ == "__main__":
    unittest.main()
