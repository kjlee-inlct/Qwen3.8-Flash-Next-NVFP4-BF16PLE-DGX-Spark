"""P2 Preview-only MTP reduced-vocabulary *candidate* source transform.

Source-pinned against the actual installed BF16 Preview MTP from DGX. Default
OFF. Never install in the protected original, mutate target weights, or
silently change the native MTP/rejection ABI.
"""
from __future__ import annotations

import ast
import hashlib

SOURCE_SHA256 = "d1ee05d4ec35360a9a801f7ef5271e8e4cda458a9c754058899441fa1e7bd0d6"
COMPUTE_METHOD_AST_SHA256 = "83eb59ba9f5f0271cbe2ff70e0f3f6b6e899f3eca33becafabba03f57686bc3a"
CLASS = "Qwen3_8FlashNextMTP"
ENV_NAME = "VLLM_P2_DRAFT_VOCAB"
HASH_ENV_NAME = "VLLM_P2_DRAFT_VOCAB_SHA256"
MARKER = "# -- P2 exact-pinned reduced-vocabulary MTP candidate, default OFF --"
SOURCE_FILE = "vllm/models/qwen3_8_flash_next/nvidia/mtp.py"

# No direct import of torch or numpy by this *build tool*. The transformed
# installed MTP source already imports torch. Its opt-in runtime imports numpy.
HOOK = r'''

# -- P2 exact-pinned reduced-vocabulary MTP candidate, default OFF --
import os as _p2dv_os
import hashlib as _p2dv_hashlib
import stat as _p2dv_stat

_P2_DV_PATH = _p2dv_os.environ.get("VLLM_P2_DRAFT_VOCAB", "")
_P2_DV_HASH = _p2dv_os.environ.get("VLLM_P2_DRAFT_VOCAB_SHA256", "")


def _p2dv_load_ids(path, expected_hash):
    import numpy as _p2dv_np

    if (not path or len(path) > 4096 or not expected_hash
            or len(expected_hash) != 64
            or any(c not in "0123456789abcdef" for c in expected_hash)):
        raise RuntimeError("P2_DRAFT_VOCAB_PATH_OR_HASH_REQUIRED")
    st = _p2dv_os.lstat(path)
    if (not _p2dv_stat.S_ISREG(st.st_mode)
            or st.st_size < 256 or st.st_size > 2_000_000):
        raise RuntimeError("P2_DRAFT_VOCAB_REGULAR_FILE_SIZE_REQUIRED")
    with open(path, "rb") as fd:
        payload = fd.read(2_000_001)
    if (_p2dv_hashlib.sha256(payload).hexdigest() != expected_hash):
        raise RuntimeError("P2_DRAFT_VOCAB_SHA256_MISMATCH")
    import io as _p2dv_io
    ids = _p2dv_np.load(_p2dv_io.BytesIO(payload), allow_pickle=False)
    if (ids.ndim != 1 or ids.size != 65536
            or ids.dtype not in (_p2dv_np.dtype("int32"), _p2dv_np.dtype("int64"))):
        raise RuntimeError("P2_DRAFT_VOCAB_DTYPE_OR_SIZE_INVALID")
    if (int(ids[0]) < 0 or int(ids[-1]) >= 248320
            or not _p2dv_np.all(ids[1:] > ids[:-1])
            or not _p2dv_np.array_equal(ids[:256],
                                        _p2dv_np.arange(256, dtype=ids.dtype))):
        raise RuntimeError("P2_DRAFT_VOCAB_SORT_OR_BYTE_IDS_INVALID")
    return ids.astype(_p2dv_np.int64, copy=True)


def _p2dv_compute_logits(self, hidden_states, spec_step_idx=0):
    # The target still owns the shared full-width lm_head. This candidate
    # materializes a private, unaliased BF16 slice on first MTP call only.
    st = getattr(self, "_p2dv_state", None)
    if st is None:
        if not _P2_DV_PATH:
            raise RuntimeError("P2_DRAFT_VOCAB_NOT_CONFIGURED")
        head = self.lm_head
        full_weight = getattr(head, "weight", None)
        if (not isinstance(full_weight, torch.Tensor)
                or full_weight.ndim != 2
                or full_weight.shape[0] != 248320
                or full_weight.dtype != torch.bfloat16
                or not full_weight.is_cuda
                or int(getattr(self.logits_processor, "org_vocab_size", -1)) != 248320):
            raise RuntimeError("P2_DRAFT_HEAD_ABI_UNVERIFIED")
        ids_np = _p2dv_load_ids(_P2_DV_PATH, _P2_DV_HASH)
        with torch.no_grad():
            ids = torch.from_numpy(ids_np).to(full_weight.device)
            reduced_weight = full_weight.detach().index_select(0, ids).contiguous()
        if (reduced_weight.data_ptr() == full_weight.data_ptr()
                or tuple(reduced_weight.shape) != (65536, int(full_weight.shape[1]))):
            raise RuntimeError("P2_DRAFT_HEAD_NOT_INDEPENDENT")
        st = (ids, reduced_weight)
        self._p2dv_state = st
    ids, reduced_weight = st
    if (hidden_states.ndim != 2 or hidden_states.shape[-1] != reduced_weight.shape[-1]
            or hidden_states.device != reduced_weight.device):
        raise RuntimeError("P2_DRAFT_HIDDEN_STATE_SHAPE_OR_DEVICE_DRIFT")
    with torch.no_grad():
        reduced = torch.nn.functional.linear(
            hidden_states.to(reduced_weight.dtype), reduced_weight)
        # Preserve existing full-vocabulary shape for stock proposer and
        # rejection. Out-of-subset logits are explicitly -inf, not zero.
        full = reduced.new_full((reduced.shape[0], 248320), float("-inf"))
        full.index_copy_(1, ids, reduced)
    return full


if _P2_DV_PATH:
    if not _P2_DV_HASH:
        raise RuntimeError("P2_DRAFT_VOCAB_SHA256_REQUIRED")
    Qwen3_8FlashNextMTP.compute_logits = _p2dv_compute_logits
'''


