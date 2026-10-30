"""P1 candidate-only bounded GDN/PLE state-content snapshot diagnostic.

This file is copied ONLY into the stopped, isolated P1 GPU candidate. Not
installed into the legacy service or pinned Stage. It collects SHA256 of
selected *natural tensor bytes*, never tensors, prompts, data pointers,
weights, or request identifiers. Snapshots are expensive and synchronize
CUDA; never enable in production. No result here certifies Prefix HIT reuse.
"""
from __future__ import annotations

import functools
import hashlib
import json
import os

PREFIX = "P1_PREFIX_STATE_SNAPSHOT_JSON:"
DIAG_PREFIX = "P1_PREFIX_STATE_PROBE_DIAG_JSON:"
# Per active request epoch, not per model lifetime. Cold prefill alone used
# the old global 8-event budget before any HIT request was observed.
MAX_EVENTS_PER_PHASE = 2
MAX_REQUEST_EPOCHS = 65535  # ordinal safety bound, NOT a sampling budget
MAX_TOTAL_EVENTS = 40
MAX_DIAGNOSTICS = 16
MAX_STATE_BYTES = 32 * 1024 * 1024
MAX_STATES_PER_EVENT = 4
# Actual last GPU run observed prefix-hit blocks equal to 6400 tokens.
TARGET_PREFIX_TOKENS = 6400
MAX_GROUPS = 8
MAX_LAYERS_PER_GROUP = 64
_seen = {}
_contexts = {}
_request_epochs = {}
_diagnostics = {}


def _int(value, *, minimum=0, maximum=10_000_000):
    if type(value) is not int or not minimum <= value <= maximum:
        return None
    return value


def _scalar(tensor):
    """Bounded one-element GPU read. Call only from this isolated candidate."""
    try:
        value = tensor.item()
        return _int(value)
    except (AttributeError, ValueError, RuntimeError, TypeError, IndexError):
        return None


def _boundary(num_computed, block_size):
    """Only instrument actual complete Mamba boundaries, not arbitrary slots."""
    n = _int(num_computed)
    b = _int(block_size, minimum=1)
    if n is None or b is None or n == 0 or n % b != 0:
        return None
    return n // b - 1


def _target_column(computed_tokens, mamba_block_size):
    """Read the completed 6400-token cache boundary in long cold/hit runs.

    Do not require the request itself to end exactly at the boundary:
    a 9503-token cold prefill may contain a completed cached 6400-token
    block while num_computed_tokens is already 9503. Unknown or smaller
    prefixes are INCONCLUSIVE, not misclassified as reusable.
    """
    n = _int(computed_tokens)
    b = _int(mamba_block_size, minimum=1)
    if (n is None or b is None or TARGET_PREFIX_TOKENS % b != 0
            or n < TARGET_PREFIX_TOKENS):
        return None
    return TARGET_PREFIX_TOKENS // b - 1


