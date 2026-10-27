# Phase 5 내부 확장 — 설치된 preview vLLM 읽기 전용 ABI 소스 점검

> 2026-10-27 (Asia/Seoul) / **최신 DGX 실측: SOURCE_TRIAGE_RUN_PASS / SOURCE_148_148 / UNIT_215_XFAIL_0 / ACTUAL_ENGINE_ABI_NOT_CERTIFIED**.
> 같은 Phase 5에서 처리한다. **새 Phase/Track B 생성 없음. 운영 vLLM 파일, 이미지, HF cache, 모델, 포트, GPU는 수정하거나 실행하지 않는다.**
>
> 기준: 개인 Fork `feature/blazux-phase5-correctness-mtp-offline` (이 단계의 부모 `f3e5fa32a30cb258acd66a9700c6db2a78eb71cc`), 이전 사용자 실기 소스 HEAD `01c9eb6ba311e3ace5f68ecc49fa56f8e0b37d94`. 원래 Phase4/Phase3/P0/main immutable.

## DGX 읽기 전용 ABI triage 실측 완료 — 최초 실행 계획보다 우선

- 검증된 정확한 소스 `9e2d1647357938f6d465eb9b3ce473d03e38e779`, `PASS_SOURCE_ONLY: 148 tracked file(s)`, Wizard Mock **38/38**, unittest **215/215 XFAIL=0**, `PHASE5_SOURCE_AST_OK`, `PHASE5_OFFLINE_ORACLES_AND_SOURCE_CONTRACTS` 및 `PHASE5_READONLY_ABI_TRIAGE_EXECUTED_NOT_CERTIFIED` 확인.
- 기존 고정 경로에서 발견하지 못했던 NVIDIA MTP와 PLE는 실제 설치 트리 **`models/qwen3_8_flash_next/nvidia/mtp.py` 및 `models/qwen3_8_flash_next/nvidia/ple_layer.py`** 에 존재. 동일 계열 AMD implementation도 별도 존재. `Qwen3_8FlashNextMTP.compute_logits(self,hidden_states,spec_step_idx)` 소스 시그니처 확인; **engine compatibility 인증 아님**.
- Mamba legacy block expression = true, Scheduler legacy block assignment = true. Parser Tool argument helper들, streaming literal-marker helper, Responses failed/incomplete helper는 분석된 파일에서 미발견. **SOURCE_ANCHOR_CANDIDATE**로만 기록, 실제 패치 적용 또는 cache/Parser/HTTP runtime 검증으로 해석 금지.
- Candidate scan 결과 `visited=536`, `matched_file_count=43` 중 **32개 후보만 반환(CANDIDATE_LIMIT_REACHED)**. 전체 모델 감사 완료 아님. 필요한 Qwen3.8 NVIDIA/AMD MTP/PLE는 반환된 목록에서 직접 관측됨.
- [Phase5 ABI triage 사용자 DGX 실측 정본](BLAZUX-PHASE5-DGX-PREVIEW-ABI-TRIAGE-RESULTS-20261027.md). 새 보고서/Manifest 커밋은 **docs-only 후속 HEAD**이며 DGX에서 215개를 재실행한 SHA가 아니다.

## 1. 왜 같은 Phase 5에서 추가 검증하는가?

[Phase 5 DGX 실측 결과](BLAZUX-PHASE5-DGX-VALIDATION-RESULTS-20261027.md)의 **208 unit PASS / 144 Source PASS**와 12개 소형 PLE CPU 벤치는 이미 확보했다. 그러나 실제 설치된 preview vLLM source inventory에서 Scheduler/Mamba/Parser/Responses는 존재했으나 MTP/PLE가 조사기의 고정 `qwen3_8_flash_next/nvidia` 경로에 없었다. **`ABSENT_OR_RELOCATED`는 특정 경로에 없다는 뜻이지 MTP/PLE 모듈이 없다는 뜻이 아니다.**

