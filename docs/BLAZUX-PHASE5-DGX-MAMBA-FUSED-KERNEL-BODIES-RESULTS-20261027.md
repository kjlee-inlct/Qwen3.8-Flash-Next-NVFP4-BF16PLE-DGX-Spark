# Track A / Phase 5 — DGX Mamba fused pre-copy/postprocess kernel 및 Context block-size 실측

> **2026-10-27 (Asia/Seoul). SOURCE_INSPECTION_DONE / BOTH_TRITON_BODIES_FOUND / CONTEXT_BLOCK_SIZE_ORIGIN_RESOLVED / OUTPUT_PARTIAL_FALSE / RUNTIME_CORRECTNESS_NOT_VERIFIED / PATCH_APPROVAL_ZERO.**
>
> 사용자 업로드 `붙여넣은 텍스트(1)(20261027-152442).txt`, 총 **649줄**. source line 출력 기반 분석이며 실제 kernel launch·모델 추론·GPU state 비교의 근거는 아니다. 기존 컨테이너 `qwen38-flash-orca-uncensored-bf16-mtp`는 이미지 SHA `sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a` 확인에만 사용; 별도 disposable `--runtime=runc --network=none --read-only --cap-drop=ALL CUDA_VISIBLE_DEVICES=-1 NVIDIA_VISIBLE_DEVICES=void` CPU-only container에서 Python source read + AST.
>
> **SHA 귀속**: 마지막으로 DGX 전체 offline source/unit Gate를 직접 확인한 **코드 HEAD `a5376cc06536ce786cdb6db8425e26e21b608910`** (276/276 unittest PASS, XFAIL0, Manifest169/169). 기존 보고서/manifest docs-only HEAD는 `2def41755c2b55e95a094acabcaf1bd90d5e3259` (Manifest171). **이번 소스 검사 로그는 전체 unit/manifest 재실행 증거가 아니며, 이 보고서를 추가하는 docs-only 후속 HEAD도 DGX 시험한 코드 SHA가 아니다**. 외부 blazux pin `8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa`.

## 1. 실제 소스/검사 범위

- 대상 고정 파일: `v1/worker/mamba_utils.py`, SHA256 `25254d005f42b64dd55d15a5c646018f5599d971c23e7ca395eb5acaf4f41ed3`, 파일 **1521 source lines**.
- **CHECK1:** `precopy_mamba_align_fused_kernel` 선언 437–519 (83줄) 및 `postprocess_mamba_fused_kernel` 255–388 (134줄) **둘 모두 본문을 출력**; 두 함수 모두 `@triton.jit`. 출력 상한 각 600 source lines 미도달.
- **CHECK2:** `MambaSpecDecodeGPUContext` 652–1116, `create` 710–789, `initialize_from_forward_context` 791–841, `run_fused_precopy` 1018–1061, `run_fused_postprocess_align` 1063–1116 모두 본문 출력. 명시적 `__init__`, `__post_init__` **METHOD_NOT_DECLARED** (이 클래스에 두 이름의 명시 메서드가 없다는 의미일 뿐 생성 불가능이라는 뜻 아님).
- `FOUND_KERNELS=['precopy_mamba_align_fused_kernel','postprocess_mamba_fused_kernel']`, `CONTEXT_CLASS_FOUND=True`, `OUTPUT_PARTIAL=False`, `PATCH_APPROVED=False`, `RUNTIME_CORRECTNESS_VERIFIED=False`, `PHASE5_MAMBA_KERNEL_SOURCE_INSPECTION_DONE`.

## 2. 핵심 해결: Context `self.block_size`의 공급자는 MambaSpec

