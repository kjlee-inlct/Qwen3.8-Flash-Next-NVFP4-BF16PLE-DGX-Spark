"""Reproduce installed site-packages/tests name collision without Docker/GPU."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPackageResolutionTests(unittest.TestCase):
    def test_repository_package_beats_installed_tests_package(self):
        with tempfile.TemporaryDirectory() as td:
            external = Path(td) / "tests"
            external.mkdir()
            (external / "__init__.py").write_text(
                "raise RuntimeError('shadow installed tests package selected')\n",
                encoding="utf-8",
            )
            program = (
                "from pathlib import Path\n"
                "import tests\n"
                "p = Path(tests.__file__).resolve(strict=True)\n"
                "assert p == Path('tests/__init__.py').resolve(strict=True), p\n"
                "from tests import test_p2_numeric_sampler_witness\n"
                "assert callable(test_p2_numeric_sampler_witness.fixture)\n"
            )
            result = subprocess.run(
                [sys.executable, "-B", "-S", "-c", program],
                cwd=ROOT,
                env={**os.environ, "PYTHONPATH": td, "PYTHONDONTWRITEBYTECODE": "1"},
                capture_output=True, text=True, timeout=15, check=False,
            )
            # -S means NumPy is deliberately absent in the subprocess. The
            # imported fixture module uses stdlib and repository source only.
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_isolated_container_uses_invoking_nonroot_uid_for_private_sources(self):
        runner = (ROOT / "scripts/p2-batch-cpu-container.sh").read_text(encoding="utf-8")
        self.assertIn('readonly HOST_UID="$(id -u)"', runner)
        self.assertIn('readonly HOST_GID="$(id -g)"', runner)
        self.assertIn('10#$HOST_UID > 0 && 10#$HOST_GID > 0', runner)
        self.assertIn('--user "$HOST_UID:$HOST_GID"', runner)
        self.assertNotIn("--user=65534:65534", runner)
        self.assertIn(' -r "$ROOT/src/p1_preview_qsa_exact_topk.py"', runner)
        self.assertIn('target=/p2,readonly', runner)
        self.assertIn("--runtime=runc --network=none --read-only", runner)
        self.assertIn("--env NVIDIA_VISIBLE_DEVICES=void", runner)
        self.assertNotIn("chmod 777", runner)
        self.assertNotIn("chown -R", runner)

    def test_docker_runner_requires_explicit_execute(self):
        runner = ROOT / "scripts/p2-batch-cpu-container.sh"
        result = subprocess.run(["bash", str(runner)], cwd=ROOT,
                                capture_output=True, text=True, timeout=10,
                                check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("explicit --execute required", result.stderr)

    def test_single_offline_bundle_has_six_explicit_modules(self):
        runner = (ROOT / "scripts/p2-batch-cpu-container.sh").read_text(encoding="utf-8")
        self.assertIn("P2_TEST_PACKAGE_LOCAL_VERIFIED", runner)
        self.assertIn("P2_TEST_PACKAGE_ORIGIN_MISMATCH", runner)
        self.assertIn("testsRun != 40", runner)
        self.assertIn("result.skipped", runner)
        self.assertIn("docker run --rm -i --pull=never", runner)


if __name__ == "__main__":
    unittest.main()
