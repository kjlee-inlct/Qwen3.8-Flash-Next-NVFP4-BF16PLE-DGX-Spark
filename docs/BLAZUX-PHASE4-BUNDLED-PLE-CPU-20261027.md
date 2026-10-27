# Track A Phase 4 — 두 가지 기본 OFF PLE 개선을 하나의 Phase로 통합

> 2026-10-27 (Asia/Seoul). **CODE_AND_OFFLINE_TESTS_PREPARED / DGX_PHASE4_NOT_RUN / GPU_NOT_RUN / CI_NOT_VERIFIED.** GitHub 코드 반영 ≠ CPU/DGX 실측 PASS. 두 플래그의 성능상 이점도 아직 실측하지 않았다.
>
> 기준 개인 Fork `kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark`; Phase 3 확정 docs HEAD `760f227e46a358445db3d3931b5efbe40de5f609`에서 Phase 4 단일 자식 `feature/blazux-phase4-ple-cpu-bundle` 생성. 이전 `main/P0/Phase1/Phase2/Phase3` ref 변경 금지.
>
> 외부 참조 blazux [PIN 8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa](https://github.com/blazux/qwen3.8-Flash-DGX/tree/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa) 의 CPU small-N gather 및 per-phase 계측 아이디어를 내부 preview PLE ABI에 **선별 적응**. upstream vLLM 0.32 class/constructor/Prometheus/pinned H2D/GPU inverse를 복사하지 않았다.

## 1. Phase 수 줄이기 — 실행 원칙 변경

- **작은 변경마다 Phase를 추가하지 않는다.** 같은 운영 격리 수준·테스트 의존성·rollback/Go-No-Go를 공유하면 하나의 Phase에서 소스 비교 → 기능별 커밋 → 통합 unit/CPU matrix → DGX 로그 검토 → docs/Manifest 확정까지 진행한다.
- **다른 최적화끼리는 각각 독립 커밋과 독립 OFF 스위치**로 추적한다. Phase4의 A/B는 구현 커밋 2개, 통합 fixture/문서 커밋 1개가 목표. 필요 시 같은 Phase 내 추가 검증/수정 커밋을 사용하고 불필요한 Phase 5/6 분기를 만들지 않는다.
- Phase 자체 분리는 ABI/엔진(GPU/Track B 등), 운영 자원·성능시험 승인, 서로 다른 rollback 신뢰 경계가 있을 때만 사용한다.
- **진입·승인 구분:** Phase4에서 CPU-only 코드 작성 허용 ≠ 새 GPU 추론/모델 95GiB 로딩/벤치 실행 승인. GPU 경쟁, 실제 checkpoint 캐시 압박, Docker 교체 등은 사용자 별도 명시적 승인 전 금지한다.

## 2. 묶음 A — 선택적 small-N inline gather

| 계약 | 값 |
|---|---|
| Flag | `VLLM_PLE_FAST_GATHER=0` (**기본 OFF**) |
| Threshold | `VLLM_PLE_FAST_GATHER_ROWS=512`; flag OFF일 때 완전히 무효 |
| OFF | 기존 `np.unique(ids,return_inverse=True)` 기반 dedup·sort→shard별 chunk·ThreadPoolExecutor→inverse expansion 그대로 |
| ON | `0 < N <= threshold`에만 shard별 boolean mask·memmap fancy indexing 순차 실행, input ID 순서/중복 byte 그대로 유지; threshold 초과는 기존 경로 |
| Fail closed | 음수 및 허용 최대 index 검사를 유지; missing shard는 명시적 `IndexError`, 마지막 short shard 범위도 memmap index에서 `IndexError` |
| Rollback | 환경 변수 OFF 또는 제거. 설치/운영 Docker 이미지는 변경하지 않았음 |

**성능주의:** small-N이 더 빠르다는 보장은 없다. read amplification, unique dedup 유무, page cache, random I/O, CPU concurrency에 따라 느릴 수도 있다. 실제 B/F comparison과 p50/p95는 독립 GPU·CPU 측정 전까지 결과 미상. 단일 CPU fixture wallclock을 운영 개선율로 주장 금지.

## 3. 묶음 B — 선택적 per-table CPU gather 통계

| 계약 | 값 |
|---|---|
| Flag | `VLLM_PLE_PHASE_STATS=0` (**기본 OFF**) |
| OFF | Stats 딕셔너리/Lock/clock sampling 없음. gather는 동일 데이터 반환 경로로 위임; Python wrapper 호출 오버헤드 자체까지 0이라는 주장은 하지 않음 |
| ON | `stats_snapshot()` 호출로 per-table `calls`, `errors`, `rows`, `logical_bytes`, `gather_s`, `fast_calls` 누적값 조회 |
| 독립성 | Fast flag OFF/ON과 관계없이 동작. `stats_snapshot()`은 복사본이며 aggregate 변경 불가 |
| 비범위 | GPU 대기시간/복사시간, 실제 NVMe 디스크 read bytes, page faults, Prometheus 등록·/metrics 노출, background thread 등 측정하지 않음 |
| Rollback | 환경 변수 OFF 또는 제거; 디폴트 데이터 반환 값 변경 없음 |

프로세스 동시 호출 시 per-table `threading.Lock`으로 통계 snapshot/갱신만 보호한다. time/perf_counter 포함 계측은 opt-in이며 성능 시험 시 계측 부하와 off-vs-on 차이 별도 보고한다.

## 4. 통합 Gate 4: 하나의 DGX 시험 창에서 함께 수행

| 항목 | 필수 기대값 |
|---|---|
| `scripts/phase4-check-offline.sh` | 소스 origin/branch/parent/clean 상태, non-strict manifest, 4 targets, Wizard mock, repo unittest, Bash syntax, publication audit, 재-manifest **PASS** |
| 전체 unit | Phase3 189 + Phase4 신규 5 = **194 tests / XFAIL=0** (실측 전 예상) |
| 기존 G2-01 방어 | 기존 duplicate index 중단, XFAIL 재발 불가 |
| 기존 real PLE CPU fixture | `PHASE3_PLE_DUPLICATE_GUARD_ALL_OK`, `PHASE2_PLE_CPU_ALL_OK` |
| Phase4 flag matrix | (fast,stats) `(0,0),(1,0),(0,1),(1,1)` 각 `byte_exact=1`; empty, duplicate, short shard, 512/513 threshold, errors/counters, torch BF16 forward |
| 완료 조건 | 마지막 `PHASE4_CPU_MATRIX_ALL_OK` + 194/194 + XFAIL 0 + exact source SHA + manifest 1:1 |
| 미확인 | 실제 PLE 128shard/95.37GiB, GPU pinned staging/race, QSA/MTP runtime/SSM, throughput/TPS, GitHub CI |

**Strict 소스 검증 금지:** 실험 브랜치는 release allowlist에 포함되지 않으므로 `scripts/verify-source-state.sh --strict` 대신 `scripts/phase4-check-offline.sh`(내부 non-strict + origin/branch/ancestor) 사용.

### A. DGX 독립 checkout 및 표준 라이브러리 시험

```bash
(
  set -Eeuo pipefail
  SRC="$HOME/Workspace/llm/blazux-phase4-ple-cpu-bundle"
  BRANCH="feature/blazux-phase4-ple-cpu-bundle"
  REPO="kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark"
  test ! -e "$SRC"
  git clone --single-branch --branch "$BRANCH" \
    "https://github.com/$REPO.git" "$SRC"
  cd "$SRC"
  git rev-parse HEAD
  scripts/phase4-check-offline.sh
)
```

기존 디렉터리가 있으면 덮어쓰지 말고 origin/clean/branch/HEAD 검증 후 `git fetch` 및 `git pull --ff-only`만 허용. `main` checkout이나 이전 Phase에 `git switch/reset/clean` 절대 금지.

### B. 기존 이미지 재사용, 임시 CPU 컨테이너 1개로 두 시험 한 번에

```bash
(
  set -Eeuo pipefail
  SRC="$HOME/Workspace/llm/blazux-phase4-ple-cpu-bundle"
  CONTAINER="qwen38-flash-orca-uncensored-bf16-mtp"
  test "$(git -C "$SRC" branch --show-current)" = \
    "feature/blazux-phase4-ple-cpu-bundle"
  test -z "$(git -C "$SRC" status --porcelain=v1 --untracked-files=normal)"
  IMAGE="$(docker inspect --format '{{.Image}}' "$CONTAINER")"
  docker run --rm --pull=never --network=none --runtime=runc \
    --read-only --tmpfs /tmp:rw,mode=1777,size=256m \
    --cpus=2 --memory=2g --pids-limit=128 \
    --mount "type=bind,src=$SRC,dst=/phase4,readonly" \
    --workdir /phase4 \
    -e CUDA_VISIBLE_DEVICES=-1 -e PYTHONDONTWRITEBYTECODE=1 \
    --entrypoint /bin/sh "$IMAGE" -c \
    'set -eu; python3 src/test_ple_phase2_cpu.py; python3 src/test_ple_phase4_cpu.py'
)
```

이 명령은 기존 이미지를 **조회만** 하고 새 CPU-only 임시 컨테이너에서 두 프로그램을 이어 실행한다. 운영 컨테이너/포트 8000·18300, HF cache·recipe view·receipt와 GPU에 쓰지 않는다. CPU/호스트 RAM만 제한적으로 점유한다.

기대 출력(실측 전):

```text
PHASE3_PLE_DUPLICATE_GUARD_ALL_OK
PHASE2_PLE_CPU_ALL_OK
PASS: PHASE4_FLAG_MATRIX fast=0 stats=0 byte_exact=1
PASS: PHASE4_FLAG_MATRIX fast=1 stats=0 byte_exact=1
PASS: PHASE4_FLAG_MATRIX fast=0 stats=1 byte_exact=1
PASS: PHASE4_FLAG_MATRIX fast=1 stats=1 byte_exact=1
PHASE4_CPU_MATRIX_ALL_OK
```

## 5. 미완료 및 후속 범위는 Phase 생성 없이 동일 Gate 안에서 관리

- **madvise `random/normal` 선택, Prometheus multiprocess, pinned async H2D/GPU inverse, QSA TopK·prefix-cache/SSM/streaming**은 소스 호환·GPU 위험 및 별도 승인 요구로 이번 CPU bundle에 넣지 않았다. 미완료 항목을 Phase 번호만 늘려 자동 진행하지 않는다.
- 가능한 다음 체크: Phase4 통합 실기 증거 기록→기능별 default-OFF 동등성 유지→필요한 별도 reviewer/사용자 Go-No-Go. 실제 **GPU A/B**는 사용자 승인 시, 운영 컨테이너 보호·메모리/포트·baseline 동일 조건을 확인하고 독립 계획 수립.
- 코드의 feature A/B는 **같은 Phase에서 각각 별도 Git commit**으로 기록한다. 하나의 최종 runbook/manifest/인수인계가 두 기능을 총괄한다.

## 6. PR/Merge 원칙

- 현재 **PR·Merge는 필수 아님**. 리뷰가 필요할 때만 `head=feature/blazux-phase4-ple-cpu-bundle` → `base=feature/blazux-phase3-ple-duplicate-shard-guard` 의 **비병합 Draft PR** 검토.
- 해당 PR 역시 **merge하지 않는다** (Phase3 불변). Phase 5는 Phase4 최종 Gate 확정 후 **서로 다른 승인/rollback 영역으로 넘어갈 때만** 자식 브랜치 생성한다. 동일 Phase의 추가 단위시험·버그 픽스·결과 기록은 새 Phase 없이 Phase4에서 처리.
- **blazux 계보에서 `main`으로 향하는 PR/merge/cherry-pick/rebase/squash/sync는 영구 금지**. P0/Phase1/Phase2/Phase3도 불변 유지. 운영 적용/모델 이미지 교체는 사용자가 별도로 승인하지 않는 한 하지 않는다.