`MambaSpecDecodeGPUContext.create`:
- `:720–728` `get_mamba_groups(kv_cache_config)`로 group 취득 후 첫 `mamba_spec`을 고르고 **모든 Mamba group의 `spec.block_size`, `num_speculative_blocks`, `mamba_cache_mode`가 같은지** assert.
- `:747–789` `return cls(..., block_size=mamba_spec.block_size, ..., mamba_group_ids, block_table_ptrs,... )`; 특히 **:772 `block_size=mamba_spec.block_size`**. 클래스 field `block_size: int`는 682행.
- `:1012` V1 fused postprocess, `:1110` V2 `run_fused_postprocess_align` 모두 **`block_size=self.block_size`**를 kernel에 전달.
- **확정 범위:** 컨텍스트 생성 경로에서 V1/V2 postprocess kernel 블록 크기가 `MambaSpec.block_size`에서 공급된다는 정적 사실; preprocess kernel의 `MAMBA_BLOCK_SIZE=mamba_spec.block_size`와 같은 source provenance이다. 실제 실행 시 정규화/재대입·별도 context 구현 가능성, active 설정 숫자나 GPU 결과는 이 소스 검사만으로 검증 불가.

## 3. Pre-copy 커널 실제 본문(437–519)

| 조건/소스 | 의미 |
|---|---|
| :478–488 | `batch_idx=program_id(0)`, `state_idx=program_id(1)`, `tile_idx=program_id(2)`. `HAS_IDX_MAPPING`일 때 `req_idx=tl.load(idx_mapping_ptr+batch_idx)`, 음수 sentinel은 skip. 그렇지 않으면 req_idx=batch_idx |
| :490–496 | `src_col=tl.load(src_col_ptr+req_idx)` (pre-advance), `dst_col=tl.load(mamba_state_idx_ptr+req_idx)` (post-advance). `src_col<0`(fresh) 또는 `src_col==dst_col`면 복사하지 않음 |
| :498–519 | `token_bias`를 불러 공통 `_copy_mamba_state_block(state_idx,batch_idx,src_col,dst_col,token_bias,per-group table ptr/stride,state layout...)` 호출 |
| Context :1037–1061 | num_reqs=0 또는 `not is_initialized`이면 skip. 그 외 grid=(num_reqs,num_states,_TEMPORAL_TILES), ctx metadata/idx_mapping, `COPY_BLOCK_SIZE=1024` 및 `HAS_IDX_MAPPING` 전달 |

복사할 경우 src/dest logical column은 위 전처리의 old/new `state_idx`를 입력으로 받는다. 여기서 실제 물리 cache block address 산식은 공통 helper `_copy_mamba_state_block` 안에 있으므로 **그 helper의 구현은 이번 출력에 없음**. `COPY_BLOCK_SIZE=1024`는 복사 chunk/tuning 인자이지 Mamba token block-size로 해석하면 안 된다.

## 4. Postprocess 커널 실제 본문(255–388)

- :317–330: grid id (batch,state,tile). `HAS_IDX_MAPPING`이면 batch→req_state slot, 음수는 skip, 그렇지 않으면 batch=req.
- :332–345: `num_accepted`와 `src_block_idx=mamba_state_idx_ptr[req_idx]`. V2 `PRECOMPUTED_NEW_COMPUTED`에서는 `new_num_computed=num_computed_tokens_ptr[req_idx]`, `num_tokens_running_state=new_num_computed-num_accepted+1`. V1 경로에서는 scheduled/computed/draft 값을 조합하여 계산. **두 모드의 수식을 혼동 금지**.
- :346–351: `aligned_new_computed=(new_num_computed//block_size)*block_size`; `needs_copy=aligned_new_computed >= num_tokens_running_state`; false면 skip.
- :354–365: `accept_token_bias=aligned_new_computed-num_tokens_running_state`, `dest_block_idx=aligned_new_computed//block_size-1`. `src_block_idx==dest_block_idx`일 때 첫 state/tile만 accepted count를 `1`로 설정; source==dest이고 bias==0이면 no-op skip. **source==dest여도 bias!=0인 경우 helper copy 호출 경로 존재**.
- :367–388: block table row는 idx_mapping V2면 **batch_idx**, V1이면 req_idx; 공통 `_copy_mamba_state_block(...)`에 원본/목적 컬럼과 bias 및 메모리 layout metadata를 전달.
- Context :1084–1115: V2 num_accepted 값을 `num_accepted_tokens_out`에 snapshot 하여 교차 program race를 피한 뒤, `PRECOMPUTED_NEW_COMPUTED=True`, `HAS_IDX_MAPPING=True` 및 `block_size=self.block_size`로 launch. 원래 모델 상태/메모리 이동 결과는 이번 시험 범위 밖.

