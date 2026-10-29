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
            self.assertEqual(cp.call_count, 3)
            self.assertEqual(verify.call_count, 3)
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
                patch.object(oracle, "probe_before_stop", return_value={"status": "PASS"}), \
                patch.object(gpu, "create_candidate",
                             side_effect=gpu.Blocked("CANDIDATE_COPY_FAILED")), \
                patch.object(gpu, "cleanup_candidate") as cleanup, \
                patch.object(gpu, "checked") as checked:
            self.assertEqual(gpu.run(["--execute", "--confirm-id", "a" * 64]), 2)
            cleanup.assert_called_once_with()
            checked.assert_not_called()

    def test_chat_payload_has_template_non_thinking_and_long_shared_prefix(self):
        short = oracle.build_payload("test-model", long_prompt=False)
        long = oracle.build_payload("test-model", long_prompt=True)
        self.assertTrue(long["messages"][1]["content"].startswith(
            short["messages"][1]["content"].split("Final question:")[0][:50]))
        self.assertGreater(len(long["messages"][1]["content"]),
                           20 * len(short["messages"][1]["content"]))
        self.assertEqual(long["chat_template_kwargs"], {"enable_thinking": False})
        self.assertEqual(long["max_tokens"], 256)
        self.assertIn("integers from 1 through 40", long["messages"][1]["content"])
        self.assertIn("seven plus five", short["messages"][1]["content"])
        self.assertIs(long["return_token_ids"], True)
        self.assertIs(long["logprobs"], True)
        self.assertEqual(long["temperature"], 0)

    def test_original_api_probe_blocks_empty_content_before_stop(self):
        identity = {"id": "a" * 64}
        original = {"State": {"Status": "running"},
                    "Config": {"User": "1000:1000", "WorkingDir": "/recipe"},
                    "HostConfig": {"Runtime": "runc"}}
        with patch.object(gpu.os, "geteuid", return_value=1000), \
                patch.object(gpu, "preflight",
                             return_value=(identity, original, {}, [], [], "orc")), \
                patch.object(gpu, "probe_vllm_root", return_value="/opt/python/vllm"), \
                patch.object(oracle, "probe_before_stop",
                             side_effect=oracle.OracleBlocked("CHAT_EMPTY_FINAL_CONTENT")), \
                patch.object(gpu, "create_candidate") as create, \
                patch.object(gpu, "checked") as checked:
            self.assertEqual(gpu.run(["--execute", "--confirm-id", "a" * 64]), 2)
            create.assert_not_called()
            checked.assert_not_called()

    def test_original_chat_probe_logprobs_and_nonempty_required(self):
        def response(text, *, logprobs=True):
            return {"choices": [{"message": {"content": text},
                                 "logprobs": {"content": [
                                     {"token": "12", "logprob": -0.25}
                                 ]} if logprobs else None,
                                 "finish_reason": "stop", "token_ids": [123]}],
                    "usage": {"prompt_tokens": 101, "completion_tokens": 1}}
        with patch.object(oracle, "request_json", return_value=response("12")):
            probe = oracle.probe_before_stop("test-model")
            self.assertEqual(probe["status"], "PASS_ORIGINAL_CHAT_PROTOCOL")
            self.assertEqual(probe["logprob_tokens"], 1)
        for r in (response(""), response("12", logprobs=False)):
            with patch.object(oracle, "request_json", return_value=r):
                with self.assertRaises(oracle.OracleBlocked):
                    oracle.probe_before_stop("test-model")

    def test_hit_counter_uses_repeat_window_not_created_counter(self):
        a = {"vllm:prefix_cache_hits_total{model_name=\"m\"}": 1.0}
        b = {**a, "vllm:prefix_cache_hits_created{model_name=\"m\"}": 4.0}
        self.assertEqual(oracle.counter_delta(a, b, "prefix_cache_hits_total"), 0.0)
        b["vllm:prefix_cache_hits_total{model_name=\"m\"}"] = 3.0
        self.assertEqual(oracle.counter_delta(a, b, "prefix_cache_hits_total"), 2.0)

    def test_oracle_requires_nonempty_output_and_late_mtp_cache_hit(self):
        def completion(text="12", lp=-0.2, token_id=100):
            return {"choices": [{
                "message": {"content": text}, "finish_reason": "stop",
                "logprobs": {"content": [{"token": "12", "logprob": lp}]},
                "token_ids": [token_id],
            }], "usage": {"prompt_tokens": 9600, "completion_tokens": 1}}
        before = {"vllm:prefix_cache_queries_total": 0.0,
                  "vllm:prefix_cache_hits_total": 0.0}
        cold = {"vllm:prefix_cache_queries_total": 9600.0,
                "vllm:prefix_cache_hits_total": 0.0}
        repeat1 = {"vllm:prefix_cache_queries_total": 19200.0,
                   "vllm:prefix_cache_hits_total": 0.0}
        repeat2 = {"vllm:prefix_cache_queries_total": 28800.0,
                   "vllm:prefix_cache_hits_total": 8000.0}
        repeat3 = {"vllm:prefix_cache_queries_total": 38400.0,
                   "vllm:prefix_cache_hits_total": 16000.0}
        responses = [completion() for _ in range(4)]
        with patch.object(oracle, "request_json", side_effect=responses), \
                patch.object(oracle, "metrics", return_value=before), \
                patch.object(oracle, "settled_metrics",
                             side_effect=[cold, repeat1, repeat2, repeat3]):
            result = oracle.run_oracle("m", 18080)
            self.assertEqual(result["status"],
                             "PASS_CACHE_HIT_NONEMPTY_OUTPUT_TOKENS_AND_STRICT_LOGPROBS")
            self.assertEqual(result["requests"], 4)
            self.assertEqual(result["cache_hit_repeat_request_indices_1_based"], [3, 4])
            self.assertEqual(result["cache_hit_token_deltas_per_request"],
                             [0.0, 0.0, 8000.0, 8000.0])
            self.assertEqual(result["max_token_logprob_abs_delta"], 0.0)
            self.assertFalse(result["active_mamba_physical_mapping_observed"])
            self.assertFalse(result["mtp_acceptance_observed"])
            self.assertEqual(result["minimum_requested_output_tokens"], 0)
        with patch.object(oracle, "request_json",
                          side_effect=[completion("") for _ in range(4)]), \
                patch.object(oracle, "metrics", return_value=before), \
                patch.object(oracle, "settled_metrics",
                             side_effect=[cold, repeat1, repeat2, repeat3]):
            with self.assertRaisesRegex(oracle.OracleBlocked,
                                        "CHAT_EMPTY_FINAL_CONTENT"):
                oracle.run_oracle("m", 18080)
        nohit = dict(repeat3)
        nohit["vllm:prefix_cache_hits_total"] = 0.0
        with patch.object(oracle, "request_json",
                          side_effect=[completion() for _ in range(4)]), \
                patch.object(oracle, "metrics", return_value=before), \
                patch.object(oracle, "settled_metrics", side_effect=[
                    cold, repeat1, {**repeat2,
                                    "vllm:prefix_cache_hits_total": 0.0}, nohit]):
            result = oracle.run_oracle("m", 18080)
            self.assertEqual(result["status"], "FAIL_ALL_REPEATS_PREFIX_CACHE_MISS")
        with patch.object(oracle, "request_json",
                          side_effect=[completion(), completion(),
                                       completion(lp=-0.2002), completion()]), \
                patch.object(oracle, "metrics", return_value=before), \
                patch.object(oracle, "settled_metrics",
                             side_effect=[cold, repeat1, repeat2, repeat3]):
            result = oracle.run_oracle("m", 18080)
            self.assertEqual(result["status"],
                             "INCONCLUSIVE_LOGPROB_DIFF_EXCEEDS_STRICT_GATE")
        with patch.object(oracle, "request_json",
                          side_effect=[completion() for _ in range(4)]), \
                patch.object(oracle, "metrics", return_value=before), \
                patch.object(oracle, "settled_metrics",
                             side_effect=[before for _ in range(4)]):
            result = oracle.run_oracle("m", 18080)
            self.assertEqual(result["status"],
                             "INCONCLUSIVE_PREFIX_CACHE_METRICS_NOT_UPDATED")

    def test_numeric_drift_cold_vs_cached_and_repeat_vs_repeat(self):
        runs = [
            {"token_ids": [101, 102], "logprobs": [-0.2, -0.3]},
            {"token_ids": [101, 102], "logprobs": [-0.2033, -0.3]},
            {"token_ids": [101, 102], "logprobs": [-0.2033, -0.3]},
            {"token_ids": [101, 102], "logprobs": [-0.2033, -0.3]},
        ]
        v = oracle.logprob_diagnostics(runs)
        self.assertTrue(v["logprob_diagnostic_complete"])
        self.assertAlmostEqual(v["cold_to_repeat_max_deltas"][0], 0.0033)
        self.assertEqual(v["repeat_to_repeat_consecutive_max_deltas"],
                         [0.0, 0.0])
        self.assertAlmostEqual(v["per_token_cold_repeat_max_deltas"][0], 0.0033)
        self.assertEqual(v["per_token_cold_repeat_max_deltas"][1], 0.0)
        runs[3]["logprobs"][1] = -0.301
        self.assertAlmostEqual(
            oracle.logprob_diagnostics(runs)[
                "repeat_to_repeat_consecutive_max_deltas"][-1], 0.001)
        runs[3]["logprobs"][1] = None
        self.assertFalse(oracle.logprob_diagnostics(runs)[
            "logprob_diagnostic_complete"])

    def test_oracle_requires_real_hit_evidence(self):
        name = "vllm:prefix_cache_hits_total"
        self.assertEqual(oracle.counter_delta({}, {}, "prefix_cache_hits_total"), 0)
        self.assertEqual(oracle.counter_delta(
            {name: 1}, {name: 2}, "prefix_cache_hits_total"), 1)
        self.assertEqual(oracle.counter_delta(
            {name: 2}, {name: 2}, "prefix_cache_hits_total"), 0)
        self.assertEqual(oracle.counter_delta(
            {}, {"vllm:external_prefix_cache_hits_total": 9},
            "prefix_cache_hits_total"), 0)

    def test_candidate_cleanup_only_with_ownership(self):
        with patch.object(gpu, "candidate_ids", return_value=["a" * 64]), \
                patch.object(gpu, "inspect_json", return_value={
                    "Id": "a" * 64, "Image": gpu.IMAGE,
                    "Config": {"Labels": {gpu.LABEL_KEY: "foreign"}}}):
            with self.assertRaisesRegex(gpu.Blocked, "REFUSE_CLEANUP_FOREIGN"):
                gpu.cleanup_candidate()

    def test_oracle_minimum_decode_and_mtp_acceptance_telemetry(self):
        response = {"choices": [{
            "message": {"content": "1, 2"}, "finish_reason": "stop",
            "logprobs": {"content": [{"token": "1", "logprob": -0.2}]},
            "token_ids": [11]}],
            "usage": {"prompt_tokens": 9492, "completion_tokens": 1}}
        before = {"vllm:prefix_cache_queries_total": 0.0,
                  "vllm:prefix_cache_hits_total": 0.0,
                  "vllm:spec_decode_num_accepted_tokens_total": 0.0}
        after = [
            {"vllm:prefix_cache_queries_total": 9492.0 * (i + 1),
             "vllm:prefix_cache_hits_total": 6400.0 * i,
             "vllm:spec_decode_num_accepted_tokens_total": 2.0 * (i + 1)}
            for i in range(4)]
        with patch.object(oracle, "request_json", side_effect=[response] * 4), \
                patch.object(oracle, "metrics", return_value=before), \
                patch.object(oracle, "settled_metrics", side_effect=after):
            result = oracle.run_oracle("m", 18080, min_output_tokens=24)
        self.assertEqual(result["status"],
                         "INCONCLUSIVE_GENERATION_TOO_SHORT_FOR_LONG_DECODE")
        self.assertTrue(result["cache_hit_observed"])
        self.assertFalse(result["all_output_lengths_sufficient"])
        self.assertEqual(result["mtp_accepted_draft_token_counter_delta"], 8.0)
        self.assertTrue(result["mtp_acceptance_observed"])

    def test_live_candidate_observer_log_summary_is_not_physical_mapping_pass(self):
        examples = [
            {"schema": 1, "kind": "scheduler",
             "self_block": {"block_size": 16}},
            {"schema": 1, "kind": "mamba",
             "cache_config": {"mamba_block_size": 32},
             "tensor_metadata": {"_mamba_state_idx_gpu": {"shape": [8]}},
             "state_seed_observed": True, "state_seed_value": 7},
        ]
        lines = "\n".join("P1_PREFIX_ACTIVE_ABI_JSON:" + json.dumps(x)
                         for x in examples)
        with patch.object(gpu.subprocess, "run",
                          return_value=Mock(returncode=0, stdout=lines,
                                            stderr="")):
            observed = gpu.read_candidate_observer()
        self.assertEqual(observed["active_scheduler_event_count"], 1)
        self.assertEqual(observed["active_mamba_add_request_event_count"], 1)
        self.assertEqual(observed["mamba_state_seed_observed_count"], 1)
        self.assertEqual(observed["scheduler_effective_blocks"], [16])
        self.assertEqual(observed["mamba_sampled_seeds"], [7])
        self.assertFalse(observed["physical_mapping_and_reuse_verified"])
        self.assertFalse(observed["mtp_speculative_acceptance_observed"])

    def test_wrapper_requires_exact_head_and_source_manifest(self):
        script = (Path(__file__).resolve().parents[1] /
                  "scripts/p1-prefix-gpu-window.sh").read_text()
        self.assertIn("verify-source-state.py", script)
        self.assertIn("WRONG_BRANCH", script)
        self.assertIn("DIRTY_TREE", script)
        self.assertNotIn("docker rm -f", script)


if __name__ == "__main__":
    unittest.main()
