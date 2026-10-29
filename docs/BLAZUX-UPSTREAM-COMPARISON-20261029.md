# blazux 최신 원본과 Orcarouter BF16 PLE/MTP 구현 비교 (2026-10-29)

> **2026-10-29 우리 구현의 실제 GPU 후속 증거:** 이 문서의 pinned `7372721` ↔ upstream `7e63dbe` 비교와 표의 'cold/hit NOT_RUN'은 **비교 당시 상태**이며 현행 P1 실측을 대체하지 않는다. 사용자 DGX `c342e033c6e601f374520eefb6a9d0e9277b54ef`: 9,492-token synthetic cold+repeat 3회, Prefix-cache HIT delta **[0,6400,6400,6400]**, nonempty 최종 text 및 token IDs 일치, strict logprob delta **0.003320594 > 1e-4**, active physical Mamba mapping 미관측, 원본 same-ID/HTTP 복구 PASS. 개선 코드가 원본 vLLM 0.32 기능과 1:1 완전 동등함을 입증하지 않는다. [실측 결과](BLAZUX-PHASE6-RESULTS.md), [현행 P1 인수인계](PHASE6-ACTIVE-SESSION-HANDOFF-20261028.md)를 우선한다.


> **분류:** 외부 공개 소스/검증 보고와 내부 DGX 증거의 비교 기록. **적용·GPU 실험·새 테스트·운영 승인 아님.** 새 upstream 기능이 Orcarouter BF16 PLE/31개 BF16 MTP overlay에 그대로 적용된다는 의미도 아니다. 장기 Track A/Track B 규칙은 [기존 도입 계획](BLAZUX-VLLM032-ADOPTION-PLAN.md), 정확한 현재 테스트 영수증은 [Phase 6 결과 장부](BLAZUX-PHASE6-RESULTS.md), 현재 진행 경계는 [P1 인수인계](PHASE6-ACTIVE-SESSION-HANDOFF-20261028.md)를 따른다.

## 1. 정확한 비교 대상과 판정 원칙

