# Track A / Phase 5 — DGX Mamba 물리 State Block 및 Metadata 소스 계약 (2026-10-28)

> **SOURCE_ONLY / FULL_BODIES_FOUND / OUTPUT_PARTIAL_FALSE / RUNTIME_CORRECTNESS_NOT_VERIFIED / PATCH_APPROVAL_ZERO.**
> 증거: 사용자 DGX 로그 `붙여넣은 텍스트(1)(20261027-161759).txt` (302줄), 이전 fused-kernel 전체 소스 검사 `붙여넣은 텍스트(1)(20261027-161437).txt`. 설치 이미지 조회 후 `--runtime=runc --network=none --read-only --cap-drop=ALL CUDA_VISIBLE_DEVICES=-1 NVIDIA_VISIBLE_DEVICES=void`의 별도 CPU 컨테이너에서 source AST/출력만 수행. 기존 서빙/모델/GPU/포트 미변경.
>
> 설치 원본 `v1/worker/mamba_utils.py` SHA256 **`25254d005f42b64dd55d15a5c646018f5599d971c23e7ca395eb5acaf4f41ed3`**, 총 1521행. `_copy_mamba_state_block` **122–252행(131줄)**와 `MambaSpecDecodeGPUContext._populate_metadata` **843–957행(115줄)** 모두 본문 출력, `SOURCE_SHA_MATCH=True`, `OUTPUT_PARTIAL=False`, `PHASE5_MAMBA_PHYSICAL_SOURCE_INSPECTION_DONE`. 이는 GPU launch/주소값 관측/CPU 회귀시험이 아니다.

## P1 — 블록 테이블과 물리 State 주소: 실제 코드 표현식

- 공통 `_copy_mamba_state_block(state_idx, bt_row_idx, src_col, dst_col, token_bias, ...)`는 **state_idx별** `state_base_addr`, `state_block_stride` (bytes), `state_elem_size`, `state_inner_size`, `conv_width`, `group_idx` metadata를 읽는다 (166–175).
- `group_idx=load(state_group_indices_ptr+state_idx)` → `group_base_addr=load(block_table_ptrs_ptr+group_idx)` → int32 pointer → `block_table_base=block_table_typed+bt_row_idx*block_table_stride_req` (175–178). 테이블 row/column offset의 단위는 **int32 elements**, state block stride의 단위는 **bytes**.
- `dest_block_id=load(block_table_base+dst_col).to(int64)`, `dst_addr=state_base_addr+dest_block_id*state_block_stride` (183–184); source physical ID 역시 int64 변환. 주석상 큰 stride에서 int32 multiply wrap 방지 목적. **물리 block ID는 논리 col과 다르다.**
- `CONV_STATE_DIM_FIRST`이고 conv일 때: `src_col`에서 block ID 취득, dim row별 `src_block_addr + d*row_stride + token_bias*elem_size`에서 `dst_addr+d*row_stride`로 각 `(conv_width-token_bias)*elem_size` 바이트 복사 (188–210). `tile_idx>0`는 skip.
- SD conv: `src_col`의 block ID, `src_offset=token_bias*state_inner_size*elem_size`; `copy_size=(conv_width-token_bias)*state_inner_size*elem_size`; `_memcpy_u64_tiled(..., NUM_TILES=1)` (212–234). `tile_idx>0` skip.
- Temporal: **`src_col+token_bias`**에서 source physical ID 로드, `copy_size=state_inner_size*state_elem_size` (natural bytes, **not block stride**), `_memcpy_u64_tiled(..., NUM_TILES=TEMPORAL_TILES)` (236–252).
- Precopy kernel에서는 `HAS_IDX_MAPPING` 시 batch→req slot을 조회하고 음수 skip, `src_col<0` 또는 동일 column이면 skip; helper 전달 `bt_row_idx=batch_idx`. Postprocess V2에서도 decision 배열은 req slot, block table row는 batch idx; V1은 mapping 없이 req idx. Postprocess source==destination이며 bias==0은 skip하지만 **같은 column + bias!=0은 helper 호출 가능**. 각 호출부의 판단과 helper 자체의 주소 계산을 혼동 금지.
- **경계 보장의 한계:** helper 본문에는 논리 col, physical block ID, group index, `token_bias`의 포괄적 runtime bounds validation이 명시되지 않음. 테이블/metadata 구성 및 호출자가 전제조건을 만족하는지 확인 필요. 실제 OOB/메모리 손상 **관측 없음**.

