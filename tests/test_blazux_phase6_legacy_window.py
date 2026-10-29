"""CPU-only tests; never invoke Docker."""
import unittest
import json
import subprocess
import tempfile
from pathlib import Path
from src import p1_legacy_service_window as w


def valid():
    cache = "/home/test/Workspace/llm/yslab-qwen38-bf16ple-dgx-spark/hf-cache"
    views = "/home/test/Workspace/llm/yslab-qwen38-bf16ple-dgx-spark/recipe-views"
    r = {"id": "a" * 64, "cache": cache, "views": views}
    c = {"Id": r["id"], "Name": "/" + w.NAME, "Image": w.IMAGE_ID,
         "Config": {"Image": w.IMAGE_TAG, "Labels": {
             "ai.yslab.recipe": w.RECIPE, "ai.yslab.target": w.TARGET}},
         "HostConfig": {"RestartPolicy": {"Name": "no"},
                        "PortBindings": {"8000/tcp": [
                            {"HostIp": "0.0.0.0", "HostPort": "8000"}]}},
         "Mounts": [
             {"Type": "bind", "Source": cache, "Destination": "/recipe/hf-cache"},
             {"Type": "bind", "Source": views, "Destination": "/recipe/recipe-views"}],
         "State": {"Status": "running", "Running": True}}
    return c, {"Id": w.IMAGE_ID}, r


class LegacyWindowTests(unittest.TestCase):
    def test_manifest_drives_original_service_identity(self):
        data = json.loads(w.POLICY_PATH.read_text())
        legacy = data["legacy"]
        self.assertEqual(w.NAME, legacy["container"])
        self.assertEqual(w.IMAGE_TAG, legacy["image"])
        self.assertEqual(w.IMAGE_ID, legacy["image_id"])
        self.assertEqual(w.RECIPE, legacy["legacy_recipe_label"])
        self.assertEqual(w.TARGET, legacy["target"])
        self.assertEqual(w.LEGACY["port"], 8000)
        self.assertEqual(w.LEGACY["bind"], "0.0.0.0")

    def test_invalid_policy_and_path_rejected(self):
        data = json.loads(w.POLICY_PATH.read_text())
        bad = json.loads(json.dumps(data))
        bad["legacy"]["image_id"] = "sha256:INVALID"
        with self.assertRaisesRegex(w.Blocked, "POLICY_IMAGE_OR_PATH_INVALID"):
            w.policy_legacy(bad)
        bad = json.loads(json.dumps(data))
        bad["legacy"]["state_relative"] = "../different"
        with self.assertRaisesRegex(w.Blocked, "POLICY_IMAGE_OR_PATH_INVALID"):
            w.policy_legacy(bad)
        bad = json.loads(json.dumps(data))
        bad["legacy"]["port"] = "8000"
        with self.assertRaisesRegex(w.Blocked, "POLICY_PORT_INVALID"):
            w.policy_legacy(bad)

    def test_running_and_exited_exact_id(self):
        c, i, r = valid()
        self.assertTrue(w.verify_identity(c, i, r))
        c["State"] = {"Status": "exited", "Running": False}
        self.assertFalse(w.verify_identity(c, i, r))

    def test_id_image_label_mount_port_and_policy_fail_closed(self):
        edits = [
            lambda c, i, r: r.update(id="b" * 64),
            lambda c, i, r: i.update(Id="sha256:bad"),
            lambda c, i, r: c["Config"]["Labels"].update({"ai.yslab.target": "wrong"}),
            lambda c, i, r: c.update(Mounts=[]),
            lambda c, i, r: c["HostConfig"].update(PortBindings={}),
            lambda c, i, r: c["HostConfig"].update(RestartPolicy={"Name": "always"}),
            lambda c, i, r: c.update(Name="/other"),
            lambda c, i, r: c.update(State={"Status": "restarting", "Running": True}),
        ]
        for edit in edits:
            c, i, r = valid()
            edit(c, i, r)
            with self.assertRaises(w.Blocked):
                w.verify_identity(c, i, r)

    def test_entry_requires_explicit_mutation_authority(self):
        self.assertEqual(w.run(["--action", "stop"]), 2)
        self.assertEqual(w.run(["--action", "start"]), 2)
        self.assertEqual(w.run(["--action", "preflight", "--execute"]), 2)

    def test_no_container_removal_or_image_changes(self):
        source = Path(w.__file__).read_text()
        self.assertNotIn('"docker", "rm"', source)
        self.assertNotIn('"docker", "exec"', source)
        self.assertNotIn('"docker", "run"', source)
        self.assertIn('"docker", "stop", "--time", "30"', source)
        self.assertIn('"docker", "start", receipt["id"]', source)


class LegacyBashEntrypointDispatchTests(unittest.TestCase):
    """Run real stop/start scripts with fake delegates; never invoke Docker."""

    def _fake_run(self, script, arguments):
        scripts = Path(__file__).resolve().parents[1] / "scripts"
        with tempfile.TemporaryDirectory(prefix="p1-stub-") as tmp:
            root = Path(tmp)
            for name in ("stop.sh", "start.sh"):
                (root / name).write_bytes((scripts / name).read_bytes())
            for name in ("p1-legacy-service-window.sh", "uninstall.sh"):
                stub = root / name
                stub.write_text("""#!/usr/bin/env bash
printf 'FAKE_TARGET=%s\\n' "$(basename "$0")"
printf 'FAKE_ARG=%s\\n' "$@"
""")
                stub.chmod(0o755)
            return subprocess.run(["bash", str(root / script), *arguments],
                                  text=True, capture_output=True,
                                  check=False, timeout=10)

    def test_stop_routes_to_legacy_only(self):
        result = self._fake_run("stop.sh", [
            "--expected-head", "a" * 40,
            "--confirm-id", "b" * 64, "--execute"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("FAKE_TARGET=p1-legacy-service-window.sh", result.stdout)
        self.assertIn("FAKE_ARG=--stop", result.stdout)
        self.assertNotIn("FAKE_ARG=--stop-only", result.stdout)

    def test_start_routes_to_same_legacy_controller(self):
        result = self._fake_run("start.sh", [
            "--expected-head", "a" * 40,
            "--confirm-id", "b" * 64, "--execute"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("FAKE_TARGET=p1-legacy-service-window.sh", result.stdout)
        self.assertIn("FAKE_ARG=--start", result.stdout)

    def test_preflight_is_legacy_and_readonly(self):
        for script in ("stop.sh", "start.sh"):
            with self.subTest(script=script):
                result = self._fake_run(script, [
                    "--preflight", "--expected-head", "a" * 40])
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("FAKE_ARG=--preflight", result.stdout)
                self.assertIn("FAKE_TARGET=p1-legacy-service-window.sh",
                              result.stdout)

    def test_wizard_requires_explicit_mode(self):
        result = self._fake_run("stop.sh", ["--wizard", "--yes"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("FAKE_TARGET=uninstall.sh", result.stdout)
        self.assertIn("FAKE_ARG=--stop-only", result.stdout)

    def test_bare_yes_and_missing_arguments_do_nothing(self):
        for script, args in (("stop.sh", []), ("stop.sh", ["--yes"]),
                             ("stop.sh", ["--wizard"]),
                             ("start.sh", []), ("start.sh", ["--wizard"])):
            with self.subTest(script=script, args=args):
                result = self._fake_run(script, args)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("FAKE_TARGET=", result.stdout)


if __name__ == "__main__":
    unittest.main()
