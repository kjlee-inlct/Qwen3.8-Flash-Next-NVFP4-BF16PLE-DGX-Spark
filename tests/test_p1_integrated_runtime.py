"""P1 integrated runtime: offline guards. These tests never use Docker/GPU."""
import unittest
from unittest.mock import patch

from src import p1_integrated_runtime as r


class Tests(unittest.TestCase):
    HEAD = "a" * 40
    ORIGINAL = "b" * 64

    def test_image_pin_and_loopback(self):
        self.assertEqual(r.PIN_TAG, "kjlee-qwen38-p1-integrated:bf80867dc5be")
        self.assertEqual(r.PORT, 18080)
        self.assertRegex(r.PIN_IMAGE_ID, r"^sha256:[a-f0-9]{64}$")

    def test_original_running_blocks_launch_no_mutations(self):
        with patch.object(r.release, "_legacy_state_for_release",
                          return_value=({"id": self.ORIGINAL}, {}, {}, "running")), \
             patch.object(r.release, "_run") as mutate:
            with self.assertRaisesRegex(r.qsa.Blocked, "ALREADY_BE_EXITED"):
                r.launch(self.HEAD, self.ORIGINAL)
            mutate.assert_not_called()

    def test_wrong_original_id_blocks_launch(self):
        with patch.object(r.release, "_legacy_state_for_release",
                          return_value=({"id": self.ORIGINAL}, {}, {}, "exited")), \
             patch.object(r.release, "_run") as mutate:
            with self.assertRaisesRegex(r.qsa.Blocked, "CONFIRM_ID_MISMATCH"):
                r.launch(self.HEAD, "c" * 64)
            mutate.assert_not_called()

    def test_restoring_wrong_original_id_never_cleans_up_candidate(self):
        with patch.object(r.release, "_legacy_state_for_release",
                          return_value=({"id": self.ORIGINAL}, {}, {}, "exited")), \
             patch.object(r, "cleanup") as cleanup:
            with self.assertRaisesRegex(r.qsa.Blocked, "RECEIPT_OR_STATE_DRIFT"):
                r.restore(self.HEAD, "c" * 64, "d" * 64)
            cleanup.assert_not_called()

    def test_owned_candidate_identity(self):
        ci = {"Name": "/" + r.NAME, "Image": r.PIN_IMAGE_ID,
              "Config": {"Labels": {r.LABEL: self.HEAD}},
              "HostConfig": {"RestartPolicy": {"Name": "no"}}}
        with patch.object(r.legacy, "inspect", return_value=ci):
            self.assertEqual(r.owned(self.HEAD), ci)
            with self.assertRaisesRegex(r.qsa.Blocked, "OWNERSHIP_MISMATCH"):
                r.owned("c" * 40)

    def test_wrong_candidate_id_never_removed(self):
        with patch.object(r, "owned", return_value={
                "Id": "c" * 64, "State": {"Status": "running"}}), \
             patch.object(r.release, "_run") as mutate:
            with self.assertRaisesRegex(r.qsa.Blocked, "CONFIRM_ID_MISMATCH"):
                r.cleanup(self.HEAD, "d" * 64)
            mutate.assert_not_called()

    def test_preflight_is_readonly(self):
        with patch.object(r.release, "_legacy_state_for_release",
                          return_value=({"id": self.ORIGINAL},
                                        {"Id": self.ORIGINAL}, {}, "running")), \
             patch.object(r, "verify_image"), \
             patch.object(r, "no_other_candidates"), \
             patch.object(r, "container_args",
                          return_value=(["docker", "create", r.PIN_TAG], "model")), \
             patch.object(r.release, "_run") as mutate:
            out = r.preflight(self.HEAD)
            self.assertFalse(out["mutated"])
            mutate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