## P2 — Metadata 공급·그룹/레이어/State 순서

- `_populate_metadata`는 `enumerate(self.mamba_group_ids)`의 group-local index → 해당 `kv_cache_groups[mamba_group_id].layer_names` → `forward_context[layer_name].kv_cache` state tensor 순서로 `idx`를 증가시키며, `len(kv_caches)==len(mamba_spec.shapes)` 및 최종 `idx==self.num_states`를 assert (850–940).
- `state_base_addrs[idx]=state.data_ptr()`; `block_stride_elems=state.stride(0)`(dim>1, 아니면 `state.numel()`); `state_block_strides[idx]=block_stride_elems*state.element_size()`; `state_elem_sizes[idx]=state.element_size()` (865–878).
- state copy type은 identity 비교로 `get_conv_copy_spec` 또는 `get_temporal_copy_spec`만 허용. Conv state는 dim=3 필수. DS(layout dim-first): `width=size(2)`, `inner_size=1`, `row_count=size(1)`, `row_stride=stride(1)*element_size`. SD: `width=size(1)`, `inner_size=stride(1)`. Temporal: `width=0`, `inner_size=state[0].numel()`(dim>1) 또는 1; uint64 비정렬 base/stride 시 warning만 기록 (880–935).
- `state_group_indices[idx]=group_local_idx` (937); group-local 번호가 실제 engine group ID와 다름을 구분한다.
- `len(block_tables)==self.num_groups`; 모든 group table의 `stride(0)`이 같아야 함; `block_table_stride_req=shared stride(0)`; `block_table_ptrs[i]=bt.data_ptr()` (942–955). `self.is_initialized=True`는 마지막 (957). 이 소스 경로는 table dtype/column/physical-ID/underlying state allocation bound 전체를 자체적으로 증명하지 않는다.

## P3 / P4 — 다음 묶음 검증 범위 및 엄격한 귀속

- 다음 **하나의 CPU-only 묶음 Gate**는 (G1) 고정 source SHA/세 함수 AST, (G2) V1/V2 mapping/sentinel, (G3) multi-group table pointer/row-stride, (G4) DS/SD conv·temporal padded stride/uint64 tail, (G5) `B_cache==B_mamba` 및 `!=` 경계/empty/resume, (G6) accepted token bias/same-col/postprocess, (G7) 잘못된 인덱스·zero-length·partial-tail을 합성 byte-array oracle로 검사한다. CPU oracle의 bounds check는 **합성 시험 설계**로서 Triton 원본에 존재한다고 주장 금지. `_memcpy_u64_tiled` 본체는 이번 로그의 P1/P2 추출 범위에 없으므로 다음 batch에서 별도로 정적 검사.
- `EngineCore.cache_config.block_size=min(group.kv_cache_spec.block_size)` 대입 분기, worker seed 분모 `cache_config.block_size`, context/pre/post 및 align gather 분모 `MambaSpec/KV spec.block_size`의 **정적 provenance 차이**는 유지. 활성 group 구성, config 숫자 동일성, branch 실행 여부 미확인. 따라서 **버그/패치 승인 없음**.
- 마지막 **실제 DGX 전체 오프라인 PASS는 코드 SHA `a5376cc06536ce786cdb6db8425e26e21b608910`**에만 귀속: unit 276/276 XFAIL0, Source169/169, source AST 10/10. 이 P1/P2 source-only log나 그 후속 **docs-only** 커밋에서 unit·Source Gate를 재실행했다는 증거 없음. CI run 0, CI PASS 아님.
- 같은 Phase5만 유지; `main`, P0, Phase1–4 불변. PR/Merge/Rebase/Cherry-pick/Squash/Sync 및 실제 blazux patch/operational Docker·GPU·weights·model·HF cache·HTTP/serving/CI 건드리지 않음.