사용자 목표는 blazux 고정 소스 `8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa`의 개선을 실제 모델에 안전하게 이식하는 것이다. 외부 패치의 타깃 클래스/메서드/patch anchor와 지금 설치된 preview 엔진이 다르다면 원본 patch를 그대로 실행해서는 안 된다.

따라서 **코드 적용 전 호환성 triage**, 실제 모듈 파일의 SHA256/클래스/메서드 시그니처/anchor 힌트만 수집한다.

## 2. 이번에 추가한 파일 및 검사 범위

| 경로 | 내용 |
|---|---|
| `src/phase5_preview_abi_audit.py` | importlib `find_spec("vllm")`로 설치 package root만 찾고, 해당 경로 아래 Python source만 read. **vLLM/model import·patch·pip·GPU 없음** |
| `tests/test_blazux_phase5_preview_abi_audit.py` | 설치 엔진이 아닌 합성 Python 소스 트리로 **7개 stdlib unittest**: 존재하지 않는 파일, block-size anchor 구분, Parser helper 공백, Qwen4Exp 우선 탐색, overflow 명시, symlink/out-of-root/대형 파일 제한, byte SHA·AST 오류 |
| `scripts/phase5-check-offline.sh` | 기존 Manifest/Mock/unit/출판감사 + 신규 소스/시험 파일 AST 검증. XFAIL 금지 유지 |

탐색 범위는 `vllm/model_executor/models`와 `vllm/models`로 제한한다. 파일명·상위 폴더 이름 기반으로 Qwen4Exp/3.8 경로의 `mtp.py`, `ple_layer.py`, `model.py`, `qwen*.py`를 우선 후보로 출력한다. **이 후보들은 자동 patch/자동 import 대상이 아니다.** 검색 제한에 도달하면 `SCAN_LIMIT_REACHED` 또는 `CANDIDATE_LIMIT_REACHED`를 명시한다. 보이지 않는 파일은 `ABSENT_OR_OUTSIDE_ROOT`, 접근 오류·symlink·크기 초과·AST syntax 오류 등은 각각 원인별 상태로 기록한다.

분석 결과 중 `PRESENT_SOURCE_PARSEABLE`은 구문이 파싱된다는 뜻뿐이고 **실제 MTP/PLE 구동·API 호환 PASS를 뜻하지 않는다**. `matches_previous_dgx_sha`는 Phase5 이전 실기 로그에서 관측한 파일 SHA와 일치하는지 보는 **drift 감시**일 뿐 설치 버전 인증이 아니다.

### 기준 anchor: pin된 blazux 원본과 대비

- `src/patch_mamba_block_size.py`: `MambaHybridModelState` state seed의 `(tokens - 1) // self.cache_config.block_size` 옛 패턴과 `mamba_block_size` 사용 패턴을 구별한다. Scheduler의 `_mamba_block_aligned_split`, `block_size = self.cache_config.block_size` / `block_size = self.block_size` 출현을 따로 기록한다.
- `src/patches/qwen-tool-argument-schema.patch`: `ParserEngine`에 `_normalize_tool_arguments`, `_arguments_block_emission`, `_skip_incomplete_tool_slot`, `_buffer_ambiguous_arguments` 관련 원본 소스 이름·시그니처가 존재하는지 확인한다.
- `src/patches/qwen-tool-marker-guard.patch`: `StreamingParserEngine._marker_is_literal` 및 `parser_engine_config.guard_literal_tool_markers` 출현 확인.
- `src/patches/qwen-safe-output.patch`: Responses streaming의 `response.failed`, `response.incomplete`, `_make_failed_response_event` source hint 확인.
- `src/patch_mtp_draft_vocab.py`: Qwen 모델 트리의 실제 MTP 후보 경로와 `compute_logits` 시그니처 존재 여부를 조사한다. **이 스크립트를 설치 엔진에 적용하지 않는다.**

