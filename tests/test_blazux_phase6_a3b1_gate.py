"""P6-A3b-1 CPU-only evidence parser and Docker execution policy regression."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "phase6_a3b1_evidence", ROOT / "src/phase6_a3b1_evidence.py"
)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def synthetic_stdout():
    data = {
        "status": "PINNED_SOURCE_AST_ONLY_NOT_CONFIG_CONSTRUCTION",
        "p6_a_runtime_status": "BLOCKED",
        "actual_scheduler_cache_mamba_config_reproduced": False,
        "actual_gpu_block_table_or_state_observed": False,
        "vllm_modules_imported": False,
        "gpu_model_http_benchmark_ci_executed": False,
        "components": [{
            "component": name, "kind": "PARSED_SOURCE_NOT_EXECUTED",
            "historical_dgx_sha_match":
                None if name == "v1/core/kv_cache_utils.py" else True,
            "declared_anchor_present": True,
        } for name in sorted(mod.EXPECTED_PATHS)],
    }
    return json.dumps(data) + "\n" + mod.MARKER + "\n"


class A3b1EvidenceTests(unittest.TestCase):
    def test_good_source_evidence_only_source_pass(self):
        result = mod.summarize(synthetic_stdout())
        self.assertEqual(result["status"], "PASS_PINNED_SOURCE_AST_ONLY")
        self.assertEqual(result["p6_a_runtime_status"], "BLOCKED")
        self.assertFalse(result["active_scheduler_cache_mamba_reproduced"])

    def test_empty_blocked(self):
        self.assertEqual(mod.summarize("")["status"], "BLOCKED")

    def test_extra_text_blocked(self):
        self.assertEqual(mod.summarize(synthetic_stdout() + "MORE")["status"], "BLOCKED")

    def test_approval_claim_blocked(self):
        raw = synthetic_stdout().replace('"p6_a_runtime_status": "BLOCKED"',
                                         '"p6_a_runtime_status": "PASS"')
        self.assertEqual(mod.summarize(raw)["status"], "BLOCKED")

    def test_sha_drift_blocked(self):
        raw = synthetic_stdout().replace('"historical_dgx_sha_match": true',
                                         '"historical_dgx_sha_match": false', 1)
        self.assertEqual(mod.summarize(raw)["status"], "BLOCKED")

    def test_incomplete_anchor_blocked(self):
        raw = synthetic_stdout().replace('"declared_anchor_present": true',
                                         '"declared_anchor_present": false', 1)
        self.assertEqual(mod.summarize(raw)["status"], "BLOCKED")

    def test_gpu_observation_claim_blocked(self):
        raw = synthetic_stdout().replace('"actual_gpu_block_table_or_state_observed": false',
                                         '"actual_gpu_block_table_or_state_observed": true')
        self.assertEqual(mod.summarize(raw)["status"], "BLOCKED")

    def test_vllm_import_claim_blocked(self):
        raw = synthetic_stdout().replace('"vllm_modules_imported": false',
                                         '"vllm_modules_imported": true')
        self.assertEqual(mod.summarize(raw)["status"], "BLOCKED")

    def test_unpinned_kv_sha_field_not_claimed(self):
        raw = synthetic_stdout().replace('"historical_dgx_sha_match": null',
                                         '"historical_dgx_sha_match": true')
        self.assertEqual(mod.summarize(raw)["status"], "BLOCKED")

    def test_output_bound(self):
        self.assertEqual(mod.summarize("x" * (mod.MAX_OUTPUT + 1))["status"], "BLOCKED")

    def test_shell_gate_includes_isolation_and_memory_floor(self):
        script = (ROOT / "scripts/phase6-a3b1-cpu-container-gate.sh").read_text()
        required = (
            '"--execute"', "docker run --rm --pull=never",
            "--runtime=runc", "--network=none", "--read-only",
            "--cap-drop=ALL", "--security-opt=no-new-privileges",
            "--cpus=1", "--memory=512m", "--memory-swap=512m",
            "--pids-limit=64", "--user=65534:65534",
            "NVIDIA_VISIBLE_DEVICES=void", "CUDA_VISIBLE_DEVICES=-1",
            "HF_HUB_OFFLINE=1", "TRANSFORMERS_OFFLINE=1",
            "PYTHONDONTWRITEBYTECODE=1", "--installed-source-only",
            "source=$ROOT,target=/phase6,readonly", "MIN_AVAILABLE_KIB=4194304",
            "legacy_identity_ok", "src/phase6_a3b1_evidence.py",
        )
        for item in required:
            with self.subTest(item=item):
                self.assertIn(item, script)
        for forbidden in ("--gpus", "--privileged", "docker exec",
                          "docker stop", "docker restart", "docker pull"):
            self.assertNotIn(forbidden, script)

    def test_preview_stays_inert(self):
        script = (ROOT / "scripts/phase6-a3b-container-preview.sh").read_text()
        self.assertIn("--preview", script)
        self.assertNotIn("docker run --rm", script)


if __name__ == "__main__":
    unittest.main()