def _sample(instance, *, phase, mapping, computed, tables, kv_config):
    """Read first valid batch row and bounded natural GPU state tensors.

    P1 events are linked by physical ID, group, layer digest, boundary count,
    and invocation ordinal. The HTTP caller association is still unknown.
    """
    result = {"status": "INCONCLUSIVE_NO_VALID_BOUNDARY",
              "content_reuse_verified": False, "samples": []}
    try:
        ctx = instance._mamba_ctx
        if ctx is None or not ctx.is_initialized:
            result["status"] = "INCONCLUSIVE_CONTEXT_UNINITIALIZED"
            return result
        _, spec = instance._get_mamba_group_info(kv_config)
        block_size = _int(spec.block_size, minimum=1)
        if block_size is None:
            result["status"] = "INCONCLUSIVE_MAMBA_BLOCK_SIZE"
            return result
        if mapping is None or len(mapping.shape) != 1:
            result["status"] = "INCONCLUSIVE_BATCH_MAPPING"
            return result
        if not isinstance(tables, (tuple, list)) or len(tables) > MAX_GROUPS:
            result["status"] = "INCONCLUSIVE_BLOCK_TABLES"
            return result
        if len(mapping) < 1:
            return result
        batch_row = 0
        slot = _scalar(mapping[batch_row])
        if slot is None:
            result["status"] = "INCONCLUSIVE_REQUEST_SLOT"
            return result
        if slot >= len(computed):
            result["status"] = "INCONCLUSIVE_COMPUTED_BOUNDS"
            return result
        n = _scalar(computed[slot])
        col = _target_column(n, block_size)
        if col is None:
            return result
        group_ids = instance._get_mamba_group_info(kv_config)[0]
        if not isinstance(group_ids, (tuple, list)) or len(group_ids) > MAX_GROUPS:
            return result
        forward_context = instance.vllm_config.compilation_config.static_forward_context
        copy_funcs_map = instance._mamba_state_copy_funcs
        if not isinstance(forward_context, dict) or copy_funcs_map is None:
            return result
        from vllm.v1.worker.mamba_utils import _get_mamba_spec_for_layer
        import torch

        # Wait for any previous async kernels (pre/postprocess, graph replay).
        # This intentionally alters candidate timing, not the legacy service.
        if torch.cuda.is_available():
            torch.cuda.synchronize()

        for gid in group_ids:
            if (type(gid) is not int or not 0 <= gid < len(tables)
                    or gid >= len(kv_config.kv_cache_groups)):
                continue
            table = tables[gid]
            if (table.dim() != 2 or batch_row >= table.shape[0]
                    or col >= table.shape[1]):
                continue
            physical = _scalar(table[batch_row, col])
            if physical is None:
                continue
            group = kv_config.kv_cache_groups[gid]
            layers = group.layer_names
            if not isinstance(layers, (tuple, list)) or len(layers) > MAX_LAYERS_PER_GROUP:
                continue
            for layer_name in layers:
                if not isinstance(layer_name, str) or layer_name not in forward_context:
                    continue
                spec_for_layer = _get_mamba_spec_for_layer(group, layer_name)
                func_set = copy_funcs_map.get(spec_for_layer.mamba_type)
                if not isinstance(func_set, (tuple, list)):
                    continue
                caches = forward_context[layer_name].kv_cache
                if len(caches) != len(func_set):
                    continue
                for state_kind_index, (tensor, func) in enumerate(zip(caches, func_set)):
                    name = getattr(func, "__name__", "")
                    if name == "get_conv_copy_spec":
                        kind = "CONV_STATE"
                    elif name == "get_temporal_copy_spec":
                        kind = "TEMPORAL_STATE"
                    else:
                        continue
                    if physical >= tensor.shape[0] or tensor.dim() < 2:
                        continue
                    state_block = tensor[physical].detach()
                    size = state_block.numel() * state_block.element_size()
                    if size < 1 or size > MAX_STATE_BYTES:
                        continue
                    # bf16 cannot be converted to numpy directly. Reinterpret
                    # the contiguous block as bytes AFTER the GPU completes.
                    natural = state_block.contiguous().view(torch.uint8).cpu()
                    digest = hashlib.sha256(natural.numpy().tobytes()).hexdigest()
                    result["samples"].append({
                        "state_kind": kind,
                        "group_id": gid,
                        "physical_block_id": physical,
                        "layer_sha256_prefix": hashlib.sha256(
                            layer_name.encode()).hexdigest()[:16],
                        "state_kind_index": state_kind_index,
                        "shape": list(state_block.shape),
                        "dtype": str(state_block.dtype),
                        "natural_byte_length": size,
                        "state_sha256": digest,
                        "block_boundary_tokens": TARGET_PREFIX_TOKENS,
                        "observed_computed_tokens": n,
                        "state_column": col,
                        "batch_row": batch_row,
                        "state_slot": slot,
                        "phase": phase,
                        "gpu_completed_before_read": True,
                        "full_logical_state_block_bytes": True,
                    })
                    if len(result["samples"]) == MAX_STATES_PER_EVENT:
                        break
                if len(result["samples"]) == MAX_STATES_PER_EVENT:
                    break
            if len(result["samples"]) == MAX_STATES_PER_EVENT:
                break
        result["status"] = ("SNAPSHOTS_COLLECTED_NOT_REUSE_PROOF"
                            if result["samples"] else
                            "INCONCLUSIVE_NO_STATE_TENSORS")
        result["block_boundary_tokens"] = TARGET_PREFIX_TOKENS
        result["observed_computed_tokens"] = n
    except Exception:
        result["status"] = "INCONCLUSIVE_GPU_SNAPSHOT_UNAVAILABLE"
    return result


