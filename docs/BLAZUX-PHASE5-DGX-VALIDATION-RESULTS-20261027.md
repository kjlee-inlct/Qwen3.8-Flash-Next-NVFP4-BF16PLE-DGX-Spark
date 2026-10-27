# Track A Phase 5 — DGX 통합 오프라인 시험·CPU 측정·vLLM 설치 소스 조사 결과

> **기록일:** 2026-10-27 (Asia/Seoul). **판정:** `PHASE5_DGX_CPU_OFFLINE_PASS / UNIT_208_XFAIL_0 / SOURCE_144_144_PASS / 12_SYNTHETIC_CPU_BENCH_POINTS / VLLM_SOURCE_INVENTORY_CAPTURED / ACTUAL_ENGINE_ABI_NOT_VERIFIED`.
>
> **사용자가 제공한 DGX Spark 터미널 로그**를 근거로 한다. 로그가 실제 확인한 코드는 `feature/blazux-phase5-correctness-mtp-offline@01c9eb6ba311e3ace5f68ecc49fa56f8e0b37d94`이다. 보고서와 Manifest를 새로 추가하는 **후속 문서 전용 Git SHA는 DGX에서 재시험한 SHA가 아니다.** GitHub connector가 DGX의 시험을 직접 실행한 것도 아니다.
>
> 실제 운영 Docker의 구동 상태, 실 모델 payload, GPU/실 PLE 95.37GiB, 실제 cached/uncached prefix correctness, installed vLLM Parser/Responses runtime behavior, MTP reduced draft acceptance/품질, 모델 TPS·TTFT/성능 A/B 및 CI는 **NOT_VERIFIED / NOT_RUN**.

## 1. Provenance / Source Gate

| 항목 | 관측 결과 |
|---|---|
| 개인 Repository | `kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark` |
| 검증 브랜치 | `feature/blazux-phase5-correctness-mtp-offline` |
| **정확한 실기 검증 HEAD** | `01c9eb6ba311e3ace5f68ecc49fa56f8e0b37d94` |
| Phase 4 확정 부모 | `69860277122dffe3082c5b065e4361a571317a8e` |
| Source Manifest | `PASS_SOURCE_ONLY: 144 tracked file(s)` (144/144) |
| Full unittest | `Ran 208 tests in 0.318s`; `OK`; `PHASE5_UNIT_PASS=208; XFAIL=0` |
| Source AST | `PHASE5_SOURCE_AST_OK` |
| Bundled source gate | `PASS: PHASE5_OFFLINE_ORACLES_AND_SOURCE_CONTRACTS` |
| Bundled CPU finish | `PASS: PHASE5_BUNDLED_DGX_OFFLINE_EXECUTION` |
| Untracked/ignored & Docker | Source verifier가 명시적으로 **검증 대상에서 제외** |
| GitHub Actions CI | 별도 workflow run 없음. 실제 CI PASS 아님 |

- 위 오프라인 wrapper는 clean/source/branch/origin/Phase4 조상, deployment manifest/Mocks/unittest/Bash syntax/publication audit를 fail-fast로 수행한다. 사용자가 제공한 자료는 마지막 결과 중심이므로 개별 Mock 카운트는 이 증거에서 확정하지 않는다.
- 새로 추가한 표준 라이브러리 oracle 14개까지 포함하여 전체 **208/208 PASS 및 XFAIL=0**. 하지만 여기의 Prefix/Tool/MTP 검사들은 실제 설치 엔진이 아닌 독립 reference/클라이언트 위험 경계 시험이다.

## 2. BF16 PLE 기존 경로 및 4가지 독립 flag 정합성

```text
PASS: BF16 mmap gather/torch forward byte-exact workers=1 chunk=1024
PASS: BF16 mmap gather/torch forward byte-exact workers=4 chunk=2
PHASE3_PLE_DUPLICATE_GUARD_ALL_OK
PHASE2_PLE_CPU_ALL_OK
PASS: PHASE4_FLAG_MATRIX fast=0 stats=0 byte_exact=1
PASS: PHASE4_FLAG_MATRIX fast=1 stats=0 byte_exact=1
PASS: PHASE4_FLAG_MATRIX fast=0 stats=1 byte_exact=1
PASS: PHASE4_FLAG_MATRIX fast=1 stats=1 byte_exact=1
PHASE4_CPU_MATRIX_ALL_OK
```

