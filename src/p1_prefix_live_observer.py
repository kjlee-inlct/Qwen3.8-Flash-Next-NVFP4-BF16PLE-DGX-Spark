"""Candidate-only P1 live ABI observation. No torch imports, logits, prompts or model content.

Injected only into an isolated, stopped candidate's writable layer. Observing
one CUDA scalar per selected add_request incurs a synchronization; never use
in production. An observed seed is NOT a verified physical block mapping.
"""
from __future__ import annotations
import functools
import inspect
import json

PREFIX = "P1_PREFIX_ACTIVE_ABI_JSON:"
MAX_EVENTS = 12
_counts = {}
_seen_calls = {}
# Sample startup plus spaced later steps instead of exhausting the 12-event
# allowance on the first 12 startup calls. Values are call ordinals, not IDs.
_SAMPLE_CALLS = frozenset((1, 2, 3, 4, 8, 16, 32, 64, 128, 256, 512, 1024))
# Bounded diagnostic-only process state; no request IDs or tensor contents.
_recent_mamba_slot = {}
_saved_mamba_tables = {}


def _number(value):
    if type(value) is int and -1_000_000_000 <= value <= 1_000_000_000:
        return value
    return None


# Narrow whitelist: never inspect arbitrary request/model fields or print repr.
# Real vLLM config/spec/request structs may use slots/properties; the original
# vars(obj)-only implementation incorrectly reported those fields as missing.
_OBSERVED_ATTRS = frozenset((
    "block_size", "mamba_block_size", "num_gpu_blocks", "num_blocks",
    "num_kv_cache_groups", "max_num_seqs", "cache_config", "kv_cache_groups",
    "cache_groups", "kv_cache_group_specs", "kv_cache_spec",
    "kv_cache_specs", "layer_names", "vllm_config", "compilation_config",
    "static_forward_context", "kv_cache", "block_tables",
    "input_block_tables", "gpu", "_mamba_group_ids", "_mamba_ctx",
    "_align_mode", "_mamba_state_idx_gpu", "_p1_observer_mamba_tables",
    "num_computed_tokens", "num_reqs", "idx_mapping", "block_table_stride_req", "state_block_strides",
    "state_elem_sizes", "state_group_indices", "state_conv_widths",
))


def _direct(obj, name):
    if obj is None or name not in _OBSERVED_ATTRS:
        return None
    try:
        local = vars(obj)
        if name in local:
            return local[name]
    except (TypeError, AttributeError):
        pass
    # Only for a whitelisted field. Needed for slots and class descriptors.
    try:
        return getattr(obj, name, None)
    except (AttributeError, TypeError, RuntimeError, ValueError):
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



def _kv_spec_info(kv_cache_config, group_ids):
    """Inspect only named Mamba KV groups and typed spec fields."""
    groups = _direct(kv_cache_config, "kv_cache_groups")
    if not isinstance(groups, (list, tuple)):
        return {}
    result = {}
    for gid in group_ids[:8]:
        if type(gid) is not int or gid < 0 or gid >= len(groups):
            continue
        group = groups[gid]
        specs = _direct(group, "kv_cache_spec")
        layer_names = _direct(group, "layer_names")
        # vLLM may use UniformTypeKVCacheSpecs instead of a bare MambaSpec.
        # Unwrap by actual layer names rather than treating the wrapper as the
        # effective MambaSpec (which silently lost its block size).
        wrapped = _direct(specs, "kv_cache_specs")
        lookup = specs if isinstance(specs, dict) else wrapped
        details = []
        if isinstance(lookup, dict):
            if not isinstance(layer_names, (list, tuple)):
                layer_names = list(lookup)
            for layer_name in list(layer_names)[:16]:
                if not isinstance(layer_name, str) or layer_name not in lookup:
                    continue
                spec = lookup[layer_name]
                details.append({"spec_class": type(spec).__name__,
                                **_scalar_fields(spec)})
        else:
            details.append({"spec_class": type(specs).__name__,
                            **_scalar_fields(specs)})
        result[gid] = {"specs": details,
                       "layer_count": len(layer_names) if isinstance(
                           layer_names, (list, tuple)) else None}
    return result