| 항목 | 외부 blazux 원본 | 우리 후보/운영 |
| --- | --- | --- |
| 저장소 | [blazux/qwen3.8-Flash-DGX](https://github.com/blazux/qwen3.8-Flash-DGX) | [kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark](https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark) |
| 비교 SHA | [`7e63dbe5761448ea833ed28781c1d32ce0d56f4c`](https://github.com/blazux/qwen3.8-Flash-DGX/tree/7e63dbe5761448ea833ed28781c1d32ce0d56f4c) (`main`, 2026-10-28 UTC) | [`73727212dcd96cec917c275523d0016f13ef9aee`](https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark/tree/73727212dcd96cec917c275523d0016f13ef9aee) (`feature/blazux-phase6-runtime-gates`, **비교 직전 docs-only HEAD**) |
| 실제 DGX 기능 검증 SHA | 외부 보고의 각 v0.32 candidate 이미지/검증 영수증에 한정 | **`29e78cdc1dccf82667d0a9c227a7b4b0629c3136`**: Phase6 185/185, Source 247/247, PLE CPU, Phase4 4조합, Phase5 합성 14/14, 실제 Preview Parser→Serving CPU 14사례 PASS |
| 기반/체크포인트 | 공식 vLLM **0.32.0**, 기본 NVIDIA NVFP4 + FP8 PLE/선택적 FP8 hybrid, GX10 실증 | 공식 Qwen3.8 Preview `0.1.dev20073`, **Orcarouter Uncensored 직접 BF16 PLE 약 95.37 GiB**, RadixArk 출처 **31개 BF16 MTP tensor overlay(MTP=2)**; 기존 port 8000 레거시 운영 서비스 보존 |
| 실제 기능 증거 | 원본 README/v0.32 실측은 **원본의 NVIDIA/hybrid 설정에만 유효** | 새 blazux 개선 기능 **DEPLOYED_VERIFIED=0**. CPU 기능 검증과 실 GPU/HTTP/API/운영 검증을 구분 |
| 원본 이전 고정점 | [`8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa`](https://github.com/blazux/qwen3.8-Flash-DGX/tree/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa) | Phase 1–5 당시의 정적 비교 기준. **새 upstream HEAD가 이전 판정을 소급하여 변경하지 않는다** |

GitHub [`8bb7a..7e63dbe` 비교](https://github.com/blazux/qwen3.8-Flash-DGX/compare/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa...7e63dbe5761448ea833ed28781c1d32ce0d56f4c)는 **후속 7개 커밋, 8개 변경 파일**이다. 주요 신규 항목은 DFlash2/patch 23이다. 공식 vLLM 0.32, Prefix, YaRN, reduced vocab 등은 이전 고정점에도 이미 구현돼 있던 기능이므로 **이번 7개 커밋에서 새로 추가된 것으로 기록하지 않는다**.

## 2. 8개 목표의 기능별 1:1 비교

| 우선 | 기능 | blazux 원본 현황(해당 프로젝트의 증거) | 우리 구현/증거(정확한 범위) | 아직 필요한 실제 검증 |
| --- | --- | --- | --- | --- |
| P1 | PLE mmap 단계별 성능 계측 | `src/vllm_ple_mmap.py`에서 호출/행/논리바이트 및 dedup, gather, GPU-wait/host stage를 로그와 선택적 Prometheus로 관측; 실제 GX10 기반 | `VLLM_PLE_PHASE_STATS=0` 기본 OFF, `normalize/dedup/gather_work/wait/stage`와 `forward/ids_to_host/tensor_view/device_copy_call` per-table 카운터; DGX 격리 CPU **PASS** | BF16 실제 디스크·모델의 page fault, TTFT/TPS, 정확한 GPU 전송 완료시간, 실제 배포 노출 **NOT_RUN** |
| P1 | Prefix-cache 정확성 회귀 | `src/patch_mamba_block_size.py`는 Mamba worker state slot 및 Scheduler prefill split 단위를 바로잡음. 원본 v0.32는 **worker fix가 native**, Scheduler 수정 유지; 반복 prefix 출력/TTFT 실측 | 정적 Scheduler/Mamba 분기 추적과 synthetic bound 오라클만. 기존 운영 `/metrics`의 `enable_prefix_caching=false`; 실제 선택 class/group/block-table/stride 미관측 → **P6-A ACTIVE ABI BLOCKED**, cold/hit **NOT_RUN** | Preview 대응 함수와 두 수정점을 독립 diff; 대상 엔진 ABI 확인; 별도 승인된 격리 후보 또는 정비창 in-process 관측 + cold/hit byte/logprob/state 검증. **원본 버그를 우리 모델에서 실측했다고 주장하지 않음** |
| P1 | Tool Calling / Responses | v0.32 patches 12/13/19/21, offered-schema 검증, 문자 그대로의 tool marker, Stream/Nonstream terminal, Chat/Responses 차이; 원본에서 실제 API 시험 | **설치 Preview 원본의 임시 SHA 고정 overlay**로 실제 Qwen3 Parser→Responses Serving + Pydantic SSE 14사례 CPU 통합 **PASS** (`29e78cd`), 설치 vLLM 불변 | 실제 모델 HTTP(Chat/Responses), tool roundtrip, streaming/비streaming, 오류 매핑 **NOT_RUN**. 원본 CPU 검증에도 알려진 parser 1개 및 schema dotted-namespace 1개 이슈가 있으므로 100% 호환이라 단정하지 않음 |
| P2 | MTP reduced draft vocabulary | `patch_mtp_draft_vocab.py`, `draft_vocab_65536.npy`: target head는 유지하고 draft만 65,536/248,320 후보로 계산, 원본 설정 기본 ON. 원본의 특정 GX10 비교에서 decode 이득 보고 | 현 BF16 MTP 31-tensor overlay에 reducer 미적용; 합성 acceptance 계약만 **PASS** | 실제 BF16 head 공유/로더/로그잇 ID mapping, acceptance·다국어·품질·속도 대조 필요. **P2 미승인** |
| P2 | PLE Gather 최적화 | 원본 `FAST_ROWS=0` 기본 pool 경로, forward에서 unique만 gather→pinned CPU stage→H2D→GPU inverse 복원. 원본은 실제 성능 측정 보고 | `VLLM_PLE_FAST_GATHER=0` 기본 OFF는 기존 dedup→pool; 선택적 small-N inline CPU 경로와 byte-exact matrix PASS. Unique-only H2D, pinned stage, GPU inverse는 **미포팅** | 95.37 GiB BF16 workload/중복률, 캐시 cold/warm, GPU memory, CUDA graph boundary, H2D 정확성·TPS 대조. **P2 미승인** |
| P2 | 별도 vLLM v0.32 호환성 | 공식 v0.32.0 빌드 및 설치 CPU·실 GPU/API/성능 검증. FP8 QSA/PLE 생성자와 v0.32 고유 경로 반영 | **Preview 유지**; v0.32 도입 문서/정적 분석만, 실제 Orcarouter BF16 PLE/overlay 런타임 포팅 **NOT_RUN** | 독립 Track B/이미지에서 PLE constructor, 31 MTP tensor, 로더/quantization, Parser, KV, GPU/메모리 검증. **P2 미승인** |
| P3 | YaRN 500K | 원본 FP8-hybrid 실모델에서 약 **498,994 input tokens**, replay **496,048 cached (99.4%)** 실측. Patch 22 M-RoPE cache window 확장 | 우리 native **240K 수준** 실증, 500K YaRN/M-RoPE/장문 정확성 미검증 | native 262,144 경계와 MTP cache window, 메모리·M-RoPE·retrieval 회귀. **P3 미승인** |
| P3 | Hybrid FP8 변환 | NVIDIA/RadixArk 측면 dense layers를 128x128 blockwise FP8-e4m3로 변환, ModelOpt 양자화 경로 적응 및 원본 속도·메모리 실측 | Orcarouter는 별도 **compressed-tensors 구조**; 동일 converter/ModelOpt dispatch로 취급할 수 없음 | tensor inventory/양자화 config, 변환시 원본 보호, 모델 로딩·품질·성능 검증. **P3 미승인** |

**정확성 주의:** 우리 `device_copy_call_s`는 호스트 `Tensor.to` 호출의 벽시계 시간으로, CUDA에서 완료된 H2D DMA/커널시간을 의미하지 않는다. 원본의 통계·성능 수치를 우리 CPU 계측 median(`147.105/111.585 µs` 소형 warm fixture)과 직접 비교하지 않는다. GPU 동기화가 필요한 원본 코드를 무비판적으로 가져오지 않는다.

## 3. P1 기술 차이와 다음의 가장 작은 가치 있는 단계

### P1-A Prefix-cache: 후보 diff는 좁히되 '실행 중 ABI PASS'로 승격 금지

**2026-10-29 후보 코드 준비:** `src/preview_p1_prefix_candidate.py`에 Preview SHA `mamba_hybrid.py=2e65f1da0a440f11a784bd36afe9206a7a2f674d522c047b838ad604e4c6acc0`, `scheduler.py=c710f49e41e974e5b7b8f1cd2f5fb9722523f4da0165252e16351199ebd03124`를 고정했다. 첫 후보는 `MambaHybridModelState.add_request`의 `_align_mode`/state-slot fill_ 분모를 `self.cache_config.block_size` → `self.cache_config.mamba_block_size`; 두 번째는 `Scheduler._mamba_block_aligned_split`에서 `block_size = self.cache_config.block_size` → `block_size = self.block_size`만 바꾼다. 실제 설치 파일의 SHA·class·method·AST 앵커와 일치하지 않으면 fail-closed. 코드 저장 장소는 일회용 컨테이너의 Python `TemporaryDirectory`뿐이며 **운영 Docker, vLLM 설치 파일, GPU, HTTP 및 캐시·모델 불변**. `p1-prefix-candidate` CPU-only 명시 번들은 **후보 소스 자체의 실제 pinned Preview 대조**로서 기존 Phase5 정적 메타데이터 반복과 다르지만, 실제 `mamba_block_size` 존재·런타임 값·Cache-hit 정합성은 독립 검증 전 여전히 BLOCKED다. **신규 HEAD DGX_NOT_RUN, P2 미착수**.

원본 [patch_mamba_block_size.py](https://github.com/blazux/qwen3.8-Flash-DGX/blob/7e63dbe5761448ea833ed28781c1d32ce0d56f4c/src/patch_mamba_block_size.py)는 두 앵커를 사용한다.

1. `v1/worker/gpu/model_states/mamba_hybrid.py`: 이전 cache-config block 대신 `mamba_block_size`로 state-slot 계산. **v0.32의 native worker 분기 존재 여부는 원본 포트의 관측**이며 우리 Preview와 동일하다는 증거가 아니다.
2. `v1/core/sched/scheduler.py`: `_mamba_block_aligned_split`에서 `self.cache_config.block_size` 대신 `self.block_size`(그룹 블록 LCM을 반영한 Scheduler 값)를 사용. **우리 Preview의 실제 분기/그룹별 block-size/DCP가 검증되기 전 값 1,600이나 8을 하드코딩하지 않는다.**

원본 [README: Prefix caching now works](https://github.com/blazux/qwen3.8-Flash-DGX/blob/7e63dbe5761448ea833ed28781c1d32ce0d56f4c/README.md)는 자사 셋업에서 cache-hit 시 state index `399`(잘못) vs `1`(정상) 및 반복 약 20K prefix TTFT `~14s → ~1.4s`를 보고한다. **우리 운영의 `block_size=8` 메트릭은 시작 시 공개된 단일 Config 값일 뿐 실 오류·선택 Scheduler·Mamba 그룹 구성의 증거가 아니다.**

현 상태에선 소스 diff와 **기본 OFF/비활성 패치 후보**까지는 별도 기능 작업으로 검토할 수 있지만, 실제 Prefix-cache correctness PASS는 active in-process observer 또는 자원·권한 분리된 후보 GPU/모델에서의 cache-hit 증거가 필요하다. 반복 metadata polling/CPU synthetic test 추가만으로는 해결하지 않는다.

### P1-B PLE: 기존 CPU 기능은 완료, 운영 성능을 주장하지 않음

원본 [PLE mmap](https://github.com/blazux/qwen3.8-Flash-DGX/blob/7e63dbe5761448ea833ed28781c1d32ce0d56f4c/src/vllm_ple_mmap.py)은 unique rows 선행 축소, pinned buffer 및 GPU-side inverse를 사용한다. 우리의 [`src/vllm_ple_mmap.py`](../src/vllm_ple_mmap.py)는 기존 전체 행 결과의 page-able H2D 구조를 유지한 채 **계측만 기본 OFF/opt-in**으로 추가했다. 실모델 H2D 개선은 **별도 P2 Gather 목표**이지 P1 계측 PASS의 일부가 아니다.

### P1-C Tool/Responses: 통합 CPU와 실 HTTP 검증을 구분

원본 [v0.32 포트 설명](https://github.com/blazux/qwen3.8-Flash-DGX/blob/7e63dbe5761448ea833ed28781c1d32ce0d56f4c/docs/VLLM-032.md)에는 실제 API 및 live streaming 검증, 알려진 parser/schema 실패가 기록돼 있다. 우리는 Preview 원본의 temporary overlay에서 **14-case native CPU Pydantic wire roundtrip PASS**까지만 확인했다. 별도 승인 없는 port-8000 API 요청/실모델 추론/운영 overlay 설치는 하지 않는다.

## 4. 원본의 추가 변화(8개 목표 외)

- **Patch 22, M-RoPE long-context MTP window:** native 262,144 위치를 넘는 YaRN+MTP 경로에서 위치 캐시 크기를 보강. 원본 [issue #60 검증 JSON](https://github.com/blazux/qwen3.8-Flash-DGX/blob/7e63dbe5761448ea833ed28781c1d32ce0d56f4c/tests/vllm032/validation/issue60-20261022/VALIDATION.json)에서는 baseline cache 크기 부족을 CPU/생성자에서 입증했지만 **기존 baseline GPU crash 자체는 해당 실행에서 재현하지 못함**. 이 수정은 미래의 P3 YaRN 검토시 독립 검증 대상이고 P1/P2의 실행 승인이 아니다.
- **Patch 23, DFlash2:** 이전 upstream PIN 이후 [7 commits / 8 files diff](https://github.com/blazux/qwen3.8-Flash-DGX/compare/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa...7e63dbe5761448ea833ed28781c1d32ce0d56f4c)로 추가된 `dflash` 프로필과 target-side integration. 원본 [README](https://github.com/blazux/qwen3.8-Flash-DGX/blob/7e63dbe5761448ea833ed28781c1d32ce0d56f4c/README.md)는 원본 설정의 K=4에서 **57.0 vs 45.2 tok/s**(MTP=2, 단일 요청)와 더 큰 GPU memory 사용을 보고한다. **우리 8개 우선순위에 포함되지 않으며 새 착수·성능 주장 금지**.
- **원본 연구와 성과 전이 제한:** QSA deterministic top-k, FP8 KV, compile cache, concurrent profile 등 추가 기능은 현재 계획으로 편입하지 않았다. 원본의 NVIDIA/hybrid GX10 수치가 직접 BF16 Orcarouter에 유효하다고 가정하지 않는다.

## 5. 다음 작업 우선순위와 변경 통제

1. **P1 Prefix-cache(우선):** pinned Preview 설치 원본과 upstream 위 두 함수의 실제 body/조건·표현 단위 1:1 비교 → Preview에 필요한 수정이 존재할 때만 **비활성·격리된 후보 diff**, fail-closed 계약 및 최소 독립 회귀 준비. 이미 정리한 실제 ABI 차단 원인은 재조사하지 않는다. **본 비교 자체로 패치 생성/운영 반영 승인 없음**.
2. **P1 계측:** CPU 검증된 opt-in 구현은 유지. 운영 계측 및 실제 BF16 PLE 성능은 별도 자원·서비스 변경 승인 뒤에만 검증한다.
3. **P1 Tool/Responses:** 이미 CPU 통합 PASS. 이후 실제 Pi Agent Chat/Responses HTTP/streaming API와 모델 추론은 전용 승인·격리/rollback 조건 후 진행. 완전 검증으로 승격하지 않는다.
4. **P2/P3:** 명시적 별도 선택 전 자동 시작하지 않는다. v0.32 전체 포팅은 **Track B 별도 브랜치**이며 이 P1 브랜치의 실행 작업과 혼합하지 않는다.

**절대 실행 금지(현 승인 기준):** 기존 운영 컨테이너 `qwen38-flash-orca-uncensored-bf16-mtp` stop/restart/exec/replace, port 8000/API 추론 부하, 모델/가중치/HF cache 수정, 새 대형 GPU 모델, CUDA/Triton 벤치, 지난 PRE-B 12×3 반복, CI 실행, 기능 PR/merge, P2/P3 자동 진행. 실제 장비 증거와 Source Manifest/GitHub 문서-only 검증을 혼합하지 않는다.

## 6. 원본·로컬 증거 링크

- 원본 [README](https://github.com/blazux/qwen3.8-Flash-DGX/blob/7e63dbe5761448ea833ed28781c1d32ce0d56f4c/README.md), [Dockerfile](https://github.com/blazux/qwen3.8-Flash-DGX/blob/7e63dbe5761448ea833ed28781c1d32ce0d56f4c/Dockerfile), [vLLM v0.32 포팅 및 검증](https://github.com/blazux/qwen3.8-Flash-DGX/blob/7e63dbe5761448ea833ed28781c1d32ce0d56f4c/docs/VLLM-032.md), [Tool/Responses 검증](https://github.com/blazux/qwen3.8-Flash-DGX/blob/7e63dbe5761448ea833ed28781c1d32ce0d56f4c/docs/SAFE-OUTPUT.md), [MTP draft vocabulary](https://github.com/blazux/qwen3.8-Flash-DGX/blob/7e63dbe5761448ea833ed28781c1d32ce0d56f4c/src/patch_mtp_draft_vocab.py), [FP8 converter](https://github.com/blazux/qwen3.8-Flash-DGX/blob/7e63dbe5761448ea833ed28781c1d32ce0d56f4c/tools/fp8_convert.py).
- 우리 [BF16 PLE 모델/호환성 정본](COMPATIBILITY.md), [Phase 4 CPU PLE](BLAZUX-PHASE4-DGX-VALIDATION-RESULTS-20261027.md), [Phase 5 Prefix ABI 소스 분석](BLAZUX-PHASE5-DGX-NARROW-BLOCK-FLOW-RESULTS-20261027.md), [P6-A 실 ABI 차단 근거](BLAZUX-PHASE6-A5-ACTIVE-ABI-OBSERVABILITY-DECISION-20261028.md), [2026-10-29 DGX 검증 장부](BLAZUX-PHASE6-RESULTS.md).

**문서 적용 규칙:** 본 비교 기록은 고정 SHA의 정적 source + 각자 공개/사용자 제공 실측 증거 범위에서만 유효. 이후 upstream HEAD 변경·우리 브랜치 HEAD 변경 시 새 비교와 새로운 실증이 필요하며, **이번 docs/Manifest 커밋 자체는 DGX_NOT_RUN**.
