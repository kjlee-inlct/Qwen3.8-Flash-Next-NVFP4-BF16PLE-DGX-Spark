"""Offline regression contract: CI and DGX main verifier cannot deploy services."""
from __future__ import annotations
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CiContractTests(unittest.TestCase):
    def test_ci_checks_pr_inventory_and_main_strict_without_installation(self):
        content = (ROOT / ".github/workflows/test.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", content)
        self.assertIn("scripts/verify-source-state.sh", content)
        self.assertIn("scripts/verify-source-state.sh --strict", content)
        self.assertIn("if: github.ref == 'refs/heads/main'", content)
        self.assertIn("scripts/run-mock-tests.sh", content)
        self.assertNotIn("install.sh --yes", content)
        self.assertNotIn("docker run", content)

    def test_main_verifier_checks_ref_without_checkout_or_docker_mutations(self):
        content = (ROOT / "scripts/verify-main-readonly.sh").read_text(encoding="utf-8")
        for forbidden in ("git switch ", "git reset ", "git clean ", "git pull ",
                          "docker stop ", "docker rm ", "docker run ", "git fetch "):
            self.assertNotIn("\n" + forbidden, content)
        self.assertIn('[[ "$branch" == main ]]', content)
        self.assertIn("scripts/verify-source-state.sh --strict", content)


if __name__ == "__main__":
    unittest.main()
