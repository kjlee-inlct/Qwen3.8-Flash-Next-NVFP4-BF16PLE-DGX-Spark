# Track A Phase5 — DGX Scheduler/KV/Mamba Kernel source inspection (2026-10-27)

**Status:** CHECK1/CHECK2/CHECK3 source inspections completed; CHECK2 OUTPUT_LIMIT/PARTIAL; state-slot/GPU/ABI/active config NOT_CERTIFIED; patch approval ZERO. Evidence: user DGX text upload named 붙여넣은 텍스트(1)(20261027-145706).txt (1033 lines). Tests used isolated runc CPU-only container from existing image sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a; read-only, no network, no GPU/device exposure. Original serving container and model unchanged.

**Strict SHA attribution:** Prior full DGX offline Gate PASS belongs to source commit a5376cc06536ce786cdb6db8425e26e21b608910 (276 unittest PASS XFAIL0, Source Manifest169/169, source AST checks 10/10); later docs-only HEAD 321d979eca30b20e5724afbddfe15fe6bf962fbe included 170 tracked manifest entries. These three new standalone inspections DID NOT rerun 276 tests or latest Source Manifest. This report and its subsequent docs-only commit MUST NOT be called tested source SHA. External blazux pin: 8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa.

## 1. SchedulerConfig factory: actual branches now understood (CHECK1)

config/scheduler.py sha256 bf399abc7216b4801fbba5fd8f5cbc1960c9458d7519a544ae3015d83dd7a7d6, SchedulerConfig.get_scheduler_cls 170–191:

| Condition in source | Return |
|---|---|
| scheduler_cls is None AND async_scheduling true | AsyncScheduler (175), imported within function |
| scheduler_cls is None AND async_scheduling false | Scheduler (178), imported within function |
| scheduler_cls not None and not a string | cast(type[SchedulerInterface], scheduler_cls) (190) |
| scheduler_cls a string | resolve_obj_by_qualname(scheduler_cls) (191) |

Field declarations: scheduler_cls: str | type[object] | None = None (117); async_scheduling: bool | None = None (148). The source does NOT prove how nullable async config is resolved in the active model/service. v1/engine/core.py sha256 f4b1e07b6d91fac1549bc74a5c804e5a88793d663b5dc045c9e455db6550f5ad: EngineCore line148 obtains local Scheduler via scheduler_config.get_scheduler_cls(), line157 unpacks KV resolver output and line161 constructs Scheduler with block_size/hash_block_size kwargs. Previous direct-import static check false came from factory/local import structure, NOT evidence of missing Scheduler import. Active selected class remains unknown.

## 2. CacheConfig.block_size value provenance and source scan limitation (CHECK2)

**Partial scan:** SCAN_OUTPUT_LIMIT_REACHED after 162 files, 3,571,805 bytes, 103 matches. CHECK2_BLOCK_ORIGINS_SOURCE_DONE signifies source inspection command termination, NOT completeness for all source files.

**New anchor v1/engine/core.py:321–324:** If kv_cache_groups exists, it executes assignment of vllm_config.cache_config.block_size to min(g.kv_cache_spec.block_size for g in kv_cache_groups). This proves that a min-of-group-specs assignment path exists, NOT its actual execution under this model or the resulting numeric size.

config/cache.py sha256 8790351601be188ed1cc7ad9de2af1978b238269da4724873af1185c91165ef6: DEFAULT_BLOCK_SIZE=16 (line48), mamba_block_size optional int (125), mamba_cache_mode default none (137), user-specified flag if mamba size set (267–268). None of these defaults certify actual running values. config/vllm.py sha256 b845db7f30bf535e7e1ed5257f5d6513f604f4ed56b5466e2d08986b92f53f53 has Mamba validation at 2530–2541 and align/chunked-MM constraints at 2507–2511.

v1/kv_cache_interface.py sha256 7452e823367960daf73520f80824aee0d5ed8ad2731d0404705695814d3bcff7: frozen MambaSpec (704+); align has 2+num_speculative_blocks resident state blocks (732–733), while block table rows remain full-sequence position-indexed (738–743). Logical position index is not identical to resident-block count. v1/core/single_type_kv_cache_manager.py:74–76 keeps scheduler_block_size distinct from per-group kv_cache_spec.block_size. v1/core/kv_cache_coordinator.py:89–93 asserts divisibility and at 627–633 checks partial Mamba hash-hit conditions. v1/attention/backends/utils.py:1125 calculates align start_indices=(seq_lens-1)//kv_cache_spec.block_size and gathers last 1+speculative entries, with 0-length clamp (sha256 9ecfa5ed0ddd22760837572eb279759afa5fdbe24b5ba607b1cf49340be7280f).

