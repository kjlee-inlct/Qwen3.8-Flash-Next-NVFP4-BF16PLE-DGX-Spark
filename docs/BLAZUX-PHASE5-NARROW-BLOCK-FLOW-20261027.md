# Track A Phase 5 — KV-group LCM → EngineCore → Scheduler 정밀 Source-only 추적

> 2026-10-27 / **신규 DGX Source-only 검증 PASS (259/259 XFAIL0, Source164/164, Mock38/38), static_chain 5/6, Scheduler import unresolved, 패치 적용 승인 0건**. 동일 Phase5 브랜치만 사용하며 Phase/PR/Merge 생성 안 함.
>
> 고정 blazux upstream `8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa`. 직전 사용자 DGX 실제 PASS: `04b871ab632b2a59d55d11f19009c48daa3ce5c0`의 unittest **244/244 XFAIL0**, Source **160/160**. 이를 문서화한 이전 docs-only HEAD는 `f61e9dc03162997253e468ab8e33737b680b1b86`이며 별도 DGX 재시험한 SHA 아님.

## 사용자 DGX Narrow Block Flow 실측 — 최신 결과 (이전 실행 전 계획보다 우선)

- **실제 시험 소스 HEAD `bc89de6288889943b50090ac9638ee95c2434a79`**: Source Manifest **164/164**, Wizard Mock **38/38**, 전체 unittest **259/259 XFAIL0**, AST + 전체 offline wrapper PASS, `PHASE5_NARROW_BLOCK_FLOW_DONE_NOT_PATCH_APPROVED` 및 최종 `PHASE5_NARROW_BLOCK_FLOW_EXECUTED_NOT_CERTIFIED`. 후속 문서만 수정한 Git HEAD는 259개를 재실행한 SHA가 아님.
- `static_chain.checks`는 **6개 중 5개 true**: KV resolver 정적 import, LCM 대입, tuple 반환, EngineCore tuple assignment, Scheduler ctor keyword 변수 사용 true. `engine_static_imports_scheduler=false` 하나가 남고 `status=UNRESOLVED_OR_PARTIAL_STATIC_CHAIN`, `runtime_flow_proven=false`, `patch_approved=false`이다.
- `kv_cache_utils.py:634`: `AttentionSpec` 그룹 `g.kv_cache_spec.block_size * dcp`, 다른 그룹 `g.kv_cache_spec.block_size`. :640 LCM, :659 prefix_cacheable 그룹 hashing subset(없으면 전체), :665 requested 또는 GCD. `return`에는 **632/647/657행 조기 반환**과 **673행 일반 반환**이 공존해 실제 값 전달에 분기 조건 확인이 필수.
- `engine/core.py:157`는 `scheduler_block_size, hash_block_size = resolve_kv_cache_block_sizes(kv_cache_config, vllm_config)`, :161에서 `Scheduler(...,block_size=scheduler_block_size,hash_block_size=hash_block_size)`. 원래 AST 수식 연결은 확보했지만 `Scheduler` **실제 import/binding 형태가 이번 scanner 기대 패턴과 일치하는지 불명**. 실패를 단순 존재 버그나 실제 잘못된 바인딩으로 오인 금지.
- 이번 6파일 모두 `PARSEABLE_ONLY`, `bounded_output_truncated=false`. 이는 **좁은 파일 범위**에 한한 결과; 원래 384파일 광역 scan의 `ASSIGN_SITE_LIMIT`/PARTIAL 이력과 분리.
- [DGX 실측 정본 보고서](BLAZUX-PHASE5-DGX-NARROW-BLOCK-FLOW-RESULTS-20261027.md)에 6파일 SHA256 및 세부 source line·검증 경계 기록. **다음 같은 Phase5**는 Scheduler binding의 정확한 선언·alias, KV resolver 조기 반환 조건/`dcp` 공급, Mamba group spec/slot alignment의 CPU fixture 검증; blazux patch 실제 적용/GPU·HTTP 실험은 여전히 금지.

## 1. 문제와 범위

- `v1/core/kv_cache_utils.py:640`에 `scheduler_block_size=math.lcm(*group_block_sizes)`, :665에 `hash_block_size` GCD/요청값 대입 발견.
- `v1/engine/core.py:161`은 `Scheduler(block_size=scheduler_block_size,hash_block_size=hash_block_size)`를 호출하며, `Scheduler.__init__:174`는 인자를 `self.block_size`에 대입.
- 이전 광역 조사는 384 Python 파일/6,448,206 bytes를 읽었지만 `ASSIGN_SITE_LIMIT=64`로 **PARTIAL**. 값의 실제 import→call→return→tuple 대입→Scheduler 생성자 연결은 미검증.
- `MambaHybridModelState.add_request:116`과 `Scheduler._mamba_block_aligned_split:392`는 여전히 `cache_config.block_size` 사용. hybrid LCM과 Mamba slot 및 hashing GCD 단위를 동일하다고 간주 금지.

