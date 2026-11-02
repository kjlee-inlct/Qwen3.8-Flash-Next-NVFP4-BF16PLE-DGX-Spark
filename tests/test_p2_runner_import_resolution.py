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

    def test_single_offline_bundle_has_six_explicit_modules(self):
        runner = (ROOT / "scripts/p2-batch-cpu-container.sh").read_text(encoding="utf-8")
        self.assertIn("P2_TEST_PACKAGE_LOCAL_VERIFIED", runner)
        self.assertIn("P2_TEST_PACKAGE_ORIGIN_MISMATCH", runner)
        self.assertIn("testsRun != 40", runner)
        self.assertIn("result.skipped", runner)
        self.assertIn("docker run --rm -i --pull=never", runner)


if __name__ == "__main__":
    unittest.main()
