"""CPU-only safety and actual Mamba context ABI-shape tests."""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from src import p1_prefix_mamba_utils_probe as probe


def fixture(*, has_copy=True):
    copy = ("        precopy_mamba_align_fused_kernel[grid](num_reqs)\n"
            if has_copy else "        self.some_other_func()\n")
    return ("class MambaSpecDecodeGPUContext:\n"
            "    def initialize_from_forward_context(self, kv_cache_config, forward_context, copy_funcs, block_tables):\n"
            "        self.state_base_addrs = forward_context\n"
            "    def _populate_metadata(self, kv_cache_config, forward_context, copy_funcs, block_tables):\n"
            "        self.state_block_strides = forward_context\n"
            "    def run_fused_precopy(self, num_reqs, state_idx_gpu, src_col_gpu, token_bias_gpu, idx_mapping):\n"
            "        grid = (num_reqs,)\n" + copy +
            "    def run_fused_postprocess_align(self, num_reqs, accepted, state_idx, new_tokens, idx_mapping):\n"
            "        grid = (num_reqs,)\n"
            "        postprocess_mamba_fused_kernel[grid](num_reqs)\n"
            "def _copy_mamba_state_block(src_col, dst_col):\n"
            "    return src_col + dst_col\n"
            "def precopy_mamba_align_fused_kernel(num_reqs):\n"
            "    return num_reqs\n"
            "def postprocess_mamba_fused_kernel(num_reqs):\n"
            "    return num_reqs\n").encode("utf8")


class Tests(unittest.TestCase):
    def test_exact_image_digest_required_and_cpu_sandbox_no_mount_or_gpu(self):
        args = probe.cpu_probe_argv(
            'sha256:' + 'a'*64, '1234:5678',
            '/usr/local/lib/python3.12/dist-packages/vllm/v1/worker/mamba_utils.py')
        for flag in ('--rm','--pull=never','--network=none','--read-only',
                     '--cap-drop=ALL','--security-opt=no-new-privileges',
                     'NVIDIA_VISIBLE_DEVICES=void','CUDA_VISIBLE_DEVICES=-1'):
            self.assertIn(flag,args)
        self.assertNotIn('--gpus', args)
        self.assertNotIn('-v', args)
        self.assertEqual(args[args.index('--user')+1], '1234:5678')
        with self.assertRaisesRegex(probe.SourceBlocked,'IMAGE_ID_INVALID'):
            probe.cpu_probe_argv('latest','','/vllm/v1/worker/mamba_utils.py')
        with self.assertRaisesRegex(probe.SourceBlocked,'SOURCE_PATH_INVALID'):
            probe.cpu_probe_argv('sha256:'+'b'*64,'','/tmp/mamba_utils.py')

    def test_source_inventory_symbol_and_triton_subscript(self):
        report = probe.inspect_source(fixture())
        self.assertFalse(report['source_runtime_state_reuse_verified'])
        self.assertFalse(report['gpu_model_loaded'])
        self.assertEqual(len(report['methods']),4)
        self.assertEqual(len(report['kernels']),3)
        self.assertEqual(report['installed_source_sha256'],hashlib.sha256(fixture()).hexdigest())
        self.assertIn('precopy_mamba_align_fused_kernel[grid]',
                      report['methods']['run_fused_precopy']['calls'])
        self.assertIn('postprocess_mamba_fused_kernel[grid]',
                      report['methods']['run_fused_postprocess_align']['calls'])

    def test_fail_closed_on_missing_or_diverted_gpu_kernel(self):
        with self.assertRaisesRegex(probe.SourceBlocked,'FUSED_KERNEL_CALL_SITES_DRIFT'):
            probe.inspect_source(fixture(has_copy=False))
        with self.assertRaisesRegex(probe.SourceBlocked,'MAMBA_GPU_CONTEXT_CLASS_DRIFT'):
            probe.inspect_source(b'class SomethingElse: pass\n')
        with self.assertRaisesRegex(probe.SourceBlocked,'MAMBA_GPU_SYMBOL_DRIFT'):
            probe.inspect_source(fixture().replace(b'def _populate_metadata',b'def missing_here'))
        with self.assertRaisesRegex(probe.SourceBlocked,'SOURCE_UNPARSEABLE'):
            probe.inspect_source(b'class Invalid(\n')

    def test_full_source_export_matches_sha_and_rejects_tamper(self):
        data=fixture()
        msg=json.dumps({'sha256':hashlib.sha256(data).hexdigest(),
                        'source_base64':base64.b64encode(data).decode()})
        self.assertEqual(probe.source_from_export(msg),data)
        bad=json.dumps({'sha256':'0'*64,'source_base64':base64.b64encode(data).decode()})
        with self.assertRaisesRegex(probe.SourceBlocked,'SOURCE_EXPORT_SHA_OR_SIZE_INVALID'):
            probe.source_from_export(bad)
        with self.assertRaisesRegex(probe.SourceBlocked,'SOURCE_EXPORT_SHA_OR_SIZE_INVALID'):
            probe.source_from_export('{"source_base64":"?","sha256":"a"}')

    def test_direct_script_invocation_imports_project_package_without_docker(self):
        script = Path(probe.__file__).resolve()
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ)
            env["PATH"] = tmp  # No access to docker/git.
            env["PYTHONPATH"] = ""
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            done = subprocess.run(
                [sys.executable, str(script), "--inspect-image"],
                cwd=tmp, env=env, capture_output=True, text=True,
                timeout=20, check=False)
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertNotIn("ModuleNotFoundError", done.stderr)
        self.assertNotIn("Traceback", done.stderr)
        self.assertIn("BLOCKED_NO_GPU", done.stdout)

    def test_window_preflight_exception_fails_closed_without_traceback(self):
        from src import p1_prefix_gpu_window as window
        with patch.object(window, "preflight",
                          side_effect=window.Blocked("SUBPROCESS_FAILED_GIT")):
            with self.assertRaisesRegex(
                    probe.SourceBlocked, "PINNED_IMAGE_CPU_PREFLIGHT_OR_PROBE_BLOCKED"):
                probe.inspect_installed_image()

    def test_actual_image_probe_is_mocked_not_executed(self):
        fake_original={'Config':{'User':'1000:1000'}}
        src=fixture()
        output=json.dumps({'sha256':hashlib.sha256(src).hexdigest(),
                           'source_base64':base64.b64encode(src).decode()})
        with patch('src.p1_prefix_gpu_window.preflight',return_value=(None,fake_original,None,None,None,None)), \
             patch('src.p1_prefix_gpu_window.probe_vllm_root',return_value='/opt/vllm'), \
             patch('src.p1_prefix_gpu_window.checked',return_value=output) as run:
            report=probe.inspect_installed_image()
        args=run.call_args.args[0]
        self.assertIn('--network=none',args)
        self.assertIn('--read-only',args)
        self.assertIn('--runtime=runc',args)
        self.assertFalse(report['source_runtime_state_reuse_verified'])
        self.assertEqual(report['source_path_relative'],probe.TARGET)


if __name__=='__main__':
    unittest.main()