def _diagnostic(instance, phase, reason):
    """Fail-closed, bounded reason codes when no state snapshot is emitted."""
    if phase not in ("before_preprocess", "after_postprocess"):
        return
    approved = {
        "REQUEST_EPOCH_LIMIT", "PHASE_CAPTURE_BUDGET",
        "GLOBAL_CAPTURE_BUDGET", "NO_SOURCE_CONTEXT",
        "POST_COMPUTED_UNAVAILABLE", "INCONCLUSIVE_NO_VALID_BOUNDARY",
        "INCONCLUSIVE_CONTEXT_UNINITIALIZED", "INCONCLUSIVE_MAMBA_BLOCK_SIZE",
        "INCONCLUSIVE_BATCH_MAPPING", "INCONCLUSIVE_BLOCK_TABLES",
        "INCONCLUSIVE_REQUEST_SLOT", "INCONCLUSIVE_COMPUTED_BOUNDS",
        "INCONCLUSIVE_NO_STATE_TENSORS", "INCONCLUSIVE_GPU_SNAPSHOT_UNAVAILABLE",
    }
    if reason not in approved or sum(_diagnostics.values()) >= MAX_DIAGNOSTICS:
        return
    key = (phase, reason)
    if _diagnostics.get(key, 0) >= 2:
        return
    _diagnostics[key] = _diagnostics.get(key, 0) + 1
    print(DIAG_PREFIX + json.dumps({
        "schema": 1, "phase": phase, "reason": reason,
        "request_epoch_ordinal": _epoch(instance),
        "reuse_verified": False,
    }, sort_keys=True, separators=(",", ":")), flush=True)


def _denial_reason(instance, phase):
    epoch = _epoch(instance)
    if epoch > MAX_REQUEST_EPOCHS:
        return "REQUEST_EPOCH_LIMIT"
    if sum(_seen.values()) >= MAX_TOTAL_EVENTS:
        return "GLOBAL_CAPTURE_BUDGET"
    if _seen.get((epoch, phase), 0) >= MAX_EVENTS_PER_PHASE:
        return "PHASE_CAPTURE_BUDGET"
    return None


def _epoch(instance):
    return _request_epochs.get(id(instance), 0)


def _capture_allowed(instance, phase):
    epoch = _epoch(instance)
    return (
        0 <= epoch <= MAX_REQUEST_EPOCHS
        and _seen.get((epoch, phase), 0) < MAX_EVENTS_PER_PHASE
        and sum(_seen.values()) < MAX_TOTAL_EVENTS
    )


def _advance_request_epoch(instance):
    """After a successful add_request, rearm only that candidate request.

    Strictly bounded per-instance and globally. Never log a real req_index.
    """
    key = id(instance)
    _request_epochs[key] = min(
        _request_epochs.get(key, 0) + 1, MAX_REQUEST_EPOCHS + 1)


def _emit(phase, sample, *, epoch=0):
    if (type(epoch) is not int or epoch < 0 or epoch > MAX_REQUEST_EPOCHS
            or sum(_seen.values()) >= MAX_TOTAL_EVENTS):
        return
    key = (epoch, phase)
    ordinal = _seen.get(key, 0) + 1
    if ordinal > MAX_EVENTS_PER_PHASE:
        return
    _seen[key] = ordinal
    sample.update({
        "schema": 1,
        "phase": phase,
        "ordinal": ordinal,
        "request_epoch_ordinal": epoch,
        "provenance": "CANDIDATE_GPU_TENSOR_READ_NOT_CACHE_HIT_PROOF",
        "content_reuse_verified": False,
        "actual_cold_hit_pair_verified": False,
    })
    print(PREFIX + json.dumps(sample, sort_keys=True, separators=(",", ":")),
          flush=True)