Phase 2~4의 small synthetic BF16 safetensors 기존/새 경로 회귀 및 Phase3 중복 샤드 거부 검사가 Phase5 실기 실행에서도 통과했다. `VLLM_PLE_FAST_GATHER`, `VLLM_PLE_PHASE_STATS`는 **독립 기본 OFF**이며 둘 다 ON에서도 반환값 바이트 일치. 실제 서빙 패키지에 이 옵션이 배포됐다는 증거는 아니다.

## 3. Phase5 합성 CPU 마이크로벤치마크 — 실제 12조건 수치

**환경·해석:** `src/test_ple_phase5_bench_cpu.py`의 실제 합성 13행×7열 BF16 file-backed table, warm page cache, FAST ON/OFF, **STATS OFF**, 4 warmup + 21 timed iteration per flag, row counts 16/64/256/512/513/1024, ID 후보 범위 `effective_unique_limit=1` 또는 `13`(실측 유일 ID 개수 자체는 아님). 단위는 **ms**이며 p95는 정렬한 21개 샘플의 20번째 값으로 계산한다. 모든 항목에서 `byte_exact=true`, `gpu=NOT_RUN`. Phase5 로그의 표준출력에 기록된 수치만 옮겼다.

| N rows | ID 후보 범위 | FAST OFF 중앙값 ms | FAST ON 중앙값 ms | OFF p95 ms | ON p95 ms |
|---:|---:|---:|---:|---:|---:|
| 16 | 1 | 0.01259 | 0.00794 | 0.01387 | 0.00816 |
| 16 | 13 | 0.21798 | 0.01669 | 0.42451 | 0.01720 |
| 64 | 1 | 0.01288 | 0.00864 | 0.01342 | 0.00885 |
| 64 | 13 | 0.14293 | 0.01813 | 0.23445 | 0.01869 |
| 256 | 1 | 0.01512 | 0.01181 | 0.01560 | 0.01232 |
| 256 | 13 | 0.12529 | 0.02323 | 0.26256 | 0.02354 |
| 512 | 1 | 0.01846 | 0.01650 | 0.01888 | 0.01688 |
| 512 | 13 | 0.14213 | 0.03059 | 0.16838 | 0.03155 |
| 513 | 1 | 0.01830 | 0.01835 | 0.01872 | 0.01888 |
| 513 | 13 | 0.24049 | 0.18542 | 0.42883 | 0.21027 |
| 1024 | 1 | 0.02422 | 0.02422 | 0.02470 | 0.02461 |
| 1024 | 13 | 0.18338 | 0.17371 | 0.25523 | 0.22229 |

- **관측:** `N <= 512`인 8개 조건은 FAST ON 중앙값이 FAST OFF보다 낮다. 특히 N=16, 후보 13 조건은 `0.21798→0.01669 ms`로 차이가 크다. 이 범위에서도 CPU threadpool overhead·캐시·입력 중복 분포가 지배할 수 있으므로 **실 서비스 가속 배수라고 주장하면 안 된다**.
- **임계치:** 현재 FAST threshold는 기본 512이므로 N=513/1024에서는 정상적으로 기존 경로에 돌아간다. 그 조건의 OFF/ON 측정값 차이는 별도 최적화 코드 실행의 우위를 뜻하지 않으며, wallclock 변동과 측정 순서 영향을 배제하지 못한다.
- **비교 한계:** 소형 13×7 fixture는 실제 `128 shard×160` PLE, 95.37GiB mmap, NVMe page faults, pinned host staging, async GPU transfer, 동시 사용자 처리 및 모델 inference/TPS/TTFT를 대표하지 않는다. 정확한 DGX CPU 하드웨어 affinity/동시 CPU load 등은 별도 원문 미제공. **성능 개선 GO 결정은 보류**.
- 로그 종료: `PHASE5_SYNTHETIC_CPU_BENCH_ALL_OK`.

## 4. 설치된 vLLM의 read-only source inventory

사용자가 `src/phase5_vllm_source_inventory.py`에서 받은 원문은 **`package=LOCATED_READ_ONLY`**, 종료 `PHASE5_VLLM_SOURCE_INVENTORY_DONE_NOT_ABI_CERTIFIED`. 파일을 import/monkeypatch한 게 아니라 설치 경로의 Python source bytes SHA256과 AST symbol names를 기록한다.

