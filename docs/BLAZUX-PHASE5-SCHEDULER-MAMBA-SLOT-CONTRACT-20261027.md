# Track A Phase5 — Scheduler Dynamic Factory와 Mamba State Slot 블록 단위 Source-only Gate

> 기준 2026-10-27 Asia/Seoul. **신규 분석 코드·17 synthetic tests 준비 / 신규 DGX 실행 NOT_RUN / 실제 blazux patch 적용 승인 0건 / GPU·모델·운영 서비스 미접근.** 기존 `feature/blazux-phase5-correctness-mtp-offline` 브랜치 하나에서 진행.
>
> 직전 사용자 전체 DGX Gate PASS: code `bc89de6288889943b50090ac9638ee95c2434a79`, unit **259/259 XFAIL0**, Source Manifest **164/164**, Wizard Mock **38/38**. 이후 3개 읽기 전용 확인은 실제 이미지에서 별도로 수행; 해당 사실을 문서화한 기준 **docs-only HEAD `3729277eba4d5c7f1e1d6a3603bbbd939ea8661a`**는 신규 소스의 테스트 SHA가 아니다. [3개 검사 실측 정본](BLAZUX-PHASE5-DGX-THREE-SOURCE-CHECKS-20261027.md). 고정 blazux upstream `8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa`.

## 1. 이번 확인의 근거

- `EngineCore.__init__:148`은 `Scheduler = vllm_config.scheduler_config.get_scheduler_cls()` 동적 Factory 반환을 사용하고 :161에서 `Scheduler(block_size=scheduler_block_size, hash_block_size=hash_block_size)`를 호출한다. `engine_static_imports_scheduler=false`는 **직접 import를 기대했던 이전 분석기 검사 범위의 한계**다. 실제 반환 클래스 및 override/default 정책을 아직 모른다.
- `resolve_kv_cache_block_sizes`는 0/1 group에서 `cache_config.block_size*dcp`를 두 크기로 반환하고, 2+ group에선 AttentionSpec만 spec block-size × DCP, 다른 Mamba group은 spec.block_size 그대로 LCM 계산한다. Prefix/connector off나 non-align Mamba group의 조기 반환과 hash override/GCD를 혼동하지 않는다.
- `MambaHybridModelState.add_request`는 align 모드에서 `(num_computed_tokens-1)//cache_config.block_size`로 상태 초기 index seed를 계산한다. `preprocess_state`에서는 `MAMBA_BLOCK_SIZE=mamba_spec.block_size`, `Scheduler._mamba_block_aligned_split`는 `cache_config.block_size`, backend는 `self.kv_cache_spec.block_size`를 사용한다. **실제 사용자 모델에서 수치가 다른지 아직 측정한 바 없다.**

## 2. 이번 같은 Phase5 구현

| 경로 | 역할 |
|---|---|
| `src/phase5_scheduler_mamba_contract.py` | 설치 vLLM을 import하지 않고 `config/scheduler.py` 및 `v1/engine/core.py`의 Scheduler factory 정의·local assignment/ctor 인자, Mamba worker `add_request/_get_mamba_group_info/_ensure_align_ctx/preprocess_state/postprocess_state`, Scheduler split, backend의 source AST와 SHA256을 조회. 표현식 상수 redaction, 함수별 최대 24 events |
| `tests/test_blazux_phase5_scheduler_mamba_contract.py` | **17개 stdlib synthetic tests**로 Scheduler default/override factory 존재·엔진 연결, legacy worker seed, group spec assert, preprocess kwarg, context/helper, postprocess hook, scheduler/backend block field, symlink·상수 redaction, 가상 token 경계 수치 계산을 fail-closed로 검증 |
| `scripts/phase5-check-offline.sh` | 기존 manifest/Mock/Unit/Source AST/audit Gate에 신규 두 파일 AST 추가 |

**예상 전체 단위시험:** 이전 **259 + 신규 17 = 276개 XFAIL0 목표**. Source Manifest는 기존 **166 + 새 파일 3개(분석기/시험/runbook) = 169개 예상**. **새 코드 SHA의 DGX 실행 결과는 아직 없다.**

### 보호된 결과의 의미

분석 JSON `source_checks` 항목은 *소스 AST에서 특정 표현이 존재하는지*만 뜻한다. 모든 값이 `true`라도 `active_scheduler_class_verified=false`, `actual_config_block_equality_verified=false`, `state_slot_correctness_verified=false`, `patch_approved=false`.

