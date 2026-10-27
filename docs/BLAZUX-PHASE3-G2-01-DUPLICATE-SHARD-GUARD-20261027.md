# Track A Phase 3 — G2-01 중복 PLE 샤드 인덱스 Fail-Closed 보완 및 회귀

> 작성: 2026-10-27 (Asia/Seoul). **최신 상태: PHASE3_G2_01_DGX_OFFLINE_PASS / XFAIL_0 / PLE_CPU_BYTE_EXACT_PASS / CI_NOT_VERIFIED / GPU_NOT_RUN.** 초기 문서의 DGX_NOT_RUN은 작성 당시 상태이며 아래 최신 결과가 우선한다. 이 문서는 소스 변경과 사용자 DGX 재검증 절차를 정의한다. 실기 PASS를 미리 선언하지 않는다.
>
> Fork: [kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark](https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark). 부모 Phase 2 확정 HEAD `76588845d7742703475ae1f49d5e8f5c174bb77a` → Phase 3 자식 `feature/blazux-phase3-ple-duplicate-shard-guard`. P0 `966ec7cf0741734b844b1cea938d56678a756469`, Phase 1 `a50fc53721f3d23325dca44eb799f0f388d65951`, 기존 main `2847e39b4131eb8aff78bf86ffce98892401722a` **절대 변경 금지**. blazux 출처는 [고정 SHA](https://github.com/blazux/qwen3.8-Flash-DGX/tree/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa).

## DGX 실기 시험 확인 — 후속 결과 (본 문서 초기 예정보다 최신)

- 사용자 제공 Phase 3 소스 HEAD `cb1de387b09786d6be35fec838c6549a78e5417c`의 로그: **Source Manifest 132/132, unittest 189/189, XFAIL=0**, `PASS: PHASE3_G2_01_OFFLINE_CONTRACTS_XFAIL_0`.
- 새 실제 PyTorch PLE CPU fixture 출력: `workers=1 chunk=1024`, `workers=4 chunk=2`의 **BF16 바이트 일치 PASS**, `PHASE3_PLE_DUPLICATE_GUARD_ALL_OK` 및 `PHASE2_PLE_CPU_ALL_OK`. G2-01은 **소형 CPU 합성 회귀 범위에서 해결**로 기록한다.
- [Phase 3 실기 검증 영구 보고서](BLAZUX-PHASE3-DGX-VALIDATION-RESULTS-20261027.md)는 명령/결과/근거/미검증 범위/원본 실측 SHA를 구분한다. 이후 docs-only SHA에서의 재시험은 아님. GPU/vLLM 운영 추론/성능/CI는 미검증.
## 1. 발견된 결함과 최소 수정

Phase 2 사용자 DGX 실기 `fd9d8cfb6938b82ae979c9804386ffbe084cc81d`에서 **Source 129/129, Mock 38/38, unittest 188 (XFAIL=1), PLE CPU BF16 byte-exact (workers=1/4) PASS**를 확인했다. 상세 근거는 [Phase 2 결과](BLAZUX-PHASE2-DGX-VALIDATION-RESULTS-20261027.md).

- **기존 문제 G2-01:** `src/vllm_ple_mmap.py::_find_shards`에서 읽은 각 safetensors 헤더마다 `shards[shard_idx] = ...`로 바로 대입해, **서로 다른 파일에 동일한 PLE `shard_N`가 존재하면 앞선 엔트리가 덮어써졌다.** 정상처럼 보이는 잘못된 checkpoint의 silent mapping 위험.
- **수정:** shard index 숫자를 파싱한 직후, 이미 본 index라면 `ValueError("PLE duplicate shard index ...")` 발생. 원래의 offset/shape/dtype/width/scale 검사, 정상 샤드 row mapping, MTP 및 다른 추론 로직은 그대로 둔다. default-OFF optimization flag를 추가하는 단계가 아니라 **명백한 입력 오류를 fail-closed시키는 안전성 검증**이다.
- **적용 경계:** 실제 `_find_shards`가 읽는 헤더들 사이의 동일한 shard index 탐지. 손상된 header JSON의 *동일 텐서 이름 중복 키*, index.json의 다른 교란, payload 외부 바이트 손상, 진짜 모델 체크포인트 전체 인증까지 해결했다고 주장하지 않는다. 이외 결함은 별도 위험/시험으로 취급한다.
- **이식 경계:** 외부 blazux vLLM 0.32 패치를 복사하거나 새 Docker 이미지·커널을 만들지 않는다. 원래 vLLM preview 기반 `src/vllm_ple_mmap.py`에서 검사만 추가.

## 2. 테스트 / 회귀 항목

| 구분 | 원래 Phase 2 | Phase 3 시험 기대 |
|---|---|---|
| no-index 여러 safetensors 파일의 중복 shard_0 | `@expectedFailure` 1개 | **XFAIL 제거 → 실제 PASS**, 중복 탐지 오류 직접 검증 |
| index.json이 다른 두 샤드 파일을 참조하고 뒤 파일에 shard_0도 존재 | 미확인 | **신규 음성 테스트**가 ValueError 요구 |
| 정상 BF16 13×7, 4-shard(4/4/4/1), dummy header prefix/offset | PASS | 원래 byte-exact 및 샤드/폭/타입 검증 계속 PASS |
| 실제 `torch` + `numpy` `_find_shards` import 경로 | 정상 path만 PASS | 정상 workers=1/4 그대로 PASS, **신규 중복 입력이 실제 모듈에서 ValueError**; `PHASE3_PLE_DUPLICATE_GUARD_ALL_OK` |
| MTP guard 31/31 및 QSA 독립 CPU oracle | PASS | 기존 unit 회귀 유지, CUDA/실 모델 결과라고 주장 금지 |

`scripts/phase3-check-offline.sh`는 Phase 3 전용 branch/origin/P2 ancestry/clean tree 검증 후 non-strict Source Manifest, deployment manifest, Wizard mocks, full unittest, Bash syntax, publication audit, 후속 Source Manifest를 검사한다. **unittest 예상 실패가 1개라도 남으면 정상 종료하지 않는다**. Optional `--ple-cpu`는 torch/numpy가 이미 준비된 별도 CPU 환경만.

**DGX 최종 Gate 기준:** 정확한 Phase 3 Git HEAD에서 Source Manifest 완전 일치, Mock 전체, full unit suite **XFAIL=0**, 정상 BF16 CPU old/new fixture 결과, 새 중복 입력 `ValueError` 및 운영 미변경 증거. GitHub Commit/Tree 검증만으로 DGX PASS를 선언하지 않는다.

## 3. DGX 별도 소스 checkout + 표준 라이브러리 시험

기존 `yslab-qwen38-bf16ple-dgx-spark` 및 Phase 2 경로를 `git switch/reset/clean` 하지 않는다. 독립 경로를 만든다. 아래 clone은 경로가 존재하면 거절하므로 기존 폴더 손상 없음.

```bash
(
  set -Eeuo pipefail
  REPO="kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark"
  BRANCH="feature/blazux-phase3-ple-duplicate-shard-guard"
  SRC="$HOME/Workspace/llm/blazux-phase3-ple-duplicate-shard-guard"

  test ! -e "$SRC"
  git clone --single-branch --branch "$BRANCH" \
    "https://github.com/$REPO.git" "$SRC"
  cd "$SRC"
  test "$(git branch --show-current)" = "$BRANCH"
  scripts/phase3-check-offline.sh
)
```

이미 Phase 3 전용 clone이 있다면 clean/origin/브랜치 검증 뒤에만 `git fetch` + `git pull --ff-only`를 사용한다. pull 전 정확한 GitHub Phase 3 SHA도 확인한다. **`--strict`는 release 브랜치 allowlist 전용**이므로 Phase 3에서 사용 금지.

예상되는 검증 출력(실기 전 예상이며 확정 PASS 아님):

```text
PASS_SOURCE_ONLY: 132 tracked file(s)
PHASE3_UNIT_PASS=189; XFAIL=0
PASS: PHASE3_G2_01_OFFLINE_CONTRACTS_XFAIL_0
```

## 4. 격리 CPU-only Docker 시험: 기존 운영 이미지 ID 재사용

이미 DGX에서 torch `2.13.0+cu130`, numpy `2.2.6`가 확인된 기존 이미지의 정확한 IMAGE ID만 읽는다. **운영 컨테이너를 stop/restart/replace하지 않는다**. GPU 요청·모델 실행·인터넷·weights/cache mount 없음. 시스템 CPU/RAM은 시험 중 제한적으로 사용.

```bash
(
  set -Eeuo pipefail
  SRC="$HOME/Workspace/llm/blazux-phase3-ple-duplicate-shard-guard"
  BRANCH="feature/blazux-phase3-ple-duplicate-shard-guard"
  CONTAINER="qwen38-flash-orca-uncensored-bf16-mtp"
  test "$(git -C "$SRC" branch --show-current)" = "$BRANCH"
  test -z "$(git -C "$SRC" status --porcelain=v1 --untracked-files=normal)"
  IMAGE="$(docker inspect --format '{{.Image}}' "$CONTAINER")"
  docker run --rm --pull=never --network=none --runtime=runc \
    --read-only --tmpfs /tmp:rw,mode=1777,size=256m \
    --cpus=2 --memory=2g --pids-limit=128 \
    --mount "type=bind,src=$SRC,dst=/phase3,readonly" \
    --workdir /phase3 \
    -e CUDA_VISIBLE_DEVICES=-1 -e PYTHONDONTWRITEBYTECODE=1 \
    --entrypoint python3 "$IMAGE" \
    src/test_ple_phase2_cpu.py
)
```

예상 종료(실측 전):

```text
PASS: BF16 mmap gather/torch forward byte-exact workers=1 chunk=1024
PASS: BF16 mmap gather/torch forward byte-exact workers=4 chunk=2
PHASE3_PLE_DUPLICATE_GUARD_ALL_OK
PHASE2_PLE_CPU_ALL_OK
```

## 5. 결과 상태·PR/Merge 정책

- GitHub source/manifest `path/mode/blob`는 커밋 후 별도 1:1 검사하고, **실제 DGX full unittest/CPU 시험은 사용자의 로그를 받기 전까지 NOT_RUN**으로 유지한다.
- 이번 변경은 PLE production source 한 곳의 fail-closed 방어 패치이므로, **운영 Docker 이미지가 이 수정으로 바뀌었다고 주장하지 않는다**. 모델/실 서비스 품질·GPU throughput·95 GiB PLE 스트리밍·vLLM parser ABI는 여전히 검증 밖.
- PR은 사용자가 원하거나 Phase 3 검증 완료 후 리뷰가 필요할 때만. 허용 가능한 Draft PR은 **`base=feature/blazux-phase2-offline-fixtures`, `head=feature/blazux-phase3-ple-duplicate-shard-guard`**이며 **리뷰 전용으로 merge하지 않는다**. `main`으로 가는 PR/merge/cherry-pick/squash/rebase/sync는 영구 금지. Phase 4는 Phase 3 검증 완료 후 정확한 docs HEAD에서 새 자식 브랜치로만 분리.
