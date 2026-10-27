# Track A / Phase 1 — Gate 1 소스·데이터 계약 1:1 비교

> 작성일: 2026-10-27 (Asia/Seoul). 상태: STATIC_SOURCE_REVIEW_COMPLETE_WITH_BLOCKERS / CPU_RUNTIME_NOT_RUN / DGX_GPU_NOT_RUN / CI_NOT_VERIFIED. **운영 반영·성능 개선 검증 아님.**
> 소스 기준: 내부 P0 `966ec7cf0741734b844b1cea938d56678a756469`; 외부 blazux `8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa`; 비교 시작 전 main `2847e39b4131eb8aff78bf86ffce98892401722a`.
> 계보: P0 → `feature/blazux-phase1-source-compare` (분기 부모 SHA `966ec7cf0741734b844b1cea938d56678a756469`). Phase 1의 결과는 main, P0, 실제 DGX에 반입하지 않는다. Track B는 승인 전 생성 금지.

## 1. 비교 범위, 검증 방식, 신뢰 경계

- Github contents API로 두 SHA의 실제 파일을 읽어 파일별 함수·입출력·코드 앵커를 대조했다. 두 저장소에 포함되지 않은 **실제 설치된 upstream vLLM 전체 소스와 동적 런타임 ABI는 확인하지 못했다**. 따라서 vLLM 0.32 내부 호출의 실제 호환성을 확정한 것이 아니다.
- 내부 [PLE]( https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark/blob/966ec7cf0741734b844b1cea938d56678a756469/src/vllm_ple_mmap.py), [PLE CPU fixture](https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark/blob/966ec7cf0741734b844b1cea938d56678a756469/src/test_ple_mmap_cpu.py), [Dockerfile](https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark/blob/966ec7cf0741734b844b1cea938d56678a756469/Dockerfile), [MTP overlay](https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark/blob/966ec7cf0741734b844b1cea938d56678a756469/src/recipe/mtp.py), [MTP guard](https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark/blob/966ec7cf0741734b844b1cea938d56678a756469/src/patch_qwen4_exp_mtp_load_guard.py), [MTP compressed ignore](https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark/blob/966ec7cf0741734b844b1cea938d56678a756469/src/patch_qwen4_exp_mtp_compressed_ignore.py), [compatibility](https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark/blob/966ec7cf0741734b844b1cea938d56678a756469/compatibility.json)을 읽었다.
- 외부 [PLE](https://github.com/blazux/qwen3.8-Flash-DGX/blob/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa/src/vllm_ple_mmap.py), [PLE CPU fixture](https://github.com/blazux/qwen3.8-Flash-DGX/blob/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa/src/test_ple_mmap_cpu.py), [Dockerfile](https://github.com/blazux/qwen3.8-Flash-DGX/blob/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa/Dockerfile), [Top-K](https://github.com/blazux/qwen3.8-Flash-DGX/blob/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa/src/patch_qsa_exact_topk.py), [QSADET](https://github.com/blazux/qwen3.8-Flash-DGX/blob/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa/src/patch_qsadet.py), [QSA FP8 KV](https://github.com/blazux/qwen3.8-Flash-DGX/blob/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa/src/patch_qsa_fp8_kv.py), [MTP prefilter](https://github.com/blazux/qwen3.8-Flash-DGX/blob/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa/src/patch_mtp_name_prefilter.py), [draft vocab](https://github.com/blazux/qwen3.8-Flash-DGX/blob/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa/src/patch_mtp_draft_vocab.py), [MTP graft](https://github.com/blazux/qwen3.8-Flash-DGX/blob/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa/scripts/prepare-mtp-graft.sh), [Mamba block](https://github.com/blazux/qwen3.8-Flash-DGX/blob/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa/src/patch_mamba_block_size.py), [M-RoPE](https://github.com/blazux/qwen3.8-Flash-DGX/blob/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa/src/patches/qwen-mrope-cache-window.patch) 및 parser/Responses patch를 읽었다.
- 정적 문자열·목록 검사: 내부 MTP guard 31개 = overlay 31개, 이름 집합 완전 일치. 관련 PLE/Top-K/Mamba/parser feature anchor 존재 확인. **이것은 스크립트 정적 검사이며 unittest 실행 또는 엔진 동작 검증이 아니다.**
- 내부 Source Manifest P0의 120개 path/mode/blob SHA는 GitHub 트리와 일치. Phase 1 문서 추가 후 별도 Manifest 갱신·동일 커밋 확인 필요.

## 2. PLE mmap: 함수별 1:1 대응표 (최우선)

| 계약·행위 | 내부 preview, 파일 내 위치 | blazux v0.32, 파일 내 위치 | 실제 차이와 경계 | 판정 |
|---|---|---|---|---|
| 활성화 | PLE enabled() L90, env VLLM_PLE_MMAP 기본 OFF | PLE enabled() L77, 동일 env 기본 OFF | opt-in 설계 동일; 환경변수 외 다수 추가 설정은 독립 플래그 필요 | **KEEP** |
| 저장 dtype 해석 | PleStorageDType 및 _resolve_ple_dtype L65–86: BF16(2 byte), FP8 E4M3/E5M2 | _FP8_DTYPES/_TABLE_DTYPES L63–75: BF16/F16/FP8 | BF16 동일한 2-byte 표현. blazux F16 추가는 현 BF16 계약에 필수 아님 | **KEEP** (BF16), **ADAPT** (F16) |
| safetensors 오프셋 | parse_safetensors_header L105–111: 8-byte little-endian header size + JSON | 동일 함수 L109–115 | tensor data_offsets를 header end에 합산해야 하며 nonzero prefix dummy tensor 존재 시험 필요. 둘 다 malformed/oversized header 완전 방어는 별도 검증 | **KEEP** |
| 인덱스·shard 검색 | _find_shards L264–328: layer regex, index/전체 파일, shard name, dtype/rowbytes, **전체 shard width 일치 검사**. 열 수를 '__cols__' 센티넬로 반환 | _find_shards L323–373: 4번째 반환값 cols, dtype/rowbytes 검사. **혼합 width 확인 없음** | blazux 최종 cols가 마지막 샤드에서 결정될 수 있음. 기존 width guard 제거 금지; 센티넬은 별도 refactor 후 회귀 필요 | **KEEP** width guard, **ADAPT** return tuple |
| 구조·전체성 검증 | _validate_shard_layout L367–385: 0..parts-1 **완전 연속 인덱스 + 정확한 rows** | _setup_table L633–676: 현재 존재하는 shard의 rows 검사. 전체 인덱스 집합을 직접 비교하지 않음 | 외부 경로에 128/128 검사를 새로 보증하지 않고 이식하면 누락 shard가 늦게 실패하거나 침묵할 위험 | **KEEP** fail-closed |
| mmap 생성 | MmapPleTable.__init__ L122–146: uint8 read-only memmap, shape=(rows,row_bytes), ThreadPoolExecutor | 동일 클래스 L126–159 + MADV_RANDOM/normal 호출 | offset과 row byte 크기 계약은 공유. Linux madvise 정책은 BF16 page-cache 동작 변화 | **PORT** 별도 기본-OFF flag 후보 |
| row gather | gather L148–188: int64 reshape → unique/sort → shard별 chunk 병렬 → CPU inverse expansion, out uint8[N,row_bytes] | gather/_gather L161–230: 소량(기본 512 이하)은 threadpool 생략, 대량은 기존 방식과 유사, stats 기록 | 작은 배치에서 unique 연산 생략: 출력 순서는 유지되어야 하며 missing/out-of-range 처리 동등성 확인 필요 | **ADAPT** 기본-OFF small-batch flag |
| out-of-range | 기존 gather L155–160는 [0, shard_size×shard_slots) 사전 검사, 완전성은 _validate_shard_layout에서 보증 | 외부 _gather L182–200는 rows_total 검사 | 유효 연속 shard 구성에서 의미가 같을 수 있으나 holes/last short shard에서 다름. 정상/오류 입력 양측 fixture로 판정 | **KEEP** 양성·음성 검증 |
| prewarm | prewarm L190–205, VLLM_PLE_MMAP_PREWARM 기본 OFF | prewarm L232–247, 기본 OFF | 기존 BF16 약 95GiB 파일 선읽기 page cache 압박 위험. full prewarm 활성화 불필요 | **KEEP** OFF |
| CPU→GPU transfer | _MmapNgramEmbedding.forward L244–258: ids D2H→전체 rows gather→CPU inverse→torch.view(dtype)→H2D | _MmapNgramEmbedding.forward L276–317: D2H→unique/inverse→unique rows gather→pinned staging→async H2D→GPU index inverse | 입력 shape [N,16], head_dim 160, dtype BF16, 비트 단위 동일성·중복 처리·GPU stream lifecycle 시험 필요. async pinned 버퍼 **재사용 race**와 메모리 증가 가능성 미검증 | **ADAPT** gate/기본 OFF |
| 별도 계측 | 내부에는 per-phase 카운터 없음 | gather L161–175, forward L288–316, _STATS/_prom L403–575: wait/dedup/gather/stage/op, Prometheus | GPU queue wait를 실제 PLE 비용과 분리. /metrics 노출은 EngineCore 멀티프로세스 설정 의존. Prometheus 카운터, 출력의 bytes는 실제 NVMe I/O와 구분해야 함 | **PORT** 안전한 계측부터 |
| scale·dequant | _read_scale L343–355, _read_required_scale L358–364: BF16 무scale, FP8 scale 필수 | _read_scale L388–400, _MmapNgramEmbeddingDevice.dequantize L717–742: FP8 scale 적용, BF16 cast | BF16 무scale 공통; scale 소유 위치가 _offload_weight_scale vs device.weight_scale로 변화. FP8 함수 직접 교체 금지 | **KEEP** BF16; **DEFER_TO_TRACK_B** FP8 device API |
| placeholder 생성 | 내부 apply/__init__ L429–466: VocabParallelEmbedding 임시 교체, config/embedding_dim/ple_dense_layer_id/max_total_tokens/**max_num_reqs**/prefix | 외부 _install L745–791: Qwen4ExpPLEDeviceEmbedding/PinnedHostEmbedding 임시 교체, **data_parallel_rank**, use_sequence_parallel, keyword-only prefix | constructor positional/keyword, embedding owner, quant_config=None, lazy param 부재의 ABI가 다름. 간단한 import/문자열 패치로 포팅 불가 | **DEFER_TO_TRACK_B** |
| load_weights | 내부 apply.load_weights L468–486: shard tensor skip, scale buffer register, 나머지 orig_load_weights | 외부 _install.load_weights L793–813: buffer + embedding.weight_scale 양쪽 설정 | 현재 128개 BF16 mmap tensor 유무와 weight map, loader iterator 중복/결손, late setup 에러가 기준. 31개 MTP guard와 별개 | **KEEP** 현 BF16 경로 |
| setup_table | 내부 L488–537: local model snapshot, shard width/layout validate, dtype resolve, mmap, log | 외부 _setup_table L633–695: VLLM_PLE_MMAP_DIR 선택, width/dtype, mmap, log | 외부 대체 디렉터리는 체크포인트와 별도 FP8 table을 읽을 수 있어 모델 정체성·revision·hash 불일치 위험 | **REJECT** 무검증 임의 DIR, 필요시 별도 검증 |
| custom op | 내부 _lookup_impl/_lookup_fake/_register_op L392–426: vllm::ple_mmap_lookup(input_ids, query_start_loc, ngram_context, output, layer_name) | 외부 _lookup_ids_impl/_lookup_ids_fake/_register_op L581–617: vllm::ple_mmap_lookup_ids(ngram_ids, output, layer_name) | 외부는 **이미 GPU에서 해시된 id**를 인자로 받음. 원래 n-gram hash가 호출되는 위치가 다름. tensor shape/torch.compile 오퍼레이터 계약 비호환 | **DEFER_TO_TRACK_B** |
| 실행 진입점·CUDA graph | 내부 forward_impl L538–559: 원래 forward_impl을 custom op로 감싸고 splitting_ops / PIECEWISE 필요 | 외부 _install.forward L820–830 및 _eager_lookup/_breakable_capture L831–858: compute_ngram_ids, static buffer, breakable eager replay, sequence parallel | 외부 v0.32 capture는 기존 PIECEWISE graph split과 독립 API. 내부 이미지에 직접 복사하면 capture/replay 파손 가능. FULL capture 금지 경계 유지 | **DEFER_TO_TRACK_B** |

### PLE 보존해야 할 데이터 계약

- 현재 Orcarouter [compatibility.json](https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark/blob/966ec7cf0741734b844b1cea938d56678a756469/compatibility.json): layer_id=1, split_parts=128, total_rows=320001536, width=160, dtype=BF16. 전체 raw 크기는 320001536×160×2 = 102400491520 bytes (약 95.37 GiB). **부분 row gather**만 메모리로 옮기는 것이 핵심.
- header data_start = 8 + header_len; 절대 tensor 시작 = data_start + data_offsets[0]. row bytes BF16=320. global row → shard=floor(row/shard_size), local=row−shard×shard_size. nonzero header/tensor offset와 최종 shard의 실제 rows를 확인한다.
- H2D 경계는 dtype 변환이 아니라 BF16 원래 bit pattern 보존이 기본. 외부의 unique->GPU inverse 경로는 CPU에서 inverse를 수행하는 내부 경로와 bitwise, order 및 shape가 동등해야 한다.
- 사용자 운영 환경에서 실제 CPU pinned buffer 재사용 시 여러 in-flight CUDA 복사가 겹치지 않는지와 copy 완료 전 버퍼 overwrite가 없는지 필요. 성능 효과는 그 후 측정한다.
- blazux 주석의 16×160 byte 가정은 FP8 설명이고 **현재 BF16은 16×160×2 byte**이다. 단편의 용량·대역폭 수치를 운영 계측으로 재사용하지 않는다.

## 3. MTP 31 BF16 tensor / prefilter / draft vocab

| 비교 대상 | 내부 실제 구현 | 외부 고정 구현 | 판정·근거 |
|---|---|---|---|
| MTP source inventory | [recipe/mtp.py L27–65](https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark/blob/966ec7cf0741734b844b1cea938d56678a756469/src/recipe/mtp.py#L27-L65) MTP_TENSOR_NAMES 31개; compatibility.json RadixArk source 3 shard/revision, expected BF16 | [prepare-mtp-graft.sh L2–35](https://github.com/blazux/qwen3.8-Flash-DGX/blob/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa/scripts/prepare-mtp-graft.sh#L2-L35): hybrid+NVFP4 donor 계보 | **KEEP** 기존 BF16 overlay |
| overlay 안전 | [recipe/mtp.py L123–263](https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark/blob/966ec7cf0741734b844b1cea938d56678a756469/src/recipe/mtp.py#L123-L263) target shard 링크/고정 fingerprint, BF16 subset, source sha·metadata, 검증 | graft는 fused BF16 2개 제거, NVFP4 6144 전문가 텐서 + 29 fullwidth tensor | **REJECT** graft를 현 Orcarouter에 직접 적용 |
| Load guard | [patch_qwen4_exp_mtp_load_guard.py L10–135](https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark/blob/966ec7cf0741734b844b1cea938d56678a756469/src/patch_qwen4_exp_mtp_load_guard.py#L10-L135) missing/unexpected/wrong dtype fail-closed, 31/31 통과 로그 | prefilter는 loader 이전 should_skip_weight 전역 wrapper, 자체 31/31 guard 대체물이 아님 | **KEEP** 검증기 절대 제거 금지 |
| compressed-tensors MTP | [patch_qwen4_exp_mtp_compressed_ignore.py L14–37](https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark/blob/966ec7cf0741734b844b1cea938d56678a756469/src/patch_qwen4_exp_mtp_compressed_ignore.py#L14-L37) ignore remap | graft/ModelOpt FP8 hybrid 전제 | **KEEP** Orcarouter-specific ignore |
| name prefilter | 내부 동일 기능 없음; guard는 load 완료 후 검사 | [patch_mtp_name_prefilter.py L23–80](https://github.com/blazux/qwen3.8-Flash-DGX/blob/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa/src/patch_mtp_name_prefilter.py#L23-L80) should_skip_weight 가변 전역 filter + loader scope, 기본 ON | **ADAPT** 함수/iteration 순서 검증 후. 전역 상태의 동시성/예외/secondary_weights, 재매핑 전후 names, guard 보존 필수 |
| reduced draft vocab | 내부는 모델의 기존 lm_head/logits acceptance 경로 보존 | [patch_mtp_draft_vocab.py L20–56](https://github.com/blazux/qwen3.8-Flash-DGX/blob/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa/src/patch_mtp_draft_vocab.py#L20-L56) lm_head 행 subset + 나머지 -inf | **REJECT** 현행 기본 적용. 후보 vocab 밖의 타깃/정답 토큰 확률·acceptance/품질 변화 가능. 실증 전 개선 주장 금지 |
| MTP vLLM ABI | 내부 class Qwen3_8FlashNextMTP, load_weights 구문 anchor 정확 match 필요 | 외부 class Qwen4ExpMTP, mapper=mapper 분기 허용 | **DEFER_TO_TRACK_B** class/loader ABI 차이 |

- 이번 세션 코드 수준의 정적 목록 비교: 내부 guard의 31개 이름과 recipe/mtp.py의 31개 이름 집합이 정확히 동일. **실제 tensor header의 31×(name,shape,dtype,bytes) 1:1 일치 시험은 수행하지 않음**. BF16 MTP=2 acceptance, proposed/accepted token 출력도 NOT_RUN.

## 4. QSA / Prefix Cache / Parser 계약 분리

| 기능 | 소스 앵커와 데이터 계약 | 내부 상태/위험 | 판정 |
|---|---|---|---|
| QSA exact top-k | [patch_qsa_exact_topk.py L13–73](https://github.com/blazux/qwen3.8-Flash-DGX/blob/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa/src/patch_qsa_exact_topk.py#L13-L73): qsa_indexer.py::_topk의 logits[B,C], visible_blocks[B], block_indices[B,K]; fill/torch.topk; 옵션 env 기본 0 | 내부 별도 동일 패치 없음. invalid/invisible column mask, tie order, k>columns, replay, prefill/decode latency 검증 필요; 0.32 소스 anchor 비확인 | **ADAPT**, 우선 CPU synthetic oracle |
| QSA deterministic kernel | [patch_qsadet.py L13–59](https://github.com/blazux/qwen3.8-Flash-DGX/blob/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa/src/patch_qsadet.py#L13-L59): _C_det.so 선택적 로드 | 외부 .so binary ABI/SM121/torch/triton 대응 미확정 | **DEFER_TO_TRACK_B** |
| QSA FP8 KV | [patch_qsa_fp8_kv.py](https://github.com/blazux/qwen3.8-Flash-DGX/blob/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa/src/patch_qsa_fp8_kv.py) _cast_kv_tile scale/kernel/warmup 변경 | 기존 BF16 KV 사용, fp8 scale와 양자화 오류 도입 | **REJECT** 현재 Track A |
| Mamba/SSM prefix restore | [patch_mamba_block_size.py L9–34](https://github.com/blazux/qwen3.8-Flash-DGX/blob/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa/src/patch_mamba_block_size.py#L9-L34): mamba state idx는 mamba_block_size, scheduler split은 그룹 LCM block size | 현재 해당 상태 복원 로직·설치 vLLM snapshot 검증 안 됨. wrong state seed는 cached-hit 정합성 훼손 | **ADAPT** 개념 검증만; 실제 적용 보류 |
| served M-RoPE cache | [qwen-mrope-cache-window.patch](https://github.com/blazux/qwen3.8-Flash-DGX/blob/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa/src/patches/qwen-mrope-cache-window.patch): target max_model_len 기반 cos/sin cache 연장 | M-RoPE cache 생성·draft 재사용·long context 미확인; 전형적 prefix hit 정합성 문제와는 구분 | **DEFER_TO_TRACK_B** |
| streaming tool marker | [qwen-tool-preamble.patch](https://github.com/blazux/qwen3.8-Flash-DGX/blob/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa/src/patches/qwen-tool-preamble.patch), [qwen-tool-marker-guard.patch](https://github.com/blazux/qwen3.8-Flash-DGX/blob/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa/src/patches/qwen-tool-marker-guard.patch) parser state + fence/line state | 내부 preview parser 실제 소스/terminal grammar에 대한 1:1 확인 전 blanket patch 금지 | **DEFER_TO_TRACK_B** |
| JSON arguments | [qwen-tool-argument-schema.patch](https://github.com/blazux/qwen3.8-Flash-DGX/blob/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa/src/patches/qwen-tool-argument-schema.patch): parser_engine.py/qwen3.py, Responses strict, ambiguous streamed wrappers | streaming delta 이미 전송 후 재작성 불가; Chat passthrough와 Responses strict 동작 차이 | **DEFER_TO_TRACK_B** |
| Responses output | [qwen-safe-output.patch](https://github.com/blazux/qwen3.8-Flash-DGX/blob/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa/src/patches/qwen-safe-output.patch): responses protocol/serving, response.failed/incomplete, tool rejection | 내부 운영 API와 동일 응답 계약 미검증, SSE event name/item ID/JSON parse regressions 필요 | **DEFER_TO_TRACK_B** |

**중요한 근거 경계:** 내부 저장소에는 patched *preview* vLLM의 qsa_indexer, mamba_hybrid, streaming_parser_engine 본문이 vendored 되어 있지 않다. 외부 저장소도 vLLM 0.32 전체 본문 대신 Dockerfile 패치 앵커를 제공한다. 따라서 해당 3개 영역은 **앵커 기반의 계약 비교**까지만 완료했고, 설치된 프레임워크 함수의 AST 1:1 또는 ABI 적합 판정은 **BLOCKED_BY_UNVENDORED_UPSTREAM**이다.

## 5. API/ABI drift 및 위험 등록부

| ID | 확인된 경계/미해결 사항 | 영향·차단 | Phase 2 이후 검증 설계 |
|---|---|---|---|
| G1-01 | Qwen3_8FlashNextNGramEmbedding.forward_impl(max_num_reqs) vs Qwen4ExpNGramEmbedding.forward(data_parallel_rank/use_sequence_parallel) | CUDA graph/lookup kwargs ABI, 잘못 이식 시 즉시 import/추론 실패 | preview 및 v0.32 고정 wheel/source 심볼·inspect.signature diff, mock constructor |
| G1-02 | 내부 shard index/width 완전성 검사 vs 외부 sentinel 없는 cols 반환/누락 index 검사 부재 | BF16 데이터 손상·오류 지연 위험 | BF16 임의 width, 빠진 shard, 중복, 최종 short shard, mismatch offset fixture |
| G1-03 | unique gather + pinned copy + GPU inverse | race, OOM, GPU 스트림 ordering, 참조 수명 | CPU bitwise fixture 뒤 CUDA event/stream 경계 안전성 검증 (DGX 실기기는 별도 승인) |
| G1-04 | short gather threshold + MADV_RANDOM | page faults/페이지 캐시 정책, latency jitter | 작은/큰 N, 중복률, random/sequential access의 독립 시험 |
| G1-05 | MTP filter는 weight_utils 전역 monkeypatch + v0.32 명칭 | 동시성 및 31/31 guard 훼손 우려 | callable adapter 재설계, name mapping before/after·모의 iterator 31/31 |
| G1-06 | MTP donor graft/FP8 KV/ModelOpt quantization은 현 Orcarouter BF16 계보와 다름 | 컨피그·텐서 shape/scale 변화 | Track A에 반입하지 않음. Track B도 별도 Go/No-Go, 원본 hash별 독립 시험 |
| G1-07 | QSA torch.topk 정확도, tie, visible mask | 정답성·결정성·성능 혼재 | CPU oracle+seeded randomized visible masks; QSA GPU 후속 승인 |
| G1-08 | SSM state restore vs prefix-hit, scheduler/mamba block size | 잘못된 과거 state 사용시 silent output drift | block boundary, prefix hit/miss, state checksum fixture, cached vs uncached 비교 |
| G1-09 | parser/Responses streaming 변경 폭, error semantics | literal marker/JSON 불일치, SSE event drift | tool offered/unoffered, fences, partial JSON, chunk boundary, chat/responses별 oracle |
| G1-10 | 원본 Benchmark corpus SHA/sampler/payload 및 7개 미첨부 원본 체크섬 | 엄격한 동등 A/B 차단 | 비공개 DGX 결과와 동일 input/corpus/config 고정 후에만 개선률 분석 |
| G1-11 | vLLM preview 실제 설치 artifact/digest, 외부 v0.32 Docker digest와 source ABI 미확인 | exact-version portability 판정 차단 | read-only wheel SHA/path/함수 signature 목록 확보, 절대 운영 runtime 변경 없음 |

## 6. 우선순위 및 기능별 실험 승인 기준

| 우선순위 | 조치 | 독립 flag (제안; 코드 미작성) | Gate 2 fixture / acceptance |
|---|---|---|---|
| P1 | 기본-OFF 원인별 PLE host/gather 시간 계측과 안전한 통계 수집 | VLLM_PLE_PHASE_STATS=0 | GPU queue wait와 CPU 비용 분리, off일 때 기존 코드 반환 동일 |
| P1 | small-N 인라인 gather / uniq GPU inverse 분리 검토 | VLLM_PLE_FAST_GATHER=0, VLLM_PLE_GPU_INVERSE=0 | BF16 bitwise exact, duplicate/offset, stream 안전성; GPU 전송 단계는 Gate 3 |
| P1 | PLE layout hard fail invariants 강화 및 합성 BF16 fixture | 코어 기존 guard 유지 (최적화 flag 아님) | 128 parts 의미를 축소한 3~4 shards, rows×160, 비정상 offset, missing shard |
| P2 | 선택적 madvise + 프리패치의 개별 영향 분리 | VLLM_PLE_MADVISE_MODE=off | page cache/latency 계측; prewarm은 계속 OFF |
| P2 | QSA exact topk 마스크/정합성 원형 시험 | VLLM_QSA_EXACT_TOPK=0 | seeded logits와 visible block, ties, 불량 NaN/Inf 케이스 |
| P2 | MTP loader 이름 early prefilter 개념 적용 검토 | VLLM_MTP_EARLY_PREFILTER=0 | 31 BF16 원형 보존, mapped names 1:1, missing/extra fail-closed |
| P3 | Parser/Responses·SSM Prefix cache의 upstream ABI 추적 | 현 단계 코드/flag 없음 | 설치 소스 확인 후 Track B 필요성 판정 |
| 보류 | MTP NVFP4 graft, FP8 KV/hybrid, reduced draft vocab, QSADET external kernel | 해당없음 | 현 Orcarouter 벤치와 격리; 임의 활성화 불허 |

## 7. Phase 2 진입 계약과 작업 결과

1. **Phase 1 결과:** 소스 앵커/함수별 차이·우선순위·fixture·위험 문서화. source 자체/배포 모델 변경 0. **비교 ≠ 호환성 인증**. 테스트: Github read-only 정적 문자열/31-set 검사만 실행. Python CPU unit/fixture NOT_RUN; Docker build, DGX GPU, HTTP A/B, CI NOT_RUN.
2. **Phase 2 진입 조건:** 이 문서와 Manifest가 동일 Phase 1 commit의 GitHub tree에서 1:1 일치하고, Phase 1 리뷰/불변 스냅샷 HEAD가 확정되면 `feature/blazux-phase2-offline-fixtures`를 그 정확한 SHA로 신규 생성. Phase 1 ref에 Phase 2 테스트 코드를 추가하지 않는다.
3. **Phase 2 완료 기준(향후):** 작은 BF16 safetensors fixture를 모델/민감 파일 없이 작성하고, offset/shape/dtype/shard complete/fail closed/duplicate/gather bitwise 및 MTP 이름 매핑, QSA CPU oracle을 단위 테스트로 직접 실행하여 결과를 원문으로 보존. GPU 동작·성능 이점은 별도 승인이 필요.
4. **기타 차단:** Benchy corpus/input SHA, 7개 파일 및 exact sampler 미검증; CI 복구 보류; installed vLLM/torch/triton/driver 버전과 CUDA graph capture ABI 미검증.
5. **변경 금지:** blazux→main PR·merge·cherry-pick·squash·rebase, Docker/포트/운영 컨테이너/HF cache/영수증 변경, 정량 개선 주장.

### 보존 파일 및 원본 SHA

| 출처 파일 | Git Blob SHA |
|---|---|
| 내부 src/vllm_ple_mmap.py | 8313aff03e1f50c1861c068a6a745b7b632c3d9d |
| 내부 src/test_ple_mmap_cpu.py | 9322b89875f96c6343c1b153ca2d3a07a7abc0f3 |
| 내부 src/recipe/mtp.py | 73141fa1000b50a3e75df936085462e6f85c5978 |
| 내부 src/patch_qwen4_exp_mtp_load_guard.py | d7b93e639daafd0acace3bf360a6d899f52104cd |
| 외부 src/vllm_ple_mmap.py | 6c3aefe0cb99d140ccd6a91a4238faf938494845 |
| 외부 src/test_ple_mmap_cpu.py | 83c285d23e7ad174ad9945c2e09519e0f4ee111d |
| 외부 src/patch_qsa_exact_topk.py | 81c0a9b7d0b61e2606aa917275eb24e7fc538178 |
| 외부 src/patch_mtp_name_prefilter.py | 32d14c4b2f50372e327989720a3caa685d518311 |

**결론:** 현재 BF16 PLE 및 31 BF16 MTP 보호 계약은 KEEP. 특정 순수 CPU 최적화/계측만 기본 OFF 조건으로 검토한다. vLLM 0.32 class/operator/graph/parser 변경은 Track A 코드에 강제 이식하지 않고 별도 Track B 판단 대상으로 둔다.
