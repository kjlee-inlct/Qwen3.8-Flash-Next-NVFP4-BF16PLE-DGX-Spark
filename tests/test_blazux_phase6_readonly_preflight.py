"""Offline Phase6 A2 security/fail-closed regression tests; no Docker/GPU."""
import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / "src/phase6_readonly_preflight.py"
spec = importlib.util.spec_from_file_location("phase6_readonly_preflight", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class ReadonlyTests(unittest.TestCase):
    def test_no_docker_is_blocked(self):
        self.assertEqual(mod.sanitize_inspect(None)["status"], "BLOCKED")

    def test_digest_mismatch_blocked(self):
        data = [{"Config": {}, "State": {"Running": True}, "Image": "sha256:wrong"}]
        self.assertEqual(mod.sanitize_inspect(data)["status"], "BLOCKED")

    def test_stopped_blocked(self):
        data = [{"Config": {}, "State": {"Running": False}, "Image": mod.PINNED_IMAGE}]
        self.assertEqual(mod.sanitize_inspect(data)["status"], "BLOCKED")

    def test_pinned_image_pass_only_deployment(self):
        data = [{"Config": {"Cmd": ["--block-size", "16"]},
                 "State": {"Running": True}, "Image": mod.PINNED_IMAGE}]
        got = mod.sanitize_inspect(data)
        self.assertEqual(got["status"], "PASS")
        self.assertIn("NOT active", got["scope"])

    def test_no_secret_or_path_ever_echoed(self):
        args = ["--api-key", "SECRET", "--model", "/secret/path",
                "--block-size=16", "--gpu-memory-utilization", "0.8",
                "--speculative-config", '{"key":"SECRET"}',
                "--enable-prefix-caching"]
        got = mod.flag_allowlist(args)
        self.assertEqual(got["--block-size"], "16")
        self.assertEqual(got["--gpu-memory-utilization"], "0.8")
        self.assertTrue(got["--enable-prefix-caching"])
        self.assertNotIn("SECRET", str(got))
        self.assertNotIn("/secret/path", str(got))

    def test_nonnumeric_is_filtered(self):
        self.assertEqual(mod.flag_allowlist(["--block-size", "SECRET"]), {})

    def test_invalid_argv_is_filtered(self):
        self.assertEqual(mod.flag_allowlist({"Cmd": "not-list"}), {})

    def test_historical_sha_formats(self):
        self.assertEqual(len(mod.BASELINE_SHA), 64)
        self.assertEqual(len(mod.BENCH_SHA), 40)


if __name__ == "__main__":
    unittest.main()