## 5. 메모리 레이아웃 초기화의 확인 범위 및 남은 차단 요소

- `initialize_from_forward_context:791–841`는 `self.is_initialized`면 skip하고 `gpu_sync_allowed` 안에서 `_populate_metadata(kv_cache_config, forward_context, mamba_state_copy_funcs, block_tables)` 호출. 실제 `_populate_metadata` 함수 본문은 **이번 targeted output에 포함되지 않았다**. `:955`에서 `self.block_table_ptrs[i] = bt.data_ptr()` 참조 줄이 출력됐지만 이 한 줄로 layout 매핑 완전성 주장 금지.
- 클래스는 state base addresses, state block strides, elem sizes, inner sizes, conv widths, per-state group indices 및 row-stride metadata를 관리. `COPY_BLOCK_SIZE` 튜닝/temporal tiles/컨볼루션 offset과 Mamba token block index를 구분해야 한다.
- **가장 중요한 미해결 단위:** `MambaHybridModelState.add_request:116`의 initial state index `floor((N-1)/B_cache)` vs preprocess의 Mamba block `ceil(N_after/B_mamba)-1`, pre-copy `src_col=old_seed` vs `dst_col=new_spec_index`, postprocess/context `B_mamba`. `CacheConfig.block_size=min(group spec block size)` 대입 경로는 이전 로그에서 발견했지만 실제 활성 `B_cache==B_mamba` 여부는 미검증. 실제 설정값 또는 full group inventory 없이 버그/OOB/wrong prefix hit이라고 단정 금지.
- **추가 source verification:** 공통 `_copy_mamba_state_block` 본체(물리 ptr, row/column indexing, conv vs temporal offset), `_populate_metadata` 본체와 indexed group/table data_ptr/strides, `CacheConfig.block_size` min assignment 시점 및 MambaSpec 생성자/default·실 spec 수치. source AST와 synthetic CPU examples를 분리하고 런타임 정합성을 과장하지 않는다.

## 6. 다음 같은 Phase5 Gate / 보호

1. 소스만 고정 함수로 조회: `v1/worker/mamba_utils.py::_copy_mamba_state_block`와 `MambaSpecDecodeGPUContext._populate_metadata`, `v1/worker/gpu/model_states/mamba_hybrid.py::add_request/preprocess_state` 및 caller source; 물리 block-table index/stride/offset·empty/fresh/same-block·idx_mapping negative sentinel·accepted token bias 정확히 분리.
2. fake KV group/CPU reference oracle로 `B_cache==B_mamba`와 `B_cache<B_mamba`, boundary/resume/speculative accepted/partial tail, req-state slot vs batch idx, source==dest+bias 등을 검사. **이것으로 GPU correctness 검증을 대신하지 않음**.
3. 활성 Docker settings/GPU/HTTP/inference, 모델 weights·HF cache/CI 및 실제 blazux patch 적용은 명시적 사용자 승인 전 금지. 모든 Parser/Responses/Tool/MTP 등 blazux patch 계열도 `APPROVED=0`, 현 Phase5만 유지.
4. `main@2847e39b4131eb8aff78bf86ffce98892401722a`, P0 `966ec7cf0741734b844b1cea938d56678a756469`, Phase1 `a50fc53721f3d23325dca44eb799f0f388d65951`, Phase2 `76588845d7742703475ae1f49d5e8f5c174bb77a`, Phase3 `760f227e46a358445db3d3931b5efbe40de5f609`, Phase4 `69860277122dffe3082c5b065e4361a571317a8e` 변경 금지. blazux→main PR/Merge/Cherry-pick/Rebase/Squash/Sync 금지, Phase5 docs-only commit로 기록.
