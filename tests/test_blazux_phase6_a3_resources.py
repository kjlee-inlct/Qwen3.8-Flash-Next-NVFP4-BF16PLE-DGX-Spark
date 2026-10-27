"""CPU-only fixture checks for P6-A3a telemetry redaction/fail-closed logic."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

FILE = Path(__file__).resolve().parents[1] / "src/phase6_a3_readonly_resources.py"
spec = importlib.util.spec_from_file_location("phase6_a3_readonly_resources", FILE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class A3PassiveTests(unittest.TestCase):
    def test_meminfo_valid_and_host_only(self):
        data = "MemTotal:       131072 kB\nMemAvailable: 65536 kB\nSwapTotal: 10 kB\nSwapFree: 5 kB\nSecret: PRIVATE\n"
        got = mod.parse_meminfo(data)
        self.assertEqual(got["status"], "OBSERVED")
        self.assertEqual(got["mem_available_mib"], 64)
        self.assertNotIn("PRIVATE", str(got))

    def test_meminfo_unavailable(self):
        self.assertEqual(mod.parse_meminfo(None)["status"], "UNAVAILABLE")
        self.assertEqual(mod.parse_meminfo("MemTotal: 5 kB")["status"], "UNAVAILABLE")

    def test_meminfo_inconsistent(self):
        self.assertEqual(mod.parse_meminfo("MemTotal: 10 kB\nMemAvailable: 20 kB")["status"], "INVALID")

    def test_meminfo_invalid_swap(self):
        self.assertEqual(mod.parse_meminfo("MemTotal: 100 kB\nMemAvailable: 20 kB\nSwapTotal: 0 kB\nSwapFree: 100 kB")["status"], "INVALID")

    def test_gpu_telemetry_available(self):
        got = mod.parse_nvidia_smi("1024, 800, 224, 13, 48\n")
        self.assertEqual(got["status"], "OBSERVED")
        self.assertEqual(got["devices"][0]["memory_free_mib"], 800)

    def test_gpu_na_is_unknown_not_zero(self):
        got = mod.parse_nvidia_smi("N/A, N/A, N/A, 10, 40\n")
        self.assertEqual(got["status"], "PARTIAL")
        self.assertIsNone(got["devices"][0]["memory_free_mib"])

    def test_gpu_telemetry_missing(self):
        self.assertEqual(mod.parse_nvidia_smi(None)["status"], "UNAVAILABLE")
        self.assertEqual(mod.parse_nvidia_smi("")["status"], "UNAVAILABLE")

    def test_gpu_malformed_shape_blocked(self):
        self.assertEqual(mod.parse_nvidia_smi("1,2,3")["status"], "INVALID")

    def test_gpu_more_than_eight_devices_invalid(self):
        self.assertEqual(mod.parse_nvidia_smi("1,2,3,4,5\n" * 9)["status"], "INVALID")

    def test_deployment_identity_is_required(self):
        self.assertEqual(mod.inspect_limits(None)["status"], "BLOCKED")
        self.assertEqual(mod.inspect_limits([{"State": {"Running": True},
                                            "HostConfig": {}, "Image": "wrong"}])["status"], "BLOCKED")

    def test_deployment_running_and_memory_limit(self):
        raw = [{"Image": mod.PIN_IMAGE, "State": {"Running": True},
                "HostConfig": {"Memory": 2 * 1024**3, "Binds": ["/private"],
                               "DeviceRequests": ["secret"]},
                "Config": {"Env": ["SECRET=PRIVATE"], "Cmd": ["--api-key", "PRIVATE"]}}]
        got = mod.inspect_limits(raw)
        self.assertEqual(got["status"], "OBSERVED")
        self.assertEqual(got["explicit_container_memory_limit_mib"], 2048)
        self.assertNotIn("PRIVATE", str(got))
        self.assertNotIn("/private", str(got))

    def test_unset_container_limit_not_physical_headroom(self):
        raw = [{"Image": mod.PIN_IMAGE, "State": {"Running": True},
                "HostConfig": {"Memory": 0}}]
        got = mod.inspect_limits(raw)
        self.assertIsNone(got["explicit_container_memory_limit_mib"])

    def test_collect_fail_closed_and_never_authorizes_gpu(self):
        observed = '{"Image":"sha256:test"}'
        with patch.object(mod, "read_command", return_value=observed), patch.object(
            mod.Path, "read_text", return_value="MemTotal: 100 kB\nMemAvailable: 50 kB"
        ):
            result = mod.collect()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["p6_a_runtime_status"], "BLOCKED")
        self.assertFalse(result["gpu_compute_and_model_load_executed"])
        self.assertEqual(result["isolated_gpu_startup_safe"], "NOT_DETERMINABLE_FROM_SNAPSHOT")


if __name__ == "__main__":
    unittest.main()
