"""Read-only P2 sampler witness audit focused tests, no Docker/GPU/API."""
from __future__ import annotations

import hashlib
import io
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from src import p2_numeric_witness_readonly_audit as audit
from src import p2_numeric_sampler_witness as witness
from tests.test_p2_numeric_sampler_witness import fixture


class WitnessStaticAuditTests(unittest.TestCase):
    @staticmethod
    def reference():
        raw=fixture()
        with patch.object(witness, "SOURCE_SHA256", hashlib.sha256(raw).hexdigest()):
            staged=witness.transform(raw)
        return raw, staged

    def test_exact_source_transform_and_guard_map_success(self):
        raw,staged=self.reference()
        with patch.object(witness,"SOURCE_SHA256",hashlib.sha256(raw).hexdigest()):
            report=audit.audit_source(raw,staged)
        self.assertTrue(report["exact_original_pinned_transform_matches_stage"])
        self.assertEqual(report["status"],
                         "P2_NUMERIC_WITNESS_STATIC_GATES_VERIFIED_RUNTIME_UNKNOWN")
        self.assertEqual(report["candidate_gpu_or_http_executed"],False)
        self.assertFalse(report["runtime_sampler_import_verified"])
        self.assertFalse(report["numeric_root_cause_located"])
        self.assertIn("PROCESSED_LOGPROBS_MUST_BE_NONE_FOR_EMISSION",
                      report["static_suppression_conditions"])
        self.assertNotIn("token_ids",json.dumps(report))

    def test_original_forward_site_map_locates_processed_logprobs_condition(self):
        result = audit.original_forward_flow(fixture())
        self.assertFalse(result["runtime_branches_observed"])
        self.assertFalse(result["runtime_assignment_values_observed"])
        self.assertFalse(result["sites_truncated"])
        sites = result["sites"]
        self.assertTrue(any(
            item["kind"] == "assignment"
            and "processed_logprobs" in item["targets"]
            for item in sites))
        self.assertTrue(any(
            item["kind"] == "conditional"
            and "processed_logprobs" in item["referenced_names"]
            for item in sites))
        self.assertTrue(any(
            item["kind"] == "assignment"
            and "num_logprobs" in item["targets"] for item in sites))
        self.assertTrue(all(
            isinstance(item["line"], int) and item["line"] > 0
            for item in sites))
        self.assertNotIn("self.sample(", json.dumps(result))
        self.assertNotIn("logits[", json.dumps(result))

    def test_original_forward_ambiguous_source_rejected(self):
        source = fixture()
        doubled = source + b"\n" + source
        with self.assertRaisesRegex(audit.AuditBlocked,
                                    "SAMPLER_FORWARD_AMBIGUOUS"):
            audit.original_forward_flow(doubled)

    def test_original_forward_syntax_and_size_fail_closed(self):
        with self.assertRaisesRegex(audit.AuditBlocked,
                                    "SAMPLER_FORWARD_SOURCE_AST_INVALID"):
            audit.original_forward_flow(b"class Sampler:\n  def forward(:\n")
        with self.assertRaisesRegex(audit.AuditBlocked,
                                    "SAMPLER_FORWARD_SOURCE_SIZE_INVALID"):
            audit.original_forward_flow(b"#" * (audit.MAX_STAGE_SOURCE + 1))

    def test_unpinned_original_rejected(self):
        raw,staged=self.reference()
        with self.assertRaisesRegex(audit.AuditBlocked,"ORIGINAL_SAMPLER_SOURCE_SHA_DRIFT"):
            audit.audit_source(raw,staged)

    def test_staged_sampler_modified_rejected(self):
        raw,staged=self.reference()
        with patch.object(witness,"SOURCE_SHA256",hashlib.sha256(raw).hexdigest()):
            with self.assertRaisesRegex(audit.AuditBlocked,"STAGED_SAMPLER_DIFFERS"):
                audit.audit_source(raw,staged+b"\n# modified")

    def test_original_container_started_at_drift_rejected(self):
        raw, staged = self.reference()
        # Create a real regular file: otherwise a missing fixture could raise
        # SAMPLER_STAGE_UNSAFE before the finally drift guard and still PASS.
        with tempfile.TemporaryDirectory(
                prefix="p2-numeric-first-divergence-unit-", dir="/tmp") as temp:
            source = Path(temp) / "sampler.py"
            source.write_bytes(staged)
            source.chmod(0o600)
            with patch.object(audit.trace, "original_identity",
                              side_effect=[("id", "img", "t1"),
                                           ("id", "img", "t2")]) as identity, \
                 patch.object(audit.window, "verify_minimal_stage") as verify, \
                 patch.object(audit.trace, "_run_docker_cp", return_value=raw) as read, \
                 patch.object(audit, "audit_source",
                              return_value={"status": "STATIC"}) as parsed:
                with self.assertRaisesRegex(
                        audit.AuditBlocked, "STARTED_AT_DRIFT"):
                    audit.read_only_audit(Path(temp))
            self.assertEqual(identity.call_count, 2)
            verify.assert_called_once_with(Path(temp))
            read.assert_called_once_with(audit.trace.SOURCES["sampler"])
            parsed.assert_called_once_with(raw, staged)

    def test_no_exec_build_stop_gpu_or_http_in_audit(self):
        raw, staged = self.reference()
        with tempfile.TemporaryDirectory(
                prefix="p2-numeric-first-divergence-unit-", dir="/tmp") as temp:
            source = Path(temp) / "sampler.py"
            source.write_bytes(staged)
            source.chmod(0o600)
            with patch.object(audit.trace, "original_identity",
                              return_value=("id", "img", "stable")) as identity, \
                 patch.object(audit.window, "verify_minimal_stage") as verify, \
                 patch.object(audit.trace, "_run_docker_cp",
                              return_value=raw) as read, \
                 patch.object(witness, "SOURCE_SHA256",
                              hashlib.sha256(raw).hexdigest()), \
                 patch.object(audit.window.release, "_run") as docker_run:
                result = audit.read_only_audit(Path(temp))
            self.assertTrue(result["original_same_id_running_verified"])
            self.assertTrue(result["stage_read_only_verified"])
            self.assertTrue(result["exact_original_pinned_transform_matches_stage"])
            self.assertFalse(result["service_stop_or_restart_performed"])
            self.assertEqual(identity.call_count, 2)
            verify.assert_called_once_with(Path(temp))
            read.assert_called_once_with(audit.trace.SOURCES["sampler"])
            docker_run.assert_not_called()

    def test_symlinked_sampler_source_rejected(self):
        raw, staged = self.reference()
        with tempfile.TemporaryDirectory(
                prefix="p2-numeric-first-divergence-unit-", dir="/tmp") as temp:
            folder = Path(temp)
            other = folder / "other.py"
            other.write_bytes(staged)
            (folder / "sampler.py").symlink_to(other)
            with patch.object(audit.trace, "original_identity",
                              return_value=("id", "img", "stable")) as identity, \
                 patch.object(audit.window, "verify_minimal_stage") as verify, \
                 patch.object(audit.trace, "_run_docker_cp",
                              return_value=raw) as read:
                with self.assertRaisesRegex(audit.AuditBlocked,
                                            "SAMPLER_STAGE_UNSAFE"):
                    audit.read_only_audit(folder)
            self.assertEqual(identity.call_count, 2)
            verify.assert_called_once_with(folder)
            read.assert_called_once_with(audit.trace.SOURCES["sampler"])

    def test_cli_static_success_and_static_block_not_invoke_gpu(self):
        from contextlib import redirect_stdout, redirect_stderr
        with patch.object(audit.qsa,"preflight"), \
             patch.object(audit,"read_only_audit",
                          return_value={"status":"P2_NUMERIC_WITNESS_STATIC_GATES_VERIFIED_RUNTIME_UNKNOWN"}) as read:
            out=io.StringIO()
            with redirect_stdout(out):
                rc=audit.main(["--expected-head","a"*40,"--stage",
                               "/tmp/p2-numeric-first-divergence-test"])
            self.assertEqual(rc,0)
            self.assertEqual(json.loads(out.getvalue())["status"],
                             "P2_NUMERIC_WITNESS_STATIC_GATES_VERIFIED_RUNTIME_UNKNOWN")
            read.assert_called_once()
        with patch.object(audit.qsa,"preflight"), \
             patch.object(audit,"read_only_audit",
                          side_effect=audit.AuditBlocked("TEST")):
            err=io.StringIO()
            with redirect_stderr(err):
                self.assertEqual(audit.main(["--expected-head","a"*40,
                    "--stage","/tmp/p2-numeric-first-divergence-test"]),2)
            self.assertIn("P2_NUMERIC_WITNESS_STATIC_AUDIT_BLOCKED",err.getvalue())


if __name__=="__main__":
    unittest.main()
