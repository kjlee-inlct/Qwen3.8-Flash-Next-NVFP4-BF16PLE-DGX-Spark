"""Offline safety tests for user-approved provisional live benchmark wrapper."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "phase6_ab_provisional_bench", ROOT / "src/phase6_ab_provisional_bench.py"
)
# add local src to sys.path for imported baseline_contract
import sys
sys.path.insert(0, str(ROOT / "src"))
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class ABProvisionalTests(unittest.TestCase):
    def test_corpus_hash_pin(self):
        self.assertEqual(len(mod.CORPUS_SHA), 64)

    def test_known_provenance_boundaries(self):
        self.assertEqual(mod.PHASE, "phase6-pre-b-provisional")
        self.assertEqual(mod.MEM_BEFORE_MIB, 8192)
        self.assertEqual(mod.MEM_STOP_MIB, 4096)
        self.assertEqual(mod.MAX_SECONDS, 3600)

    def test_result_name_positive(self):
        self.assertIsNotNone(mod.RESULT_BASENAME.fullmatch(
            "20261028T230001Z-phase6-pre-b-provisional-A1b2c3"
        ))

    def test_result_name_rejects_baseline_or_traversal(self):
        self.assertIsNone(mod.RESULT_BASENAME.fullmatch("20261026T221925Z-pre-blazux"))
        self.assertIsNone(mod.RESULT_BASENAME.fullmatch("../result.json"))

    def test_deployment_unavailable_fails_closed(self):
        with patch.object(mod, "command", return_value=None):
            self.assertIsNone(mod.deployment_identity())

    def test_docker_identity_wrong_image_blocked(self):
        text = json.dumps([{"Image": "wrong", "State": {"Running": True}}])
        with patch.object(mod, "command", return_value=text):
            self.assertIsNone(mod.deployment_identity())

    def test_docker_identity_correct(self):
        text = json.dumps([{"Image": mod.IMAGE, "Id": "testid",
                            "State": {"Running": True, "StartedAt": "t1"}}])
        with patch.object(mod, "command", return_value=text):
            self.assertEqual(mod.deployment_identity(), ("testid", mod.IMAGE, "t1"))

    def test_baseline_original_sha_strict_preflight(self):
        with patch.object(mod.baseline_contract, "verify_immutable_baseline", return_value={
            "status": "BLOCKED"
        }):
            self.assertEqual(mod.preflight()["status"], "BLOCKED")

    def test_mem_floor_blocks(self):
        with patch.object(mod.baseline_contract, "verify_immutable_baseline", return_value={
            "status": "SOURCE_BASELINE_MATRIX_VALIDATED"
        }), patch.object(mod, "command", return_value=mod.baseline_contract.RUNNER_SHA), patch.object(
            mod, "digest", return_value=mod.CORPUS_SHA
        ), patch.object(mod, "deployment_identity", return_value=("x", "i", "t")), patch.object(
            mod, "memory_available_mib", return_value=1024
        ), patch.object(mod.Path, "is_dir", return_value=True), patch.object(
            mod.Path, "is_symlink", return_value=False
        ), patch.object(mod.Path, "is_file", return_value=True):
            self.assertEqual(mod.preflight()["status"], "BLOCKED")

    def test_checksum_ledger_parser_rejects_missing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "result.json").write_text('{}', encoding="utf-8")
            self.assertEqual(mod.verify_run_dir(path)["status"], "INCOMPLETE")

    def test_wrapper_source_never_touches_existing_container(self):
        script = (ROOT / "scripts/phase6-ab-provisional-run.sh").read_text()
        engine = (ROOT / "src/phase6_ab_provisional_bench.py").read_text()
        for forbidden in ("docker stop", "docker restart", "docker rm", "docker exec",
                          "docker run", "--gpus", "git push", "os.kill(1,"):
            for line in (script+"\n"+engine).splitlines():
                if not line.strip().startswith("#"):
                    self.assertNotIn(forbidden, line)

    def test_wrapper_requires_explicit_execute(self):
        shell = (ROOT / "scripts/phase6-ab-provisional-run.sh").read_text()
        self.assertIn('"$1" == "--execute"', shell)
        self.assertIn('"$1" == "--preflight"', shell)

    def test_no_outside_results_in_repo(self):
        self.assertIn("bench-results-staging", str(mod.OUT_ROOT))
        self.assertNotIn(str(ROOT), str(mod.OUT_ROOT))

    def test_pinned_legacy_wrapper_is_single_bash_child(self):
        code = (ROOT / "src/phase6_ab_provisional_bench.py").read_text()
        self.assertIn('["bash", str(SCRIPT)]', code)
        self.assertIn("start_new_session=True", code)
        self.assertIn("os.killpg(proc.pid, sig)", code)

    def test_provisional_run_never_claims_a_or_d_pass(self):
        code = (ROOT / "src/phase6_ab_provisional_bench.py").read_text()
        self.assertIn('"actual_runtime_abi": "BLOCKED"', code)
        self.assertIn('"formal_p6_d_comparison": "NOT_RUN"', code)

    def _synthetic_completed_bench_directory(self, path: Path) -> None:
        import hashlib
        historical = ROOT / mod.baseline_contract.BASELINE_REL
        (path / "result.json").write_bytes(historical.read_bytes())
        provenance = {
            "phase": mod.PHASE,
            "visibility": "PRIVATE_DO_NOT_COMMIT",
            "tool_git_sha": mod.baseline_contract.RUNNER_SHA,
            "tokenizer_sha256": mod.baseline_contract.TOKENIZER_SHA,
            "book_sha256": mod.CORPUS_SHA,
            "served_model": mod.MODEL_ID,
            "prompt_rng_seed": 20261027,
            "parameters": {
                "pp": [2048, 8192], "tg": [128, 256],
                "depth": [0, 4096, 16384], "concurrency": [1],
                "runs": 3, "warmup_runs": 1, "exact_tg": True,
                "latency_mode": "generation",
            },
        }
        (path / "environment.private.json").write_text(
            json.dumps(provenance) + "\n", encoding="utf-8"
        )
        for filename in mod.TAGS:
            if filename not in ("result.json", "environment.private.json"):
                (path / filename).write_text("test-only placeholder\n", encoding="utf-8")
        with (path / "SHA256SUMS").open("w", encoding="ascii") as ledger:
            for filename in mod.TAGS:
                content = (path / filename).read_bytes()
                ledger.write(f"{hashlib.sha256(content).hexdigest()}  {filename}\n")

    def test_synthetic_success_runs_36_raw_repeats(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            self._synthetic_completed_bench_directory(path)
            result = mod.verify_run_dir(path)
            self.assertEqual(result["status"], "PASS_PROVISIONAL_PRE_B_36")
            self.assertEqual(result["measured_repeats"], 36)
            self.assertEqual(len(result["metrics"]), 12)
            self.assertEqual(result["actual_runtime_abi"], "BLOCKED")

    def test_checksum_tamper_fails_without_exposing_private_data(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            self._synthetic_completed_bench_directory(path)
            (path / "run.log").write_text("TAMPER_SECRET\n", encoding="utf-8")
            result = mod.verify_run_dir(path)
            self.assertEqual(result["status"], "INCOMPLETE")
            self.assertNotIn("TAMPER_SECRET", str(result))


if __name__ == "__main__":
    unittest.main()
