# Track A Phase 3 — DGX 실측 검증 결과: G2-01 CPU 회귀 완료

> **기록 날짜:** 2026-10-27 (Asia/Seoul). **판정:** `PHASE3_G2_01_DGX_OFFLINE_PASS / XFAIL_0 / PLE_CPU_BYTE_EXACT_PASS / PRODUCTION_DEPLOYMENT_NOT_DONE / GPU_NOT_RUN / CI_NOT_VERIFIED`.
>
> **증거 출처:** 사용자가 제공한 DGX 터미널의 `scripts/phase3-check-offline.sh` 최종 로그 및 후속 `src/test_ple_phase2_cpu.py` 출력 4줄. GitHub 플러그인으로 사용자 DGX 프로세스를 직접 실행하거나 원본 컨테이너의 런타임 상태를 검사한 것은 아니다.
>
> **실측 소스 HEAD:** `cb1de387b09786d6be35fec838c6549a78e5417c`. 이 결과 문서와 인수인계·Source Manifest만 추가한 *문서 전용 후속 커밋*에서는 DGX 시험을 재실행하지 않았다. GitHub tree/Blob 검증은 별도 확인한다.

## 1. Branch provenance / 격리 정책

| 항목 | 값 |
|---|---|
| 개인 저장소 | `kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark` |
| Phase 3 | `feature/blazux-phase3-ple-duplicate-shard-guard` |
| 실제 소스 검증 HEAD | `cb1de387b09786d6be35fec838c6549a78e5417c` |
| Phase 3 분기 부모 (Phase 2 확정) | `76588845d7742703475ae1f49d5e8f5c174bb77a` |
| Phase 1 확정 HEAD | `a50fc53721f3d23325dca44eb799f0f388d65951` |
| P0 불변 HEAD | `966ec7cf0741734b844b1cea938d56678a756469` |
| 보호 대상 main | `2847e39b4131eb8aff78bf86ffce98892401722a` (기록 시 원격 재확인) |
| 비교 blazux pin | [외부 고정 소스](https://github.com/blazux/qwen3.8-Flash-DGX/tree/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa), `8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa` |

**실험 내용:** Phase 2의 알려진 `G2-01` 결함(여러 safetensors 헤더에 동일 PLE `shard_N` 존재 시 dictionary 덮어쓰기)을 Phase 3의 `src/vllm_ple_mmap.py::_find_shards`에서 중복 인덱스 발견 즉시 `ValueError`로 중단하게 보완. 정상 PLE gather/forward, MTP 및 vLLM 런타임 패치 경로는 변경하지 않았다. 새 Docker image 빌드, 서빙 교체, 운영 모델 로딩은 이 단계 범위 밖.

## 2. 실기 A: Source Manifest 및 Python 회귀

사용자가 제공한 Phase 3 실행 로그에 의하면 다음 결과가 확인됐다.

```text
----------------------------------------------------------------------
Ran 189 tests in 0.818s

OK
PHASE3_UNIT_PASS=189; XFAIL=0
PASS_SOURCE_ONLY: 132 tracked file(s)
  branch=feature/blazux-phase3-ple-duplicate-shard-guard HEAD=cb1de387b09786d6be35fec838c6549a78e5417c
  NOTE: Untracked/ignored files, model payload, Docker and runtime are NOT verified
PASS: PHASE3_G2_01_OFFLINE_CONTRACTS_XFAIL_0
NOT_RUN: GPU inference, vLLM integration, runtime throughput, CI
```

- `scripts/phase3-check-offline.sh`는 정확한 fork origin/branch/Phase 2 부모 조상/clean checkout, non-strict Source Manifest, deployment manifest, Wizard mocks, full unit, Bash syntax, publication audit, 최종 Manifest를 **fail-fast** 순서로 실행한다. 마지막 PASS가 있으므로 전체 스크립트는 종료 성공했다. 단, 이 메시지에 전체 개별 출력이 없으므로 Mock 수 등은 이전 Phase에서의 실측 숫자로 대체하지 않는다.
- **전체 단위시험 189/189 / XFAIL=0.** Phase 2의 `@unittest.expectedFailure`가 제거되고 두 헤더의 duplicate shard index 검증 및 index.json 사용 회귀가 시험된다.
- **Source Manifest 132/132 PASS.** 해당 기록은 위 정확한 실측 SHA 기준이다. Source verifier 자체 안내대로 ignored/untracked payload 및 runtime 상태는 보증하지 않는다.
- 명시된 `GPU inference, vLLM integration, runtime throughput, CI`는 **NOT_RUN**으로 유지한다.

## 3. 실기 B: 실제 PyTorch BF16 PLE CPU 경로

사용자가 별도로 제공한 신규 CPU fixture의 최종 출력:

```text
PASS: BF16 mmap gather/torch forward byte-exact workers=1 chunk=1024
PASS: BF16 mmap gather/torch forward byte-exact workers=4 chunk=2
PHASE3_PLE_DUPLICATE_GUARD_ALL_OK
PHASE2_PLE_CPU_ALL_OK
```

- 실제 `src/vllm_ple_mmap.py` 모듈을 import하는 `src/test_ple_phase2_cpu.py`에서 작은 합성 BF16 safetensors에 대한 NumPy mmap gather와 `torch.bfloat16` forward가 바이트 단위로 기준값에 일치한다.
- workers=1/chunk=1024, workers=4/chunk=2의 정상 경로가 모두 일치한다. 별도 indexed second-file duplicate 샤드 구성에서 `_find_shards`가 기대한 `ValueError`를 발생시켜 `PHASE3_PLE_DUPLICATE_GUARD_ALL_OK`가 출력되는 경로를 확인했다.
- 사용자는 출력 4줄을 제공했으며, **이후 메시지에는 실행 명령 전체/이미지 digest/실행 사용자/컨테이너 ID가 새로 포함되지는 않았다.** 따라서 앞서 제시한 격리 CPU-only 실행 절차와 별개로, 실제 관측 증거가 보장하는 것은 이 fixture의 출력이다. 기존 운영 Docker에서 이미지 교체·서빙 재시작이 있었다고 해석하지 않는다.
- CPU 합성 시험은 실제 95GiB PLE tensor의 전체 데이터·NVMe page fault·GPU stream/pinned H2D·CUDA graph·speculative decoding 정확성·TPS/TTFT를 입증하지 않는다.

## 4. Gate 3 판정과 열린 위험

| 구분 | 상태 | 근거 및 경계 |
|---|---|---|
| `G2-01` 중복 PLE shard index 감지 | **CLOSED_FOR_SYNTHETIC_CPU_REGRESSION** | no-index 및 indexed header CPU 회귀, XFAIL 0, 실제 `_find_shards` negative case PASS |
| PLE BF16 byte-exact 정상 경로 | **PASS_FOR_SMALL_SYNTHETIC_CPU** | workers 1/4 모두 동일 bytes |
| 전체 Project offline regression | **PASS** | 189 tests, XFAIL 0, Source Manifest 132 |
| 실제 Docker image / GPU serving 적용 | **NOT_DEPLOYED / NOT_RUN** | 운영 서비스를 변경하지 않았음 |
| JSON 중복 키·corrupt index·임의 header/payload 검증 | **별도 범위** | G2-01의 숫자 인덱스 중복만 직접 방어함 |
| MTP 실제 체크포인트 tensor shapes, vLLM API/ABI | **NOT_VERIFIED** | 기존 offline name/dtype 및 static comparison과 구분 |
| GPU 성능 A/B, KV/QSA/Mamba state, streaming/parser | **NOT_RUN** | 이후 Phase 독립 검증 및 별도 승인 필요 |
| GitHub Actions CI | **NOT_VERIFIED** | Actions run 0건 |

**결론:** Phase 3에 정의된 **G2-01 CPU 오프라인 회귀 Gate 완료**. 이것을 **실 운영 적용 승인**이나 **blazux TPS 향상 증거**로 확대 해석하지 않는다. 다음 Phase가 필요하면 Phase 3의 기록 확정 HEAD에서 새 자식 브랜치로 분기한다.

## 5. GitHub/PR·Merge 정책

- 사용자 DGX에서 실제 실행한 소스 커밋 `cb1de387b09786d6be35fec838c6549a78e5417c`와 본 보고서·handoff·Manifest를 추가한 후속 docs-only 커밋의 SHA를 엄격히 구분한다.
- 이전의 `main`, P0, Phase 1, Phase 2는 모두 **고정·불변**. 새 Phase에서도 `main` 대상 PR/merge/cherry-pick/rebase/squash/sync 금지. 배포는 별도의 명시적 승인 없이는 금지한다.
- 리뷰가 정말 필요할 때 허용 가능한 비교는 `base=feature/blazux-phase2-offline-fixtures`, `head=feature/blazux-phase3-ple-duplicate-shard-guard`의 **Draft PR (review only)**이며 해당 PR도 **merge하지 않는다**. 지금은 PR/merge 필수 아님.
