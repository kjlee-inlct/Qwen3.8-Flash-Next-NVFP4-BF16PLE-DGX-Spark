"""P6-B1a passive read-only feasibility, not CUDA or B formal Gate."""
import importlib.util
import io
import json
from pathlib import Path
from contextlib import redirect_stdout
from unittest import TestCase, main
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/phase6_b1_readonly_feasibility.py"
spec = importlib.util.spec_from_file_location("b1_readonly", SOURCE)
b1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b1)
IDENT = "a" * 64
STARTED = "2026-10-28T00:00:00.123456789Z"


def deployment(ident=IDENT, started=STARTED, image=b1.PIN_IMAGE, running=True):
    return json.dumps([{
        "Id": ident, "Image": image,
        "State": {"StartedAt": started, "Running": running},
        "Config": {"Env": ["TOKEN=private-do-not-print"]},
    }])


def host(mib=15000):
    return {"status": "OBSERVED", "mem_available_mib": mib}


def scenario():
    return (
        b1.parse_identity(deployment()),
        b1.parse_identity(deployment()),
        host(), host(), {"status": "PARTIAL"},
    )


class B1aPassiveFeasibilityTests(TestCase):
    def test_exact_identity_present(self):
        value = b1.parse_identity(deployment())
        self.assertEqual(value["status"], "VERIFIED")

    def test_json_never_echoes_docker_identity_or_secrets(self):
        result = b1.evaluate(*scenario())
        payload = json.dumps(result)
        self.assertNotIn(IDENT, payload)
        self.assertNotIn(STARTED, payload)
        self.assertNotIn("TOKEN=", payload)

    def test_nvidia_na_is_partial_not_failure_or_zero(self):
        result = b1.evaluate(*scenario())
        self.assertEqual(result["status"], "PASSIVE_METADATA_COLLECTED_NOT_GPU_READY")
        self.assertEqual(result["gpu_telemetry_scope"], "PARTIAL")
        self.assertFalse(result["unified_memory_headroom_proven"])
        self.assertFalse(result["gpu_allocation_authorized"])

    def test_even_full_nvml_does_not_approve_gpu(self):
        args = list(scenario())
        args[-1] = {"status": "OBSERVED"}
        output = b1.evaluate(*args)
        self.assertEqual(output["gpu_telemetry_scope"], "TELEMETRY_ONLY")
        self.assertFalse(output["second_model_feasible_proven"])

    def test_nvml_unavailable_does_not_mean_zero(self):
        args = list(scenario())
        args[-1] = {"status": "UNAVAILABLE"}
        self.assertEqual(b1.evaluate(*args)["gpu_telemetry_scope"], "UNKNOWN")
        self.assertEqual(b1.evaluate(*args)["status"], "PASSIVE_METADATA_COLLECTED_NOT_GPU_READY")

    def test_different_id_blocks(self):
        args = list(scenario())
        args[1] = b1.parse_identity(deployment(ident="b" * 64))
        result = b1.evaluate(*args)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("DEPLOYMENT_IDENTITY_DRIFT", result["reasons"])

    def test_different_started_at_blocks(self):
        args = list(scenario())
        args[1] = b1.parse_identity(deployment(started="2026-10-28T00:00:01Z"))
        self.assertIn("DEPLOYMENT_IDENTITY_DRIFT", b1.evaluate(*args)["reasons"])

    def test_wrong_image_blocks(self):
        args = list(scenario())
        args[1] = b1.parse_identity(deployment(image="sha256:" + "a" * 64))
        self.assertIn("PINNED_DEPLOYMENT_UNVERIFIED", b1.evaluate(*args)["reasons"])

    def test_not_running_blocks(self):
        self.assertEqual(b1.parse_identity(deployment(running=False))["status"], "BLOCKED")

    def test_invalid_id_blocks(self):
        self.assertEqual(b1.parse_identity(deployment(ident="abc"))["status"], "BLOCKED")

    def test_missing_started_blocks(self):
        self.assertEqual(b1.parse_identity(deployment(started=""))["status"], "BLOCKED")

    def test_invalid_docker_json_blocks(self):
        for text in ("oops", "{}", "[]", "[null]", None):
            with self.subTest(text=text):
                self.assertEqual(b1.parse_identity(text)["status"], "BLOCKED")

    def test_observation_floor_blocks_below(self):
        args = list(scenario())
        args[2] = host(8191)
        self.assertIn("HOST_MEMORY_BEFORE_BELOW_METADATA_FLOOR",
                      b1.evaluate(*args)["reasons"])

    def test_after_floor_blocks_below(self):
        args = list(scenario())
        args[3] = host(8191)
        self.assertEqual(b1.evaluate(*args)["status"], "BLOCKED")

    def test_equal_to_floor_is_metadata_only(self):
        args = list(scenario())
        args[2] = host(8192)
        args[3] = host(8192)
        self.assertEqual(b1.evaluate(*args)["status"],
                         "PASSIVE_METADATA_COLLECTED_NOT_GPU_READY")

    def test_host_unavailable_blocks(self):
        args = list(scenario())
        args[2] = {"status": "UNAVAILABLE"}
        self.assertIn("HOST_MEMORY_BEFORE_UNAVAILABLE", b1.evaluate(*args)["reasons"])

    def test_bool_memory_value_not_accepted(self):
        args = list(scenario())
        args[2] = host(True)
        self.assertEqual(b1.evaluate(*args)["status"], "BLOCKED")

    def test_gpu_work_is_always_not_run(self):
        for nvml in ("OBSERVED", "PARTIAL", "UNAVAILABLE"):
            with self.subTest(nvml=nvml):
                args = list(scenario())
                args[-1] = {"status": nvml}
                r = b1.evaluate(*args)
                self.assertEqual(r["p6_b1_gpu_runtime"], "NOT_RUN")
                self.assertEqual(r["p6_b_formal_gate"], "BLOCKED")
                self.assertEqual(r["p6_a_active_abi"], "BLOCKED")
                self.assertFalse(r["docker_gpu_model_http_inference_benchmark_executed"])

    def test_collect_does_not_use_gpu_compute(self):
        calls = []
        def fake_cmd(*argv, limit):
            calls.append((argv, limit))
            if argv[0] == "docker":
                return deployment()
            return "N/A, N/A, N/A, 0, 35"
        with patch.object(b1, "_command", side_effect=fake_cmd), \
             patch.object(b1, "_meminfo", side_effect=[host(), host()]):
            output = b1.collect()
        self.assertEqual(output["status"], "PASSIVE_METADATA_COLLECTED_NOT_GPU_READY")
        self.assertEqual([x[0][0] for x in calls], ["docker", "nvidia-smi", "docker"])
        self.assertEqual([x[0][1] for x in calls if x[0][0] == "docker"], ["inspect", "inspect"])

    def test_no_gpu_or_model_runtime_dependencies(self):
        source = SOURCE.read_text(encoding="utf-8")
        for keyword in ("import torch", "import vllm", "import triton", "docker run",
                        "docker exec", "cudaMalloc", "requests.get(", "curl ",
                        "nvidia-smi -lgc", "run-llama-benchy.sh"):
            with self.subTest(keyword=keyword):
                self.assertNotIn(keyword, source)

    def test_wrapper_rejects_exec_and_uses_manifest(self):
        source = (ROOT / "scripts/phase6-b1a-readonly-feasibility.sh").read_text(encoding="utf-8")
        for required in ("verify-source-state.py", "feature/blazux-phase6-runtime-gates",
                         "phase6_b1_readonly_feasibility.py --observe"):
            self.assertIn(required, source)
        for forbidden in ("docker run", "docker exec", "curl ", "--execute", "run-llama-benchy.sh"):
            self.assertNotIn(forbidden, source)

    def test_main_json_redacted(self):
        out = io.StringIO()
        fake = b1.evaluate(*scenario())
        with patch.object(b1, "collect", return_value=fake), redirect_stdout(out):
            code = b1.main(["--observe"])
        self.assertEqual(code, 0)
        self.assertIn("PHASE6_B1A_PASSIVE_FEASIBILITY_DONE_NOT_GPU_APPROVAL", out.getvalue())
        self.assertNotIn(IDENT, out.getvalue())

    def test_main_blocks_invalid_snapshot(self):
        with patch.object(b1, "collect", return_value={"status": "BLOCKED"}), \
             redirect_stdout(io.StringIO()):
            self.assertEqual(b1.main(["--observe"]), 2)


if __name__ == "__main__":
    main()