**Conditional risk:** CacheConfig.block_size CAN be derived from the minimum group spec while a MambaSpec block-size can come from a different group. Equality is NOT implied by source design; actual group inventory, branch reachability and numerical discrepancy are not observed in this log. Do not infer corruption or any real prefix cache hit error.

## 3. State seed, preprocess, pre-copy, postprocess: source contract (CHECK3)

CHECK3_MAMBA_SLOT_SOURCE_DONE; 352 Python files scanned and 8 targeted function definitions printed. Source fingerprints: v1/worker/gpu/model_states/mamba_hybrid.py sha256 2e65f1da0a440f11a784bd36afe9206a7a2f674d522c047b838ad604e4c6acc0; v1/worker/mamba_utils.py sha256 25254d005f42b64dd55d15a5c646018f5599d971c23e7ca395eb5acaf4f41ed3.

| Location | Static behavior |
|---|---|
| mamba_hybrid.py:113–117 | Align add_request seeds state_idx=(num_computed_tokens-1)//cache_config.block_size |
| mamba_utils.py:420–434 | preprocess_mamba_align_fused_kernel loads old state_idx, stores src_col=old_idx and src_off=max(num_accepted-1,0), computed_after=num_computed+query_end-query_start, new_state_idx=(computed_after+MAMBA_BLOCK_SIZE-1)//MAMBA_BLOCK_SIZE-1; changes accepted count to 1 when old and new idx differ |
| mamba_hybrid.py:195–218 | MAMBA_BLOCK_SIZE=mamba_spec.block_size in preprocess; calls ctx.run_fused_precopy |
| mamba_utils.py:1018–1061 | run_fused_precopy feeds dst/source indices, accepted-token bias, tables and memory layout to precopy_mamba_align_fused_kernel |
| mamba_hybrid.py:306–345 | postprocess under align/non-null context calls run_fused_postprocess_align |
| mamba_utils.py:1063–1116 | run_fused_postprocess_align snapshots accepted counts and calls postprocess_mamba_fused_kernel(block_size=self.block_size, ...); source of context self.block_size not resolved |
| v1/attention/backends/utils.py:1095–1134 | all/none mode returns table, align mode selects position-indexed block table windows using kv_cache_spec.block_size |

Mathematical contrast: initial seed floor((N-1)/B_cache) vs updated index ceil(N_after/B_mamba)-1, for positive N_after equivalent to floor((N_after-1)/B_mamba). Unequal B values MAY yield different indices for the same position. No active block sizes, real source/destination address, runtime success/failure or CUDA state consistency were measured.

**Important missing definitions in CHECK3:** user-chosen function names omitted the actual Triton implementations precopy_mamba_align_fused_kernel and postprocess_mamba_fused_kernel, so their bodies were NOT read. MambaSpecDecodeGPUContext.create/initialize_from_forward_context, self.block_size provenance, layout/strides/slot restoration also remain unverified. One must not claim full kernel correctness.

## 4. Next same Phase5 no-go gates

1. Inspect fixed source locations in v1/worker/mamba_utils.py for precopy_mamba_align_fused_kernel and postprocess_mamba_fused_kernel bodies plus MambaSpecDecodeGPUContext create/initialize_from_forward_context and self.block_size assignment. Source read-only, no kernel execution.
2. Inspect v1/engine/core.py:321–324 assignment reachability, CacheConfig and MambaSpec group creation; actual active model config numbers require separately approved read-only access if operational assets would be touched.
3. Isolated stdlib synthetic CPU boundary fixtures for B_cache equal/less-than B_mamba, resume, empty, speculative acceptance shift, idx_mapping sentinel and block-table columns. Synthetic math not GPU correctness. Scheduler factory branch/source is now documented but chosen active Scheduler not certified.
4. blazux Mamba/Prefix, Tool Calling/Responses and reduced-vocabulary MTP patch approval 0; no runtime/weights/HF cache/ports/GPU/HTTP/TPS/CI modifications; no new phase.

Protected refs: main 2847e39b4131eb8aff78bf86ffce98892401722a; P0 966ec7cf0741734b844b1cea938d56678a756469; Phase1 a50fc53721f3d23325dca44eb799f0f388d65951; Phase2 76588845d7742703475ae1f49d5e8f5c174bb77a; Phase3 760f227e46a358445db3d3931b5efbe40de5f609; Phase4 69860277122dffe3082c5b065e4361a571317a8e. Keep current Phase5 only; no PR/merge/cherry-pick/rebase/squash/sync to main.