**중요:** 이 문자열/AST 검사만으로 취약점의 존재, 대응 패치 적용 가능성, native upstream fix, 실 API 동작을 확정하지 않는다. 의미론적 호환성은 함수 본문·config shape·spec decoding 및 cache state lifecycle을 별도로 비교해야 한다. 이 단계는 다음 안전한 검증 범위를 결정할 증거 수집이다.

## 3. DGX에서 이번 추가 단계만 실행 (운영 자원 격리)

Phase 5 전용 경로가 기존에 존재해야 한다. 신규 clone/이전 브랜치 checkout/Reset/clean을 하지 않는다. `git pull --ff-only`는 원격 Phase 5만 가져오며, 변경·untracked 소스가 있으면 **중단한다**.

```bash
(
  set -Eeuo pipefail
  REPO="kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark"
  SRC="$HOME/Workspace/llm/blazux-phase5-correctness-mtp-offline"
  BRANCH="feature/blazux-phase5-correctness-mtp-offline"
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
  git rev-parse HEAD
  scripts/phase5-check-offline.sh

  IMAGE="$(docker inspect --format '{{.Image}}' "$CONTAINER")"
  docker run --rm --pull=never --network=none --runtime=runc \
    --read-only --tmpfs /tmp:rw,mode=1777,size=256m \
    --cpus=2 --memory=2g --pids-limit=128 \
    --mount "type=bind,src=$SRC,dst=/phase5,readonly" \
    --workdir /phase5 \
    -e CUDA_VISIBLE_DEVICES=-1 -e PYTHONDONTWRITEBYTECODE=1 \
    --entrypoint python3 "$IMAGE" \
    src/phase5_preview_abi_audit.py

  echo "PASS: PHASE5_READONLY_ABI_TRIAGE_EXECUTED_NOT_CERTIFIED"
)
```

### 기대 출력 구분

- Stdlib 테스트: 이전 208개에 **신규 7개를 추가한 총 215개, XFAIL=0 예상**. Source Manifest는 신규 파일 수에 따라 갱신된다. **DGX 실제 실행 전에는 기대값일 뿐 PASS가 아님.**
- 설치 엔진 조사: JSON에 `components.mamba`, `scheduler`, `parser_engine`, `parser_qwen3`, `streaming_parser`, `parser_config`, `responses_serving`, `responses_protocol`, `model_search`가 기록되고, 마지막에 `PHASE5_PREVIEW_ABI_SOURCE_AUDIT_DONE_NOT_COMPATIBILITY_CERTIFIED` 출력.
- **`model_search.state`이 `SCAN_LIMIT_REACHED`/ `CANDIDATE_LIMIT_REACHED`면 일부 후보 미확인**이다. 파일 위치 탐색을 더 좁혀 같은 Phase5에서 검증하고, 해당 영역 적용은 계속 보류.
- 마지막 echo PASS는 *읽기 전용 분석 실행 성공*이지 실제 vLLM 호환성 승인/테스트 통과를 뜻하지 않는다.

## 4. 이후 같은 Phase 5에서 할 일과 승인 제한

사용자 DGX의 source triage JSON/HEAD를 받아 **실제 모델 MTP/PLE 경로**와 legacy/native fix 여부, parser용 클래스·시그니처·소스 anchor를 비교하고 **PATCH_CANDIDATE / NATIVE_ALREADY_PRESENT / ABI_MISMATCH / INCONCLUSIVE**처럼 증거 중심으로 범위를 확정한다. 네 상태는 평가 분류이지 runtime PASS가 아니다. Source-only 선별 이후에도 GPU/HTTP 실 추론·MTP acceptance·캐시 state checksum은 별도 승인까지 금지.

현재 **PR·Merge 불필요**. 필요해도 Phase5 `head` → Phase4 `base` 비병합 Draft 리뷰만 허용하며, `main` 대상 PR/merge/cherry-pick/rebase/squash/sync 영구 금지. P0/Phase1~4는 불변.
