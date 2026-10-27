# Phase 5 확장 — pinned blazux 패치별 Source Preflight (no-write)

> **최신 상태: DGX_SOURCE_PREFLIGHT_PASS / SOURCE_152_152 / MOCK_38_38 / UNIT_223_XFAIL_0 / PATCH_APPLICATION_NOT_APPROVED / ENGINE_COMPATIBILITY_NOT_CERTIFIED.** 2026-10-27 Asia/Seoul.
> 이전 Phase5 **DGX 실제 통과**: source `9e2d1647357938f6d465eb9b3ce473d03e38e779`, 148/148 Source, unittest 215/215 XFAIL=0. 이후 **문서 전용** HEAD `e3ea43e95cb444197400389b0dfe3064a3e9f879`. 이번 코드와 보고서가 추가된 **새 소스 HEAD는 아직 DGX 재실행 전**이다.
>
> 비교 기준: blazux [PIN `8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa`](https://github.com/blazux/qwen3.8-Flash-DGX/tree/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa). 동일 Phase5 브랜치 `feature/blazux-phase5-correctness-mtp-offline` 유지; PR/Merge·운영 수정 없음.

## 동일 Phase 5의 다음 Dependency Trace — 신규 작업 (DGX 실행 전)

- 직전 사용자 DGX 실측은 Source 152/152, unit 223/223 XFAIL0의 실제 `2c7c6896430be0d9eada656f17edf97d9c5f4d3f`; 이를 보고한 docs-only HEAD는 `e0dbed59b3ef8c5b7a3c843a904c4c96532f22e6`.
- 다음 동일 브랜치 Gate는 [Mamba/Scheduler·Parser/Responses·MTP AST Dependency Trace](BLAZUX-PHASE5-DEPENDENCY-TRACE-READONLY-20261027.md). 새 코드 `src/phase5_dependency_trace.py` 및 신규 10개 stdlib fixture를 포함해 **233 tests XFAIL0 예상**, 실제 새 DGX 실행은 아직 NOT_RUN.
- `mamba_block_size`의 source STORE/LOAD는 runtime cache field provisioning을 보증하지 않고, Parser/Responses AST 호출관계는 실제 SSE/Chat tool 실행이 아니며, MTP `lm_head` 대입은 같은 tensor storage alias·TP shard shape를 보증하지 않는다. **어떤 blazux source patch도 바로 적용하지 않는다**.

## 2026-10-27 DGX 실제 Patch Preflight 결과 — 최초 준비 상태보다 우선

- **사용자 DGX 실측 정확한 HEAD `2c7c6896430be0d9eada656f17edf97d9c5f4d3f`**: Source Manifest 152/152 PASS(전후), Wizard mocks 38/38 PASS, unittest 223/223 PASS, XFAIL=0, AST 검사 PASS, `PHASE5_OFFLINE_ORACLES_AND_SOURCE_CONTRACTS`, `PHASE5_PATCH_PREFLIGHT_SOURCE_ONLY_DONE_NO_APPLY_APPROVAL`, `PHASE5_PATCH_PREFLIGHT_EXECUTED_NOT_CERTIFIED` PASS.
- 설치 preview vLLM **12개 파일 Source SHA256/AST method fingerprint/anchor count 수집 완료**. 다섯 패치 계열의 `preflight.status`는 각각 Mamba `SOURCE_PREIMAGE_CANDIDATE_UNSAFE_TO_APPLY`, Tool Schema 및 Literal Marker `MULTI_FILE_PATCH_PREREQUISITES_UNVERIFIED`, Responses `PROTOCOL_AND_SERVING_COMPATIBILITY_UNVERIFIED`, MTP `MTP_COMPUTE_LOGITS_HOOK_CANDIDATE_NOT_APPROVED`. **적용 승인 0건**.
- **Mamba:** legacy `self.cache_config.block_size` 1회, `self.cache_config.mamba_block_size` 0회, Scheduler legacy assignment 1회. 해당 field/LCM/state-slot 단위 연결 확인 전 수정 금지.
- **MTP:** NVIDIA `models/qwen3_8_flash_next/nvidia/mtp.py`의 `compute_logits(self,hidden_states,spec_step_idx)` lines 465–468, `load_weights(self,weights)` lines 470–488 확인. 실제 lm_head 공유/weight shape/vocab/acceptance 미검증.
- **Tool/Responses:** Parser/Adapter helper 및 Responses failed/incomplete event source anchor 부재(현재 확인된 각 소스에서만). 다중파일 패치 전제 및 실제 SSE/Chat 동작 검증 전 적용 금지.
- [DGX Source Preflight 정본 실측 보고서](BLAZUX-PHASE5-DGX-PATCH-PREFLIGHT-RESULTS-20261027.md)에 원래 SHA 및 12개 컴포넌트 SHA·추가 차단요소 기록. **이후 보고서/Manifest만 추가한 docs-only SHA는 DGX에서 223개 재실행된 SHA가 아니다**. GPU/실 모델/HTTP/TPS/CI 전부 NOT_RUN/NOT_VERIFIED.

## 1. 이번에 구현한 검증

| 파일 | 목적 |
|---|---|
| `src/phase5_patch_readiness.py` | 기존 이미지의 `vllm` 패키지를 import하지 않고 Python 소스 **12개**를 bounded read/AST parse하여 SHA256, 고정 anchor 개수, 클래스별 함수 인자·line range·AST 구조 SHA256 기록. **소스 원문과 절대 설치경로는 출력하지 않음** |
| `tests/test_blazux_phase5_patch_readiness.py` | 별도 fake Python 패키지 트리의 Mamba/Scheduler preimage, native/no legacy, Parser/Responses multi-file, MTP class/hooks, 해시·broken AST, symlink 안전, non-approved 상태 등 **신규 8개 unittest** |
| `scripts/phase5-check-offline.sh` | 이전 unit 215개 + 신규 8개 = **223개 예상, XFAIL 0 목표**. Source Manifest/Mocks/AST/audit 검증 포함 (실기 실행 전 값은 예상일 뿐) |

**주의:** 이 검사기는 pinned blazux patch 파일 자체에 patch를 적용하거나 서버 코드를 수정하지 않는다. **Pinned patch의 명확한 전제조건**을 실제 설치된 preview source AST/문자열과 대조할 재현 가능한 기록을 생성한다. String anchor는 주변 문맥이나 실행 조건을 보증하지 않으므로 `SOURCE_PREIMAGE_CANDIDATE_UNSAFE_TO_APPLY`도 실제 patch 승인 상태는 아니다.

## 2. 발견된 실제 ABI 계약과 다음 검증 경계

이전 [사용자 DGX 설치 소스 보고서](BLAZUX-PHASE5-DGX-PREVIEW-ABI-TRIAGE-RESULTS-20261027.md)로 아래 소스는 이미 확인했다.

- NVIDIA `models/qwen3_8_flash_next/nvidia/mtp.py`: `Qwen3_8FlashNextMTP.compute_logits(self,hidden_states,spec_step_idx)`·`load_weights(self,weights)`, PLE `ple_layer.py`의 `forward(self,hidden_states,input_ids,query_start_loc,ngram_context)`. 이는 source-only 확인.
- Mamba `MambaHybridModelState.add_request`의 legacy state-index 계산 및 Scheduler `_mamba_block_aligned_split`의 legacy block assignment source 표현 존재. blazux pinned `patch_mamba_block_size.py`의 첫 수정은 `(num_computed_tokens - 1)//(self.cache_config.mamba_block_size or self.cache_config.block_size)`, Scheduler 수정은 `self.block_size`를 사용한다. **`cache_config.mamba_block_size` 실제 필드 공급, worker/scheduler group LCM, state-slot lookup/restore 메모리 레이아웃을 함께 검증하지 않으면 변경 불가**.
- Tool/Responses는 pinned `qwen-tool-argument-schema.patch`, `qwen-tool-marker-guard.patch`, `qwen-safe-output.patch`가 `ParserEngine`, `Qwen3Parser`, adapters, abstract parser, Streaming Parser/Config, Responses Protocol/Serving 및 **신규 validation helper**를 가로지른다. 이전 preview 소스에서 `_check_skip_tool_parsing`, `_normalize_tool_arguments`, `_marker_is_literal`, `_make_failed_response_event` 등을 찾지 못했다. **단일 파일 패치 불가; 정확한 여러 파일의 preimage·하위 의존성 검사 우선**.
- Pinned `patch_mtp_draft_vocab.py`는 `VLLM_MTP_DRAFT_VOCAB=<ids.npy>`가 설정될 때 **draft `lm_head.weight` 행 subset을 GPU에서 만들고 외부 ID에 `-inf`를 채우는 hook**이다. 현재 `compute_logits` 이름이 같아도 weight shape/group/shared head, vocabulary 원형, sampler, EOS/한국어/Tool 출력, speculative acceptance 및 메모리 여유를 검증해야 한다. **프로덕션 checkpoint와 실제 MTP `lm_head`는 절대 건드리지 않는다.**
- PLE는 현재 CPU synthetic byte-exact 테스트와 실제 95GiB NVMe/GPU inference를 구분. Phase 4 FAST 기본 OFF와 통계 기본 OFF도 변경 없음.

## 3. 이번 Gate 평가 상태 (소스 기준만)

| 후보 | 점검기 결과 분류 | Gate 조건 |
|---|---|---|
| Mamba + Scheduler | `SOURCE_PREIMAGE_CANDIDATE_UNSAFE_TO_APPLY` 또는 `PREIMAGE_MISMATCH_OR_NATIVE_REVIEW` | 두 소스 파일 + 기존 표현 + cache config/body/LCM 문맥 필요 |
| Tool argument schema | `MULTI_FILE_PATCH_PREREQUISITES_UNVERIFIED` | 여러 Parser/serving 파일 및 validator dependency와 schema state 연결 |
| Tool literal marker | `MULTI_FILE_PATCH_PREREQUISITES_UNVERIFIED` | Token ID / partial token / parser config 연결 |
| Responses terminal | `PROTOCOL_AND_SERVING_COMPATIBILITY_UNVERIFIED` | ResponseFailed/Incomplete / error conversion / sequencing 확인 |
| MTP draft vocabulary | `MTP_COMPUTE_LOGITS_HOOK_CANDIDATE_NOT_APPROVED` 혹은 `MTP_ABI_SIGNATURE_INCOMPLETE` | lm_head sharing / weight loader / sampling·acceptance 검증 |

**어떤 상태도 `APPLY_APPROVED`를 생성하지 않는다.** 실제 함수의 AST 구조 fingerprint와 샘플 소스 anchor count를 비교해 사후 diff 시 변경 여부를 판별하되, AST/문자열만으로 함수 동작과 논리 정합성을 증명할 수는 없다.

## 4. 단일 DGX 검증 블록

기존 Phase5 **전용 별도 checkout**을 ff-only 업데이트한 다음 source/Mock/unit/AST/audit를 먼저 실행하고, 운영 중인 컨테이너의 **기존 이미지 ID를 조회만** 해서 읽기 전용 CPU-only 임시 컨테이너에서 source preflight JSON을 실행한다. 원본 Docker stop/restart/recreate, image build, GPU 작업, HF cache/weights 변경, main/다른 Phase checkout 작업은 하지 않는다.

```bash
(
  set -Eeuo pipefail
  REPO="kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark"
  SRC="$HOME/Workspace/llm/blazux-phase5-correctness-mtp-offline"
  BRANCH="feature/blazux-phase5-correctness-mtp-offline"
  EXPECTED="REPLACE_WITH_PHASE5_COMMITTED_HEAD"
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
    --entrypoint python3 "$IMAGE" src/phase5_patch_readiness.py

  echo "PASS: PHASE5_PATCH_PREFLIGHT_EXECUTED_NOT_CERTIFIED"
)
```

**주의:** 본 문서의 `EXPECTED`는 문서 생성 시 새 커밋 SHA를 알 수 없으므로 배포 설명에 placeholder로 남긴다. 최종 사용자 명령에는 GitHub에서 정확히 검증된 새 SHA를 하드코딩한다. 절대로 이전 실기 SHA를 새 코드 실측으로 주장하지 않는다.

예상 종료 `PHASE5_UNIT_PASS=223; XFAIL=0`, `PHASE5_PATCH_PREFLIGHT_SOURCE_ONLY_DONE_NO_APPLY_APPROVAL`, 최종 `PHASE5_PATCH_PREFLIGHT_EXECUTED_NOT_CERTIFIED` (이상 실행 전 기대 출력). 조사 JSON의 `preflight` 5항목과 `components` 12파일, 선택 함수 AST fingerprint를 영구 기록하고 **실제 PATCH_READY/PATCH_APPLIED/GPU_VERIFIED 같은 용어로 승격하지 않는다**.

## 5. PR / Safety

동일 CPU/source-only 안전 경계의 문제·추가 시험·문서 보고는 Phase5 브랜치 내부에 모아 시행한다. **지금 PR/Merge 불필요**; 필요해도 `head=feature/blazux-phase5-correctness-mtp-offline` → `base=feature/blazux-phase4-ple-cpu-bundle` **비병합 Draft review**만 허용. `main` 대상 PR/merge/cherry-pick/rebase/squash/sync **영구 금지**. 이전 Phase, 기존 운영 Docker/모델/포트/컨테이너 receipts/HF cache 변경 금지.
