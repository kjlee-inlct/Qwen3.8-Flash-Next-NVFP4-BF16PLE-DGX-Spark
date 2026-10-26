# publication-audit: allow-test-fixture
"""Simulated Docker/Git/legacy tests; no real commands, downloads or API traffic."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "wizard"))
import cli as wizard_cli
import engine
import probe
import state


LEGACY_ID = "a" * 64
IMG_ID = "sha256:" + "b" * 64
TARGET = "orca-uncensored-bf16-mtp"
CONTAINER = "qwen38-flash-orca-uncensored-bf16-mtp"


def fake_container(repo: Path) -> dict:
    return {
        "Id": LEGACY_ID, "Image": IMG_ID,
        "Config": {"Labels": {
            "ai.yslab.recipe": probe.RECIPE_LABEL, "ai.yslab.target": TARGET}},
        "State": {"Status": "running"},
        "HostConfig": {"PortBindings": {"8000/tcp": [
            {"HostIp": "0.0.0.0", "HostPort": "8000"}]}},
        "Mounts": [
            {"Source": str(repo / "hf-cache"), "Destination": "/recipe/hf-cache"},
            {"Source": str(repo / "recipe-views"), "Destination": "/recipe/recipe-views"}],
    }


class FakeLegacyProbeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / "model-checkout"
        self.cache = self.repo / "hf-cache"
        self.repo.mkdir()
        self.cache.mkdir()
        (self.repo / "recipe-views").mkdir()
        self.receipts = self.root / "legacy-state"
        self.receipts.mkdir()
        (self.receipts / "paths").write_text(
            f"{self.repo}\n{self.cache}\n", encoding="utf-8")
        (self.receipts / "image-id").write_text(IMG_ID + "\n", encoding="utf-8")
        (self.receipts / "container-id").write_text(LEGACY_ID + "\n", encoding="utf-8")
        self.policy = {"legacy": {
            "state_relative": "legacy-state", "repo_relative": "old-ySlab",
            "origin_url": "https://github.com/YSLAB-ai/old.git",
            "pin": "9" * 40, "cache_name": "hf-cache",
            "image": "yslab-qwen38-bf16ple:9492b78c",
            "container": CONTAINER, "target": TARGET,
            "port": 8000, "bind": "0.0.0.0",
        }}
        self.env = patch.dict(os.environ, {
            "YSLAB_STATE_DIR": str(self.receipts),
            "YSLAB_REPO_DIR": str(self.repo)}, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)

    def fake_git(self, args: list[str], **kwargs):
        if args[0] != "git":
            raise AssertionError("attempt to issue unmocked external command")
        if "remote" in args:
            output = "https://github.com/kjlee-inlct/current-fork.git\n"
        elif "rev-parse" in args:
            output = "c" * 40 + "\n"
        elif "cat-file" in args:
            output = "commit\n"
        elif "status" in args:
            output = ""
        else:
            raise AssertionError(f"unhandled fake git command: {args}")
        return subprocess.CompletedProcess(args, 0, stdout=output, stderr="")

    def observe(self, *, current=None, actual_image=None) -> dict:
        cont = current if current is not None else fake_container(self.repo)
        img = actual_image if actual_image is not None else {"Id": IMG_ID}
        with patch.object(probe, "command", side_effect=self.fake_git), \
             patch.object(probe, "container", return_value=cont), \
             patch.object(probe, "image", return_value=img), \
             patch.object(probe, "_legacy_api_observation", return_value={
                 "health": "PASS", "models": "PASS"}):
            return probe.legacy_observation(self.policy)

    def test_git_drift_is_warning_but_identity_pass(self):
        record = self.observe()
        self.assertTrue(record["identity_verified"])
        self.assertTrue(record["verified"])
        self.assertFalse(record["checkout"]["origin_matches_install"])
        self.assertFalse(record["checkout"]["head_matches_install_pin"])
        self.assertTrue(record["checkout"]["install_pin_available"])
        self.assertTrue(all(record["checks"].values()))
        self.assertEqual(record["management_authority"], "OBSERVE_ONLY")
        self.assertEqual(record["reasons"], [])

    def test_mismatched_container_id_fails(self):
        cont = fake_container(self.repo)
        cont["Id"] = "d" * 64
        record = self.observe(current=cont)
        self.assertFalse(record["identity_verified"])
        self.assertFalse(record["checks"]["container_identity"])

    def test_mount_mismatch_fails_without_mutation(self):
        cont = fake_container(self.repo)
        cont["Mounts"][0]["Source"] = "/other/path"
        record = self.observe(current=cont)
        self.assertFalse(record["checks"]["model_mounts"])
        self.assertFalse(record["identity_verified"])

    def test_port_bind_mismatch_fails(self):
        cont = fake_container(self.repo)
        cont["HostConfig"]["PortBindings"]["8000/tcp"][0]["HostIp"] = "127.0.0.1"
        record = self.observe(current=cont)
        self.assertFalse(record["checks"]["port_binding"])

    def test_bad_image_id_fails(self):
        record = self.observe(actual_image={"Id": "sha256:" + "c" * 64})
        self.assertFalse(record["checks"]["image_identity"])

    def test_read_only_registration_never_grants_remove_rights(self):
        report = self.observe()
        with patch.object(engine, "require_user"), \
             patch.object(engine, "legacy_observation", return_value=report), \
             patch.object(engine, "policy", return_value=self.policy), \
             patch.object(engine, "load", return_value=state.empty()), \
             patch.object(engine, "save") as save, \
             patch.object(engine, "command") as docker_command:
            result = engine.adopt_legacy(LEGACY_ID)
        self.assertEqual(result["management_authority"], "OBSERVE_ONLY")
        self.assertEqual(save.call_args.args[0]["legacy_observation"], report)
        self.assertEqual(save.call_args.args[0]["containers"], {})
        docker_command.assert_not_called()

    def test_read_only_registration_rejects_wrong_full_id(self):
        report = self.observe()
        with patch.object(engine, "require_user"), \
             patch.object(engine, "legacy_observation", return_value=report), \
             patch.object(engine, "policy", return_value=self.policy), \
             patch.object(engine, "save") as save:
            with self.assertRaises(engine.WizardError):
                engine.adopt_legacy("c" * 64)
        save.assert_not_called()


class FakeInstallerSafetyTests(unittest.TestCase):
    def test_install_activate_refuses_existing_legacy_name(self):
        with patch.object(engine, "policy", return_value={"service": {
            "image": "wizard-image", "host_bind": "127.0.0.1", "host_port": 18300}}), \
             patch.object(engine, "_runtime_target", return_value={"served_model_name": "qwen3.8"}), \
             patch.object(engine, "load", return_value=state.empty()), \
             patch.object(engine, "_image_owned", return_value=IMG_ID), \
             patch.object(engine, "container", return_value={"Id": LEGACY_ID}), \
             patch.object(engine, "require_user"), \
             patch.object(engine, "cli") as recipe_cli, \
             patch.object(engine, "command") as docker_command:
            with self.assertRaisesRegex(engine.WizardError, "name occupied"):
                engine.activate(target=TARGET, mtp=2, dry_run=False)
        recipe_cli.assert_not_called()
        docker_command.assert_not_called()

    def test_uninstall_requires_wizard_container_receipt(self):
        with patch.object(engine, "_runtime_target"), \
             patch.object(engine, "load", return_value=state.empty()), \
             patch.object(engine, "command") as command:
            with self.assertRaisesRegex(engine.WizardError, "no wizard ownership"):
                engine.stop_or_remove(target=TARGET, operation="remove", dry_run=False)
        command.assert_not_called()

    def test_uninstall_rejects_wrong_container_identity(self):
        rec = state.empty()
        rec["containers"][CONTAINER] = {
            "id": LEGACY_ID, "image_id": IMG_ID, "target": TARGET}
        actual = fake_container(Path("/tmp/fake"))
        actual["Id"] = "d" * 64
        with patch.object(engine, "_runtime_target"), \
             patch.object(engine, "load", return_value=rec), \
             patch.object(engine, "container", return_value=actual), \
             patch.object(engine, "command") as command:
            with self.assertRaises(probe.ProbeError):
                engine.stop_or_remove(target=TARGET, operation="remove", dry_run=False)
        command.assert_not_called()

    def test_dry_run_does_not_build_download_or_start(self):
        with patch.object(engine, "command") as command, \
             patch.object(engine, "cli") as recipe_cli:
            self.assertIn("PLAN:", engine.build_image(dry_run=True))
            self.assertIn("PLAN:", engine.prepare(
                target=TARGET, mtp=2, skip_login=True, dry_run=True))
            self.assertIn("PLAN:", engine.activate(
                target=TARGET, mtp=2, dry_run=True))
        command.assert_not_called()
        recipe_cli.assert_not_called()

    def test_image_removal_rejects_shared_image(self):
        with patch.object(engine, "policy", return_value={"service": {"image": "wizard-image"}}), \
             patch.object(engine, "load", return_value=state.empty()), \
             patch.object(engine, "_image_owned", return_value=IMG_ID), \
             patch.object(engine, "image_in_use", return_value=True), \
             patch.object(engine, "command") as command:
            with self.assertRaisesRegex(engine.WizardError, "still referenced"):
                engine.remove_image(dry_run=False)
        command.assert_not_called()

    def test_image_removal_rejects_missing_receipt(self):
        with patch.object(engine, "policy", return_value={"service": {"image": "wizard-image"}}), \
             patch.object(engine, "load", return_value=state.empty()), \
             patch.object(engine, "image", return_value={"Id": IMG_ID}), \
             patch.object(engine, "command") as command:
            with self.assertRaisesRegex(engine.WizardError, "no matching"):
                engine.remove_image(dry_run=False)
        command.assert_not_called()

    def test_cli_replace_is_blocked(self):
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()), \
             contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(wizard_cli.main(["install", "--replace", "--yes"]), 1)

    def test_status_does_not_perform_docker_writes(self):
        with patch.object(engine, "policy", return_value={
            "policy_id": "test", "service": {"image": "wizard-image"}}), \
             patch.object(engine, "load", return_value=state.empty()), \
             patch.object(engine, "image", return_value=None), \
             patch.object(engine, "legacy_observation", return_value={
                 "identity_verified": True}), \
             patch.object(engine, "command") as command, \
             patch.object(engine, "save") as save:
            report = engine.deployment_status()
        self.assertTrue(report["legacy"]["identity_verified"])
        command.assert_not_called()
        save.assert_not_called()


    def test_owned_container_stop_uses_exact_id_only(self):
        rec = state.empty()
        rec["containers"][CONTAINER] = {
            "id": LEGACY_ID, "image_id": IMG_ID, "target": TARGET, "ready": True}
        actual = fake_container(Path("/tmp/fake"))
        with patch.object(engine, "_runtime_target"), \
             patch.object(engine, "load", return_value=rec), \
             patch.object(engine, "container", return_value=actual), \
             patch.object(engine, "require_user"), \
             patch.object(engine, "command") as command, \
             patch.object(engine, "save") as save:
            result = engine.stop_or_remove(
                target=TARGET, operation="stop", dry_run=False)
        command.assert_called_once_with(["docker", "stop", LEGACY_ID])
        self.assertIn("DONE:", result)
        self.assertFalse(save.call_args.args[0]["containers"][CONTAINER]["ready"])

    def test_owned_container_removal_preserves_legacy_observation(self):
        rec = state.empty()
        rec["legacy_observation"] = {"read_only": True, "management_authority": "OBSERVE_ONLY"}
        rec["containers"][CONTAINER] = {
            "id": LEGACY_ID, "image_id": IMG_ID, "target": TARGET}
        actual = fake_container(Path("/tmp/fake"))
        with patch.object(engine, "_runtime_target"), \
             patch.object(engine, "load", return_value=rec), \
             patch.object(engine, "container", return_value=actual), \
             patch.object(engine, "require_user"), \
             patch.object(engine, "command") as command, \
             patch.object(engine, "save") as save:
            engine.stop_or_remove(target=TARGET, operation="remove", dry_run=False)
        command.assert_called_once_with(["docker", "rm", "-f", LEGACY_ID])
        saved = save.call_args.args[0]
        self.assertEqual(saved["containers"], {})
        self.assertEqual(saved["legacy_observation"]["management_authority"], "OBSERVE_ONLY")

    def test_unshared_wizard_image_removal_uses_recorded_tag(self):
        rec = state.empty()
        rec["image"] = {"tag": "wizard-image", "id": IMG_ID, "source": "wizard-build"}
        with patch.object(engine, "policy", return_value={"service": {"image": "wizard-image"}}), \
             patch.object(engine, "load", return_value=rec), \
             patch.object(engine, "image", return_value={"Id": IMG_ID}), \
             patch.object(engine, "image_in_use", return_value=False), \
             patch.object(engine, "require_user"), \
             patch.object(engine, "command") as command, \
             patch.object(engine, "save") as save:
            engine.remove_image(dry_run=False)
        command.assert_called_once_with(["docker", "image", "rm", "wizard-image"])
        self.assertIsNone(save.call_args.args[0]["image"])


if __name__ == "__main__":
    unittest.main()