## 2. 같은 Phase5의 구현 묶음

| 파일 | 기능 |
|---|---|
| `src/phase5_block_flow_narrow.py` | **설치 vLLM import 없이** 관련 파일 6개의 read-only AST. EngineCore import/method, KV resolver group 생성/LCM/GCD/return, EngineCore 반환값 대입, Scheduler 호출, Mamba/Scheduler/Backend 메서드 지문 |
| `tests/test_blazux_phase5_block_flow_narrow.py` | synthetic tree의 정적 연결, 바뀐 import, tuple return, 누락·파손·symlink·source hash·redaction·출력 제한에 대한 **15개 stdlib unit** |
| `scripts/phase5-check-offline.sh` | 기존 Source/Mock/Unit/Bash/AST/audit Gate에 신규 파일 포함 |

읽기 대상 6개: `v1/engine/core.py`, `v1/core/kv_cache_utils.py`, `v1/core/sched/scheduler.py`, `v1/worker/gpu/model_states/mamba_hybrid.py`, `v1/attention/backends/mamba_attn.py`, `config/cache.py`.

`static_chain.checks`의 독립 기준: EngineCore의 resolver import, Scheduler import, KV resolver의 LCM 대입, 두 변수 반환, EngineCore의 resolver→scheduler_block_size 변수 대입, Scheduler 생성자 block_size=해당 변수. **전부 참이어도 `STATIC_CHAIN_CANDIDATE_NOT_RUNTIME_CERTIFIED`**이며 `runtime_flow_proven=false`, `patch_approved=false`를 유지한다.

보호: 기존 안전 함수 `_safe_read`에서 symlink/외부 경로/큰 파일 거부. AST expression 문자·숫자 상수 redaction, 160자 제한, method별 64 records, relevant EngineCore method 최대 32. 제한·파싱 오류가 있으면 미확인/부분 스캔으로 기록. 동적 import·runtime branch·사용자 KV cache 그룹·Mamba state restore 및 실 GPU inference를 보증하지 않음.

## 3. DGX 단일 Source/CPU-only 재현

`EXPECTED`는 최종 GitHub 커밋 SHA로 대체. 기존 Phase5 전용 clean checkout만 fast-forward하고 운영 이미지 ID를 읽어서 네트워크·GPU·쓰기 접근 없는 disposable CPU 컨테이너 실행.

```bash
(
  set -Eeuo pipefail
  REPO="kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark"
  SRC="$HOME/Workspace/llm/blazux-phase5-correctness-mtp-offline"
  BRANCH="feature/blazux-phase5-correctness-mtp-offline"
  EXPECTED="REPLACE_WITH_FINAL_VERIFIED_SHA"
  CONTAINER="qwen38-flash-orca-uncensored-bf16-mtp"
  test -d "$SRC/.git"
  cd "$SRC"
  test "$(git branch --show-current)" = "$BRANCH"
  case "$(git remote get-url origin)" in
    "https://github.com/$REPO"|"https://github.com/$REPO.git"|"git@github.com:$REPO"|"git@github.com:$REPO.git") ;;
    *) echo "STOP: origin" >&2; exit 2 ;;
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
    --mount "type=bind,src=$SRC,dst=/phase5,readonly" \
    --workdir /phase5 -e CUDA_VISIBLE_DEVICES=-1 \
    -e PYTHONDONTWRITEBYTECODE=1 \
    --entrypoint python3 "$IMAGE" src/phase5_block_flow_narrow.py
  echo "PASS: PHASE5_NARROW_BLOCK_FLOW_EXECUTED_NOT_CERTIFIED"
)
```

**예상, 아직 DGX 미실행**: unit **259개/XFAIL0**, Source Manifest **164개** (161+신규3), `PHASE5_NARROW_BLOCK_FLOW_DONE_NOT_PATCH_APPROVED` marker.

## 4. 이후 Gate

사용자 JSON `files.engine_core`, `files.kv_utils`, `static_chain`을 근거로 누락된 import/return/tuple unpack/호출을 판정한다. 모든 소스 조건을 충족해도 Mamba group spec·SSM state slot/restore·실 cache hit 정확성/출력 정합성은 **별도 fixture와 실 모델 승인 Gate** 필요.

`main`/P0/Phase1~4 immutable, 새 PR/Merge 불필요, `main` PR/Merge/Cherry-pick/Rebase/Squash/Sync 영구 금지. 운영 Docker·모델·weights·ports·HF cache·GPU/HTTP/TPS는 명시적 승인 전 접근·변경 금지.
