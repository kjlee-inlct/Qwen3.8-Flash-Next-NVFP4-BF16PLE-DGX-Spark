# Track A Phase 1 — 실제 DGX 오프라인 검증 결과 (2026-10-27)

> **판정: PHASE1_STATIC_AND_DGX_OFFLINE_PASS / GPU_INFERENCE_NOT_RUN / BLAZUX_OPTIMIZATION_NOT_IMPLEMENTED / CI_NOT_VERIFIED.**
>
> 이 문서는 **사용자가 제공한 DGX Spark 터미널 로그**에서 확인한 결과를 기록한다. GitHub 앱은 DGX 호스트에 직접 접속하거나 테스트를 재실행하지 않았다. raw 로그를 공개 저장소에 그대로 포함하지 않고 공개 가능한 조건·요약·해시만 기록한다.
>
> **검증 대상은 문서 기록 커밋 직전의 실측 SHA** `8555a0a5a73d6bf390eeeb3495a01257c0ca3327`이다. 이 보고서와 Source Manifest 변경으로 생성될 후속 docs-only SHA에서는 실기 테스트를 재실행하지 않았으며, 변경 후 GitHub tree 무결성은 별도로 확인한다.

## 1. Provenance / 변경하지 않은 보호 기준

| 항목 | 값 |
|---|---|
| 실기 검증 날짜 | 2026-10-27, 사용자 제공 로그; 정확한 실행 시각은 로그에서 확정 불가 |
| 호스트 | NVIDIA DGX Spark (GB10) / Linux ARM64, 사용자 제공 시험 환경 |
| 개인 Fork | `kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark` |
| 검증 분리 checkout 브랜치 | `feature/blazux-phase1-source-compare` |
| **실측 HEAD** | `8555a0a5a73d6bf390eeeb3495a01257c0ca3327` |
| 부모 계보 P0 | `966ec7cf0741734b844b1cea938d56678a756469` |
| 외부 참조 blazux | [blazux/qwen3.8-Flash-DGX](https://github.com/blazux/qwen3.8-Flash-DGX/tree/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa) @ `8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa` |
| 보호 `main` | `2847e39b4131eb8aff78bf86ffce98892401722a` (원격 상태는 기록 시 재확인) |

## 2. 실측 A — 별도 Phase 1 checkout / 오프라인 시험

사용자 실행 스크립트에 `set -Eeuo pipefail`을 사용했다. 브랜치/HEAD/clean checkout 선행 assertion이 통과했고 전체 블록은 `PASS: Phase 1 offline verification completed`로 정상 종료했다.

| 실제 검사/명령 | 사용자 제공 증거 | 판정 |
|---|---|---|
| `git branch --show-current`와 고정 `HEAD` | 정확히 `feature/blazux-phase1-source-compare` / `8555a0a5...` | PASS |
| `git status --porcelain` | clean assertion 통과 | PASS (일반 untracked; ignored는 범위 외) |
| `scripts/verify-source-state.sh` (non-strict) | `PASS_SOURCE_ONLY: 122 tracked file(s)` (전·후 두 번) | **122/122 PASS** |
| `scripts/manifest.sh validate` | `manifest OK: kjlee-qwen38-dgx-spark-wizard, 4 target(s)` | PASS |
| `scripts/run-mock-tests.sh` | `Ran 38 tests in 0.015s; OK` | **38/38 PASS** |
| `PYTHONPATH=src:. python3 -m unittest discover -s tests -v` | `Ran 172 tests in 0.521s; OK` | **172/172 PASS** |
| `bash -n scripts/*.sh scripts/qwen38-dgx-spark` | 블록 내 fail-fast 후 후속 검증 계속·최종 PASS | PASS (별도 stdout 없음) |
| `python3 tools/audit_publication.py` | 블록 내 fail-fast 후 후속 검증 계속·최종 PASS | PASS (별도 stdout 없음) |

`--strict`는 이 실험 브랜치를 의도적으로 허용하지 않으며 **실행하지 않았다**. non-strict에서도 개인 Fork origin, manifest 자체 blob, HEAD-tree/path/mode/blob, 작업 파일 blob 검사 유지. 모델 weight·untracked/ignored 상태·Docker runtime·GPU는 Source PASS로 보증하지 않는다.

## 3. 실측 B — 격리된 기존 이미지의 PLE CPU fixture

사용자는 우선 **실행 중인 운영 컨테이너에서 조회만** 수행했으며 다음 패키지와 BF16 CPU 텐서 생성 성공을 보고했다.

- NumPy `2.2.6`
- PyTorch `2.13.0+cu130`
- `torch.ones(4, dtype=torch.bfloat16)` CPU 경로 정상

이후 기존 컨테이너의 **정확한 이미지 ID**를 가져와, 네트워크 없이 `--runtime=runc`, `--read-only`, `--tmpfs /tmp`, `--cpus=2`, `--memory=2g`, `--pids-limit=128`, CPU-only `CUDA_VISIBLE_DEVICES=-1`, 소스 read-only bind mount를 사용한 **임시 Docker 컨테이너**에서 Phase 1의 기존 `src/test_ple_mmap_cpu.py`를 실행했다. `docker stop/rm/restart` 등을 운영 컨테이너에 수행하는 절차는 포함하지 않았다.

| fixture 출력 | 결과 |
|---|---|
| gather rows 1 | OK, 2.78 ms |
| gather rows 16 | OK, 4.48 ms |
| gather rows 5,000 | OK, 5.12 ms |
| gather rows 131,072 | OK, 243.76 ms |
| FP8 placeholder forward | OK, shape `(300, 16, 160)` |
| **BF16 placeholder forward bit/value equivalence** | **OK**, shape `(6, 7)` |
| zeros path | OK |
| out-of-range IndexError | OK |
| prewarm fixture | OK |
| 종료 | **`ALL OK`** |

기존 CPU fixture에는 합성 safetensors dummy-prefix offset, BF16 부분 샤드/경계/중복, 혼합 width 거부, 누락 shard·잘못된 row count 거부 등의 정합성 검사가 이미 포함되어 있다. 이 실행을 **blazux PLE fast path, pinned staging, GPU inverse, CUDA graph 또는 실 PLE 95GiB의 성능 검증으로 해석하지 않는다.** gather 시간은 제한된 소형 CPU 합성 시험의 참고값이지 추론 throughput/TPS 향상 근거가 아니다.

## 4. 종료 기준과 미검증 항목

- **Phase 1 Gate 1 종료 판정: PASS.** 두 pinned Git SHA의 정적 함수/데이터 계약 비교와 DGX host 오프라인 source/manifest/mock/unit + 기존 PLE CPU fixture 실행을 확인했다.
- **코드 구현 추가 없음.** Gate 1 보고서에 분류한 PLE 계측/소량 gather, GPU pinned/inverse, QSA, MTP prefilter는 여전히 후속 Phase 또는 Track B 판단 대상이다.
- **NOT_RUN:** 신규/기존 GPU inference A/B, blazux 최적화 적용, 실제 체크포인트 MTP 31개 torch tensor 로딩, vLLM 0.32 ABI 동적 재현, 장시간/다중 부하, baseline llama-benchy 재실행, GitHub Actions CI.
- **운영 안전:** 기존 운영 컨테이너/이미지/가중치/cache/receipt/port를 변경하는 배포 시험 없음. 이 문서는 사용자의 로그를 근거로 하며 실제 서비스 현재 상태 재조회가 아니다.
- **문서 커밋 경계:** `8555a0a5...`가 사용자 DGX에서 직접 시험된 정확한 HEAD다. 이후 GitHub documentation/Source Manifest commit은 새 HEAD가 되므로 이전 122/122을 새 HEAD의 호스트 실행 결과로 옮겨 적지 않는다. GitHub에서 새 소스 Tree/Manifest 일치는 확인 가능하며, 사용자 측 최신 HEAD의 소스 검증을 원하면 별도 pull 후 실행한다.
- **Phase 2:** `feature/blazux-phase2-offline-fixtures`는 Phase 1 **문서 확정 HEAD**에서만 생성한다. 새 소형 BF16 synthetic fixture/옵션 기능은 그 자식 브랜치에 구현한다. `main`과 P0를 절대 변경하지 않는다.
