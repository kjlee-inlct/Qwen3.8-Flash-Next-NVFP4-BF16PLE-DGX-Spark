# Track A Phase 5 — P1 정확성·P2 후보 위험 검증을 하나의 Gate로 통합

> **최신 상태: PHASE5_DGX_CPU_OFFLINE_PASS / SOURCE_144_144 / UNIT_208_XFAIL_0 / MICROBENCH_12_CONDITIONS / INSTALLED_SOURCE_INVENTORY_CAPTURED / ACTUAL_VLLM_ABI_NOT_VERIFIED / GPU_NOT_RUN / CI_NOT_VERIFIED.**
>
> 작성: 2026-10-27 (Asia/Seoul). **부모:** Phase 4 검증 기록 HEAD `69860277122dffe3082c5b065e4361a571317a8e`; **자식 브랜치:** `feature/blazux-phase5-correctness-mtp-offline`. 이전 P0/Phase 1~4 및 `main` 불변. 사용자의 Phase 최소화 요구에 따라 Prefix/cache·Parser/Responses·MTP vocabulary 후보·CPU gather 벤치를 **하나의 Phase 5**에 묶어 진행한다.
>
> blazux 소스는 [외부 PIN `8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa`](https://github.com/blazux/qwen3.8-Flash-DGX/tree/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa)에 고정한다. 출처 기능: `src/patch_mamba_block_size.py`, `src/patch_mtp_draft_vocab.py`, `src/patches/qwen-tool-marker-guard.patch`, `src/patches/qwen-tool-argument-schema.patch`, `src/patches/qwen-safe-output.patch`.
>
> **핵심 경계:** 이 Phase 5는 실제 설치된 preview vLLM의 `StreamingParserEngine`, `MambaHybrid`, speculative drafter를 패치하는 단계가 **아니다**. 저장소에는 그 프레임워크 본문이 vendored되어 있지 않아 소스 ABI를 모르는 상태에서 적용하면 잘못된 기능 PASS를 만들 수 있다. 합성 oracle 테스트 성공은 실제 prefix hit·Tool Calling·Responses·MTP acceptance 성공과 다르다.

## DGX 통합 실기 시험 완료 — 실행 계획 이후 최종 결과

- **정확한 실측 소스 HEAD `01c9eb6ba311e3ace5f68ecc49fa56f8e0b37d94`**: `PASS_SOURCE_ONLY: 144 tracked file(s)`; **208 tests OK, XFAIL=0**, `PHASE5_SOURCE_AST_OK`, `PASS: PHASE5_OFFLINE_ORACLES_AND_SOURCE_CONTRACTS`, 최종 `PASS: PHASE5_BUNDLED_DGX_OFFLINE_EXECUTION`.
- 기존 Phase2~4 BF16 PLE workers 1/4 byte-exact, 중복 샤드 guard, 4가지 FAST/STATS byte-exact 전부 PASS. 신규 소형 합성 CPU microbench **12조건 정상 종료**: `PHASE5_SYNTHETIC_CPU_BENCH_ALL_OK`. 이는 실제 95.37GiB NVMe·모델 TPS 성능 검증이 아니다.
- 설치 vLLM **읽기 전용 소스 SHA/AST inventory 확보**, `PHASE5_VLLM_SOURCE_INVENTORY_DONE_NOT_ABI_CERTIFIED`. `mamba_hybrid/scheduler/parser_qwen3/parser_engine/streaming_parser/responses_serving` 소스 확인, 조사기의 `qwen38_mtp` 및 `qwen38_ple` 두 **예상 경로는 ABSENT_OR_RELOCATED** — 실제 코드가 없다는 확정이 아니라 경로/ABI 추가 확인 필요.
- 실제 prefix cache/SSM state cache-hit 정합성, Tool Calling/Responses 실 엔진 JSON/SSE, MTP reduced draft vocab acceptance, GPU/실 모델/TPS/CI는 **NOT_VERIFIED**. 합성 oracle 성공을 실제 엔진 적용·기능 PASS로 과대 표시하지 않는다.
- [Phase5 DGX 검증 결과 정본](BLAZUX-PHASE5-DGX-VALIDATION-RESULTS-20261027.md)에 12건 CPU latency 원문 수치 및 8개 설치 소스 관측 결과를 기록했다. 이 문서를 추가하는 **docs-only 후속 Git SHA는 DGX에서 실행한 SHA가 아니다.**

## 1. 한 Phase 안에 묶은 기능과 실제 구현

| 우선순위 | 작업 | 구현 파일 | 인정 가능한 증거 | 미인정 |
|---|---|---|---|---|
| P1 | Prefix cache/Mamba state index 정렬 계약 | `src/phase5_offline_contracts.py`; `tests/test_blazux_phase5_contracts.py` | `(tokens-1)//mamba_block_size`, 1600/16 경계·미정렬 거부의 synthetic CPU oracle | 실제 scheduler cache hit / SSM state restore 정확성 |
| P1 | Tool Calling / Responses 클라이언트 경계 | 위 두 파일 | offered/unoffered, JSON arguments, schema 제한, partial/wrapped JSON, Chat untrusted vs Responses rejected, completed/failed/incomplete/error terminal, stream sequence 검사 | 설치 parser/tokenizer/SSE와 동등성 |
| P2 | MTP reduced draft vocabulary 위험 평가 | 위 두 파일 | 범위/중복/필수 ID fail-closed, 후보 subset이 제안 토큰과 conceptual acceptance를 바꾸는 예시 | 실제 BF16 lm_head subset/hybrid loader/throughput/quality/acceptance |
| P2 | PLE Fast Gather OFF/ON 소형 CPU wallclock | `src/test_ple_phase5_bench_cpu.py` | 동일 합성 데이터, stats OFF, seed/warmup/repeats 명시, byte-exact 확인과 median/p95 출력 | 실제 95GiB PLE I/O/TPS/TTFT 개선 판정 |
| P1 준비 | 현재 설치 vLLM read-only ABI 조사지 | `src/phase5_vllm_source_inventory.py` | import/패치 없이 설치 vLLM 파일 존재·SHA256·AST symbol inventory (안 보이면 ABSENT_OR_RELOCATED) | ABI 호환 인증, 런타임 동작 |
| 공통 | 통합 한 번의 offline gate | `scripts/phase5-check-offline.sh` | Source Manifest/Mock/unit/audit/branch 보호 및 XFAIL 0 | 모델·GPU·운영 서비스 검증 |

### 1.1 중요한 의사결정

- **Prefix-cache:** 외부 `patch_mamba_block_size.py`는 그룹의 작은 QSA block(예: 16)과 Mamba state block(예: 1600)을 혼용하는 문제를 다룬다. 여기서는 *개념적 index oracle*만 확인한다. 실제 캐시 사용 전후 logits/생성 결과 비교는 이후 **실제 엔진에서 별도 승인된 추론 검증**이 필요하다. Cache hit을 CPU 계산만으로 PASS라고 주장하지 않는다.
- **Tool Calling/Responses:** Chat 출력으로 노출된 unoffered tool name은 클라이언트가 오류 복구에 사용할 수 있으나 **실행하면 안 된다**. Responses strict는 reject 분류. 해당 분류는 안전한 클라이언트 측 fixture이며 preview/v0.32의 서버 구현이라고 주장하지 않는다. 현재 제공하는 schema oracle은 string/integer/boolean·required subset만 지원하고 unsupported type은 fail closed한다. Partial JSON이나 nested wrapper도 자동실행 금지.
- **MTP reduced vocabulary:** 원 blazux script는 `lm_head` 일부 행만으로 draft logits를 만들고 후보 외 토큰을 `-inf`로 채운다. 이 변경은 draft 후보 및 target의 accepted draft 횟수를 바꿀 수 있다. Orcarouter의 BF16 MTP 31개 텐서·원본 `lm_head`·현재 모델 checkpoint는 **절대 수정하지 않는다**. **기본 적용 REJECT / 별도 호환성 판단 전 코드 패치 없음**. 최소 vocab ID 정책·실제 tokenizer/sampler·EOS/한국어/도구 출력 품질 Gate가 필요하다.
- **Fast Gather:** 이전 Phase 4의 `VLLM_PLE_FAST_GATHER=0`과 `VLLM_PLE_PHASE_STATS=0`은 그대로 기본 OFF. Phase 5 소형 benchmark는 *측정 설계/출력*이며 실행 전 결과 없음. 샘플이 13행×7열이어서 페이지 캐시·NVMe latency를 재현하지 못한다.

## 2. 성공 조건과 Go/No-Go

**1차 Gate 5 (본 커밋으로 준비한 것):** 별도 DGX checkout의 exact HEAD, Source Manifest 전체 일치, Mock, unittest의 기존 194건 + 신규 14건 = **총 208건 기대, XFAIL=0**, Bash·Publication Audit·AST 구문 PASS. 실행 전 기대 수치이므로 **아직 PASS를 선언하지 않는다**.

**2차 Gate 5 (기존 CPU 이미지의 격리 임시 컨테이너):** 기존 Phase 3 중복 샤드 및 Phase 4 4-mode byte exact 재확인, 새 PLE CPU microbench 결과 JSON 12개와 `PHASE5_SYNTHETIC_CPU_BENCH_ALL_OK`, 설치 preview vLLM 파일 SHA/심볼 read-only inventory 결과 `PHASE5_VLLM_SOURCE_INVENTORY_DONE_NOT_ABI_CERTIFIED` 기록. 빈 소스 혹은 미발견 ABI는 BLOCKED로 기록하며 새 vLLM 설치/다운로드로 보완하지 않는다.

**후속 승인 경계:** 실제 Prefix-cache 검증, Tool/Responses HTTP 비교, MTP 축소 draft 적용은 테스트 oracle PASS만으로 **자동 실행 불가**. 저장소의 정식 baseline(12조건×3회=36회)은 다른 모델/설정의 결과와 동일 기준으로 비교해야 하며, 사용자 별도 GPU/모델 시험 승인 전에는 이식/가동하지 않는다.

## 3. DGX 단일 오프라인 검증 절차

기존 `yslab-qwen38-bf16ple-dgx-spark` 체크아웃을 switch/clean/reset 하지 않는다. 다른 Phase 체크아웃도 수정하지 않는다. 다음 단일 Shell 블록은 **Phase 5 전용 빈 경로**에서만 새 clone을 만들고 모든 표준 라이브러리 시험을 수행한 후, 기존 컨테이너의 정확한 이미지 ID로 **별도 임시 CPU-only 컨테이너 하나**에서 CPU 시험 3개와 ABI 인벤토리를 이어서 실행한다. 기존 Docker 컨테이너를 stop/restart/rm/recreate하지 않는다.

```bash
(
  set -Eeuo pipefail
  REPO="kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark"
  SRC="$HOME/Workspace/llm/blazux-phase5-correctness-mtp-offline"
  BRANCH="feature/blazux-phase5-correctness-mtp-offline"
  CONTAINER="qwen38-flash-orca-uncensored-bf16-mtp"

  test ! -e "$SRC"
  git clone --single-branch --branch "$BRANCH"     "https://github.com/$REPO.git" "$SRC"
  cd "$SRC"
  git rev-parse HEAD
  scripts/phase5-check-offline.sh

  IMAGE="$(docker inspect --format '{{.Image}}' "$CONTAINER")"
  docker run --rm --pull=never --network=none --runtime=runc     --read-only --tmpfs /tmp:rw,mode=1777,size=256m     --cpus=2 --memory=2g --pids-limit=128     --mount "type=bind,src=$SRC,dst=/phase5,readonly"     --workdir /phase5     -e CUDA_VISIBLE_DEVICES=-1 -e PYTHONDONTWRITEBYTECODE=1     --entrypoint /bin/sh "$IMAGE" -c     'set -eu; python3 src/test_ple_phase2_cpu.py; python3 src/test_ple_phase4_cpu.py; python3 src/test_ple_phase5_bench_cpu.py; python3 src/phase5_vllm_source_inventory.py'

  echo "PASS: PHASE5_BUNDLED_DGX_OFFLINE_EXECUTION"
)
```

`$SRC` 경로가 이미 존재하면 위 clone을 다시 시도하지 않는다. 별도 안전한 `git fetch --no-tags origin "$BRANCH"` / clean·origin·branch 확인 / `git pull --ff-only` 경로를 사용할 것. 원본 이미지에는 이미 Phase 2/3/4 PyTorch CPU fixture 성공 증거가 있지만, Phase5 코드는 새 HEAD이므로 반드시 새 로그를 구분한다.

## 4. 기밀/성능 해석·분기 정책

- ABI 인벤토리 도구는 패키지를 import/monkeypatch하지 않고 Python spec와 **해당 파일만** 읽으며, SHA256·문법·심볼 목록을 표준출력한다. `ABSENT_OR_RELOCATED`를 호환성 PASS로 사용하지 않는다. `NOT_ABI_CERTIFIED`가 출력돼도 실제 API 호환성을 인증한 것이 아니다.
- CPU microbench 21회 샘플/4회 warmup, N=16/64/256/512/513/1024, 분포 2종의 소형 13×7 파일만 사용하며 실제 `throughput` 개선값으로 보고하지 않는다. 타 실험 CPU 부하에 따라 오차가 발생할 수 있다.
- 이 Phase는 **사용자 요청대로 통합**한다. 신규 oracle 결함, 추가 정확성 fixture, CPU 결과 기록은 Phase 5 자체에서 수정·보강·커밋한다. 사소한 작업마다 Phase 6/7로 늘리지 않는다.
- **허용 PR 방향(실제 필요할 때만, 비병합 Draft):** `head=feature/blazux-phase5-correctness-mtp-offline` → `base=feature/blazux-phase4-ple-cpu-bundle`. 해당 Draft도 **Merge하지 않는다**.
- **영구 금지:** blazux 실험에서 `main` 대상으로 PR/Merge/Cherry-pick/Rebase/Squash/Sync 금지. P0, Phase1~4 refs 불변. runtime Docker/Model/HF cache/ports/receipts 변경 금지.

## 5. Gate 이후 보류 항목 (별도 승인)

- 실제 Mamba state cached-vs-uncached byte/logit/reasoning equivalence, parser/Responses SSE/JSON streamed chunk tests는 **실 엔진 ABI를 확인한 후에만** 실제 테스트 harness 사용 가능. 별도 승인 전 기존 운영 endpoint 호출·추론 작업 금지.
- MTP reduced draft vocab은 기본 적용하지 않는다. Tokenizer 원형, draft-vs-target vocab, EOS/한국어/공백/Tool Calling·품질·acceptance·속도 데이터를 기반으로 Go/No-Go가 필요하다.
- vLLM 0.32 엔진 포팅은 **별도 Track B**, Go/No-Go 이전 브랜치 생성 금지. YaRN 500K, Hybrid FP8는 P3 보류.

**기준:** [Phase 4 DGX PASS 보고서](BLAZUX-PHASE4-DGX-VALIDATION-RESULTS-20261027.md)와 최초 [blazux 소스 계약 비교표](BLAZUX-PHASE1-GATE1-SOURCE-COMPARE-20261027.md). 모든 실측 결과는 exact Git HEAD와 증거를 분리 기록한다.
