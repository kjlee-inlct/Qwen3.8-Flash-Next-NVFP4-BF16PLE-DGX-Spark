# Track A Phase 5 — Scheduler 생성자 block_size 출처 / Mamba State Slot 정렬 조사

> **최신 상태: DGX_SOURCE_ONLY_GATE_PASS_244 / MANIFEST_160 / SCHEDULER_LCM_AND_CTOR_ANCHORS_FOUND / ASSIGN_SCAN_PARTIAL / NO_PATCH_APPROVAL / NO_GPU.**
> 날짜: 2026-10-27 (Asia/Seoul). 기존 Phase 5 브랜치 `feature/blazux-phase5-correctness-mtp-offline`에서 유지. 별도 Phase 6/Track B/PR을 생성하지 않는다.
>
> **기반 docs-only Git HEAD:** `fbfe28774ed8b7915ab6c44f6b5fe8a0c5f906d1`. 실제 DGX Source-only trace를 실행한 SHA는 `2cadc7369b4b813332a767733faa9c2529413cd9`이며 JSON+marker만 확보됐다. 이 SHA의 전체 233개 unit 및 Source 156/156 **실측 PASS는 확인되지 않았다**. 마지막 확정 전체 test PASS는 `2c7c6896430be0d9eada656f17edf97d9c5f4d3f` (223/223, mocks38/38, Source152/152).
>
> 외부 blazux pinned `8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa`와 설치 preview vLLM의 패치 호환 여부는 **아직 결정하지 않는다**.

## DGX Source-only 실제 실행 결과 (최신, 이전 실행 계획보다 우선)

- 사용자 첨부 `붙여넣은 텍스트(1)(20261027-102956).txt`: **실측 소스 HEAD `04b871ab632b2a59d55d11f19009c48daa3ce5c0`**, 전체 unittest `PHASE5_UNIT_PASS=244; XFAIL=0`, Source Manifest **160/160**, `PHASE5_SOURCE_AST_OK`, `PHASE5_OFFLINE_ORACLES_AND_SOURCE_CONTRACTS`, `PHASE5_SCHEDULER_PROVENANCE_SOURCE_ONLY_DONE_NOT_PATCH_APPROVED` 및 최종 `PHASE5_SCHEDULER_PROVENANCE_EXECUTED_NOT_CERTIFIED` PASS.
- **Source 연결 후보 발견:** `v1/engine/core.py:161`의 `Scheduler(block_size=scheduler_block_size, hash_block_size=hash_block_size)`, `v1/core/kv_cache_utils.py:640`의 `scheduler_block_size=math.lcm(*group_block_sizes)`, `kv_cache_utils.py:665`의 `hash_block_size=requested if requested is not None else math.gcd(*hashing_sizes)`, `Scheduler.__init__:174`의 `self.block_size=block_size`. **각 위치는 AST 관측이지만 실제 caller↔return import/value flow는 아직 확인되지 않았다**.
- **중요 PARTIAL:** Python 384 파일(6,448,206 bytes, unreadable=0)을 스캔했어도 **`ASSIGN_SITE_LIMIT`=64**에 도달, assignment 출력은 **부분 목록**. Scheduler direct-name 후보 1개는 `NAME_MATCH_SCHEDULER_NOT_RESOLVED`, dynamic-ctor 0은 그 스코프의 관측에 한정. 모든 곳을 완전 검사했다고 주장하지 말 것.
- [DGX Scheduler Provenance 실측 정본](BLAZUX-PHASE5-DGX-SCHEDULER-PROVENANCE-RESULTS-20261027.md)에서 source lines/판정·잔여 검증 조건 기록. Mamba worker와 Scheduler aligned split은 계속 `cache_config.block_size`를 사용하는 source preimage; 현 실 모델 state-slot 정확성 미검증, 패치 적용 승인 0, GPU/운영 미실행. **후속 docs-only Git SHA는 DGX에서 재실행된 소스 HEAD가 아니다.**

## 1. 직접 확인된 문제와 이번 접근

[DGX AST Trace 실측 정본](BLAZUX-PHASE5-DGX-DEPENDENCY-TRACE-RESULTS-20261027.md)에서 아래가 확정됐다.

- `config/cache.py:125`에는 `mamba_block_size` AST STORE, `config/cache.py:267`와 `config/vllm.py:2535–2536`에는 LOAD가 있다. 필드가 **일부 소스에 존재한다**는 증거이지 사용자 모델 설정 값의 보장은 아니다.
- `MambaHybridModelState.add_request:116`의 state index 나눗셈은 `self.cache_config.block_size`; `Scheduler._mamba_block_aligned_split:392`도 `self.cache_config.block_size`를 로컬에 대입한다.
- `Scheduler.__init__:174`에서 `self.block_size = block_size`이다. **Scheduler 생성자에 이 인자를 전달하는 호출부**, LCM/Hybrid group 단위 및 `hash_block_size`가 어떻게 계산되는지는 아직 모른다. 이 정보를 모른 채 단순 치환하면 cache state 정합성을 보장할 수 없다.

이번 작업은 이 **생성자 호출자의 후보**를 안전하게 찾기 위한 두 번째, 더욱 좁은 정적 조사다.

| 신규 파일 | 목적 |
|---|---|
| `src/phase5_scheduler_provenance.py` | `config`와 `v1` 내부 Python 파일의 `Scheduler(...)`·`scheduler_cls(...)`·동적 factory 후보 호출, `block_size`/ `hash_block_size` 위치/키워드 인자와 관련 대입식/LCM 형태, `mamba_block_size` LOAD/STORE, Scheduler/Mamba 메서드 지문을 **소스만** 읽어 기록 |
| `tests/test_blazux_phase5_scheduler_provenance.py` | 가상 소스에서 direct keyword/positional/dynamic constructor 후보, LCM, Mamba field, 원본 state slot/scheduler 메서드, 검색 상한, symlink 및 상수 제거를 **신규 11개 stdlib unit**으로 확인 |
| `scripts/phase5-check-offline.sh` | 기존 전체 unit·Manifest·Mock·AST·Bash·publication audit + 신규 분석기와 회귀시험 AST 포함 |

