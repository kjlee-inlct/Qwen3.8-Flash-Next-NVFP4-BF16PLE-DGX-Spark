"""P1 GPU window stdlib-only contract: no Docker or model is executed."""
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import tarfile
import unittest
from unittest.mock import patch, Mock
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

    def test_prewarm_default_and_disabled_explicit_preserved(self):
        image = {"Env": []}
        self.assertEqual(gpu.environment_delta(
            {"Env": ["VLLM_PLE_MMAP_PREWARM=0"]}, image),
            ["VLLM_PLE_MMAP_PREWARM=0"])
        self.assertEqual(gpu.environment_delta({"Env": []}, image), [])
        for value in ("1", "2", "true"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(gpu.Blocked, "PLE_PREWARM_MUST_BE_DISABLED"):
                    gpu.environment_delta(
                        {"Env": ["VLLM_PLE_MMAP_PREWARM=" + value]}, image)

    def test_candidate_presence_failure_is_not_treated_as_absent(self):
        with patch.object(gpu, "checked", side_effect=gpu.Blocked("DOCKER_PS_FAILED")):
            with self.assertRaisesRegex(gpu.Blocked, "DOCKER_PS_FAILED"):
                gpu.candidate_ids()
            with self.assertRaisesRegex(gpu.Blocked, "DOCKER_PS_FAILED"):
                gpu.cleanup_candidate()

    def test_candidate_absence_checked_without_daemon_inspect(self):
        with patch.object(gpu, "checked", return_value="") as cp:
            gpu.cleanup_candidate()
            cp.assert_called_once()

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

    def test_user_override_preserved_by_candidate_patch_copy(self):
        receipt = {"cache": "/a", "views": "/b"}
        with tempfile.TemporaryDirectory() as td:
            stage = Path(td)
            patches = {}
            for name, (target, _) in gpu.PATCHES.items():
                content = (name + "-fixture").encode()
                (stage / name).write_bytes(content)
                os.chmod(stage / name, 0o600)
                patches[name] = (target, hashlib.sha256(content).hexdigest())
            os.chmod(stage, 0o700)
            inspected = {"Image": gpu.IMAGE,
                         "State": {"Status": "created"},
                         "Config": {"Labels": {gpu.LABEL_KEY: gpu.LABEL_VALUE},
                                    "User": "1000:1000", "WorkingDir": "/recipe"},
                         "Mounts": [
                             {"Source": "/a", "Destination": "/recipe/hf-cache",
                              "Type": "bind", "RW": False},
                             {"Source": "/b", "Destination": "/recipe/recipe-views",
                              "Type": "bind", "RW": False}]}
            commands = []
            def capture(argv, **kwargs):
                commands.append(argv)
                return ""
            with patch.object(gpu, "STAGE", stage), \
                    patch.object(gpu, "PATCHES", patches), \
                    patch.object(gpu, "checked", side_effect=capture), \
                    patch.object(gpu, "inspect_json", return_value=inspected), \
                    patch.object(gpu, "docker_cp_to_stopped_candidate") as cp, \
                    patch.object(gpu, "verify_candidate_code") as verify:
                gpu.create_candidate("/opt/python/vllm", receipt, ["recipe-views"],
                                     [], "runc", "1000:1000", "/recipe")
            self.assertIn("--user", commands[0])
            self.assertEqual(commands[0][commands[0].index("--workdir")+1],
                             "/recipe")
            self.assertEqual(commands[0][commands[0].index("--user")+1],
                             "1000:1000")
            self.assertEqual(sum(arg == "--mount" for arg in commands[0]), 2)
            self.assertNotIn(str(stage), repr(commands[0]))
            self.assertEqual(cp.call_count, 2)
            self.assertEqual(verify.call_count, 2)
            self.assertEqual(os.stat(stage).st_mode & 0o777, 0o700)
            self.assertEqual(os.stat(stage / "mamba_hybrid.py").st_mode & 0o777,
                             0o600)

    def test_copy_uses_bytes_mode_0644_not_original_private_host_files(self):
        data = b"safe-patch-source"
        def stub(args, **kwargs):
            self.assertEqual(args[:3], ["docker", "cp", "-"])
            with tarfile.open(fileobj=io.BytesIO(kwargs["input"])) as archive:
                member = archive.getmembers()[0]
                self.assertEqual(member.name, "scheduler.py")
                self.assertEqual(member.mode & 0o777, 0o644)
                self.assertEqual(archive.extractfile(member).read(), data)
            return Mock(returncode=0)
        with patch.object(gpu.subprocess, "run", side_effect=stub):
            gpu.docker_cp_to_stopped_candidate(
                "/opt/python/vllm/v1/core/sched", "scheduler.py", data)

    def test_copy_readback_requires_exact_sha_and_mode(self):
        data = b"safe-patch-source"
        digest = hashlib.sha256(data).hexdigest()
        def archive(mode):
            stream = io.BytesIO()
            with tarfile.open(fileobj=stream, mode="w") as tar:
                member = tarfile.TarInfo("scheduler.py")
                member.mode = mode
                member.size = len(data)
                tar.addfile(member, io.BytesIO(data))
            return stream.getvalue()
        with patch.object(gpu.subprocess, "run",
                          return_value=Mock(returncode=0, stdout=archive(0o644))):
            gpu.verify_candidate_code("/opt/python/vllm/v1/core/sched",
                                      "scheduler.py", digest)
            with self.assertRaisesRegex(gpu.Blocked,
                                        "CANDIDATE_PATCH_SHA256_MISMATCH"):
                gpu.verify_candidate_code("/opt/python/vllm/v1/core/sched",
                                          "scheduler.py", "f" * 64)
        with patch.object(gpu.subprocess, "run",
                          return_value=Mock(returncode=0, stdout=archive(0o600))):
            with self.assertRaisesRegex(gpu.Blocked,
                                        "CANDIDATE_PATCH_PERMISSIONS"):
                gpu.verify_candidate_code("/opt/python/vllm/v1/core/sched",
                                          "scheduler.py", digest)

    def test_original_nonroot_cpu_probe_no_private_stage_mount(self):
        response = json.dumps({"root": "/opt/python/vllm", "sha256_pins_match": True})
        with patch.object(gpu, "checked", return_value=response) as cp:
            self.assertEqual(gpu.probe_vllm_root("1000:1000"), "/opt/python/vllm")
        argv = cp.call_args.args[0]
        self.assertEqual(argv[argv.index("--user") + 1], "1000:1000")
        self.assertNotIn("--mount", argv)
        self.assertIn("--network=none", argv)
        self.assertIn("--runtime=runc", argv)

    def test_failed_candidate_setup_does_not_stop_original(self):
        identity = {"id": "a" * 64}
        original = {"State": {"Status": "running"},
                    "Config": {"User": "1000:1000", "WorkingDir": "/recipe"},
                    "HostConfig": {"Runtime": "runc"}}
        with patch.object(gpu.os, "geteuid", return_value=1000), \
                patch.object(gpu, "preflight",
                             return_value=(identity, original, {}, [], [], "orc")), \
                patch.object(gpu, "probe_vllm_root", return_value="/opt/python/vllm"), \
                patch.object(gpu, "create_candidate",
                             side_effect=gpu.Blocked("CANDIDATE_COPY_FAILED")), \
                patch.object(gpu, "cleanup_candidate") as cleanup, \
                patch.object(gpu, "checked") as checked:
            self.assertEqual(gpu.run(["--execute", "--confirm-id", "a" * 64]), 2)
            cleanup.assert_called_once_with()
            checked.assert_not_called()

    def test_oracle_requires_real_hit_evidence(self):
        self.assertFalse(oracle.hit_evidence({}, {}))
        self.assertTrue(oracle.hit_evidence(
            {"vllm:prefix_cache_hits_total": 1},
            {"vllm:prefix_cache_hits_total": 2}))
        self.assertFalse(oracle.hit_evidence(
            {"vllm:prefix_cache_hits_total": 2},
            {"vllm:prefix_cache_hits_total": 2}))

    def test_candidate_cleanup_only_with_ownership(self):
        with patch.object(gpu, "candidate_ids", return_value=["a" * 64]), \
                patch.object(gpu, "inspect_json", return_value={
                    "Id": "a" * 64, "Image": gpu.IMAGE,
                    "Config": {"Labels": {gpu.LABEL_KEY: "foreign"}}}):
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