def _state_group_allocations(instance, kv_cache_config, gid):
    """Read actual allocated model cache tensor metadata, without addresses.

    No state tensor contents, request IDs, logits or GPU pointer values leak.
    Missing any selected layer is explicitly unknown, never a passed bound.
    """
    groups = _direct(kv_cache_config, "kv_cache_groups")
    if not isinstance(groups, (list, tuple)) or gid >= len(groups):
        return {"allocation_blocks": None, "state_tensor_count": 0,
                "allocation_complete": False, "sample_tensors": []}
    layers = _direct(groups[gid], "layer_names")
    config = _direct(instance, "vllm_config")
    compilation = _direct(config, "compilation_config")
    context = _direct(compilation, "static_forward_context")
    if (not isinstance(layers, (list, tuple)) or not layers or
            len(layers) > 128 or not isinstance(context, dict)):
        return {"allocation_blocks": None, "state_tensor_count": 0,
                "allocation_complete": False, "sample_tensors": []}
    blocks = []
    samples = []
    complete = True
    n = 0
    for layer in layers:
        if not isinstance(layer, str) or layer not in context:
            complete = False
            continue
        caches = _direct(context[layer], "kv_cache")
        if not isinstance(caches, (list, tuple)) or not caches:
            complete = False
            continue
        for tensor in caches:
            n += 1
            meta = _tensor_metadata(tensor)
            if meta is None or not meta["shape"] or not meta["view_within_allocation"]:
                complete = False
                continue
            blocks.append(meta["shape"][0])
            if len(samples) < 4:
                samples.append(meta)
    minimum = min(blocks) if complete and blocks else None
    return {"allocation_blocks": minimum,
            "state_tensor_count": n,
            "allocation_complete": minimum is not None,
            "sample_tensors": samples}


def _remember_physical_tables(instance, args, kwargs, fn):
    """References are candidate-only; no model tensor is copied or mutated."""
    try:
        bound = inspect.signature(fn).bind_partial(instance, *args, **kwargs)
        kv_config = bound.arguments.get("kv_cache_config")
        tables_obj = bound.arguments.get("block_tables")
        tables = (tables_obj if isinstance(tables_obj, (list, tuple))
                  else _direct(tables_obj, "block_tables"))
        group_ids = bound.arguments.get("mamba_group_ids")
        if not isinstance(group_ids, (list, tuple)) or len(group_ids) > 8:
            group_ids = ()
        saved = {}
        spec_info = _kv_spec_info(kv_config, list(group_ids))
        for gid in group_ids:
            if type(gid) is not int or gid < 0:
                continue
            if not isinstance(tables, (list, tuple)) or gid >= len(tables):
                continue
            # Actual pinned Preview ABI is tuple[torch.Tensor, ...]:
            # block_tables[gid] is itself a batch-order 2-D GPU tensor.
            # The old .gpu-only lookup silently dropped every real group.
            raw = tables[gid]
            direct_meta = _tensor_metadata(raw)
            batch_order = direct_meta is not None
            bt = raw if batch_order else _direct(raw, "gpu")
            meta = direct_meta if batch_order else _tensor_metadata(bt)
            if meta is None or len(meta["shape"]) != 2:
                continue
            allocation = _state_group_allocations(
                instance, kv_config, gid)
            saved[gid] = {"table": bt, "meta": meta,
                          "batch_order_rows": batch_order,
                          "group": spec_info.get(gid, {}),
                          "allocation": allocation}
        # Keep references outside the model object: no injected model attrs.
        if len(_saved_mamba_tables) >= 8 and id(instance) not in _saved_mamba_tables:
            _saved_mamba_tables.clear()
        _saved_mamba_tables[id(instance)] = saved
    except (TypeError, AttributeError, ValueError, RuntimeError, IndexError):
        _saved_mamba_tables.pop(id(instance), None)


