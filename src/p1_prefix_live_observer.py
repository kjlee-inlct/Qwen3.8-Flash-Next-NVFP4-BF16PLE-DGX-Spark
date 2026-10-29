"""Candidate-only P1 live ABI observation. No torch imports, logits, prompts or model content.

Injected only into an isolated, stopped candidate's writable layer. Observing
one CUDA scalar per selected add_request incurs a synchronization; never use
in production. An observed seed is NOT a verified physical block mapping.
"""
from __future__ import annotations
import functools
import inspect
import json
import math

PREFIX = "P1_PREFIX_ACTIVE_ABI_JSON:"
MAX_EVENTS = 12
_counts = {}


def _number(value):
    if type(value) is int and -1_000_000_000 <= value <= 1_000_000_000:
        return value
    return None


def _direct(obj, name):
    try:
        return vars(obj).get(name)
    except (TypeError, AttributeError):
        return None


def _scalar_fields(obj):
    if obj is None:
        return {}
    found = {}
    for name in ("block_size", "mamba_block_size", "num_gpu_blocks",
                 "num_blocks", "num_kv_cache_groups", "max_num_seqs"):
        n = _number(_direct(obj, name))
        if n is not None:
            found[name] = n
    return found


def _tensor_metadata(tensor):
    """No data copy or allocation, only existing shape/stride/offset metadata."""
    try:
        shape = [int(x) for x in tensor.shape]
        stride = [int(x) for x in tensor.stride()]
        offset = int(tensor.storage_offset())
        width = int(tensor.element_size())
        capacity = int(tensor.untyped_storage().nbytes())
        if (not shape or len(shape) > 8 or len(shape) != len(stride)
                or any(x < 0 or x > 100_000_000 for x in shape)
                or any(x < 0 or x > 1_000_000_000 for x in stride)
                or not (0 < width <= 32)
                or offset < 0 or capacity < 0):
            return None
        maximal = offset + sum((size - 1) * st for size, st in zip(shape, stride) if size)
        within = bool(all(shape) and (maximal + 1) * width <= capacity)
        return {"shape": shape, "element_strides": stride,
                "storage_offset_elements": offset, "element_bytes": width,
                "allocation_bytes": capacity, "view_within_allocation": within,
                "device_kind": str(tensor.device).split(":", 1)[0]}
    except (AttributeError, TypeError, ValueError, RuntimeError, OverflowError):
        return None


def _groups(obj):
    """Direct instance attributes only; no arbitrary repr, tensors or IDs."""
    result = {}
    for attr in ("kv_cache_groups", "cache_groups", "kv_cache_group_specs"):
        groups = _direct(obj, attr)
        if isinstance(groups, (list, tuple)) and len(groups) <= 32:
            result[attr] = [{"class": type(x).__name__, **_scalar_fields(x)}
                            for x in groups]
    return result


def _observe(kind, instance, fn, args, kwargs):
    event = {"schema": 1, "kind": kind, "active_class": type(instance).__name__,
             "active_module": type(instance).__module__,
             "self_block": _scalar_fields(instance)}
    cache = _direct(instance, "cache_config")
    event["cache_config"] = _scalar_fields(cache)
    event["cache_groups"] = _groups(cache)
    event["instance_groups"] = _groups(instance)
    if kind == "mamba":
        event["align_mode"] = (_direct(instance, "_align_mode") is True)
        tensors = {}
        for name, value in list(vars(instance).items()):
            if (len(tensors) >= 12 or not name.startswith("_")
                    or not any(part in name.lower() for part in
                               ("mamba", "state", "block", "cache"))):
                continue
            metadata = _tensor_metadata(value)
            if metadata is not None:
                tensors[name] = metadata
        event["tensor_metadata"] = tensors
        idx = None
        try:
            bound = inspect.signature(fn).bind_partial(instance, *args, **kwargs)
            idx = _number(bound.arguments.get("req_index"))
        except (TypeError, ValueError):
            pass
        index_tensor = _direct(instance, "_mamba_state_idx_gpu")
        index_meta = _tensor_metadata(index_tensor) if index_tensor is not None else None
        event["state_slot_index_in_bounds"] = bool(
            idx is not None and idx >= 0 and index_meta and
            len(index_meta["shape"]) >= 1 and idx < index_meta["shape"][0])
        event["state_seed_observed"] = False
        # Deliberately bounded CUDA scalar read, for candidate diagnostic only.
        if event["state_slot_index_in_bounds"]:
            try:
                value = index_tensor[idx].item()
                seed = _number(value)
                if seed is not None:
                    event["state_seed_observed"] = True
                    event["state_seed_value"] = seed
            except (RuntimeError, TypeError, ValueError, IndexError):
                event["state_seed_read_error"] = True
    return event


def install(cls, method, kind):
    if (kind, method) not in (("mamba", "add_request"),
                              ("scheduler", "_mamba_block_aligned_split")):
        raise ValueError("UNAPPROVED_OBSERVER_SITE")
    fn = getattr(cls, method)
    if getattr(fn, "_p1_prefix_observed", False):
        return
    @functools.wraps(fn)
    def wrapped(self, *args, **kwargs):
        result = fn(self, *args, **kwargs)
        current = _counts.get(kind, 0)
        if current < MAX_EVENTS:
            _counts[kind] = current + 1
            try:
                event = _observe(kind, self, fn, args, kwargs)
            except Exception:
                event = {"schema": 1, "kind": kind,
                         "observer_error": "SNAPSHOT_UNAVAILABLE"}
            print(PREFIX + json.dumps(event, sort_keys=True, separators=(",", ":")),
                  flush=True)
        return result
    wrapped._p1_prefix_observed = True
    setattr(cls, method, wrapped)
