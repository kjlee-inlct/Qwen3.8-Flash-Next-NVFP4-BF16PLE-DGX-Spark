"""P1 GPU window stdlib-only contract: no Docker or model is executed."""
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from src import p1_prefix_gpu_window as gpu
from src import p1_prefix_gpu_oracle as oracle


class CandidateWindowTests(unittest.TestCase):
    def test_exact_stage_owner_permissions_and_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            original = gpu.PATCHES
            try:
                mapping = {}
                for name, (relative, _) in original.items():
                    data = ("test-" + name).encode()
                    (root / name).write_bytes(data)
                    os.chmod(root / name, 0o600)
                    mapping[name] = (relative, hashlib.sha256(data).hexdigest())
                os.chmod(root, 0o700)
                with patch.object(gpu, "PATCHES", mapping):
                    self.assertEqual(gpu.verify_stage(root), {
                        name: digest for name, (_, digest) in mapping.items()})
                    os.chmod(root / "scheduler.py", 0o644)
                    with self.assertRaisesRegex(gpu.Blocked, "STAGE_FILE_OWNER_OR_MODE"):
                        gpu.verify_stage(root)
            finally:
                os.chmod(root, 0o700)

    def test_cmd_only_one_flag_changes_and_preserves_mtp(self):
        cmd = ["recipe-views", "--port", "8000", "--host", "0.0.0.0",
               "--served-model-name", "orc", "--gpu-memory-utilization", "0.8",
               "--max-model-len", "262144", "--max-num-seqs", "8",
               "--no-enable-prefix-caching", "--speculative-config",
               '{"method":"mtp","num_speculative_tokens":2}']
        new, model = gpu.candidate_cmd(cmd)
        self.assertEqual(model, "orc")
        self.assertEqual(len(new), len(cmd))
        self.assertEqual(new.count("--enable-prefix-caching"), 1)
        self.assertEqual(cmd.count("--no-enable-prefix-caching"), 1)
        with self.assertRaises(gpu.Blocked):
            gpu.candidate_cmd(new)
        with self.assertRaises(gpu.Blocked):
            gpu.candidate_cmd(cmd[:-1])

    def test_unapproved_environment_name_is_denied_without_values(self):
        original = {"Env": ["HF_HUB_OFFLINE=1", "SECRET_TOKEN=do-not-display"]}
        image = {"Env": []}
        with self.assertRaises(gpu.Blocked) as cm:
            gpu.environment_delta(original, image)
        self.assertIn("SECRET_TOKEN", str(cm.exception))
        self.assertNotIn("do-not-display", str(cm.exception))

    def test_no_gpu_transitions_in_preflight(self):
        identity = {"id": "a" * 64}
        with patch.object(gpu.os, "geteuid", return_value=1000), \
                patch.object(gpu, "preflight",
                             return_value=(identity, {"State": {"Status": "running"},
                                                      "Config": {"User": "1000:1000"}},
                                           {}, [], [], "orc")), \
                patch.object(gpu, "probe_vllm_root", return_value="/opt/venv/vllm") as probe:
            self.assertEqual(gpu.run(["--preflight"]), 0)
            probe.assert_called_once_with("1000:1000")

    def test_user_override_preserved_by_candidate_and_cpu_probe(self):
        with patch.object(gpu, "checked", return_value=""), \
                patch.object(gpu, "inspect_json", return_value={
                    "Image": gpu.IMAGE, "Config": {"Labels": {
                        gpu.LABEL_KEY: gpu.LABEL_VALUE}}}):
            commands = []
            def capture(argv, **kwargs):
                commands.append(argv)
                return ""
            with patch.object(gpu, "checked", side_effect=capture):
                gpu.create_candidate("/opt/python/vllm",
                                     {"cache": "/a", "views": "/b"},
                                     ["recipe-views"], [], "runc", "1000:1000", "/recipe")
            self.assertIn("--user", commands[0])
            self.assertEqual(commands[0][commands[0].index("--workdir")+1],
                             "/recipe")
            self.assertEqual(commands[0][commands[0].index("--user")+1],
                             "1000:1000")

    def test_oracle_requires_real_hit_evidence(self):
        self.assertFalse(oracle.hit_evidence({}, {}))
        self.assertTrue(oracle.hit_evidence(
            {"vllm:prefix_cache_hits_total": 1},
            {"vllm:prefix_cache_hits_total": 2}))
        self.assertFalse(oracle.hit_evidence(
            {"vllm:prefix_cache_hits_total": 2},
            {"vllm:prefix_cache_hits_total": 2}))

    def test_candidate_cleanup_only_with_ownership(self):
        with patch.object(gpu, "inspect_json", return_value={
                "Image": gpu.IMAGE, "Config": {"Labels": {gpu.LABEL_KEY: "foreign"}}}):
            with self.assertRaisesRegex(gpu.Blocked, "REFUSE_CLEANUP_FOREIGN"):
                gpu.cleanup_candidate()

    def test_wrapper_requires_exact_head_and_source_manifest(self):
        script = (Path(__file__).resolve().parents[1] /
                  "scripts/p1-prefix-gpu-window.sh").read_text()
        self.assertIn("verify-source-state.py", script)
        self.assertIn("WRONG_BRANCH", script)
        self.assertIn("DIRTY_TREE", script)
        self.assertNotIn("docker rm -f", script)


if __name__ == "__main__":
    unittest.main()
