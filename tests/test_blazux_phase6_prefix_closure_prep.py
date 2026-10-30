"""Safety contract for one-shot P1 CPU-only closure preparation."""
from pathlib import Path
import subprocess
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/p1-prefix-closure-prep.sh"


class ClosurePrepTests(unittest.TestCase):
    def test_shell_syntax_and_expected_head_required(self):
        cp = subprocess.run(["bash", "-n", str(SCRIPT)],
                            check=False, capture_output=True, text=True)
        self.assertEqual(cp.returncode, 0, cp.stderr)
        cp = subprocess.run(["bash", str(SCRIPT)], check=False,
                            capture_output=True, text=True)
        self.assertEqual(cp.returncode, 2)
        self.assertIn("Usage:", cp.stdout)

    def test_never_implicitly_changes_gpu_service_or_threshold(self):
        body = SCRIPT.read_text()
        self.assertIn("p1-prefix-gpu-window.sh", body)
        self.assertIn("--preflight", body)
        self.assertIn("verify-source-state.py", body)
        self.assertIn("git status --porcelain", body)
        self.assertIn("test_blazux_phase6_prefix_state_reuse_contract.py", body)
        self.assertIn("test_blazux_phase6_prefix_mamba_utils_probe.py", body)
        self.assertIn("test_blazux_phase6_prefix_copy_region_contract.py", body)
        self.assertIn("test_blazux_phase6_prefix_state_snapshot.py", body)
        self.assertIn("test_blazux_phase6_prefix_offline_evidence.py", body)
        self.assertIn("test_blazux_phase6_prefix_release.py", body)
        self.assertIn("src.p1_prefix_state_reuse_contract", body)
        self.assertNotIn("--execute", body)
        self.assertNotIn("--recover", body)
        self.assertNotIn("docker stop", body)
        self.assertNotIn("docker start", body)
        self.assertNotIn("stop.sh --", body)
        self.assertNotIn("start.sh --", body)
        self.assertNotIn("docker rm", body)
        self.assertNotIn("1e-3", body)


if __name__ == "__main__":
    unittest.main()