def _sample_physical(instance, request_idx, expected_col, mamba_block_size, *,
                     batch_row=None):
    """Compare a sampled request state-slot / Mamba column with physical IDs.

    This verifies bounded table entries, not the SSM state contents or
    cold-to-hit state reuse. A scalar GPU read is diagnostic-only.
    """
    snapshots = []
    saved = _saved_mamba_tables.get(id(instance))
    if saved is None:
        saved = _direct(instance, "_p1_observer_mamba_tables")
    if not isinstance(saved, dict) or request_idx is None or expected_col is None:
        return snapshots
    for gid, info in list(sorted(saved.items()))[:8]:
        meta = info["meta"]
        shape = meta["shape"]
        group_sizes = [
            part.get("block_size") for part in info["group"].get("specs", [])
            if part.get("block_size") is not None]
        allocation = info.get("allocation", {})
        allocated = allocation.get("allocation_blocks")
        # A batch-order table row is NOT a persistent req_index slot. Without
        # the input_batch permutation, never read [req_index, col] or claim
        # a matching physical block ID. Metadata is still useful evidence.
        batch_order = info.get("batch_order_rows") is True
        mapped_row = (batch_row if type(batch_row) is int and batch_row >= 0
                      else None)
        resolved = batch_order and mapped_row is not None
        entry = {"group_id": gid, "group_block_sizes": group_sizes,
                 "table_row_semantics": (
                     "IDX_MAPPING_BATCH_ROW_OBSERVED" if resolved else
                     "BATCH_ORDER_ROW_UNRESOLVED" if batch_order else
                     "OPAQUE_WRAPPER_LEGACY_PROBE"),
                 "request_slot_to_table_row_verified": resolved,
                 "state_allocation_blocks": allocated,
                 "state_allocation_complete": allocation.get(
                     "allocation_complete") is True,
                 "table_shape": shape,
                 "table_row_stride_elements": meta["element_strides"][0],
                 "table_within_allocation": meta["view_within_allocation"],
                 "row_in_bounds": (
                     0 <= mapped_row < shape[0] if resolved else
                     None if batch_order else 0 <= request_idx < shape[0]),
                 "column_in_bounds": 0 <= expected_col < shape[1],
                 "block_size_matches_mamba_config": (
                     None if not group_sizes or mamba_block_size is None
                     else all(x == mamba_block_size for x in group_sizes)),
                 "physical_entry_observed": False,
                 "physical_id_within_state_allocation": None}
        if batch_order and not resolved:
            entry["physical_read_skipped_reason"] = (
                "BATCH_ROW_TO_REQUEST_SLOT_UNVERIFIED")
        if (meta["view_within_allocation"] and
                entry["row_in_bounds"] and entry["column_in_bounds"]
                and (not batch_order or resolved)):
            try:
                row = mapped_row if resolved else request_idx
                block = _number(info["table"][row, expected_col].item())
                if block is not None:
                    entry["physical_entry_observed"] = True
                    entry["physical_block_id"] = block
                    entry["physical_entry_nonnegative"] = block >= 0
                    entry["physical_id_within_state_allocation"] = (
                        0 <= block < allocated if type(allocated) is int else None)
            except (TypeError, IndexError, RuntimeError, ValueError):
                entry["physical_read_unavailable"] = True
        snapshots.append(entry)
    return snapshots


def _preprocess_mapping_event(instance, fn, args, kwargs):
    """Bounded candidate-only batch row -> persistent state-slot diagnostic.

    Source ABI: preprocess_state(input_batch, block_tables, kv_cache_config,
    num_computed_tokens) calls fused kernels with input_batch.idx_mapping.
    GPU scalar reads are deliberately limited to 8 batch rows + one state
    column + at most 8 group entries for an *observed* row. No state contents
    or request IDs are logged. This cannot prove cache state reuse.
    """
    event = {"batch_row_to_state_slot_observed": False,
             "state_column_observed": False, "physical_map_samples": [],
             "batch_row_count": None, "idx_mapping_metadata": None}
    try:
        bound = inspect.signature(fn).bind_partial(instance, *args, **kwargs)
        batch = bound.arguments.get("input_batch")
        count = _number(_direct(batch, "num_reqs"))
        indices = _direct(batch, "idx_mapping")
        meta = _tensor_metadata(indices)
        event["batch_row_count"] = count
        event["idx_mapping_metadata"] = meta
        if (count is None or count <= 0 or meta is None
                or len(meta["shape"]) != 1 or not meta["view_within_allocation"]
                or meta["shape"][0] < count):
            event["mapping_reason"] = "BATCH_IDX_MAPPING_UNAVAILABLE"
            return event
        slots = _direct(instance, "_mamba_state_idx_gpu")
        slot_meta = _tensor_metadata(slots)
        if (slot_meta is None or len(slot_meta["shape"]) != 1
                or not slot_meta["view_within_allocation"]):
            event["mapping_reason"] = "MAMBA_STATE_SLOT_UNAVAILABLE"
            return event
        valid_slots = 0
        for batch_row in range(min(count, 8)):
            req_slot = _number(indices[batch_row].item())
            if req_slot is None or not (0 <= req_slot < slot_meta["shape"][0]):
                continue
            valid_slots += 1
            event["batch_row_to_state_slot_observed"] = True
            state_col = _number(slots[req_slot].item())
            if state_col is None or state_col < 0:
                continue
            event["state_column_observed"] = True
            event["batch_row_sample"] = batch_row
            event["state_slot_sample"] = req_slot
            event["state_column_sample"] = state_col
            mamba_bs = _number(_direct(_direct(instance, "cache_config"),
                                       "mamba_block_size"))
            event["physical_map_samples"] = _sample_physical(
                instance, req_slot, state_col, mamba_bs, batch_row=batch_row)
            return event
        event["valid_batch_slot_mapping_count_bounded"] = valid_slots
        event["mapping_reason"] = "NO_NONNEGATIVE_STATE_COLUMN_IN_SAMPLE"
    except (TypeError, ValueError, AttributeError, IndexError, RuntimeError):
        event["mapping_reason"] = "GPU_MAPPING_READ_UNAVAILABLE"
    return event


