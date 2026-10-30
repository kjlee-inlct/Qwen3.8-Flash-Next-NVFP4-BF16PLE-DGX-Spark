"""P1 operational release: exact two-file image and same-ID safety properties."""
import unittest
from pathlib import Path
from unittest.mock import patch

from src import p1_prefix_release as release


class Tests(unittest.TestCase):
    HEAD = "a" * 40
    BASE = {"Id": release.gpu.IMAGE,
            "RootFS": {"Layers": ["sha256:" + "b" * 64,
                                 "sha256:" + "c" * 64]}}
    ROOT = "/usr/local/lib/python3.12/site-packages/vllm"

    def image(self, *, layers=None, labels=None):
        return {
            "Id": "sha256:" + "d" * 64,
            "RootFS": {"Layers": layers or [
                *self.BASE["RootFS"]["Layers"],
                "sha256:" + "e" * 64, "sha256:" + "f" * 64]},
            "Config": {"Labels": (
                release._labels(self.HEAD, self.ROOT)
                if labels is None else labels)},
        }

    def test_release_source_contains_exact_two_copy_no_run_or_observer(self):
        dockerfile = release.dockerfile_for(self.ROOT)
        self.assertEqual(dockerfile.count("\nCOPY "), 2)
        self.assertIn("FROM " + release.RELEASE_BASE, dockerfile)
        self.assertIn("mamba_hybrid.py", dockerfile)
        self.assertIn("scheduler.py", dockerfile)
        self.assertNotIn("\nRUN ", dockerfile)
        self.assertNotIn("_p1_prefix_state_snapshot", dockerfile)
        self.assertNotIn("_p1_prefix_live_observer", dockerfile)
        self.assertNotIn("http", dockerfile)
        self.assertIn("--chmod=0644", dockerfile)

    def test_root_and_head_must_be_exact_safe_identifiers(self):
        self.assertEqual(release.release_tag(self.HEAD),
                         "kjlee-qwen38-p1-prefix:" + self.HEAD[:12])
        for invalid in ("", "abc", "G" * 40, "../vllm"):
            with self.assertRaises(release.ReleaseBlocked):
                release.release_tag(invalid)
        for invalid in ("../../vllm", "/tmp/vllm;touch", "/vllm",
                        "/root/.vllm", "/tmp/foo/vllm/../../evil"):
            with self.assertRaises(release.ReleaseBlocked):
                release.dockerfile_for(invalid)

    def test_parent_layer_provenance_accepts_only_exact_base_plus_two_copy(self):
        with patch.object(release, "_inspect_image", return_value=self.BASE):
            info = release.check_image(self.image(), self.HEAD)
            self.assertEqual(info["image_id"], "sha256:" + "d" * 64)
            with self.assertRaisesRegex(
                    release.ReleaseBlocked, "PARENT_LAYERS_DRIFT"):
                release.check_image(self.image(layers=[
                    *self.BASE["RootFS"]["Layers"],
                    "sha256:" + "e" * 64]), self.HEAD)
            with self.assertRaisesRegex(
                    release.ReleaseBlocked, "PARENT_LAYERS_DRIFT"):
                release.check_image(self.image(layers=[
                    "sha256:" + "a" * 64,
                    *self.BASE["RootFS"]["Layers"],
                    "sha256:" + "e" * 64]), self.HEAD)

    def test_forged_or_missing_label_cannot_be_launched(self):
        forged = self.image(labels={
            **release._labels(self.HEAD, self.ROOT),
            release.RELEASE_LABEL: "f" * 40})
        with patch.object(release, "_inspect_image", return_value=self.BASE):
            with self.assertRaisesRegex(
                    release.ReleaseBlocked, "PROVENANCE_MISMATCH"):
                release.check_image(forged, self.HEAD)

    def test_original_running_blocks_release_launch_before_docker_mutation(self):
        receipt = {"id": "a" * 64}
        ci = {"Config": {}}
        base = {"Config": {}}
        with patch.object(release, "_legacy_state_for_release",
                          return_value=(receipt, ci, base, "running")), \
             patch.object(release, "_run") as docker:
            with self.assertRaisesRegex(
                    release.ReleaseBlocked, "MUST_ALREADY_BE_STOPPED"):
                release.launch(self.HEAD, receipt["id"])
            docker.assert_not_called()

    def test_wrong_original_id_blocks_launch_before_docker_mutation(self):
        receipt = {"id": "a" * 64}
        with patch.object(release, "_legacy_state_for_release",
                          return_value=(receipt, {}, {}, "exited")), \
             patch.object(release, "_run") as docker:
            with self.assertRaisesRegex(
                    release.ReleaseBlocked, "CONFIRMATION_MISMATCH"):
                release.launch(self.HEAD, "b" * 64)
            docker.assert_not_called()

    def test_stop_wrong_original_receipt_does_not_remove_release(self):
        with patch.object(release, "_legacy_state_for_release",
                          return_value=({"id": "a" * 64}, {}, {}, "exited")), \
             patch.object(release, "cleanup_release") as cleanup:
            with self.assertRaisesRegex(
                    release.ReleaseBlocked, "RECEIPT_OR_STATE_DRIFT"):
                release.stop_and_restore(self.HEAD, "b" * 64, "c" * 64)
            cleanup.assert_not_called()

    def test_release_container_ownership_verifies_image_and_full_head(self):
        ci = {
            "Name": "/" + release.RELEASE_NAME, "Image": "sha256:" + "a" * 64,
            "Config": {"Labels": {release.RELEASE_LABEL: self.HEAD}},
            "HostConfig": {"RestartPolicy": {"Name": "no"}},
        }
        with patch.object(release.legacy, "inspect", return_value=ci):
            owned = release._owner_inspect(self.HEAD, "sha256:" + "a" * 64)
            self.assertEqual(owned["Image"], "sha256:" + "a" * 64)
            with self.assertRaisesRegex(
                    release.ReleaseBlocked, "OWNERSHIP_MISMATCH"):
                release._owner_inspect(self.HEAD, "sha256:" + "b" * 64)

    def test_shell_wrapper_has_source_manifest_and_no_implicit_stop(self):
        shell = (Path(__file__).resolve().parents[1] /
                 "scripts/p1-prefix-release.sh").read_text()
        self.assertIn("verify-source-state.py", shell)
        self.assertIn("HEAD_MISMATCH", shell)
        self.assertIn("--confirm-original-id", shell)
        self.assertIn("--confirm-release-id", shell)
        self.assertNotIn("docker stop ", shell)
        self.assertNotIn("docker rm -f", shell)


if __name__ == "__main__":
    unittest.main()
