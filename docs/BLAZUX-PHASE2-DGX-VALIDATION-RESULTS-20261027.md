# Track A Phase 2 — 실제 DGX 오프라인 검증 결과 (2026-10-27)

> **판정:** `GATE2_DGX_OFFLINE_COMPLETE_WITH_KNOWN_XFAIL_1`. 합성 BF16 경로와 오프라인 단위시험 성공. **중복 PLE 샤드 감지 결함(G2-01)은 미해결**이므로 fail-closed 안전성 전체 PASS가 아니다. GPU inference/A·B, vLLM serving, blazux runtime 최적화와 CI는 `NOT_RUN`/`NOT_VERIFIED`.
>
> 사용자 제공 DGX Spark 터미널 로그 및 이후 CPU fixture stdout에 근거하며 GitHub 플러그인은 DGX에서 명령을 재실행하지 않았다. 실측은 **Phase 2 코드 HEAD `fd9d8cfb6938b82ae979c9804386ffbe084cc81d`** 대상으로 기록한다. 본 결과 문서/Manifest를 더한 docs-only 후속 커밋 SHA는 DGX에서 아직 재검증하지 않았다.

## 1. 재현 계보와 시험 경계

| 항목 | 검증 가능한 사실 |
|---|---|
| 날짜/하드웨어 | 2026-10-27, 사용자 DGX Spark 실기 로그 (정확 시작 시각 제공 없음) |
| 개인 GitHub | `kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark` |
| Phase 2 브랜치 | `feature/blazux-phase2-offline-fixtures` |
| 실제 오프라인 소스 HEAD | `fd9d8cfb6938b82ae979c9804386ffbe084cc81d` |
| Phase 1 확정 부모 | `a50fc53721f3d23325dca44eb799f0f388d65951` |
| P0 부모 기준 | `966ec7cf0741734b844b1cea938d56678a756469` |
| 외부 참조 blazux | [blazux/qwen3.8-Flash-DGX](https://github.com/blazux/qwen3.8-Flash-DGX/tree/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa) @ `8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa` |
| 가상 Python 및 vLLM 운영 컨테이너 | 기존 운영 컨테이너에는 패키지 설치/이미지 재빌드하지 않음. PyTorch/NumPy는 이전에 확인된 운영 이미지 환경을 이용한 별도 CPU-only fixture 실행 절차를 안내했음 |

## 2. 실기 A: Phase 2 소스·Mock·Unit 계약

사용자는 전용 Phase 2 디렉터리에서 `scripts/phase2-check-offline.sh`를 실행했다. 해당 스크립트는 `set -Eeuo pipefail`, 개인 Fork origin, Phase 2 branch, clean source, Phase 1 부모 SHA의 조상 여부를 검사한 뒤 단계별 검증을 수행한다. 사용자 로그는 마지막 `PASS: PHASE2_OFFLINE_SOURCE_AND_STDLIB_CONTRACTS`까지 정상 종료했다.

| 실행 범주 | 사용자 제공 결과 | 판정 |
|---|---|---|
| 정확한 브랜치/HEAD | `feature/blazux-phase2-offline-fixtures` @ `fd9d8cfb...` | PASS |
| `scripts/verify-source-state.sh` | `PASS_SOURCE_ONLY: 129 tracked file(s)` **시작/종료 두 번** | 129/129 PASS |
| `scripts/manifest.sh validate` | `manifest OK: kjlee-qwen38-dgx-spark-wizard, 4 target(s)` | PASS |
| `scripts/run-mock-tests.sh` | `Ran 38 tests in 0.014s; OK` | 38/38 PASS |
| `python3 -m unittest discover -s tests -v` | `Ran 188 tests in 0.314s; OK (expected failures=1)` | **정상 완료 / known XFAIL=1** |
| Bash 구문 및 공개 소스 감사 | fail-fast 스크립트에서 해당 명령 후 최종 PASS | PASS (개별 출력 없음) |
| 신규 PLE/BF16 fixture | 샤드 경계/오프셋/dtype·width·크기 불일치, 단일/누락 shard 등 | 테스트 동작 정상 (known XFAIL 별도) |
| MTP BF16 guard / QSA CPU oracle | 31/31 이름·dtype 경계와 독립 Top-K oracle 검사 | 해당 Unit tests 정상 |

**해석:** 188개 중 1개는 `expected failure`이고 187개는 정상 성공했다. 테스트 runner가 `OK`라고 끝나더라도 **G2-01 중복 샤드 무결성 검사가 통과한 것은 아니다**. 현재 테스트에서 발견된 동작을 그대로 기록한다.

## 3. 실기 B: 신규 PLE mmap/PyTorch BF16 바이트 단위 테스트

이전 메시지에서 제시한 전용 CPU-only 임시 컨테이너 실행 명령은 Phase 2 고정 SHA/브랜치를 확인하고 `--network=none --runtime=runc --read-only --cpus=2 --memory=2g --pids-limit=128` 및 read-only 소스 bind mount, `CUDA_VISIBLE_DEVICES=-1`를 사용한다. 사용자는 그 신규 fixture 실행 종료로 아래 출력 3줄을 제출했다. **이번 메시지에는 컨테이너 실행 전체 명령이나 이미지 ID/버전 로그가 포함되지 않으므로 이전에 제시한 시험 절차를 사용한 것으로 해석하되, 그 세부값의 현장 재확인을 주장하지 않는다.**

```text
PASS: BF16 mmap gather/torch forward byte-exact workers=1 chunk=1024
PASS: BF16 mmap gather/torch forward byte-exact workers=4 chunk=2
PHASE2_PLE_CPU_ALL_OK
```

- `src/test_ple_phase2_cpu.py`는 실제 기존 `src/vllm_ple_mmap.py`를 import하고 합성 safetensors 13×7/4 shards를 temp에 만든다. 중복/역순/샤드 경계/마지막 짧은 샤드를 통과하는 row gather를 CPU oracle과 **bytes-equivalent** 확인한다.
- workers=1/chunk=1024 및 workers=4/chunk=2의 결과가 각각 동일한 oracle과 일치한다. `torch.bfloat16` placeholder forward 및 결과 `uint8` bytes 전체 비교, 빈 ID, 음수/범위 초과 인덱스 거부를 검사한 뒤 `PHASE2_PLE_CPU_ALL_OK`로 끝난다.
- 테스트의 범위는 기존 PLE CPU 경로다. 실제 모델 weights, 95GiB PLE page fault 특성, CUDA pinned staging, GPU inverse, asynchronous stream race, CUDA graph, inference output, TPS는 검증한 적 없다.

## 4. 미해결 위험/Go-No-Go

| ID | 상태 | 필요한 후속 조치 |
|---|---|---|
| `G2-01` duplicate PLE shard index | **OPEN / XFAIL=1** | `src/vllm_ple_mmap.py::_find_shards()`가 여러 safetensors 헤더에서 동일한 shard index를 발견할 때 fail closed하지 않을 수 있다. Production source 수정은 Phase 2에서 하지 않았다. 후속 독립 Phase에서 수정을 검토하고 negative test의 `expectedFailure` 제거 후 실제 PASS 증명 |
| PLE BF16 CPU byte equivalence | **PASS** (small synthetic only) | GPU/stream/real checkpoint는 별도 검증 |
| MTP 31/31 | **Unit contract PASS** | 실제 tensor shape/load, MTP acceptance 및 깊이별 처리 미검증 |
| QSA CPU oracle | **Unit reference PASS** | vLLM exact TopK 커널/동점·NaN 정책 및 품질 검증 미실행 |
| CI | **CI_NOT_VERIFIED** (GitHub Actions 0) | 사용자의 CI 보류 정책 유지 |

**Gate 2 결정:** 원래 Phase 2 Gate 2에 정의된 모든 *오프라인 시험 실행* 조건은 충족했다. 그러나 `G2-01`을 해결하지 않았으므로 **오프라인 검증 완료 ≠ fail-closed 안전성 승인**. 이후 Phase에 들어간다면 최우선 작업은 중복 샤드 방어/회귀의 별도 구현이며, 실 운영 배포는 여전히 금지한다.

## 5. 커밋·운영·PR 경계

- 이 실기 결과는 코드를 변경하기 전 HEAD `fd9d8cfb...`의 정적/CPU 시험이다. 이 보고서·Gate 2 문서·handoff·Source Manifest만 추가하는 **새 docs-only 커밋은 다른 SHA**이므로 해당 후속 SHA에서 사용자 DGX 188/188이 재실행되었다고 말하지 않는다.
- GitHub tree `path/mode/blob` 전수 대조는 docs-only commit 직후 수행한다. `main`, P0, Phase 1은 불변; 운영 컨테이너·모델·HF cache·포트는 절대 수정하지 않는다.
- **PR 시점:** Phase 2 결과 리뷰가 필요할 때 `base=feature/blazux-phase1-source-compare`, `head=feature/blazux-phase2-offline-fixtures`로 *draft/unmerged review PR*만 가능하며 현재는 필요하지 않다. **해당 PR도 merge 금지.** `main` 대상으로 PR/merge/squash/cherry-pick/rebase/sync 영구 금지.
