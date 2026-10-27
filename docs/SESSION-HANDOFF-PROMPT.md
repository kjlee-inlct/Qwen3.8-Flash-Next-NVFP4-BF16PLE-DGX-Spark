# SESSION-HANDOFF-PROMPT.md

> 기준: **2026-10-27 (Asia/Seoul)**. 이 파일은 다른 ChatGPT/개발 세션에서 현재 프로젝트를 그대로 이어받기 위한 **상시 인수인계 프롬프트**다. 2026-10-26 Wizard 시험은 역사적 운영 증거이며, 최신 진행 과제는 **blazux Track A 정적 비교(Gate 1)**다.  
> 개인 저장소: [kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark](https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark).  
> **중요:** 이 문서의 commit/시험 결과는 기록 당시의 스냅샷이다. 새 세션에서는 GitHub의 실제 최신 `main`, PR, CI와 사용자 DGX의 새로운 로그를 확인해야 한다.

---

## 현재 진행 상태 및 새 세션 우선 읽기 — 2026-10-27

> **현재 작업을 이어받을 때 이 절을 가장 먼저 적용한다.** 아래 2026-10-26 Wizard 검증·PR #1/#3 기록은 실제로 수행된 **과거 테스트**이며 삭제하지 않는다. 새로운 GitHub HEAD에 대해 DGX 테스트가 다시 PASS했다는 뜻이 아니다.

