"""CPU-only tests; never invoke Docker."""
import unittest
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


if __name__ == "__main__":
    unittest.main()