**전체 unit 목표:** 이전 Phase5 233(기대) + 신규 11 = **244개 XFAIL0 예상**. Source Manifest는 157에서 새 3개 tracked file 추가로 **160개 예상**이다. 아직 DGX 실행 결과가 아니다.

## 2. 출력 해석 및 적용 차단 기준

- **직접 이름 `Scheduler(...)`**: `NAME_MATCH_SCHEDULER_NOT_RESOLVED`. 이름은 같아도 import binding을 해석하지 않았으므로 현재 설치된 `v1/core/sched/scheduler.py` 클래스 생성이라고 **확정하면 안 된다**.
- **`scheduler_cls(...)` 등 동적 호출**: `DYNAMIC_CTOR_UNRESOLVED`. 인자 표현은 기록하지만 해당 클래스의 정확한 시그니처, 위치 인자 의미를 추측하지 않는다. 발견되지 않았다는 것이 호출 부재를 뜻하지 않으며 dynamic dispatch 가능성은 계속 남는다.
- **`block_size` 인자 / `hash_block_size`**: 직접 생성자 후보에 한해, 기존 DGX Scheduler `__init__` 시그니처의 관측된 위치(4·5번째 명시적 인자) 또는 키워드 형태를 기록한다. import/alias가 일치하는지와 실제 LCM 공급자는 다시 확인해야 한다. 저장되는 `self.block_size`, `cache_config.block_size`, `self.hash_block_size`를 하나로 혼동하면 안 된다.
- **`lcm(...)`, `math.lcm(...)` 대입**: 이름/정적 AST 후보만 출력하며 **실제 hybrid group LCM 계산이 그 호출이라고 인증하지 않는다**. runtime config, 그룹별 크기 및 `MambaHybridModelState` state slot/restore와 동일 단위인지 별도 검증.
- **제한 / 기밀**: `config`+`v1` 하위 최대 1600개 Python source/24MiB 검사. source `_safe_read`가 symlink/out-of-tree/대형 파일 거부, 상수는 `<redacted>`/`<number>`로 대체, 표현은 최대 160자. scan `PARTIAL`이면 미스캔 영역을 **인식하고 확정판정 금지**. `COMPLETE_IN_SCANNED_SCOPE`도 외부 패키지·동적 생성·함수 body 의 실제 실행 경로는 포함하지 않음.
- **무조건 `patch_approved=false`**, 최종 `PHASE5_SCHEDULER_PROVENANCE_SOURCE_ONLY_DONE_NOT_PATCH_APPROVED`. 이 분석은 실제 prefix-cache hit, Model/GPU, performance, ABI/runtime, PLE/MTP throughput을 측정하지 않는다.

## 3. DGX 한 번의 재현 — 같은 Phase5 전용 체크아웃

```bash
(
  set -Eeuo pipefail
  REPO="kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark"
  SRC="$HOME/Workspace/llm/blazux-phase5-correctness-mtp-offline"
  BRANCH="feature/blazux-phase5-correctness-mtp-offline"
  EXPECTED="REPLACE_WITH_FINAL_VERIFIED_PHASE5_HEAD"
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
    --mount "type=bind,src=$SRC,dst=/phase5,readonly" \
    --workdir /phase5 -e CUDA_VISIBLE_DEVICES=-1 \
    -e PYTHONDONTWRITEBYTECODE=1 \
    --entrypoint python3 "$IMAGE" src/phase5_scheduler_provenance.py
  echo "PASS: PHASE5_SCHEDULER_PROVENANCE_EXECUTED_NOT_CERTIFIED"
)
```

**예상 출력:** `PHASE5_UNIT_PASS=244; XFAIL=0`; `PASS_SOURCE_ONLY: 160 tracked file(s)`; `PHASE5_SCHEDULER_PROVENANCE_SOURCE_ONLY_DONE_NOT_PATCH_APPROVED`; 최종 `PHASE5_SCHEDULER_PROVENANCE_EXECUTED_NOT_CERTIFIED`. 실행 전에는 **NOT_RUN**. 출처 기록 시 정확한 Git HEAD와 JSON의 `scheduler_constructor_candidates`, `block_assignments`, `mamba_field_references`, `core_method_traces`, `scan.state`를 보존한다.

## 4. 그다음 같은 Phase 5에서 진행

실제 DGX JSON을 보고 **Scheduler 생성자의 `block_size` 인자를 공급하는 함수/메서드, `hash_block_size`의 별도 정렬 단위 및 Mamba state slot 단위를 검증**한다. `Scheduler(...)` 직접 참조가 없고 동적 factory만 발견되면 AST static trace를 포기하지 않고 그 동적 class resolution 및 factory 함수 정의를 범위를 좁혀 읽기 전용 조사한다. patch preimage와 cache state lifecycle이 독립적으로 확정되기 전까지 blazux `patch_mamba_block_size.py` **실제 적용 금지**.

Tool Calling/Responses·MTP reduced draft vocabulary는 이전 Phase5 미승인 상태 유지. 실제 모델/운영 Docker/weights/HF cache/ports/GPU/HTTP/TPS/CI 변경 및 실험 금지. 현재 PR/Merge 불필요; `main` 대상 PR/Merge/Cherry-pick/Rebase/Squash/Sync 영구 금지, P0/Phase1~4 ref 불변.
