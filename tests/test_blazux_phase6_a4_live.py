"""No-inference public /metrics contract: partial live evidence never P6-A PASS."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "phase6_a4_live_observer", ROOT / "src/phase6_a4_live_observer.py"
)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class A4ActualExposureTests(unittest.TestCase):
    def test_valid_prometheus_cache_metric(self):
        raw = ('# HELP vllm:cache_config_info Information\n'
               'vllm:cache_config_info{block_size="16",cache_dtype="auto",'
               'enable_prefix_caching="False",gpu_memory_utilization="0.8",'
               'cpu_offload_gb="0"} 1.0\n')
        got = mod.parse_cache_metric(raw)
        self.assertEqual(got["status"], "ACTIVE_METRIC_EXPOSED")
        self.assertEqual(got["cache_config"]["block_size"], 16)
        self.assertFalse(got["cache_config"]["enable_prefix_caching"])
        self.assertEqual(got["cache_config"]["gpu_memory_utilization"], 0.8)

    def test_no_cache_metric_not_observed(self):
        self.assertEqual(mod.parse_cache_metric("vllm:num_requests_running 0\n")["status"],
                         "NOT_EXPOSED")

    def test_bad_label_never_echoes_secrets(self):
        got = mod.parse_cache_metric(
            'vllm:cache_config_info{api_key="SECRET",block_size="0"} 1\n')
        self.assertEqual(got["status"], "INCONSISTENT_OR_UNPARSEABLE")
        self.assertNotIn("SECRET", str(got))

    def test_duplicate_conflicting_engine_blocked(self):
        raw = ('vllm:cache_config_info{block_size="16"} 1\n'
               'vllm:cache_config_info{block_size="32"} 1\n')
        self.assertEqual(mod.parse_cache_metric(raw)["status"], "AMBIGUOUS_MULTI_ENGINE")

    def test_nonnumeric_cannot_be_declared(self):
        self.assertEqual(mod.parse_cache_metric(
            'vllm:cache_config_info{block_size="abc"} 1\n')["status"],
            "INCONSISTENT_OR_UNPARSEABLE")

    def test_models_exact_served_id(self):
        doc = '{"data":[{"id":"qwen3.8-flash-next-orca-uncensored-bf16-mtp"}]}'
        self.assertEqual(mod.parse_models(doc)["status"], "MATCHED_PINNED_SERVED_ID")

    def test_models_missing_and_wrong_id_blocked(self):
        self.assertEqual(mod.parse_models('{}')["status"], "BLOCKED")
        self.assertEqual(mod.parse_models('{"data":[{"id":"other"}]}')["status"], "BLOCKED")

    def test_identity_drift_blocked_no_success(self):
        with patch.object(mod, "_docker_state", side_effect=[
            (True, ("x", mod.PINNED_IMAGE, "time1")),
            (True, ("x", mod.PINNED_IMAGE, "time2")),
        ]), patch.object(mod, "_read_http", return_value=None):
            got = mod.observe()
        self.assertEqual(got["status"], "BLOCKED")

    def test_metrics_missing_still_active_gate_blocked(self):
        doc = '{"data":[{"id":"qwen3.8-flash-next-orca-uncensored-bf16-mtp"}]}'
        with patch.object(mod, "_docker_state", return_value=(
            True, ("x", mod.PINNED_IMAGE, "t")
        )), patch.object(mod, "_read_http", side_effect=[doc, None]):
            got = mod.observe()
        self.assertEqual(got["p6_a_runtime_status"], "BLOCKED")
        self.assertEqual(got["status"], "ABI_METRICS_NOT_USABLE")

    def test_metric_present_still_cannot_certify_group_pointers(self):
        doc = '{"data":[{"id":"qwen3.8-flash-next-orca-uncensored-bf16-mtp"}]}'
        metric = 'vllm:cache_config_info{block_size="16"} 1.0\n'
        with patch.object(mod, "_docker_state", return_value=(
            True, ("x", mod.PINNED_IMAGE, "t")
        )), patch.object(mod, "_read_http", side_effect=[doc, metric]):
            got = mod.observe()
        self.assertEqual(got["status"], "PARTIAL_EXPOSED_RUNTIME_CACHE_METADATA")
        self.assertEqual(got["p6_a_runtime_status"], "BLOCKED")
        self.assertEqual(got["actual_gpu_tensor_ptr_shape_stride_allocations"],
                         "NOT_OBSERVED")

    def test_only_fixed_loopback_endpoints(self):
        self.assertEqual(mod._read_http("https://example.org/private"), None)

    def test_shell_source_only_no_live_mutation(self):
        shell = (ROOT / "scripts/phase6-a-live-observe.sh").read_text()
        for snippet in ("docker run", "docker exec", "docker stop", "docker restart",
                        "llama-benchy", "curl -X POST", "--gpus"):
            for line in shell.splitlines():
                if not line.strip().startswith("#"):
                    self.assertNotIn(snippet, line)


if __name__ == "__main__":
    unittest.main()