class Blocked(RuntimeError):
    pass


def transform(raw: bytes, *, expected_sha: str = SOURCE_SHA256,
              method_sha: str = COMPUTE_METHOD_AST_SHA256) -> bytes:
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise Blocked("PINNED_MTP_SOURCE_SHA_DRIFT")
    try:
        text = raw.decode("utf-8")
        tree = ast.parse(text)
    except (SyntaxError, UnicodeError):
        raise Blocked("MTP_SOURCE_INVALID") from None
    if MARKER in text:
        raise Blocked("MTP_ALREADY_PATCHED")
    classes = [x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == CLASS]
    if len(classes) != 1:
        raise Blocked("PINNED_MTP_CLASS_DRIFT")
    methods = [x for x in classes[0].body
               if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))
               and x.name == "compute_logits"]
    if len(methods) != 1:
        raise Blocked("PINNED_MTP_COMPUTE_METHOD_DRIFT")
    digest = hashlib.sha256(ast.dump(methods[0], include_attributes=False).encode()).hexdigest()
    if digest != method_sha:
        raise Blocked("PINNED_MTP_COMPUTE_AST_DRIFT")
    # Ensure installed symbols this hook will reference are in the pinned
    # compute method, but do not infer target-sharing from name matches.
    if not any(isinstance(x, ast.Attribute) and x.attr == "lm_head"
               for x in ast.walk(methods[0])):
        raise Blocked("PINNED_MTP_HEAD_ANCHOR_MISSING")
    if not any(isinstance(x, ast.Attribute) and x.attr == "logits_processor"
               for x in ast.walk(methods[0])):
        raise Blocked("PINNED_MTP_LOGITS_ANCHOR_MISSING")
    output = text.rstrip("\n") + "\n\n" + HOOK
    try:
        ast.parse(output)
    except SyntaxError:
        raise Blocked("PATCHED_MTP_INVALID") from None
    if output.count(MARKER) != 1:
        raise Blocked("MTP_MARKER_COUNT_INVALID")
    return output.encode("utf-8")


def candidate_receipt() -> dict:
    return {
        "status": "P2_PINNED_MTP_REDUCED_DRAFT_SOURCE_IMPLEMENTED_NOT_RUNTIME_TESTED",
        "installed_mtp_source_sha256": SOURCE_SHA256,
        "installed_compute_method_ast_sha256": COMPUTE_METHOD_AST_SHA256,
        "runtime_opt_in": ENV_NAME,
        "required_mapping_hash_env": HASH_ENV_NAME,
        "full_vocab_output": 248320,
        "draft_weight_rows": 65536,
        "out_of_subset_fill": "-inf",
        "original_target_head_mutated": False,
        "native_proposer_or_acceptance_code_modified": False,
        "candidate_gpu_or_api_executed": False,
    }
