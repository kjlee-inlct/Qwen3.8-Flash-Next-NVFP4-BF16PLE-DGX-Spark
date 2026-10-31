"""P1 stock-QSA MTP2-OFF C-arm: CPU-only negative safety tests."""
import unittest
from unittest.mock import patch
from src import p1_mtp_off_numeric_isolation as c


class Tests(unittest.TestCase):
    H = "a" * 40
    O = c.PIN_ORIGINAL_ID
    C = "c" * 64

    def sample_command(self):
        return ["--no-enable-prefix-caching", "--speculative-config",
                '{"method":"mtp","num_speculative_tokens":2}',
                "--port", "8000", "--host", "0.0.0.0"]

    def test_removes_only_exact_mtp_pair(self):
        original = self.sample_command()
        with patch.object(c.b, "original_command", return_value=(original, "m")):
            reduced = c.cmd_without_mtp(original)
        self.assertEqual(reduced, [
            "--no-enable-prefix-caching", "--port", "8000",
            "--host", "0.0.0.0"])
        self.assertEqual(original[1], "--speculative-config")

    def test_mtp_flag_drift_blocks(self):
        with patch.object(c.b, "original_command", return_value=([], "m")):
            for bad in (["--no-enable-prefix-caching"],
                        ["--no-enable-prefix-caching", "--speculative-config=x"],
                        ["--no-enable-prefix-caching", "--speculative-config", "a",
                         "--speculative-config", "b"]):
                with self.assertRaises(c.Blocked):
                    c.cmd_without_mtp(bad)

    def test_template_uses_original_stock_image_only_and_mtp_off(self):
        cmd = self.sample_command()
        template = ["docker", "create", "--name", c.b.NAME,
                    "--label", c.b.LABEL+"="+self.H,
                    "--label", c.b.LABEL+".image-id="+c.b.PIN_IMAGE_ID,
                    "--publish=127.0.0.1:18080:8000",
                    c.b.PIN_TAG, *cmd]
        with patch.object(c.b, "container_args",
                          return_value=(template, "model")), \
             patch.object(c.b, "original_command", return_value=(cmd, "model")):
            args, model = c.args_for(
                self.H, {"Config": {"Cmd": cmd}}, {}, {})
        self.assertIn(c.TAG, args)
        self.assertIn(c.NAME, args)
        self.assertNotIn(c.b.PIN_TAG, args)
        self.assertNotIn("--speculative-config", args)
        self.assertIn("--no-enable-prefix-caching", args)
        self.assertEqual(model, "model")

    def test_foreign_container_refused_before_removal(self):
        with patch.object(c, "ids", return_value=[self.C]), \
             patch.object(c, "owned", side_effect=c.Blocked("FOREIGN")), \
             patch.object(c.release, "_run") as mutate:
            with self.assertRaisesRegex(c.Blocked, "FOREIGN"):
                c.guarded_cleanup(self.H, {"id": self.O})
        mutate.assert_not_called()

    def test_restore_if_original_running_skips_start(self):
        with patch.object(c, "inspect_original", return_value=(
                 {"id": self.O}, {}, {}, "running")), \
             patch.object(c, "ids", return_value=[]), \
             patch.object(c.b, "restore_original") as start, \
             patch.object(c.window, "check_original_running"):
            c.restore(self.H, "model")
        start.assert_not_called()

    def test_restore_exited_removes_owned_then_starts_original(self):
        with patch.object(c, "inspect_original", return_value=(
                 {"id": self.O}, {}, {}, "exited")), \
             patch.object(c, "ids", side_effect=[[self.C], [], []]), \
             patch.object(c, "guarded_cleanup") as cleanup, \
             patch.object(c.b, "restore_original") as start, \
             patch.object(c.window, "check_original_running"):
            c.restore(self.H, "model")
        cleanup.assert_called_once()
        start.assert_called_once_with(self.H, self.O, "model")

    def test_invalid_candidate_presence_does_not_restore_original(self):
        with patch.object(c, "inspect_original", return_value=(
                 {"id": self.O}, {}, {}, "exited")), \
             patch.object(c, "ids", return_value=[self.C]), \
             patch.object(c, "guarded_cleanup", side_effect=c.Blocked("FOREIGN")), \
             patch.object(c.b, "restore_original") as start:
            with self.assertRaisesRegex(c.Blocked, "FOREIGN"):
                c.restore(self.H, "model")
        start.assert_not_called()

    def test_strict_comparator_labels_c_not_stock_original(self):
        def vec(d):
            return {"token_ids": list(range(150)), "logprobs": [-0.2 + d]*150,
                    "finish_reason": "stop"}
        a = [vec(d) for d in (0, 0.00025, 0, 0)]
        off = [vec(d) for d in (0, 0.00002, 0, 0)]
        report = c.measurement(a, off, "p"*64, 0)
        self.assertEqual(report["A_MTP2"]["status"],
                         "ORIGINAL_PREFIX_OFF_NUMERIC_ABOVE_STRICT")
        self.assertEqual(report["C_MTP_OFF"]["status"],
                         "MTP_OFF_STOCK_PREFIX_OFF_NUMERIC_WITHIN_STRICT")
        self.assertTrue(report["C_MTP_OFF"]["numeric_reproducible_at_strict"])
        self.assertTrue(report["mtp_off_runtime_counter_zero"])
        self.assertFalse(report["p1_final_pass"])

    def test_A_incomplete_never_stops_original(self):
        bad = {"token_ids": [0], "logprobs": [-0.2], "finish_reason": "stop"}
        with patch.object(c.qsa, "preflight"), \
             patch.object(c, "inspect_original", return_value=(
                 {"id": self.O}, {"Id": self.O}, {}, "running")), \
             patch.object(c, "args_for", return_value=(["docker"], "m")), \
             patch.object(c, "no_other_candidates"), \
             patch.object(c.window, "check_original_running"), \
             patch.object(c.oracle, "build_payload", return_value={
                 "messages": [{"role": "user", "content": "test"}]}), \
             patch.object(c.window, "collect", return_value=[bad]*4), \
             patch.object(c.window, "stop_original") as stop:
            with self.assertRaisesRegex(c.Blocked, "A_INCOMPLETE"):
                c.execute(self.H)
        stop.assert_not_called()


if __name__ == "__main__":
    unittest.main()