def install(cls):
    """Add optional diagnostic to the copied Stage class in candidate only."""
    if os.environ.get("P1_PREFIX_STATE_SNAPSHOT") != "1":
        return
    if cls.__name__ != "MambaHybridModelState":
        raise ValueError("P1_SNAPSHOT_UNAPPROVED_CLASS")
    pre = getattr(cls, "preprocess_state")
    post = getattr(cls, "postprocess_state")
    align = getattr(cls, "_ensure_align_ctx")
    add = getattr(cls, "add_request")
    if getattr(pre, "_p1_content_probe", False):
        return

    @functools.wraps(add)
    def add_wrapper(self, req_index, new_req_data):
        result = add(self, req_index, new_req_data)
        _advance_request_epoch(self)
        return result


    @functools.wraps(pre)
    def pre_wrapper(self, input_batch, block_tables, kv_cache_config,
                    num_computed_tokens):
        # The first _mamba_ctx is created WITHIN the original preprocess
        # method. Save its inputs now, sample only after _ensure_align_ctx
        # returns (before fused advance/precopy or the model forward).
        _contexts[id(self)] = (block_tables, kv_cache_config,
                               input_batch.idx_mapping, num_computed_tokens)
        if len(_contexts) > 8:
            _contexts.clear()
            _contexts[id(self)] = (block_tables, kv_cache_config,
                                   input_batch.idx_mapping, num_computed_tokens)
        return pre(self, input_batch, block_tables, kv_cache_config,
                   num_computed_tokens)

    @functools.wraps(align)
    def align_wrapper(self, kv_cache_config, mamba_group_ids, block_tables):
        result = align(self, kv_cache_config, mamba_group_ids, block_tables)
        pending = _contexts.get(id(self))
        if pending is None or pending[1] is not kv_cache_config:
            _diagnostic(self, "before_preprocess", "NO_SOURCE_CONTEXT")
        elif not _capture_allowed(self, "before_preprocess"):
            _diagnostic(self, "before_preprocess",
                        _denial_reason(self, "before_preprocess"))
        else:
            snapshot = _sample(
                self, phase="before_preprocess",
                mapping=pending[2], computed=pending[3],
                tables=pending[0], kv_config=pending[1])
            if snapshot.get("block_boundary_tokens") is not None:
                _emit("before_preprocess", snapshot,
                      epoch=_epoch(self))
            else:
                _diagnostic(self, "before_preprocess",
                            snapshot.get("status", "INCONCLUSIVE_NO_VALID_BOUNDARY"))
        return result

    @functools.wraps(post)
    def post_wrapper(self, idx_mapping, num_sampled, num_computed_tokens=None):
        result = post(self, idx_mapping, num_sampled, num_computed_tokens)
        pair = _contexts.get(id(self))
        if pair is None:
            _diagnostic(self, "after_postprocess", "NO_SOURCE_CONTEXT")
        elif num_computed_tokens is None:
            _diagnostic(self, "after_postprocess", "POST_COMPUTED_UNAVAILABLE")
        elif not _capture_allowed(self, "after_postprocess"):
            _diagnostic(self, "after_postprocess",
                        _denial_reason(self, "after_postprocess"))
        else:
            snapshot = _sample(
                self, phase="after_postprocess",
                mapping=idx_mapping, computed=num_computed_tokens,
                tables=pair[0], kv_config=pair[1])
            if snapshot.get("block_boundary_tokens") is not None:
                _emit("after_postprocess", snapshot,
                      epoch=_epoch(self))
            else:
                _diagnostic(self, "after_postprocess",
                            snapshot.get("status", "INCONCLUSIVE_NO_VALID_BOUNDARY"))
        return result

    pre_wrapper._p1_content_probe = True
    align_wrapper._p1_content_probe = True
    post_wrapper._p1_content_probe = True
    add_wrapper._p1_content_probe = True
    setattr(cls, "add_request", add_wrapper)
    setattr(cls, "preprocess_state", pre_wrapper)
    setattr(cls, "_ensure_align_ctx", align_wrapper)
    setattr(cls, "postprocess_state", post_wrapper)