가상 CPU oracle의 `config_block_size=16, mamba_block_size=16`와 `16,32` 비교는 `(N-1)//B` **계산 민감도 예시**일 뿐이다. 실제 GPU slot address/사용자 Mamba spec/SSM rollback 결과, 실제 에러/버그의 증거가 아니다. `N>0`의 bounded fake position만 검사하고 무제한 데이터/실 weights/GPU 접근은 없다.

파일 읽기 대상은 고정 Python source 6개이며 `_safe_read`로 symlink/out-of-root/2MiB 이상을 거부, source SHA를 보고. `find_spec("vllm")`은 package root 위치 조회에만 쓰며 `import vllm`·CUDA 초기화·monkeypatch·docker exec·network 접근 없음.

## 3. DGX 검증 명령

최종 GitHub 확인 후 `EXPECTED`에 실 커밋 SHA를 넣어 전용 **clean Phase5 checkout만** ff-only 갱신한다. 운영 중인 서비스의 기존 이미지 ID를 조회해 `--runtime=runc --network=none --read-only` 별도 일회용 CPU-only container에서 **분석기만** 실행한다.

```bash
(
  set -Eeuo pipefail
  REPO="kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark"
  SRC="$HOME/Workspace/llm/blazux-phase5-correctness-mtp-offline"
  BRANCH="feature/blazux-phase5-correctness-mtp-offline"
  EXPECTED="REPLACE_WITH_FINAL_PHASE5_SOURCE_HEAD"
  CONTAINER="qwen38-flash-orca-uncensored-bf16-mtp"
  test -d "$SRC/.git"
  cd "$SRC"
  test "$(git branch --show-current)" = "$BRANCH"
  case "$(git remote get-url origin)" in
    "https://github.com/$REPO"|"https://github.com/$REPO.git"|"git@github.com:$REPO"|"git@github.com:$REPO.git") ;;
    *) echo "STOP: wrong origin" >&2; exit 2 ;;
  esac
  test -z "$(git status --porcelain=v1 --untracked-files=normal)"
  git fetch --no-tags origin "$BRANCH"
  git pull --ff-only origin "$BRANCH"
  test "$(git rev-parse HEAD)" = "$EXPECTED"
  scripts/phase5-check-offline.sh
  IMAGE="$(docker inspect --format '{{.Image}}' "$CONTAINER")"
  docker run --rm --pull=never --network=none --runtime=runc \
    --read-only --tmpfs /tmp:rw,mode=1777,size=256m \
    --cpus=2 --memory=2g --pids-limit=128 \
    --cap-drop=ALL --security-opt=no-new-privileges \
    --mount "type=bind,src=$SRC,dst=/phase5,readonly" \
    --workdir /phase5 -e CUDA_VISIBLE_DEVICES=-1 \
    -e NVIDIA_VISIBLE_DEVICES=void -e PYTHONDONTWRITEBYTECODE=1 \
    --entrypoint python3 "$IMAGE" src/phase5_scheduler_mamba_contract.py
  echo "PASS: PHASE5_SCHEDULER_MAMBA_CONTRACT_EXECUTED_NOT_CERTIFIED"
)
```

**목표 출력(실측 아님):** `PHASE5_UNIT_PASS=276; XFAIL=0`; `PASS_SOURCE_ONLY: 169 tracked file(s)`; `PHASE5_SOURCE_AST_OK`; `PHASE5_SCHEDULER_MAMBA_CONTRACT_DONE_NOT_PATCH_APPROVED` 및 별도 wrapper 최종 마커.

## 4. 이후 같은 Phase5 Go/No-Go

출력 `file_evidence.scheduler_config.methods.get_scheduler_cls`의 Factory default/override 처리, `source_checks`의 true/false, Mamba `_ensure_align_ctx` 및 세 stage의 static fingerprint를 함께 확인한다. 불일치가 보이면 설치 source 변경이나 GPU tests가 아니라 먼저 사용자의 config vs actual MambaSpec block 크기를 **읽기 전용·별도 승인 범위** 내에서 확인하는 절차를 설계한다. 소스만으로 알 수 없는 실제 활성 설정/그룹 topology/slot copy kernel의 결과는 인증 불가.

**절대 유지:** blazux Mamba/Prefix, Tool/Responses, MTP Reduced Draft Vocabulary 적용 승인 0. `main`·P0·Phase1~4 불변, `main` PR/Merge/Cherry-pick/Rebase/Squash/Sync 금지. Phase5 안의 CPU/source-only 증거만 진행; 운영 Docker/model/HF cache/ports/GPU/HTTP/TPS/CI 실험 및 변형 금지.
