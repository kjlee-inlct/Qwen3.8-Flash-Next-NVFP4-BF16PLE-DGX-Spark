# publication-audit: allow-test-fixture
"""Offline monitoring/receipt comparison tests; NO actual Docker or HTTP calls."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "wizard"))
import monitor
import cli as wizard_cli


def sample() -> dict:
    return {
        "identity_verified": True, "verified": True,
        "repo_dir": "/example/repo", "cache_dir": "/example/repo/hf-cache",
        "container_name": "qwen38-flash-orca-uncensored-bf16-mtp",
        "recorded_container_id": "a" * 64, "observed_container_id": "a" * 64,
        "recorded_image_id": "sha256:" + "b" * 64,
        "observed_image_id": "sha256:" + "b" * 64,
        "container_status": "running", "image_tag": "yslab:pin",
        "mount_paths": {"hf_cache": "/example/repo/hf-cache",
                        "recipe_views": "/example/repo/recipe-views"},
        "checks": {
            "recorded_paths": True, "container_identity": True,
            "image_identity": True, "docker_labels": True,
            "port_binding": True, "model_mounts": True},
        "checkout": {"origin": "https://example.org/a", "head": "a" * 40,
                     "tracked_worktree_clean": True},
        "checkout_warnings": [], "read_only": True,
        "management_authority": "OBSERVE_ONLY",
        "api": {"health": "PASS", "models": "PASS"},
    }


class SnapshotMonitorTests(unittest.TestCase):
    def test_identical_snapshot(self):
        result = monitor.compare_observations(sample(), sample())
        self.assertEqual(result["status"], "UNCHANGED")
        self.assertEqual(result["counts"], {"identity": 0, "health": 0, "git": 0})

    def test_no_saved_receipt(self):
        result = monitor.compare_observations(None, sample())
        self.assertEqual(result["status"], "UNREGISTERED")
        self.assertEqual(result["differences"], [])

    def test_current_inspection_unavailable(self):
        self.assertEqual(monitor.compare_observations(sample(), None)["status"], "UNKNOWN")

    def test_container_id_changed_is_identity_change(self):
        current = sample()
        current["observed_container_id"] = "c" * 64
        result = monitor.compare_observations(sample(), current)
        self.assertEqual(result["status"], "CHANGED")
        self.assertEqual(result["counts"]["identity"], 1)

    def test_mount_change_is_identity_change(self):
        current = sample()
        current["mount_paths"]["hf_cache"] = "/different/cache"
        result = monitor.compare_observations(sample(), current)
        self.assertEqual(result["status"], "CHANGED")
        self.assertEqual(result["counts"]["identity"], 1)

    def test_checkout_drift_is_informational(self):
        current = sample()
        current["checkout"]["head"] = "d" * 40
        current["checkout"]["origin"] = "https://github.com/kjlee-inlct/fork"
        result = monitor.compare_observations(sample(), current)
        self.assertEqual(result["status"], "GIT_CHANGED")
        self.assertEqual(result["counts"]["identity"], 0)
        self.assertEqual(result["counts"]["git"], 2)

    def test_api_failure_does_not_remove_identity(self):
        current = sample()
        current["api"]["health"] = "UNAVAILABLE"
        result = monitor.compare_observations(sample(), current)
        self.assertEqual(result["status"], "HEALTH_CHANGED")
        self.assertEqual(result["counts"]["identity"], 0)

    def test_old_schema_missing_fields_is_unknown(self):
        saved = sample()
        del saved["mount_paths"]
        self.assertEqual(monitor.compare_observations(saved, sample())["status"], "UNKNOWN")

    def test_report_never_mutates_local_state(self):
        before, now = sample(), sample()
        with patch.object(monitor.engine, "deployment_status",
                          return_value={"recorded_legacy": before, "legacy": now}):
            report = monitor.status_report()
        self.assertEqual(report["comparison"]["status"], "UNCHANGED")
        self.assertNotIn("health", report)

    def test_capacity_advisory_does_not_fail_healthy_service(self):
        with patch.object(monitor, "_disk", return_value={"status": "LOW_SPACE", "free_gib": 2.0}), \
             patch.object(monitor, "_memory", return_value={"status": "OBSERVED"}):
            result = monitor.host_health(sample())
        self.assertEqual(result["status"], "WARN")
        self.assertEqual(result["identity"], "PASS")

    def test_unknown_disk_does_not_claim_health_pass(self):
        with patch.object(monitor, "_disk", return_value={"status": "UNKNOWN"}), \
             patch.object(monitor, "_memory", return_value={"status": "UNKNOWN"}):
            result = monitor.host_health(sample())
        self.assertEqual(result["disk"]["hf_cache"]["status"], "UNKNOWN")

    def test_api_health_failure_is_failure(self):
        record = sample()
        record["api"]["health"] = "UNAVAILABLE"
        with patch.object(monitor, "_disk", return_value={"status": "PASS"}), \
             patch.object(monitor, "_memory", return_value={"status": "OBSERVED"}):
            self.assertEqual(monitor.host_health(record)["status"], "UNKNOWN")

    def test_summary_compact_contains_required_states(self):
        data = {"legacy": sample(), "comparison": monitor.compare_observations(sample(), sample()),
                "warnings": []}
        lines = monitor.summary_lines(data)
        self.assertTrue(any("OBSERVE_ONLY" in line for line in lines))
        self.assertTrue(any("UNCHANGED" in line for line in lines))
        self.assertTrue(any("PASS" in line for line in lines))

    def test_cli_defaults_to_compact_and_json_optional(self):
        report = {"legacy": sample(), "comparison":
                  monitor.compare_observations(sample(), sample()), "warnings": []}
        with patch.object(wizard_cli, "status_report", return_value=report):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(wizard_cli.main(["status"]), 0)
            self.assertIn("UNCHANGED", output.getvalue())
            self.assertNotIn('"recorded_container_id"', output.getvalue())
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(wizard_cli.main(["status", "--json"]), 0)
            self.assertEqual(json.loads(output.getvalue())["comparison"]["status"], "UNCHANGED")

    def test_cli_strict_rejects_identity_drift(self):
        current = sample()
        current["observed_container_id"] = "c" * 64
        report = {"legacy": current, "comparison":
                  monitor.compare_observations(sample(), current), "warnings": []}
        with patch.object(wizard_cli, "status_report", return_value=report), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(wizard_cli.main(["status", "--strict"]), 1)


if __name__ == "__main__":
    unittest.main()