| 조사지 (조사지의 고정 경로 기준) | 상태 | 실제 DGX 출력 SHA256 |
|---|---|---|
| `v1/worker/gpu/model_states/mamba_hybrid.py` | PRESENT_SOURCE_PARSEABLE | `2e65f1da0a440f11a784bd36afe9206a7a2f674d522c047b838ad604e4c6acc0` |
| `v1/core/sched/scheduler.py` | PRESENT_SOURCE_PARSEABLE | `c710f49e41e974e5b7b8f1cd2f5fb9722523f4da0165252e16351199ebd03124` |
| `parser/qwen3.py` | PRESENT_SOURCE_PARSEABLE | `8a7ee658322de7b736ea5b0f802d70dd07a124b5878b4f8ad2f99eca8e1d35fb` |
| `parser/engine/parser_engine.py` | PRESENT_SOURCE_PARSEABLE | `f837bd5ae7bf759732a7d829209f93444b5692746d981509630c9bd3fcb39edb` |
| `parser/engine/streaming_parser_engine.py` | PRESENT_SOURCE_PARSEABLE | `d00aba98ad26a2593e022a1faf5d048348d892822f75be40d19cf1dd522570f2` |
| `entrypoints/openai/responses/serving.py` | PRESENT_SOURCE_PARSEABLE | `d5fdb9ca62fa767d6feb61f6b3f5280f288051eea8605d27afa698cc00067968` |
| `model_executor/models/qwen3_8_flash_next/nvidia/mtp.py` | **ABSENT_OR_RELOCATED** | 없음 |
| `model_executor/models/qwen3_8_flash_next/nvidia/ple_layer.py` | **ABSENT_OR_RELOCATED** | 없음 |

**관찰한 주요 AST 이름:** `MambaHybridModelState`, `Scheduler._mamba_block_aligned_split`, `Scheduler._get_local_prefix_cache_hit`, `ParserEngine`, `Qwen3Parser`, `StreamingParserEngine`, `OpenAIServingResponses`, `_process_simple_streaming_events`. 단순 이름 출현은 해당 함수 인자·block-size 의미·사용하는 parser 설정·실제 state restore 동작의 인증이 아니다.

- **중요한 차단:** `qwen38_mtp`/ `qwen38_ple`의 *조사기가 가정한 경로*에서는 파일을 찾지 못했다. 따라서 **재배치 가능성을 확인하기 전 실제 설치 모듈 부재라고 결론내리지 않는다**. 안전한 read-only 경로 탐색·실제 클래스 파일 SHA 확인이 뒤따라야 한다.
- Parser Engine inventory는 이름 목록에서 blazux patch의 `_normalize_tool_arguments` 같은 helper를 제시하지 않았다. patch 미적용을 확정하기보다는 정확한 고정 소스 본문과 class method signature/anchor를 비교한 뒤 판단할 것.
- `MambaHybridModelState`와 `Scheduler._mamba_block_aligned_split` 존재는 prefix-state 로딩이 1600을 올바르게 쓰는지 설명하지 못한다. 실제 cached-vs-uncached 출력·state checksum 테스트는 별도 승인 필요.

## 5. 완료 판정 / 미완료 / 다음 승인 Gate

**Phase5 계획된 synthetic CPU/source Gate: PASS**, 그리고 read-only 설치 소스 목록은 확보했다. **P1 Prefix-cache 및 Tool/Responses 기능 자체가 구현·검증 완료인 것은 아니며, P2 MTP reduced draft vocabulary는 미적용/미검증**이다.

다음 순서는 **새 Phase 번호를 만들지 않고 같은 Phase 5 내부에서** 설치 엔진 후보 경로/함수·메서드 시그니처/실제 source anchor를 read-only로 탐색하고, 대상 소스가 일치하면 mock/fragment-based parser fixture와 SSM state 정합성 테스트 설계를 검토하는 것이다. 운영 추론/HTTP endpoint 테스트 및 GPU checkpoint load/성능 A/B는 사용자의 별도 명시적 승인 전 금지한다. vLLM 0.32 이식은 계속 별도 Track B.

**PR/Merge:** 현재 필요 없음. 사용자 리뷰가 필요해지면 `head=feature/blazux-phase5-correctness-mtp-offline` → `base=feature/blazux-phase4-ple-cpu-bundle`로 **비병합 Draft PR**만 가능. 그 PR도 merge하지 않는다. `main` 대상으로 PR/merge/cherry-pick/rebase/squash/sync 영구 금지. P0/Phase 1~4 immutable.