| 항목 | 최신 확인된 기준 | 다음 세션의 해석 |
| --- | --- | --- |
| 개인 GitHub \`main\` | **2847e39b4131eb8aff78bf86ffce98892401722a** | 2026-10-27 조회한 PR #5 병합 커밋. 새 세션에서 HEAD 재조회 |
| 현재 개발 브랜치 | **\`feature/blazux-vllm032-evaluation-20261027\`** | blazux **Track A** 검토·계획 브랜치. 새 세션에서 HEAD/트리 재조회 |
| 기록된 설계 보강 커밋 | **0e9b25d93eb533b1936930c77bf7f7b874ec0b60** | 2026-10-27 설계서 보강 기준. **본 핸드오프 갱신 커밋 자체의 SHA 아님** |
| 신규 PR | **없음** (2026-10-27 조회) | 현재 브랜치를 성급히 \`main\`에 병합하지 않는다 |
| 실험 원본 blazux | **8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa** | [외부 기술 참조](https://github.com/blazux/qwen3.8-Flash-DGX); 원본 저장소 전체 merge·serve.sh 실행 금지 |
| 성능 Baseline | PR **#5 MERGED**, 정식 **12조건 × 각 3회 = 36회** | [보고서](benchmark/LLAMA-BENCHY-BASELINE-20261027.md) 및 원본 JSON·해시가 \`main\`에 보존됨 |
| Benchmark helper | \`scripts/benchmark/run-llama-benchy.sh\` | PR #5에 포함됐으나 **신규 wrapper 자체의 DGX 실행은 NOT_RUN** |
| Wizard DGX 검증 | \`main=66051cdcd4b2c5766de55421579867c195fe4084\` | 2026-10-26 source **114/114**, mock **38/38**, unit **172/172**, legacy Health PASS; **이후 소스 SHA로 승격 금지** |
| Source Manifest | 현 기능 브랜치의 \`files[]\` **120개 + Manifest 자체 1개** | 새 변경시 Git 트리 path/mode/blob SHA와 모두 일치시켜 **같은 커밋**에 저장 |
| GitHub CI / branch protection | Actions run **0** → \`CI_NOT_VERIFIED\`; \`main.protected=false\` | CI 정상화는 사용자 요청으로 보류. \`main\`의 PR 리뷰 보호는 **운영 정책**, 강제된 GitHub 보호 설정이 아님 |
| 엔진·GPU 실기기 | blazux 구현/이미지 빌드/A/B 시험 **NOT_STARTED** | 기존 레거시 컨테이너·모델·포트·영수증은 변경 금지 |

**두 개발 트랙은 섞지 않는다.** **Track A**는 현재 preview vLLM에서 가능한 계측·정확성/성능 개선만 독립적으로 검토하고, **Track B** 공식 vLLM 0.32 포팅은 Go/No-Go 판단 뒤 \`feature/vllm032-bf16ple-port\` 별도 장기 브랜치에서 착수한다(**현재 해당 브랜치는 미생성**). Track A 작업이 Track B 시작이나 GPU 활성화를 자동 승인하지 않는다.

**최우선 다음 단계: Gate 1 정적 1:1 계약 비교.** [설계서](BLAZUX-VLLM032-ADOPTION-PLAN.md) §1.4/§3.1/Gate 1을 읽고, 현 preview와 고정 blazux 소스의 PLE \`mmap\`·BF16 offset/gather, MTP 31텐서/가드, QSA top-k, prefix-cache/SSM, Tool/Responses parser를 함수·데이터 flow 단위로 매핑한다. **KEEP / PORT / ADAPT / DEFER_TO_TRACK_B / REJECT**를 각 기능별 출처/위험/테스트 계약과 함께 기록한다. 새 GPU/Docker 작업은 하지 않는다.

---

## 2026-10-26 Wizard 검증 기준: DGX `main` 읽기 전용 실측 (PR #3 이후; 과거 이력)

> **Wizard 운영·시험에 한정된 당시 최신 기준.** 아래 오래된 PR #1/기능 브랜치 시험 및 보류 목록은
> 작성 당시의 **과거 이력**이다. 현재 진행 상태는 맨 위의 **2026-10-27 작업 요약**이 우선하며, 항목이 충돌하면 현재 GitHub 소스/새 DGX 로그를 대조한다.
> **이 문서를 포함한 다음 docs-only 머지 커밋은 DGX에서 다시 실행한 것이 아니다.**

- 최종 검증 대상: GitHub [PR #3](https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark/pull/3)
  **MERGED**, `main=66051cdcd4b2c5766de55421579867c195fe4084`.
- 사용자가 **실 DGX**의 `main`에서 `scripts/verify-main-readonly.sh` 실행 완료:
  `SOURCE_HEAD`가 위 SHA 및 로컬 `origin/main`과 일치, 마지막
  `PASS: local source/tests/observations; real new deployment NOT_TESTED` 출력.
- Source `--strict` **PASS_SOURCE_ONLY 114 tracked files**,
  deployment manifest PASS **4 targets**, wizard fake/mock **38/38 PASS**,
  전체 unit **172/172 PASS**. 쉘 구문과 publication audit도 읽기 전용
  일괄 스크립트가 오류 없이 통과했으나 별도 검사 로그는 분리되어 있지 않음.
- 기존 YSLAB 레거시: 컨테이너 **running**, 설치 식별 **PASS**, API Health·모델 목록
  **PASS/PASS**, Health **PASS**, **OBSERVE_ONLY**. Snapshot `GIT_CHANGED`
  (설치 정체성 0 / 서비스 변경 0 / Git HEAD 1): stored
  `3522190192da605c17709bede32a0df98d0ed406` →
  `66051cdcd4b2c5766de55421579867c195fe4084`.
  캐시·recipe-view 저장 여유 각 **539.74 GiB**, MemAvailable 약 **14.24~14.30 GiB**.
- PR #3: 기능 브랜치 `feature/ci-wizard-isolation-main-readonly-20261026`에서
  **2 commits**, 19 files changed, 일반 merge SHA 위의 `66051cdc...`.
  신규 Wizard 전용 `qwen38-wizard-<target>` 이름, 전용 ownership label,
  엄격한 영수증/ID 검증, 레거시 running 시 단일 GB10 동시 GPU 기동 차단.
  해당 소스의 모의 회귀시험은 위 최신 DGX 172/172에 포함된다.
- **P0-3 완료:** DGX 로컬 `main` 전환 및 병합 소스 검증 확인.
  **P0-2 코드/모의 검증 완료, 실 신규 배포/제거 미시험.**
  **P0-1 GitHub Actions 정상화는 사용자의 명시적인 결정으로 연기.**
  GitHub Actions **run=0 / check run=0** (최신 조회 시점),
  `CI_NOT_VERIFIED`; 원인 조사, 워크플로 수정, 설정 변경 및 재실행을
  이번 문서 동기화 PR에서 진행하지 않는다.
- 그 외 미완료: 신규 Wizard 이미지 빌드/가중치 준비/활성화/소유 자산 제거,
  실패 rollback, 중복 다운로드 회피, 레거시→Wizard 소유권 이전, 단일 GB10
  신규 GPU 및 240K/MTP 성능·안정성 실기기 검증. **현재 서비스 정지/교체 금지.**
- **향후 우선순위:** 운영 자산 보호 → 원격 최신 HEAD/로컬 clean·Health 관찰 →
  안전한 offline mock·rollback 설계 → 중복 다운로드 방지 설계 →
  실기기 신규 배포는 별도 명시 승인. CI는 사용자가 재개를 요청할 때 다룬다.

자세한 명령·로그별 구분: [2026-10-26 검증 증거](../scripts/VALIDATION-RESULTS-20261026.md).

---

## 0. 새 세션에서 사용할 최상위 지시

당신은 **단일 NVIDIA DGX Spark(GB10)**에서 실행하는 Qwen3.8-Flash-Next NVFP4/BF16 PLE + BF16 MTP 레시피의 **개인 Fork 운영·위자드 유지보수 및 blazux 선택적 최적화 검토 프로젝트**를 이어받은 엔지니어링 보조자다. **한국어**로 기술 분석, 코드, 설명, 보고를 작성한다. 현재 실행 과제는 **Track A의 Gate 1 함수별 소스 계약 비교**이며, 신규 위자드 실배포 또는 vLLM 0.32 포팅이 아니다.

**제1원칙은 현재 운영 중인 기존 YSLAB 서비스, Docker 이미지/컨테이너, HF 캐시, recipe views, 모델 가중치, 로컬 상태 파일, 포트 8000, 다른 Ollama/OpenWebUI 및 네트워크 서비스를 변경하지 않는 것이다.** GitHub 소스 변경과 운영 서버에 대한 변경은 서로 다르다.

연결된 **GitHub 플러그인/앱 도구**를 활용하면 저장소 파일 조회, 코드/문서 수정, 신규 스크립트 생성, blob/tree/commit 생성, 브랜치/PR 생성, diff 리뷰, PR 머지와 결과 재검증을 **직접 수행할 수 있다**. 사용자에게 불필요하게 수동 UI 작업을 시키지 말라. 단, 실제 연결 가능 여부를 매 세션 확인하고, 실행하지 않은 작업을 완료했다고 주장하지 말라. GitHub 작업 권한이 있다고 해서 실제 DGX Docker 서비스 변경 권한이 생기는 것은 아니다.

**실제 코드와 최신 GitHub `main`을 진실의 기준으로 삼는다.** 과거 계획서의 '미구현', 오래된 README의 'NOT TESTED' 표기는 나중에 수집된 DGX 로그·Git HEAD와 대조한다. 모순은 시점/출처를 밝혀 해결하고 문서에 반영한다. 이전 채팅이 끊겨도 이 문서의 우선순위/검증 방법을 따르도록 한다.

### 다음 세션 시작용 사용자 메시지 예시

> 개인 GitHub 저장소 `kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark`의 `main`과 `feature/blazux-vllm032-evaluation-20261027` 최신 HEAD를 **둘 다 먼저 확인**하고, 기능 브랜치의 `docs/SESSION-HANDOFF-PROMPT.md`와 `docs/BLAZUX-VLLM032-ADOPTION-PLAN.md`를 읽으세요. PR #5 Baseline 원본은 `main`에 병합됐고, 현재는 **Track A Gate 1 blazux↔현 preview 함수/텐서 계약 1:1 비교** 단계입니다. P1→P2→P3 우선순위, 별도 Track B `feature/vllm032-bf16ple-port` 미생성 상태, DGX 레거시/위자드 보호 규칙을 준수하세요. 필요한 변경만 문서·테스트·Source Manifest와 함께 기능 브랜치에 커밋하고, PR/머지는 사용자 요청과 리뷰 범위 안에서 직접 수행하세요. 테스트 미실행/CI 부재는 명시하고 Docker·모델 파일은 변경하지 마세요.

---

## 1. 프로젝트 및 확정된 Git 이력

| 대상 | 확인한 사실 |
| --- | --- |
| 개인 Fork | `https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark` |
| YSLAB 원본 upstream | `https://github.com/YSLAB-ai/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark` |
| 원본 PIN | `9492b78c6bc04638587b42f2ffeb0680b0fcb3ef` |
| 기능 브랜치 | `feature/install-uninstall-wizard-20261026` |
| 마지막 기능 브랜치 SHA | `25949fd7fb16ff62f8c6bdfc6f9fe9ab74fd0f8a` |
| [PR #1](https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark/pull/1) | **MERGED / CLOSED**, 일반 merge commit(8개 기능 커밋 유지) |
| PR #1 merge SHA | `bdc84eae28b7ce49ea2dde3c3923cfdf60382cf6` |
| 인수인계 문서 작업 시작 직전 `main` | `bdc84eae28b7ce49ea2dde3c3923cfdf60382cf6` |
| PR #1 병합 후 Git tree | `78ced78bb0c4381d3dd52c84b8d0f7f1082b3e9d` |
| 당시 Source Manifest | 111개 추적 파일 + Manifest 자체 blob SHA 일치 |
| GitHub Actions | 마지막 조회에서 workflow run/check run **0건**(CI PASS라고 주장 금지) |
| 이 문서 반영 이후 | **새 commit/PR가 생길 수 있으므로 반드시 원격 HEAD를 다시 확인** |

**이 단락은 PR #1 직후의 과거 기록이다.** 당시 개인 Fork `main`과 기능 브랜치의 Git tree 동일성을 GitHub 도구로 확인했다. 당시 사용자 DGX 로그는 기능 HEAD `25949fd7...`였지만 **이후 2026-10-26 사용자 DGX 로그에서 `main=66051cdc...` 전환·114/114, 38/38, 172/172 PASS가 확인되었다.** 현 원격 `main=2847e39...` 또는 blazux 기능 브랜치의 새 문서 커밋에 대해 DGX에서 재시험한 증거는 없다. GitHub PR 머지는 DGX 컨테이너를 재실행하거나 가중치를 변경하지 않는다.

---

## 2. 운영 중인 DGX — 바뀌면 안 되는 자산

사용자는 단일 NVIDIA DGX Spark를 운영하고 있다. 원래 YSLAB 설치로 모델을 실행했지만 설치 당시 repo 경로의 현재 Git origin이 **개인 Fork로 변경**되었다. **디렉터리 이름이 'yslab'이라고 해서 Git origin이 YSLAB이라고 판단하지 않는다.**

| 구분 | 사용자 DGX 로그에서 확인한 상태 |
| --- | --- |
| 호스트 checkout | `$HOME/Workspace/llm/yslab-qwen38-bf16ple-dgx-spark` |
| 원격 origin | `kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark.git` |
| 레거시 Docker 이미지 | `yslab-qwen38-bf16ple:9492b78c` |
| 레거시 컨테이너 | `qwen38-flash-orca-uncensored-bf16-mtp` — `running` |
| API 바인딩 | `0.0.0.0:8000`; 방화벽/외부 접근 정책 보존 |
| 모델 alias | `qwen3.8-flash-next-orca-uncensored-bf16-mtp` |
| 모델 context 보고값 | `262144` — API 메타데이터, 최신 회차 장문 추론 시험은 아님 |
| 캐시 mount | `$REPO_DIR/hf-cache` → `/recipe/hf-cache` |
| Recipe View mount | `$REPO_DIR/recipe-views` → `/recipe/recipe-views` |
| 레거시 receipt | `~/.local/state/yslab-qwen38-bf16ple/{paths,image-id,container-id}` |
| 새 wizard receipt | `~/.local/state/qwen38-flash-dgx/deployment-state.json` (XDG_STATE_HOME 등 오버라이드 가능) |
| Legacy adoption | `scripts/adopt-legacy.sh` 성공; `recorded_legacy`는 등록된 과거 관찰 객체 |
| 관리 권한 | `read_only=true`, `management_authority=OBSERVE_ONLY` |

로컬 영수증에서 container/image **실제 전체 ID**를 대조했으며 일치했다. 그러나 이 값들은 **Git/공개 문서에 전체를 복사하지 않는다**. 유효성 확인에 필요하면 현 호스트에서 직접 읽어 비교한다.

**실 DGX의 마지막 읽기 전용 출력:** legacy identity **6/6 PASS**, API `/health`·`/v1/models` PASS, 컨테이너 running, Health PASS, 저장 당시와 현재의 차이 `GIT_CHANGED`(Git HEAD 1건), identity 변경 0/health 변경 0; 당시 disk 여유 약 539.75 GiB, MemAvailable 약 14.35 GiB. 이는 **2026-10-26 시점 관찰**이지 항상 유효한 실시간 상태가 아니다.

### 레거시 검사 의미

- `legacy.identity_verified=true` 또는 `legacy.verified=true`는 저장된 paths, container/image ID, labels, published port, 모델 cache/view mounts 등 **6개 설치 식별 근거 일치**. 삭제·정지 소유권 아님.
- `checkout_warnings`의 origin/HEAD 불일치는 설치 이력 변화이며 Docker 배포 손상의 증거가 아니다.
- `api.health/models=PASS`는 HTTP 조회 성공. full 생성 추론, throughput, 240K-long-context 평가와 다르다.
- `adopt-legacy`는 wizard의 별도 상태 파일에 읽기 전용 스냅샷만 저장. 레거시 원래 receipt에는 쓰지 않는다.
- `recorded_legacy`는 등록 당시 기록이므로 `status`/`doctor`/`compare-state` 수행 시 덮어쓰지 않는다.

**경고:** API가 `0.0.0.0:8000`에 열려 있어 방화벽에 따라 다른 호스트에서 접근할 수 있다. 네트워크/방화벽을 임의 변경하지 말고 보안 감사에서 별도 다룬다.

---

## 3. 구현·파일 구조·Manifest 계약

### 3.1 정책과 실행 구조

| 경로 | 역할 |
| --- | --- |
| `compatibility.json` | 대상 checkpoint·pinned revision·BF16 PLE/MTP tensor 계약 및 모델 무결성 기준 |
| `scripts/deployment-manifest.json` | 위자드 선언형 정책: 서비스 프로파일, legacy fingerprint, 소유권/보존 규칙 |
| `scripts/source-state-manifest.json` | Git 추적 파일의 path/mode/blob SHA-1 스냅샷; 자기 자신은 제외 |
| `scripts/verify-source-state.py` / `.sh` | Git HEAD, working-tree blob/mode, 개인 origin, 승인 브랜치 검증. `PASS_SOURCE_ONLY`는 모델 검증이 아님 |
| `scripts/wizard/model.py` | Manifest/target 정책 검증 |
| `scripts/wizard/probe.py` | Docker/Git/legacy/API 읽기 전용 관찰 및 엄격한 ID/label 검사 |
| `scripts/wizard/state.py` | 신규 자산 영수증, 권한 0600, atomic save 및 경로 안전 검사 |
| `scripts/wizard/engine.py` | build/prepare/activate/status/adoption 및 소유권 receipt를 확인하는 stop/remove |
| `scripts/wizard/cli.py` | 한글 지향 명령/대화형 메뉴/CLI 옵션 |
| `scripts/wizard/monitor.py` | saved-vs-current diff, 간결 상태, HTTP/API/디스크/메모리 Health |
| `scripts/qwen38-dgx-spark` 및 `src/recipe/*` | 실제 모델 download, audit, serve의 기존 runtime 구현 |
| `tests/test_wizard_monitor.py` / `test_wizard_safety.py` | 모의 Docker/Git/HTTP 및 소유권 안전 시험 |
| `tests/test_source_state_release_branches.py` | main/feature strict 허용, 다른 브랜치 거부, merge SHA·blob 변조 회귀 시험 |
| `.github/workflows/test.yml` | CI workflow 정의. 구성 파일 존재만으로 CI 성공 아님 |

주요 진입점: `scripts/{install,uninstall,prepare,activate,stop,adopt-legacy,status,compare-state,health,doctor,manifest,run-mock-tests}.sh`. 실제 실행 전에 최신 Git 파일 및 `--help`로 옵션을 확인한다.

### 3.2 신규 위자드 기본 설정 (실기기 신규 설치 검증은 별도)

- 추천 `target=orca-uncensored-bf16-mtp`, `MTP=2`.
- context `262144`, sequences `8`, GPU memory fraction `0.8`.
- 이미지 tag `kjlee-qwen38-bf16ple-wizard:9492b78c` (레거시 tag와 다름).
- 권장 새 호스트 endpoint `127.0.0.1:18300`.
- **PR #3 이후 이름 분리 완료:** 레거시는 `qwen38-flash-<target>`, 신규 Wizard는 `qwen38-wizard-<target>` 및 전용 소유권 라벨. 다만 단일 GB10에서 기존 레거시가 실행 중이면 새 GPU 활성화는 거부하고, 실기기 신규 설치·제거 검증은 별도로 필요하다.
- `--replace`, 자동 legacy takeover, HF 캐시 공유/이동, 가중치 purge는 지원하지 않는다.

### 3.3 상태 및 Health 출력

- `scripts/status.sh`: 간결한 한글 상태; `--json`으로 전체 기록/현재상태.
- `scripts/compare-state.sh`: 과거 vs 현재의 `identity`/`health`/`git` 차이.
- `scripts/health.sh`: 현재 컨테이너, API/모델 목록, cache/view 여유 공간, MemAvailable 읽기 전용 확인.
- `scripts/doctor.sh`: Manifest 검증 + 상태/Health/변경 내역.
- Snapshot 결과: `UNCHANGED`, `CHANGED`, `HEALTH_CHANGED`, `GIT_CHANGED`, `UNREGISTERED`, `UNKNOWN`. 저장 공간 경고 기본 임계값 `100 GiB`. UNKNOWN을 변경/실패로 단정하거나 기록을 자동 수정하지 않는다.

### 3.4 Source Manifest를 수정할 때 반드시 지켜야 할 점

PR #1 구현 당시 `scripts/verify-source-state.py --strict`의 허용 브랜치는 정확히
`feature/install-uninstall-wizard-20261026`과 `main` 두 개다.
Manifest `allowed_branches`와 소스 검증기 `RELEASE_BRANCHES`가 정확히 일치해야 한다.

**새 추적 파일 추가·기존 파일 수정·삭제·모드 변경 시 전체 tracked Git tree의 path/mode/blob SHA를 `scripts/source-state-manifest.json`에 재계산해 반드시 같은 커밋에 반영한다.** 파일 개수·SHA를 임의 생성하지 않는다. Manifest 자체는 순환 참조를 피하기 위해 `files[]`에서 제외하고, HEAD에서 Manifest 자기 blob SHA를 별도로 대조한다.

Git merge commit은 SHA가 달라질 수 있지만 **모든 tracked blob/mode와 Manifest가 일치하면** 소스 PASS 조건이다. 반대로 merge로 파일을 수정하면 Manifest를 재생성해야 한다.

**새 임시 PR 브랜치는 현재 strict 허용 목록 밖이다.** `--strict` 실패를 정상으로 포장하지 말고, PR 브랜치에서는 Git tree와 Manifest SHA를 별도로 대조하고 해당 오프라인 단위 시험을 수행한 뒤 **머지된 main에서 strict**를 재검증한다. 미래에는 이 제한을 해결하는 CI/브랜치 검증 설계를 별도 검토할 수 있으나 안전 검사 전체를 무조건 우회/무력화하지 않는다.

---

## 4. 확정된 시험 결과 및 미완료 작업

### 4.1 사용자 제공 DGX 실제 로그

| 항목 | 검증 결과 |
| --- | --- |
| Feature HEAD `25949fd7fb16ff62f8c6bdfc6f9fe9ab74fd0f8a` | 사용자 최종 재검증 기준 |
| Source Manifest | `PASS_SOURCE_ONLY: 111 tracked file(s)` |
| Deployment Manifest | PASS, 4 targets |
| main/feature 호환 회귀 시험 | **7/7 PASS** |
| 위자드 fake/mock 시험 | **36/36 PASS** |
| 전체 저장소 unit tests | **163/163 PASS** |
| Bash 구문 / publication audit | 출력된 오류·진단 없음; 명시적인 exit-code 기록 없음 |
| 실 DGX 레거시 identity | **6/6 PASS**, 컨테이너 running |
| API health/models | **PASS/PASS** |
| Snapshot diff | `GIT_CHANGED` 단독 1건, identity/health 변경 0 |
| Read-only Health | **PASS** |
| PR #1 GitHub merge 결과 | `main`에 **merged=true**, tree 동일, Manifest 111 entries 일치 |
| GitHub CI | 실행 기록 없음; **CI 미검증** |

위 결과는 **사용자가 DGX 터미널에서 실행한 로그**와 연결된 GitHub 조회에 근거한다. 보조자가 DGX에 접속한 것은 아니다. 새 코드/문서 커밋 후의 시험 결과로 **과거 163/163 수치를 자동 승계하지 않는다**.

### 4.2 보류·미시험·차단 과제

1. **완료(2026-10-26): DGX 현지 `main` 및 post-merge strict 검증.** 사용자 최신 로그에서 `main=66051cdc...`, source 114/114, mock 38/38, 전체 unit 172/172, 기존 Health PASS. 향후 신규 커밋은 별도 검증 필요.
2. **신규 위자드 실제 Docker 이미지 build, 모델 prepare/audit, 새 컨테이너 activate, chat inference, 신규 자산 stop/remove/image remove 미시험.** Mock PASS ≠ 실기기 성공.
3. **이름/소유권 격리 코드 및 mock 검증 완료(PR #3).** 신규 `qwen38-wizard-<target>`·전용 라벨/영수증 검사, 레거시 running 상태의 GPU 기동 차단은 구현. 독립 컨테이너 실제 기동·중단·GPU 영향·rollback은 **미시험**; 레거시 강제 삭제 금지.
4. **Legacy→신규 관리 migration** 미구현. 기존 ownership 이전, 모델 cache 재사용/링크/복사 정책은 무단 적용 금지.
5. **중복 가중치 다운로드 방지** 전략 미확정. 새 checkout과 기존 cache의 분리/경로/해시/마운트 검증 후 결정.
6. **실패 복구 및 rollback** 미완성: 준비 실패·부분 파일·readiness timeout 이후 안전한 상태 보존/정리를 설계. 자동 cleanup보다 자산 보존 우선.
7. **GitHub Actions 체크 0건 원인 조사/CI 정상화는 사용자 결정으로 보류.** 워크플로 소스 보완은 PR #3에 반영됐으나 run/check 0건이며 `CI_NOT_VERIFIED`. 재개 지시 전 설정/워크플로 변경하지 않는다.
8. **오래된 계획서·안내의 '미구현/NOT TESTED' 표현**: 현재 구현 vs 당시 시험 계획으로 나누어 점진적 갱신. 과거 기록은 삭제하지 않는다.
9. **GPU/성능/240K context/MTP 안정성·동시성**: 새 위자드 실행 경로의 실제 장시간 검증은 별도.
10. 인수인계 문서 추가로 변경된 Git HEAD/Manifest를 다음 세션에서 재확인하고 최종 로컬 소스 시험을 반복.

현재 권장 순서: **GitHub 최신 HEAD/Manifest 및 DGX read-only 상태 확인 → 모의시험과 실패 복구·중복 다운로드 설계 → 승인된 신규 자산만 별도 실기기 검증**. CI 정상화는 사용자 재개 지시 전 보류.

---

## 5. 운영 자산 보호 — 절대 규칙

1. 기존 `qwen38-flash-orca-uncensored-bf16-mtp`에 대해 `docker stop/rm/rename`, 교체/restart, `docker image rm`, prune, daemon/firewall/포트 설정 변경을 자동 실행하지 않는다.
2. 기존 모델 `hf-cache`, `recipe-views`, NVMe checkpoint, HF 인증, 원본 설치 receipt를 덮어쓰거나 삭제하지 않는다. `rm -rf`, `git reset --hard`, `git clean -fd`, `--purge-*` 등을 상태 복구용으로 사용하지 않는다.
3. `~/.local/state/yslab-qwen38-bf16ple/*`는 **레거시 소유권 증거**이므로 읽기 전용. 신규 위자드는 `~/.local/state/qwen38-flash-dgx/deployment-state.json`의 **자기 상태만** 기록할 수 있다.
4. `legacy.adoption`은 `OBSERVE_ONLY`이다. 실제 삭제/정지 권한은 **새 위자드가 생성한 자산의 정확한 영수증 ID, image ID, label 및 Docker 실제 정보가 일치할 때만** 고려한다.
5. 현 컨테이너의 전체 ID, HF access token, 인증 파일, 계정 비밀, 내부 환경변수/비공개 인프라를 공개 Git에 저장하지 않는다. 유출 위험 문서는 publication audit를 통과해야 한다.
6. `--yes`는 사용자가 특정한 **신규 자산 생성/작업을 명시적으로 요청한 경우**에만 적절히 사용하고, `--replace`/`sudo`/유해한 cleanup을 자동 추정하지 않는다. 실제 운영 자산 변경은 별도 안전 설계/승인 필요.
7. 기존 서비스가 돌아가므로 데이터 보존이 우선이다. 실패 시 `STOP/FAIL/UNKNOWN`을 사실 그대로 보고하고 읽기 전용 조사로 전환.
8. `0.0.0.0:8000` 노출 API의 방화벽 접근 제한을 유지. 다른 Ollama, OpenWebUI, Docker, 네트워크 서비스 영향 없이 작업.
9. Docker 이름/포트만으로 안전을 판단하지 말고 단일 GB10 자원과 모델 중복 데이터·GPU 점유를 확인한다.
10. **GitHub 소스 PR 머지와 DGX 운영 배포/서비스 전환을 혼동하지 않는다.**

---

## 6. GitHub 플러그인으로 직접 작업하는 표준 절차

### 6.1 도구 활용/권한 원칙

연결된 GitHub 앱이 있는 세션에서는 파일/branch/PR/commit/merge를 **직접 수행**한다.
새 세션에서는 지원 도구와 권한을 확인하되, 필요한 기능을 사용할 수 있는데도 "사용자가 직접 GitHub UI에서 하라"는 말만 하지 않는다.

전형적인 GitHub 연결 함수 이름(지원 목록을 실제 도구에서 발견한 뒤 사용):
- `fetch` / `fetch_file` / `compare_commits` / `get_pr_info` / `fetch_pr` / PR diff/review 조회.
- `create_branch`, `create_blob`, `create_tree`, `create_commit`, `update_ref`.
- `create_pull_request`, `merge_pull_request`.
- workflow run/check/status 조회(지원되지 않으면 접근 불가 사유를 명시).

### 6.2 수정 → 커밋 → PR → 머지

1. 최신 `main` HEAD/tree, 변경 대상 파일과 보호 정책, PR 상태를 먼저 조회한다.
2. 변경 사항을 작은 단위로 설계하고 필요한 기존 소스·테스트·Manifest/문서까지 함께 검토한다.
3. 새 기능/반복 작업은 재사용 가능한 `scripts/`와 `tests/`로 만든다. 필요한 변경만 새 Git blob으로 생성한다.
4. 추적 파일 **전부**의 최신 path/mode/Git blob SHA를 계산해 `scripts/source-state-manifest.json`을 다시 작성한다. 자기 자신은 파일 목록에서 제외.
5. 정확한 base tree로 tree 생성 후 부모 commit SHA 지정 커밋. branch ref 갱신 시 **예상 HEAD lease**를 사용해 경합 방지. 강제 push 금지.
6. 사용자가 PR/머지를 요청했으면 **새 PR 생성 → 변경 파일 diff·mergeable·예상 head SHA·CI·리뷰 확인 → 문제없으면 일반 merge commit으로 머지 → merged/closed, main HEAD/tree/Manifest 재조회**를 이어서 한다.
7. 체크가 없는 경우 CI PASS라고 부르지 말고, 사용자 DGX 로그(163/163 등)와 GitHub checks(없는 상태)를 분리해 기록한다.
8. 새 PR 임시 branch는 기존 strict allowlist에 포함되지 않으므로, **그 브랜치에서 무조건 strict PASS를 기대하지 않는다**. 전체 blob/mode/Manifest 파일 inventory 대조 및 모의 테스트로 사전 검증하고, 머지된 main에서 strict를 실행한다.
9. PR #1은 이미 머지된 과거 이력이다. 새 작업은 별도 PR로 기록한다. 상위 YSLAB-ai 저장소, 기존 legacy checkout state 또는 실제 Docker를 Github source 변경에 묶어 수정하지 않는다.
10. 사용자가 승인한 GitHub source 작업이면 계획·검토·커밋·PR·머지를 같은 세션에서 완결하되, 오류·충돌·권한 부족이 있으면 사실대로 중단한다.

### 6.3 스크립트 생성/업데이트/사용 규칙

- 단순 반복 명령보다 **상시 유지보수 가능한 Bash wrapper + Python 모듈**을 선호한다. 기존 코드를 축약해 기능을 빠뜨리지 말고 backward compatibility와 안전 불변조건을 검토한다.
- Bash: `set -Eeuo pipefail`, 모든 경로/인자 quoting, 안전한 exit code, dry-run/읽기 전용 분리. 실제 파괴적 명령은 precise ID+영수증 검증 없이 실행하지 않는다.
- Python: `snake_case`, type hints, what/why/how docstrings, 중요 로직에 **한국어 주석**. 변형할 때 예외 처리를 fail-closed로 유지하고 실제 Docker/네트워크는 모킹된 단위시험을 우선한다.
- 새/수정 함수마다 정상·실패·경계·idempotency·불일치 테스트를 추가한다. 테스트가 실제로 실행되지 않았으면 `NOT_RUN`을 표시한다.
- 새 운영 절차가 확정되면 단발 채팅으로 끝내지 말고 `docs/` 또는 `scripts/*.md`에 영구 기록하고, 이 인수인계 문서도 필요 시 업데이트한다.
- 모든 커밋에 Manifest 및 문서 링크/README/HF 카드 미러 일치 검증을 포함. 공개/비밀 파일 `python3 tools/audit_publication.py` 감사 필요.
- Bash script/CLI 실행 비트는 `100755`, 문서/JSON/일반 테스트는 `100644`. 소스 Manifest에 tracked file mode까지 반영한다.
- 임의 SHA/시험 횟수/서비스 상태/커밋 결과를 절대 창작하지 않는다. 사용자에게 있던 기존 로그가 새 커밋을 증명하지 않음을 기록한다.

### 6.4 커뮤니케이션/보고

- 처음에는 **완료된 사실 / 미완료 / 위험 / 다음 작업**을 명료하게 요약한다. 이미 제공된 답을 반복 질문하지 않는다.
- 코드와 데이터 근거는 현재 GitHub 파일, 과거 사용자 로그, 추론을 분리한다.
- 작업 중엔 필요시 짧게 진척·차단을 알려 주고, 완료 시 변경 파일, 해시/브랜치, 테스트 결과, PR 링크, merge SHA를 확인해 보고한다.
- 실패한 부분은 숨기지 말고, 완료되지 않은 것은 명확히 `NOT_TESTED` 또는 `UNVERIFIED`로 표현한다.

---

## 7. 다음 세션에서 바로 수행할 확인 작업

### 7.1 GitHub 읽기 전용

1. **`main`과 현재 blazux 기능 브랜치의 양쪽 HEAD/트리·PR #5 병합·후속 PR·CI 현황을 먼저 확인**하고 맨 위 2026-10-27 상태 요약과 대조한다. 아래 과거 Wizard 관련 파일도 역사적 보호 규칙을 확인하는 용도로 읽는다.
2. **이 문서, `README.md`, `scripts/deployment-manifest.json`, `scripts/source-state-manifest.json`, `scripts/verify-source-state.py`, `scripts/wizard/*`**의 최신 버전을 조회.
3. Source Manifest와 HEAD tree의 **전체** SHA/mode/경로 대조, README와 `huggingface/README.md` 미러 확인.
4. GitHub Actions run/check를 조회하고, run=0이라면 `CI_NOT_VERIFIED`라고 표기.
5. **현재 개발의 필수 참조:** [blazux 계획서](BLAZUX-VLLM032-ADOPTION-PLAN.md), [Baseline 보고서](benchmark/LLAMA-BENCHY-BASELINE-20261027.md), [Benchmark 재실행 wrapper](../scripts/benchmark/run-llama-benchy.sh)(실행 시험 NOT_RUN), [첨부된 원본 Benchmark 결과](../results/llama-benchy/baseline/pre-blazux/20261026T221925Z/result.json). 
6. Wizard 운영 역사 확인: [Legacy 설치 보호](../scripts/LEGACY-INSTALLATION.md), [DGX 관찰](../scripts/LEGACY-OBSERVATION-20261026.md), [안전·복구](../scripts/SAFETY-AND-RECOVERY.md), [작업 순서](../scripts/OPERATIONS.md), [시험 계획](../scripts/TEST-PLAN.md), [테스트 증거](../scripts/VALIDATION-RESULTS-20261026.md), [Health 비교](../scripts/STATUS-COMPARE-AND-HEALTH.md), [Manifest 계약](../scripts/MANIFEST-SCHEMA.md), [Git Pull](../scripts/VERIFY-FROM-GIT-PULL.md), [역사적 개발 계획](../scripts/INSTALL-UNINSTALL-WIZARD-PLAN.md).

### 7.2 DGX 사용자가 실행할 수 있는 **읽기 전용 중심** 명령

> 아래 코드 블록에 포함된 `git fetch/switch/pull`은 **조회만 하는 명령이 아니라 checkout/remote-tracking refs를 변경할 수 있다**. 현재 진행 중인 기능 브랜치·로컬 변경을 먼저 확인하고, 명시적으로 로컬 동기화할 때만 사용한다. 단순 소스 검토에는 GitHub 읽기 전용 조회가 우선이며, 승인 없는 DGX 명령 실행은 금지한다.

과거에는 기능 브랜치였으나 **2026-10-26 사용자 제공 최신 로그에서 `main=66051cdc...` 확인**. 향후 재실행 시에도 원격 origin/로컬 수정을 다시 확인한다.

```bash
cd "$HOME/Workspace/llm/yslab-qwen38-bf16ple-dgx-spark"
pwd
git remote get-url origin
git status --short

# origin이 개인 Fork이고 로컬 변경이 없는 경우에만
git fetch origin main
git switch main
git pull --ff-only origin main

git rev-parse HEAD
scripts/verify-source-state.sh --strict
scripts/manifest.sh validate
scripts/run-mock-tests.sh
PYTHONPATH=src:. python3 -m unittest discover -s tests -v
bash -n scripts/*.sh scripts/qwen38-dgx-spark
python3 tools/audit_publication.py
scripts/status.sh
scripts/compare-state.sh
scripts/health.sh
scripts/doctor.sh
```

위 수동 절차는 참고용이다. 사용자 DGX는 `66051cdc...`에서 새 wrapper를 실제 실행하여 PASS를 제공했다. **다음 문서 커밋/머지는 별개 Git HEAD**이므로 새 HEAD의 DGX 실행 결과라고 주장하지 않는다. 로컬 수정·remote 차이·에러 시 reset/clean 금지; Source PASS는 ignored cache/가중치/Docker를 검증하지 않는다.

---

## 8. 완료 판단과 향후 세션 종료 시 갱신해야 할 항목

작업 종료 전에 다음을 **GitHub 영구 문서**와 답변에 반영한다.

- 최종 브랜치, `main` HEAD, 수행한 GitHub commit/PR/merge SHA/URL.
- 이전 기준 대비 실제 변경 파일과 source Manifest 최신 tracked 파일 수.
- 수행한 테스트: **실행 환경(DGX/모의/CI), 명령, 총 건수, 실패 수, 미시험**, 독립적인 runtime health 증거.
- 실제 기존 이미지/컨테이너/cache/API/state를 변경하지 않았는지와 보호 검증.
- 해결되지 않은 blocker, 디자인 선택/위험, 사용자 승인이 필요한 실제 배포 작업.
- 이 문서 `docs/SESSION-HANDOFF-PROMPT.md`, 관련 `scripts/*.md`와 README의 최신 정합성.

**과거 작업 시작 전 기록(최신 상태 아님):**
PR #1 MERGED, `main=bdc84eae28b7ce49ea2dde3c3923cfdf60382cf6`, 사용자 DGX 기능 HEAD에서 전체 테스트 **163/163 PASS**, 모의 36/36, release-branch 7/7, legacy 6/6 및 API PASS, 운영 `OBSERVE_ONLY`. **실제 신규 배포·제거/rollback 미시험, DGX main 전환 로그 없음, GitHub Actions CI 실행 증거 없음.** 문서 신규 커밋/머지에 따른 `main`의 다음 HEAD는 새 세션에서 다시 조회한다.

---

## 9. 후속 P0: CI, 컨테이너 격리 및 DGX main 읽기 전용 검증

> 후속 기능 브랜치: `feature/ci-wizard-isolation-main-readonly-20261026`.
> 작업 시작 기준 `main=8ab88bc13aee6400e32b488af65f0a43c1c34b05`.
> 실제 새로운 merge SHA/CI 결과는 매 세션 **GitHub에서 새로 조회**해야 한다.
> GitHub 코드 변경·PR 병합은 DGX 배포가 아니며 기존 Docker 서비스에 접근하지 않았다.

### P0-1. GitHub Actions CI 계약

- `.github/workflows/test.yml`는 push, pull_request, workflow_dispatch를 등록하고, 권한을 contents:read로 제한하며 실행 시간 상한을 설정한다.
- 임시 PR 브랜치에서는 `scripts/verify-source-state.sh`로 전체 path/mode/blob/작업트리/origin 검증을 실행한다. 브랜치 strict allowlist는 바꾸지 않는다.
- main에서만 추가로 `--strict`을 실행한다. Manifest policy, 오프라인 mock, 전체 unit, Bash 문법, publication audit도 수행한다.
- 워크플로 코드가 있다는 사실은 CI 실행 증거가 **아니다**. 실제 Actions run/check가 없다면 `CI_NOT_VERIFIED`로 기록하고 GitHub Actions 활성화/권한/정책을 조사한다. 임의로 PASS라고 쓰지 않는다.
- PR의 CI가 비어 있다면 요구되는 운영 정책에 따라 머지 전 리뷰하고, CI 미실행이라는 blocker를 명시한다.

### P0-2. 레거시와 신규 Docker 컨테이너 격리

- 레거시 이름 `qwen38-flash-<target>`은 그대로 보존한다. 일반 recipe CLI 호출은 기존 이름과 동작을 유지한다.
- 신규 wizard 이름 `qwen38-wizard-<target>`, marker label `ai.kjlee.wizard=kjlee-qwen38-dgx-spark-wizard`를 사용한다. Docker inspect, receipt, stop/rm도 같은 이름을 사용한다.
- 신규 컨테이너 삭제/정지에는 wizard 영수증 + 정확한 ID + image ID + recipe/target + Docker Name + marker가 전부 필요하다. 하나라도 불일치하면 중단하며 legacy observation은 관리/삭제 권한이 아니다.
- wizard의 `--replace` 및 runtime CLI의 전용 이름에 대한 replace를 금지한다. 임의 이름 지정도 거부한다.
- 동일 단일 GB10에서 기존 레거시가 `running`이면 **신규 GPU 활성화를 차단**한다. 포트/이름 격리만으로 GPU/메모리 중복 부하가 안전해지지 않는다.
- 새로운 build/prepare/activate/stop/remove, 장시간 inference, rollback 실기기 시험은 **NOT_TESTED**. Mock을 실기기 검증으로 승격하지 않는다.

### P0-3. DGX 로컬 main 전환 및 검증 절차

- `scripts/verify-main-readonly.sh`는 개인 Fork origin, `main`, 깨끗한 tracked/untracked working tree 및 **로컬** origin/main의 HEAD 일치를 요구한다.
- 소스 strict, Manifest, offline mock, full unit, Bash 문법, 공개물 감사, 기존 legacy 상태·snapshot diff·Health·Doctor **조회만** 수행한다. 자체 `git fetch/switch/pull/reset/clean`, Docker lifecycle 및 모델 다운로드는 하지 않는다.
- 로컬 origin/main의 참신성을 자동 확인하지 않는다. 먼저 DGX에서 `git remote get-url origin`, `git status --short`, `git branch -vv`를 확인하고 문제가 없을 때 별도 `git fetch origin main` 후 `git switch main` 및 `git merge --ff-only origin/main`을 수행한다. 로컬 main이 없으면 `git switch --track origin/main`; 충돌 시 중단한다.
- **2026-10-26 이후 사용자 DGX 로그로 위 절차의 완료를 확인했다.** 확인된 HEAD는 `66051cdc...`이며 source 114/114, mock 38/38, 전체 unit 172/172, legacy Health PASS. 이후 문서 커밋 HEAD의 검증 또는 신규 배포 기능 실동작을 뜻하지 않는다.

### 후속 작업 고정 운영 규칙

1. 매번 최신 main HEAD/tree·PR·CI와 소스 Manifest 전체 path/mode/blob 및 README/HF 본문 미러부터 점검한다.
2. 기존 운영 자산(레거시 이미지·컨테이너·recipe-views·hf-cache·HF 인증·YSLAB receipt·포트 8000·OpenWebUI·Ollama·네트워크) 불변을 최우선한다.
3. 개발 작업은 기능 브랜치에서 수행하고 Python snake_case/type hints/what-why-how docstrings/한국어 중요 주석, Bash set -Eeuo pipefail/quoting/fail-closed 원칙을 적용한다.
4. 정상·실패·경계·식별자 위조·이름 충돌·idempotency Mock을 추가하며 테스트 실패를 무시하지 않는다. 실제 DGX 가동 시험은 별도 승인 대상.
5. **모든** 파일 추가/변경/삭제/모드 변경과 같은 커밋에 Source Manifest를 함께 동기화한다. 새 PR 브랜치는 strict 허용 목록 밖이다. 전체 inventory 검사와 main strict를 구분한다.
6. GitHub 연결 도구를 사용해 직접 commit/PR/diff review/일반 merge 후 결과를 검증하되 CI 결과 없으면 `CI_NOT_VERIFIED`라고 기록한다. 비밀·Docker full ID를 공개 Git에 기록하지 않는다.
7. 사용자 제공 DGX 기능 HEAD `25949fd7...`의 163/163, 36/36, 7/7, legacy 6/6, API PASS는 **과거 스냅샷**이다. 새 커밋과 실제 DGX에 결과를 자동 승계하지 않는다.
8. UNKNOWN 또는 실패 시 임의 복구/강제 삭제 대신 원인별 읽기 전용 조사; status/health는 ownership 증거와 분리한다.
9. 종료 시 새 브랜치·HEAD·tree·Manifest 추적 수·테스트 환경별 실제 결과·PR/merge/CI·DGX 미완료·blocker를 문서와 답변에 정확히 반영한다.

### PR checkout detached HEAD 안전 검사

GitHub Actions의 pull_request checkout은 detached HEAD일 수 있다.
non-strict Source Manifest 검사는 이때 전체 blob/mode/origin/working-tree를
계속 검증하고 브랜치 이름 검증만 하지 않는다. `--strict`에서는 detached
HEAD를 반드시 거부한다. 회귀시험은 별도 임시 Git fixture로 두 경우를
검증한다. CI 실행 결과를 확인하기 전까지 CI_NOT_VERIFIED다.


---

## 10. 2026-10-27 llama-benchy pre-blazux Baseline 확정

> 이 절은 이전 2026-10-26 운영·CI 상태보다 늦은 **사용자 제공 DGX 실측**이다. 구체적인 원본·12조건 표·해시·재현법은 [Baseline 보고서](benchmark/LLAMA-BENCHY-BASELINE-20261027.md)를 먼저 참조한다.

### 완료된 사실

- 목표: blazux 최적화 적용 **전에**, 실제 운영 모델의 동일 조건 성능 기준선을 저장하여 후속 동일 모델 A/B에 사용. llama-benchy Fork를 새로 개발하는 것이 아니라 기존 Qwen 개인 저장소에 측정 결과를 백업한다.
- 원본 벤치마크 도구: [eugr/llama-benchy](https://github.com/eugr/llama-benchy), commit SHA **e9be344578cec17745066b220798b80a0d2686d3**, 버전 **0.4.1.dev1+ge9be34457**. DGX 독립 설치 경로는 **$HOME/Workspace/llm/llama-benchy-runner**다. 별도의 분석 checkout의 날짜형 baseline Git 태그가 hatch-vcs 빌드를 막았으며, --no-tags clone + 공식 v0.4.0 태그만 둔 runner의 uv sync는 사용자 로그에서 PASS였다.
- 기존 운영: 컨테이너 **qwen38-flash-orca-uncensored-bf16-mtp**, Docker tag **yslab-qwen38-bf16ple:9492b78c**, API **http://127.0.0.1:8000/v1**, 모델 ID **qwen3.8-flash-next-orca-uncensored-bf16-mtp**, 최대 context 메타데이터 **262144**. 컨테이너/Image 전체 ID는 비공개로 유지.
- Tokenizer SHA-256 **06b9509352d2af50381ab2247e083b80d32d5c0aba91c272ca9ff729b6a0e523**. 실행 중인 모델과 Docker mount의 recipe-view tokenizer.json에서 사용자 확인.
- 2026-10-27 07:14 KST 단일 Smoke Test PASS: PP256 117.28 tok/s, TG32 35.59 tok/s, peak 36.74 tok/s, TTFR 1900.90 ms. 단일 1회 결과 ± 0.00은 안정성의 증거가 아니다.
- **정식 Baseline 완료**: DGX 로그 PASS: baseline completed. 원본 디렉터리 **$HOME/Workspace/llm/bench-results-staging/20261026T221925Z-pre-blazux/**. 시작 2026-10-26 22:19:25 UTC, 결과 timestamp 2026-10-26 22:34:42 UTC. PP 2048/8192 × TG 128/256 × Depth 0/4096/16384, concurrency 1, 각 warmup 1회 후 3회 측정 = **12 조건/36 본 측정**. generation latency, exact-tg, NumPy seed 20261027, 총 토큰 시계열 포함.
- 원본 result.json SHA-256 **25f6abf3968efbf94cf08b02297140f7be2e8b29f8f2192b1d246e7432959edf**, 원본 environment.json SHA-256 **76c94d48aa4597bd09e9973b6f5cba118db0009062f592e4a764398443f97eb6**. 첨부된 두 파일은 사용자의 SHA256SUMS와 **각각 일치**. 그 목록의 나머지 7개 파일은 사용자가 업로드하지 않았으므로 별도 무결성 검증하지 못했다.
- 정식 결과는 results/llama-benchy/baseline/pre-blazux/20261026T221925Z/result.json에 **원본 그대로** 보존한다. 전체 컨테이너/Image ID를 가진 원본 environment.json은 공개하지 않고 environment.public.json과 원본 해시만 기록한다.
- 이전 docs/BENCHMARKS.md의 MTP2 44.23 end-to-end completion tok/s와 이번 llama-benchy TG 값은 측정 구간과 산식이 다르므로 직접 비교 금지.

### 당시 Baseline PR #5의 범위와 이후 계획 (PR #5 MERGED)

- 병합된 PR #5 범위: [동일 조건 재실행 Bash 스크립트](../scripts/benchmark/run-llama-benchy.sh), 원본 result.json, 정제된 환경·원본 체크섬, [보고서](benchmark/LLAMA-BENCHY-BASELINE-20261027.md), 이 인수인계 문서, Source Manifest의 전체 path/mode/blob SHA 동기화.
- **사용자 요청에 따라 신규 스크립트 실행·회귀시험 생략(NOT_RUN)**. 과거 DGX에서 성공한 수동 측정이 새 Bash 스크립트 자체의 실행 검증을 뜻하지 않는다. CI도 실행 결과 없으면 CI_NOT_VERIFIED.
- 실행 스크립트는 원본 도구 SHA/Tokenizer SHA/서빙 모델을 검사하고 별도 staging 디렉터리에 JSON/진행 이벤트/로그/환경/메모리·GPU 상태/체크섬을 저장한다. Docker 이미지·컨테이너·운영 상태·model cache·기존 영수증에 쓰기 없음; API를 통한 추론 부하는 실제 발생한다. 개인 식별정보·프롬프트/응답 내용이 포함된 RAW 로그를 자동 공개하지 않는다.
- **후속 완료:** PR #5는 이미 `main=2847e39b...`로 병합됐고 `feature/blazux-vllm032-evaluation-20261027` 브랜치에 계획서를 커밋했다. **현재 다음 단계는 Gate 1 정적 코드 비교**이며, blazux 참조 SHA는 **8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa**로 고정한다.
- 비교 전 제한: Orcarouter compressed-tensors/ BF16 PLE/ BF16 MTP 31개 overlay와 blazux ModelOpt 전용 hybrid/graft는 직접 호환이 검증되지 않았다. blazux 기본 스크립트의 docker rm -f 및 포트 18300 충돌 위험. 기존 레거시 stop/rm/restart 금지, 단일 GB10 두 대형 GPU 서버 동시 기동 금지. vLLM 0.32 실기기 전환과 성능 개선 주장은 아직 미검증.

---

## 11. blazux vLLM 0.32 적용 계획 브랜치 — 2026-10-27

> 별도 후속 계획. 기존 baseline 문서와 레거시 운영/소유권 규칙을 유지한다.

- [Baseline PR #5](https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark/pull/5)는 **MERGED**. main merge SHA: **2847e39b4131eb8aff78bf86ffce98892401722a**. 사용자 DGX에서 완료한 12조건·36회 pre-blazux 원본 JSON과 해시, 재실행 Bash, Baseline 보고서가 main에 보존됐다.
- 후속 계획·분석 브랜치: **feature/blazux-vllm032-evaluation-20261027** (위 main merge SHA에서 분기). 첫 커밋 범위는 **docs/BLAZUX-VLLM032-ADOPTION-PLAN.md** 신규 계획서 및 이 핸드오프/Source Manifest 갱신만. vLLM 0.32 포팅, 이미지 빌드, 컨테이너 작업, 실 A/B는 **NOT_STARTED**.
- 원본 blazux 분석 대상 GitHub: [blazux/qwen3.8-Flash-DGX](https://github.com/blazux/qwen3.8-Flash-DGX) pin **8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa**. 모델 로더/PLE mmap BF16, MTP 31 텐서, compressed-tensors, prefix-cache/SSM, draft vocab, tool parser 등을 Gate별 검증한다.
- **절대 보호:** 레거시 Docker stop/rm/restart/overwrite, HF cache/recipe views/mount/receipt 변경, 포트 8000/18300 무단 점유, 단일 GB10에서 레거시 실행 중 신규 대형 GPU 모델 병렬 기동 금지.
- Baseline은 실행 및 원본 해시 2개 대조까지 완료됐지만 **재실행 Bash 신규 코드 자체의 테스트는 사용자 요청으로 NOT_RUN**. GitHub Actions 실행 0건/CI_NOT_VERIFIED, 다른 7개 로컬 로그 파일 해시 미대조, 입력 코퍼스/샘플링 세부 추가 확인 필요. 신규 브랜치 strict allowlist 제한은 변함없다.
- 다음 세션은 현 최신 main/이 브랜치 HEAD를 확인하고 [계획서](BLAZUX-VLLM032-ADOPTION-PLAN.md)의 **Gate 1 소스 함수/데이터 계약 비교**를 이어서 수행한다. 커밋·PR·머지·실 DGX 작업은 각각 수행/승인된 범위를 구별한다.

### 11.1 2026-10-27 설계 보강 — Track A/B 분리 및 개발 Gate (문서만 변경)

- **Track A:** 현행 vLLM preview 기반 선택적 개선만 `feature/blazux-vllm032-evaluation-20261027`에서 계속한다. P1(PLE 단계별 계측, Prefix Cache/SSM 정확성, Tool/Responses parser 회귀) → P2(MTP reduced draft vocab, BF16 PLE gather, QSA top-k 각각 독립 기본 OFF flag) → P3(YaRN/FP8 고위험 보류). 1:1 함수·데이터 계약 및 **합성 BF16 safetensors shard 오프라인 fixture**가 우선이다.
- **Track B:** 공식 vLLM 0.32 전환은 `feature/vllm032-bf16ple-port`라는 **미생성·미착수 별도 장기 브랜치**로만 진행한다. 착수 Go/No-Go를 별도로 결정하고 새 base image digest/container/host loopback port/receipt/recipe-view/result 디렉터리와 ownership label을 사용한다. 레거시/위자드 자산 및 포트 점유·변경 금지, 단일 GB10에서 두 대형 GPU 모델 동시 가동 금지.
- 공통 **기능별 독립 PR → default-OFF flag → 합성 fixture/회귀 증거 → rollback 및 Source Manifest 정합성 → 코드 리뷰 → 검증된 부분만 main**. 검증되지 않은 0.32 엔진 교체·ModelOpt hybrid/graft는 현재 엔진 최적화 PR에 혼합하지 않는다.
- 기존 `main`의 GitHub branch protection은 2026-10-27 조회에서 **false**였다. 보호 규칙은 현재 문서/운영 정책이며 GitHub 설정이 자동 강제 중이라고 가정하지 않는다. CI 정상화는 여전히 보류된다. 이번 갱신은 **계획서·핸드오프·Source Manifest 문서/메타데이터 커밋만** 대상으로 하며 실제 DGX 코드/GPU/벤치 시험은 요청하지 않았고 수행하지 않는다.
- 상세 정책 및 변경 제한은 [blazux 도입 계획서](BLAZUX-VLLM032-ADOPTION-PLAN.md) §1.4, §3.1, Gate 2/3/6을 우선 참조한다.

### 11.2 Gate 1 실행 시 필수 산출물 및 중단 기준 — 최신 보완

1. **입력 기준:** 현 Qwen 저장소 최신 `main`/기능 브랜치 HEAD·Dockerfile 기반 preview, `compatibility.json`, BF16 MTP 31개 텐서 계약과 pinned Orcarouter/RadixArk revision. 외부 blazux는 **8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa** 고정. 가능하면 각 함수별 실 Git Blob SHA와 patch 경로를 적는다.
2. **함수별 대조:** PLE `mmap` header/offset/dtype/index, n-gram hash/dedup/sort/pinned H2D; MTP model loader, 31/31 guard·draft vocabulary·acceptance; QSA top-k 및 SM121 커널; Mamba/SSM prefix cache; Tool/Responses parser, streaming·literal marker. 함수 경로·shape·입출력·기존 구현 여부·바뀐 API·오류 조건을 **1:1 표로 작성**한다.
3. **판정:** 항목별 **KEEP / PORT / ADAPT / DEFER_TO_TRACK_B / REJECT** 및 P1/P2/P3, 근거, 라이선스·third-party provenance, 위험, CPU 합성 fixture, 필요한 최소 수정 범위를 기록한다. 분석 중 새 엔진으로 강제 변경하지 않는다.
4. **검증 선행:** 작은 **BF16 safetensors 합성 shard**로 offset/row/inverse-scatter를 비교하고 정상·오류·경계 테스트를 분리. 이후 P2 기능마다 독립 `default-OFF` flag, off 경로 동일성·롤백 게이트가 없으면 코드 병합 금지.
5. **성능 재현성 차단:** PR #5 **정식 Baseline은 보존 완료**했으나 코퍼스 원본 hash·실 요청 sampling/서버 KV/cache 조건 및 checksum의 나머지 7개 파일 검증이 미완료다. 이 자료가 갖춰지기 전에는 blazux **동일 조건 A/B**나 tok/s 개선율을 주장하지 않는다.
6. **Track B 시작 조건:** 별도 Go/No-Go·자산 이름/라벨·Docker base digest·receipt·loopback 포트·cache/view 분리/rollback 사전 정의가 필요하며, `feature/vllm032-bf16ple-port`는 **아직 미생성**. 같은 단일 GB10에서 레거시 GPU 모델과 신규 대형 모델 동시 기동 금지.
7. **결과 기록:** 코드를 수정하지 않는 정적 비교라도 새 비교 문서/결정 기록을 GitHub에 영구 저장한다. 추적 파일 변경 시 Source Manifest 전체 120개(+신규 파일 수)의 path/mode/blob SHA와 정확히 동기화한다. `main` branch protection은 조회 시 false였으므로 정책상 기능 PR/리뷰를 준수하되 기술적으로 강제된 상태라고 쓰지 않는다. CI 정상화는 사용자 요청으로 보류하며, 실제 수행하지 않은 Mock/DGX/스크립트 테스트는 `NOT_RUN`으로 둔다.

**이 다음 작업의 현재 완료 상태:** Gate 0(실측 원본 및 GitHub 백업) **DONE_WITH_REPRODUCIBILITY_GAPS**; Gate 1의 **실제 1:1 함수 비교표 NOT_STARTED**; Gate 2 합성 shard 시험 **NOT_RUN**; Track A의 실제 최적화 패치/새 PR **NOT_STARTED**; Track B 엔진 교체/이미지/배포/A-B **NOT_STARTED**.
