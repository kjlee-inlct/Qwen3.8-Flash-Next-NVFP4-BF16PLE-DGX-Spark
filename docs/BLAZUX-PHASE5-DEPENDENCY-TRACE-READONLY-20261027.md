# Phase 5 연속 Gate — Preview vLLM AST Dependency Trace / Source-Only

> **상태: CODE_AND_TESTS_PREPARED / DGX_NEW_HEAD_NOT_RUN / NO_ENGINE_PATCH / NO_GPU / NO_MODEL_ACCESS.**
>
> 날짜: 2026-10-27 (Asia/Seoul). 동일 `feature/blazux-phase5-correctness-mtp-offline` 브랜치 유지. 이전 **사용자 DGX 실제 PASS 코드 SHA `2c7c6896430be0d9eada656f17edf97d9c5f4d3f`** (Source 152/152, mocks 38/38, unit 223/223 XFAIL0, pinned patch source preflight). 기록 완료된 이전 **docs-only HEAD `e0dbed59b3ef8c5b7a3c843a904c4c96532f22e6`**에서 후속 작업 시작. 이번 신규 HEAD는 실제 DGX 미실행.
>
> blazux upstream 비교 대상 고정 [`8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa`](https://github.com/blazux/qwen3.8-Flash-DGX/tree/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa); 이 도구는 pinned 소스와 실제 엔진의 **관계 증거를 수집할 뿐 자동 patch·적용 승인·실 runtime 정합성 판단은 하지 않는다.**

## 1. 한 Phase에 묶은 조사 목적

기존 `src/phase5_patch_readiness.py`는 파일 SHA/AST 메서드 지문·앵커 건수 12파일로 patch 계열을 보수적으로 분류했다. DGX 결과에서 다섯 계열 모두 `APPLY_APPROVED=0`으로 남았다. 이번에는 동일 Phase 5 안에서 아래 미확인 **실제 계산 구조·제어 흐름의 출처**를 확인할 수 있도록 읽기 전용 추적을 구현한다.

| 작업 | 수집되는 정적 증거 | 이 검사만으로 인정하지 않는 것 |
|---|---|---|
| **Mamba/Scheduler Prefix-cache** | `MambaHybridModelState.add_request/preprocess_state/postprocess_state`의 floor division/mod RHS, attribute `cache_config.block_size`·`mamba_block_size` 사용; Scheduler `__init__`의 `self.block_size` 공급과 `_mamba_block_aligned_split`/prefix-hit method의 assignment/call edge | `mamba_block_size` 런타임 공급, LCM 실제 수치, SSM slot 저장·복원 정확성 |
| **mamba_block_size 공급자 스캔** | 설치 package 내부 `config` 및 `v1` 하위 `.py` 파일에서 **AST STORE/LOAD** 위치(상대 경로·행 번호), 명시적인 탐색 제한/읽기 오류 | 동적 `setattr`/런타임 생성/다른 package root까지 전부 조사했다는 주장 |
| **Tool Calling/Responses** | `ParserEngine._handle_tool_end/_compute_arg_delta/_flush_arg_converter`, `Qwen3Parser.extract_reasoning`, `StreamingParserEngine.feed/finish`, `OpenAIServingResponses._process_simple_streaming_events` 및 보완 helper의 **정적 호출명·return 표현 shape** | HTTP/SSE 실제 동작, chunk timing, parser 인자 계약·JSON schema 품질 |
| **MTP/PLE** | NVIDIA `Qwen3_8FlashNextMTP.__init__/compute_logits/forward/load_weights`의 `self.lm_head`, `self.logits_processor` 대입·호출·return shape 및 PLE forward 메서드 | `lm_head.weight` 실제 공유 alias, BF16 dtype/shape/TP, reduced vocabulary acceptance, 실제 95GiB 모델 적합성 |

**파일:** `src/phase5_dependency_trace.py`, 합성 stdlib `tests/test_blazux_phase5_dependency_trace.py` **신규 10개 unit**, `scripts/phase5-check-offline.sh` 소스 AST gate 확장. 원래 전체 unit 223 + 신규 10 = **233개 예상(XFAIL=0 목표)**. 보고서에 실제 새 DGX PASS를 미리 기재하지 않는다.

## 2. 제한·보호 장치

- **절대 설치 엔진 import/monkeypatch 금지.** `find_spec("vllm")`로 패키지 source root만 확인; `.py`만 AST 파싱하고 모듈 함수 호출·CUDA·GPU/모델/weight/huggingface cache 접근·네트워크 사용 없음. 사용자 운영 컨테이너를 stop/recreate하지 않음.
- 함수 표현(`floor_div`, `mod`, `self.block_size` assignment, `return` 형태)은 **숫자·문자열 상수를 `<number>`, `<redacted>`로 대체**하고 최대 160자로 제한. 소스 본문, 원래 문자열 리터럴, 실제 host 절대경로는 출력하지 않는다. package-root-relative 파일명·행 번호, 정적 호출명·속성명과 bytes SHA만 수집.
- `_safe_read`로 symlink/out-of-tree/2MiB 초과 단일 파일 거부. `config`+`v1` 전체 탐색은 **최대 Python 1600개, 총 24MiB, field site 48개**; 한계나 읽기 오류가 있으면 `FILE_LIMIT_EXCEEDED`, `BYTE_LIMIT_EXCEEDED`, `SITE_LIMIT_EXCEEDED`, `SCANNED_WITH_UNREADABLE_FILES` 등으로 명시. 읽기 실패/탐색 제한이면 그 결과를 전체 공급자 부재의 근거로 사용 불가.
- `mamba_block_size` **STORE** 발견은 정적 필드 대입 후보일 뿐 실 runtime object에 올바르게 공급된다는 증거가 아니다. **LOAD**만 보이거나 `sites=[]`여도 다른 패키지·dynamic assignment 가능성이 있어 `ABSENT` 확정 금지.
- Parser/MTP 호출명 탐색은 AST method scope만 검사하며 실제 dispatch alias/동적 속성 결합은 누락 가능. **어떤 상태도 `PATCH_READY` / `APPLY_APPROVED`로 전환하지 않는다**. 사용자의 Phase5 안전정책 및 main 영구 보호 유지.

## 3. 합본 DGX 단일 실행 절차 (추가 Gate 5만)

Phase5 전용 기존 checkout이 **깨끗한 상태**여야 한다. 다른 브랜치·운영 체크아웃·MTP weights/모델은 손대지 않는다. `EXPECTED`에는 최종 GitHub 커밋 SHA를 사용한다(여기서는 생성 시 미정).

```bash
(
  set -Eeuo pipefail
  REPO="kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark"
  SRC="$HOME/Workspace/llm/blazux-phase5-correctness-mtp-offline"
  BRANCH="feature/blazux-phase5-correctness-mtp-offline"
  EXPECTED="REPLACE_WITH_NEW_PHASE5_HEAD"
  CONTAINER="qwen38-flash-orca-uncensored-bf16-mtp"

  test -d "$SRC/.git"
  cd "$SRC"
  test "$(git branch --show-current)" = "$BRANCH"
  case "$(git remote get-url origin)" in
    "https://github.com/$REPO"|"https://github.com/$REPO.git"|"git@github.com:$REPO"|"git@github.com:$REPO.git") ;;
    *) echo "STOP: unexpected origin" >&2; exit 2 ;;
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
    --workdir /phase5 \
    -e CUDA_VISIBLE_DEVICES=-1 -e PYTHONDONTWRITEBYTECODE=1 \
    --entrypoint python3 "$IMAGE" src/phase5_dependency_trace.py

  echo "PASS: PHASE5_DEPENDENCY_TRACE_EXECUTED_NOT_CERTIFIED"
)
```

**합격/자료 표시 목표 (아직 실측 아님):** `PHASE5_UNIT_PASS=233; XFAIL=0`, Manifest **156개 예상**, `PHASE5_OFFLINE_ORACLES_AND_SOURCE_CONTRACTS` PASS, `PHASE5_DEPENDENCY_TRACE_DONE_NOT_PATCH_APPROVED`, 최종 `PHASE5_DEPENDENCY_TRACE_EXECUTED_NOT_CERTIFIED`. JSON `components`·`mamba_field_scan`·`next_gates`로 어떤 필드가 직접 대입되고 호출되는지 수집. 설치 package scan 한계 초과 시 **검사 부분 완료**로 표시하고 같은 Phase5에서 탐색 범위만 좁혀 보완한다.

## 4. 다음 Go/No-Go 순서 및 GitHub 안전 정책

정적 결과를 받은 다음 **1) Mamba config field 공급 여부 및 Scheduler block-size 생성 경로, 2) Parser/Responses 함수 호출 그래프·신규 helper 패치 순서, 3) MTP shared head ownership/weight loader**를 증거 기반으로 비교한다. 검증된 경계 내의 **합성 CPU source fixture/patch staging**은 *Phase5 같은 브랜치에서* 별도 명시적 기본 OFF 가드와 롤백으로 준비할 수 있지만, 설치 preview 엔진에 바로 patch하거나 GPU/실 모델/서빙 실험은 사용자 승인 전 시작하지 않는다.

**영구 금지:** `main` 대상 PR/merge/cherry-pick/rebase/squash/sync. P0 및 Phase1~4 immutable. Phase5→Phase4 리뷰 Draft PR도 현재 불필요하고 merge하지 않는다. 운영 Docker/이미지/실 weights/ports 8000·18300/HF cache/receipt는 변경 대상이 아니다.

**증거 구분:** 223 PASS는 `2c7c6896...` 코드만의 사용자 DGX 실기 사실, 그 이후 docs-only HEAD는 `e0dbed59...`. 이번 233 테스트 목표의 새 소스 SHA는 GitHub final verified HEAD를 따르며 DGX 로그 수신 전까지 `NOT_RUN`.