def _observe(kind, instance, fn, args, kwargs):
    event = {"schema": 1, "kind": kind, "active_class": type(instance).__name__,
             "active_module": type(instance).__module__,
             "self_block": _scalar_fields(instance)}
    cache = _direct(instance, "cache_config")
    event["cache_config"] = _scalar_fields(cache)
    event["cache_groups"] = _groups(cache)
    event["instance_groups"] = _groups(instance)
    if kind == "preprocess":
        event.update(_preprocess_mapping_event(instance, fn, args, kwargs))
    if kind == "align_ctx":
        tables = _saved_mamba_tables.get(id(instance))
        if tables is None:
            tables = _direct(instance, "_p1_observer_mamba_tables")
        event["mamba_group_table_count"] = (
            len(tables) if isinstance(tables, dict) else 0)
        event["physical_table_metadata"] = [
            {"group_id": gid, "table": table["meta"],
             "table_row_semantics": ("BATCH_ORDER_ROW_UNRESOLVED" if
                                     table.get("batch_order_rows") else
                                     "OPAQUE_WRAPPER_LEGACY_PROBE"),
             "group": table["group"],
             "state_allocation": table.get("allocation")}
            for gid, table in list(sorted(tables.items()))[:8]
        ] if isinstance(tables, dict) else []
        context = _direct(instance, "_mamba_ctx")
        recent = _recent_mamba_slot.get(id(instance))
        event["deferred_state_to_physical_samples"] = (
            _sample_physical(instance, recent[0], recent[1], recent[2])
            if isinstance(recent, tuple) and len(recent) == 3 else [])
        event["fused_ctx_present"] = context is not None
        if context is not None:
            event["fused_ctx_block_stride_req"] = _number(
                _direct(context, "block_table_stride_req"))
            event["fused_ctx_block_size"] = _number(
                _direct(context, "block_size"))
            event["fused_state_layout_tensors"] = {
                name: _tensor_metadata(_direct(context, name))
                for name in ("state_block_strides", "state_elem_sizes",
                             "state_group_indices", "state_conv_widths")
                if _tensor_metadata(_direct(context, name)) is not None}
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
        request_data = None
        try:
            request_data = bound.arguments.get("new_req_data")
        except (NameError, UnboundLocalError):
            pass
        computed = _number(_direct(request_data, "num_computed_tokens"))
        mamba_bs = _number(_direct(cache, "mamba_block_size"))
        expected = ((computed - 1) // mamba_bs
                    if computed is not None and mamba_bs is not None
                    and mamba_bs > 0 else None)
        event["num_computed_tokens"] = computed
        event["expected_mamba_seed"] = expected
        event["state_seed_observed"] = False
        # Deliberately bounded CUDA scalar read, for candidate diagnostic only.
        if event["state_slot_index_in_bounds"]:
            try:
                value = index_tensor[idx].item()
                seed = _number(value)
                if seed is not None:
                    event["state_seed_observed"] = True
                    event["state_seed_value"] = seed
                    if (idx is not None and idx >= 0 and expected is not None
                            and expected >= 0 and mamba_bs is not None):
                        if len(_recent_mamba_slot) >= 8 and id(instance) not in _recent_mamba_slot:
                            _recent_mamba_slot.clear()
                        _recent_mamba_slot[id(instance)] = (idx, expected, mamba_bs)
                    event["state_seed_matches_expected"] = (
                        expected is not None and expected == seed)
            except (RuntimeError, TypeError, ValueError, IndexError):
                event["state_seed_read_error"] = True
        event["physical_map_samples"] = _sample_physical(
            instance, idx, expected, mamba_bs)
    return event


def install(cls, method, kind):
    if (kind, method) not in (("mamba", "add_request"),
                              ("align_ctx", "_ensure_align_ctx"),
                              ("preprocess", "preprocess_state"),
                              ("scheduler", "_mamba_block_aligned_split")):
        raise ValueError("UNAPPROVED_OBSERVER_SITE")
    fn = getattr(cls, method)
    if getattr(fn, "_p1_prefix_observed", False):
        return
    @functools.wraps(fn)
    def wrapped(self, *args, **kwargs):
        result = fn(self, *args, **kwargs)
        if kind == "align_ctx":
            _remember_physical_tables(self, args, kwargs, fn)
        ordinal = _seen_calls.get(kind, 0) + 1
        _seen_calls[kind] = ordinal
        current = _counts.get(kind, 0)
        if ordinal in _SAMPLE_CALLS and current < MAX_EVENTS:
            _counts[kind] = current + 1
            try:
                event = _observe(kind, self, fn, args, kwargs)
            except Exception:
                event = {"schema": 1, "kind": kind,
                         "observer_error": "SNAPSHOT_UNAVAILABLE"}
            event["observer_call_ordinal"] = ordinal
            print(PREFIX + json.dumps(event, sort_keys=True, separators=(",", ":")),
                  flush=True)
        return result
    wrapped._p1_prefix_observed = True
    setattr(cls, method, wrapped)
