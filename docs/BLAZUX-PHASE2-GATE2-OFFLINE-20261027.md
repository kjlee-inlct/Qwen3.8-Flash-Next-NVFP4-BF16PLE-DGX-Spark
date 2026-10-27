# Track A Phase 2 — Gate 2 합성 BF16/CPU 계약 시험 및 DGX 실행 절차

> 2026-10-27 (Asia/Seoul). 상태: **GATE2_IMPLEMENTED_AWAITING_REAL_DGX_EXECUTION / CI_NOT_VERIFIED / GPU_NOT_RUN**. 신규 최적화 커널·vLLM 패치·Docker image 변경은 없음. GitHub에 코드/문서가 저장됐다는 사실은 테스트 PASS가 아니다.
>
> 전 단계: [Phase 1 DGX 실측](BLAZUX-PHASE1-DGX-VALIDATION-RESULTS-20261027.md) / 검증 HEAD `8555a0a5a73d6bf390eeeb3495a01257c0ca3327`; Phase 1 확정 문서 HEAD `a50fc53721f3d23325dca44eb799f0f388d65951`.
>
> 본 Phase 2 브랜치 `feature/blazux-phase2-offline-fixtures`는 Phase 1 확정 HEAD에서 정확히 분기. 외부 분석 기준 [blazux/qwen3.8-Flash-DGX](https://github.com/blazux/qwen3.8-Flash-DGX/tree/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa) @ `8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa`.

## 1. 구현 범위와 역할 분리

| 파일 | 실행 의존성 | 시험 대상/역할 |
|---|---|---|
| `tests/phase2_ple_fixtures.py` | Python 표준 라이브러리 | 실제 모델을 쓰지 않는 임시 BF16 safetensors 13×7, 4 shard (4/4/4/1), 2 파일, dummy tensor prefix, 정해진 BF16 원시 비트, 옵션별 손상·QSA 기준 oracle |
| `tests/test_blazux_phase2_ple.py` | Python 표준 라이브러리 | **실제 내부 `src/vllm_ple_mmap.py` AST에서 원본 네 함수만 컴파일**: header/parser, shard 탐색, dtype 크기, fail-closed layout. Torch/vLLM import 없음. 샤드 경계·비정렬 offset·dtype/width/payload 길이·누락/row count·index 파일 유무 |
| `tests/test_blazux_phase2_mtp_qsa.py` | Python 표준 라이브러리 | 기존 BF16 MTP guard 31/31 이름·dtype·누락/추가 거부 및 **독립 QSA CPU reference** visible-mask/k/tie/NaN 조건 시험 (vLLM 커널 실행이 아님) |
| `src/test_ple_phase2_cpu.py` | NumPy + PyTorch (CPU만) | **실제 PLE production module**의 mmap gather + placeholder forward 실행, workers=1/4, duplicate IDs·short shard·out-of-range, BF16 byte-for-byte 기준값 |
| `scripts/phase2-check-offline.sh` | Bash, Git, Python 표준 라이브러리 | 정확한 개인 Fork/Phase 2 branch/P1 부모/깨끗한 소스 요구; manifest, fake/mocks, 전체 unittest, Bash syntax, 출판 감사; 기본 GPU/Docker 동작 없음. `--ple-cpu`는 명시적 opt-in |

### 실제 코드·계약 구분

- `src/vllm_ple_mmap.py`, MTP overlay/guard, Dockerfile, 모델 config, Docker/런타임 코드는 **수정하지 않았다**. 테스트는 해당 production 함수나 source contract를 관찰한다.
- Stdlib AST 파서는 `_find_shards`, `parse_safetensors_header`, `_itemsize`, `_validate_shard_layout` **원본 함수 정의**를 직접 컴파일하는 시험이다. 전체 torch runtime의 module import/프로세스 동작과 동일하다고 주장하지 않는다. 실제 mmap/torch 데이터 경로는 별도의 CPU-only 시험으로 분리했다.
- QSA Top-K oracle의 동점 우선순위는 **열 번호 오름차순으로 고정한 단순 CPU 기준값**이다. vLLM/torch `topk` 실제 동점 순서·NaN 정책을 증명하거나 blazux `patch_qsa_exact_topk.py`를 포팅한 것은 아니다.
- MTP **31개 이름/데이터형 fail-closed**는 현재 source contract를 실제 guard 함수 호출로 테스트하지만 텐서 shape와 실제 체크포인트 31개 tensor 로딩은 미검증이다.
- CPU PLE fixture는 bitwise 정합성/안전 경계 시험이지 실제 95GiB NVMe 페이지 폴트 속도나 pinned H2D/stream race 시험이 아니다.
- 모든 합성 파일은 `tempfile.TemporaryDirectory` 아래 소량 바이트로 생성한다. 원본 모델, cache, 임시 파일의 상시 보관·변조 없음.

## 2. 미해결 위험 및 XFAIL 정책

| Gate 1 위험 | 현재 시험/판정 |
|---|---|
| `G1-01` BF16 헤더/오프셋/엔디언 | 표준 라이브러리의 safetensors raw header byte offset + Docker CPU torch BF16 바이트 비교로 검증 예정 |
| `G1-02` 4 shard 구성·최종 short·dtype/width 불일치 | 정상/음성 test 추가. 결함 입력의 실패 지점 확인 |
| `G2-01` **중복 shard 인덱스** (서로 다른 safetensors 파일) | 내부 `_find_shards`는 중복 index를 덮어쓰므로 fail-closed 보장이 없다. **`@unittest.expectedFailure` 1개**로 결함을 명시. `expected failure`를 정상 기능 PASS라고 해석 금지. 향후 기본 경로 수정을 검토하면 decorator 제거 후 실제 PASS 요구 |
| `G1-03` pinned H2D/GPU inverse 및 CUDA graph | Phase 2에서 하지 않음. Stream/lifetime/GPU는 별도 승인과 장치 환경 필요 |
| `G1-04` MTP 31 텐서 | 이름/dtype guard 실제 함수 시험. shape/real weights/vLLM 로더는 미검증 |
| `G1-05` QSA exact TopK | 독립 CPU oracle 기대 결과만. vLLM kernel/softmax/acceptance 동등성 미검증 |
| `G1-08` Mamba/SSM prefix state, tool parser/Responses | 엔진 ABI 및 모델 상태 의존 → Phase 2 구현 밖. 가짜 GPU/품질 PASS 만들지 않음 |

**Gate 2 오프라인 시험 완료 조건:** DGX 정확한 Phase 2 HEAD에서 source/manifest/mocks/unit/출판 감사 통과, 별도 CPU-only 컨테이너에서 `PHASE2_PLE_CPU_ALL_OK` 출력, 예상 XFAIL 개수 기록, 모든 미해결 위험 및 테스트 제외 범위 기록. 이 조건들이 모두 확인되기 전에는 Phase 2 최종 PASS 또는 새 Phase 진입을 선언하지 않는다.

## 3. DGX 전용 Checkout: pull 및 표준 라이브러리 시험

현재 운영 `yslab-qwen38-bf16ple-dgx-spark` Git HEAD를 switch하지 말 것. 기존 서비스를 위한 Docker·이미지·모델·HF cache·receipts·포트 8000/18300은 변경 금지. 다음은 사용자 DGX에서 실행할 명령이다.

```bash
set -Eeuo pipefail
REPO="kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark"
BRANCH="feature/blazux-phase2-offline-fixtures"
SRC="$HOME/Workspace/llm/blazux-phase2-offline-fixtures"

if [[ ! -e "$SRC" ]]; then
  git clone --single-branch --branch "$BRANCH" \
    "https://github.com/$REPO.git" "$SRC"
fi
test -d "$SRC/.git"
cd "$SRC"
test "$(git branch --show-current)" = "$BRANCH"
test -z "$(git status --porcelain=v1 --untracked-files=normal)"
git fetch --no-tags origin "$BRANCH"
git pull --ff-only origin "$BRANCH"
echo "PHASE2_HEAD=$(git rev-parse HEAD)"

scripts/phase2-check-offline.sh
```

`scripts/phase2-check-offline.sh`는 개인 Fork 정확한 origin을 확인하고, P1 확정 HEAD가 선행 조상인지 확인하며, 빈 branch/dirty checkout/unexpected HEAD 경로를 추측으로 복구하지 않는다. **소스 검증에서 `--strict` 금지:** 기존 verifier의 release-branch allowlist에 Phase 2는 포함하지 않는다. non-strict라도 blob/mode/origin 검증을 진행한다.

## 4. 실제 PyTorch mmap/CPU 시험: 운영 이미지 재사용, 모델 실행 없음

앞서 Phase 1에서 검증된 기존 이미지에는 NumPy `2.2.6`/PyTorch `2.13.0+cu130`가 있었다. 운영 컨테이너를 **중지·재시작하지 않고**, 정확한 이미지 ID만 조회하여 제한된 임시 **CPU-only** 컨테이너에서 새 test 파일을 실행한다.

```bash
(
  set -Eeuo pipefail
  SRC="$HOME/Workspace/llm/blazux-phase2-offline-fixtures"
  CONTAINER="qwen38-flash-orca-uncensored-bf16-mtp"

  test "$(git -C "$SRC" branch --show-current)" = \
    "feature/blazux-phase2-offline-fixtures"
  IMAGE="$(docker inspect --format '{{.Image}}' "$CONTAINER")"

  docker run --rm --pull=never --network=none --runtime=runc \
    --read-only --tmpfs /tmp:rw,mode=1777,size=256m \
    --cpus=2 --memory=2g --pids-limit=128 \
    --mount "type=bind,src=$SRC,dst=/phase2,readonly" \
    --workdir /phase2 \
    -e CUDA_VISIBLE_DEVICES=-1 -e PYTHONDONTWRITEBYTECODE=1 \
    --entrypoint python3 "$IMAGE" \
    src/test_ple_phase2_cpu.py
)
```

기존 이미지와 운영 컨테이너의 상태는 유지하지만, 임시 컨테이너는 CPU/host RAM 자원을 잠시 점유할 수 있다. `docker run` 호출이므로 Docker에 새 임시 컨테이너 객체는 생성/자동 삭제되지만 모델 컨테이너를 관리하지 않는다. `--memory=2g`의 작은 합성 시험만 수행.

예상 종료 출력(실행 후 실제 확인 필요): `PASS: BF16 mmap gather/torch forward byte-exact workers=1...`, `workers=4...`, 마지막 `PHASE2_PLE_CPU_ALL_OK`. 기존 `src/test_ple_mmap_cpu.py`의 Phase 1 시험과 다른 **신규** 소스 시험이다.

## 5. PR/브랜치 정책과 다음 Gate

**현재 PR 불필요 / 병합 금지.** Phase 2 실기 오프라인 시험과 리뷰를 완료한 시점에, 원하면 **비병합 리뷰 전용 draft PR**만 `base=feature/blazux-phase1-source-compare`, `head=feature/blazux-phase2-offline-fixtures`로 개설한다. 부모 Phase 1은 불변이므로 **그 PR도 merge하지 않는다**.

Phase 2 완료 판정 후 Phase 3은 Phase 2의 고정 HEAD에서 **새 자식 브랜치**로만 생성한다. 실험 코드를 `main`으로 PR, merge, cherry-pick, squash, rebase, sync하지 않는 정책은 성능 결과와 무관하게 영구 유지한다.

## 6. 실행 결과 기록 형식

- 검증한 정확한 Phase 2 HEAD, origin/branch, Source Manifest `N/N`, mock `N/N`, full unittest `N/N`, known-gap **expectedFailures 개수**, stdout final PASS, 별도 `PHASE2_PLE_CPU_ALL_OK`.
- CPU/PyTorch, GPU visible flag, 실제 실행/미실행 구분. CI=NOT_VERIFIED (Actions 0). 기존 모델 서비스 생존 여부는 별도 관찰하지 않았으면 UNKNOWN.
- 사용자 제공 결과를 검토한 뒤에만 영구 보고서의 `AWAITING_REAL_DGX_EXECUTION` 상태를 변경한다. 새 docs-only commit SHA를 테스트한 것처럼 쓰지 않는다.
