# Source snapshot update — 2026-10-26

- 전체 추적 Git 파일의 blob SHA/모드와 원격 Fork 브랜치를 증명하는
  `scripts/source-state-manifest.json`, `scripts/verify-source-state.py`,
  `scripts/verify-source-state.sh` 추가.
- `scripts/VERIFY-FROM-GIT-PULL.md`에 기존 설치를 보호하는 fetch/switch/pull,
  무결성 검증, 정적 구문 점검, 읽기 전용 호스트 상태 확인 명령 작성.
- 소스 상태 검증과 배포 정책 검증, 실 DGX/모델 시험을 명시적으로 분리.
- 사용자 지시에 따라 이 커밋의 Python/Shell/단위/실 DGX 테스트는 **NOT RUN**.
- 참조 legacy 이미지, 모델 cache, Docker, `main`은 변경하지 않음.

---

# Implementation update — 2026-10-26 (feature branch only)

> **Source written; NO tests run, NO real DGX operations run.**
> The earlier plan below is historical design guidance. This implementation follows a
> *more restrictive, fail-closed* legacy compatibility rule to protect the user's
> already-running installation.

### Delivered in this feature branch

- Declarative policy manifest: `scripts/deployment-manifest.json`, intentionally
  distinct from pinned `compatibility.json`.
- Bash entrypoints: `install.sh`, `uninstall.sh`, `status.sh`,
  `adopt-legacy.sh`, `manifest.sh`, `doctor.sh`, `prepare.sh`,
  `activate.sh`, and `stop.sh`.
- Python implementation: `scripts/wizard/{model,state,probe,engine,cli}.py`.
- Documents: `README-WIZARDS.md`, `LEGACY-INSTALLATION.md`,
  `MANIFEST-SCHEMA.md`, `SAFETY-AND-RECOVERY.md`, `OPERATIONS.md`,
  `TEST-PLAN.md`; root `README.md` updated.

### Deliberate differences from the original plan

1. The user's existing YSLAB deployment was installed by an older reference
   script. It uses `yslab-qwen38-bf16ple:9492b78c`, the container name
   `qwen38-flash-orca-uncensored-bf16-mtp`, host port 8000, and state files under
   `~/.local/state/yslab-qwen38-bf16ple`. The wizard **only observes** this
   installation. Explicit adoption creates a read-only *observation* receipt,
   not destructive ownership.
2. A new deployment uses a different image tag and port 18300. The same target
   still maps to the same container name in upstream runtime, so activation must
   refuse while the legacy container exists. No automatic stop/replace/migration.
3. `--replace` is recognized but intentionally blocked; there is no qualified
   rollback yet. Data purge and repository deletion are completely absent.
4. The default wizard operates in the **already checked-out fork** without
   cloning/resetting another repo. Default cache is this checkout's `hf-cache`
   and it will **not** silently reuse/modify legacy model storage.
5. The installer records new image/container IDs in a **private local receipt**
   and checks Docker IDs+labels before deletion. `manifest` is policy, not a
   claim of actual Docker ownership.

### Outstanding

- This branch is **NOT TESTED**. Run static checks, mock tests, DGX inventory,
  image build, and real readiness checks in separate approved validation work.
- Rollback, cross-checkout cache sharing, container name namespace changes,
  legacy takeover, and general data purge are deferred.
- Do not merge to `main` or describe this as safe for production until verified.

---

# DGX Spark 설치·제거 위자드 구현 계획

> **상태: PLAN ONLY — 미구현**
>
> 작성일: 2026-10-26 (KST)  
> 저장소: `kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark`  
> 브랜치: `feature/install-uninstall-wizard-20261026`  
> 시작점: `main` @ `9492b78c6bc04638587b42f2ffeb0680b0fcb3ef`  
> 대상: 단일 NVIDIA DGX Spark(GB10), Linux ARM64 / Ubuntu, Bash + Python 3  
> 최우선 원칙: **기존 모델, 캐시, 사용자 컨테이너 및 다른 서비스를 기본값으로 삭제하거나 손상시키지 않는다.**

## 1. 목적과 이번 단계의 범위

`scripts/install.sh` 및 `scripts/uninstall.sh`를 대화형 CLI 위자드와 비대화형 자동화 CLI로 구현한다. 단순 명령 나열이 아니라 설치 전 점검, 대상 선택, 작업 미리보기, 명시적 승인, 소유권 확인, 실제 API 정상 동작 판정, 실패 복구 및 상태 기록까지 포함한다.

**현재 P0 단계는 이 문서를 feature 브랜치에 커밋하는 것까지다.** 이번 작업에서는 셸/Python 위자드 파일을 구현하거나 Docker·HF 다운로드를 실행하지 않는다. `main`, 원본 YSLAB-ai 저장소, Docker, 파일 시스템의 기존 모델 데이터는 변경하지 않는다.

### 설계 원칙

1. 기존 `scripts/qwen38-dgx-spark` 및 `src/recipe/`의 CLI, 다운로드, 정적 audit, Manifest·MTP 검증 기능을 재사용하고 중복 구현을 피한다.
2. `--dry-run`은 계획과 검사를 위한 읽기 전용 모드이며 이미지 빌드, 다운로드, 컨테이너 정지/삭제 또는 사용자 파일 작성이 없어야 한다.
3. 기존 자산만으로 재활성화하는 `--activate-only`는 **download/login/build 금지**를 코드와 테스트로 보장한다.
4. 소유권을 입증할 수 없는 컨테이너·이미지·디렉터리는 작업하지 않는다(fail closed).
5. 정상 Docker 시작과 LLM API readiness를 구분하며, 검사 실패를 성공으로 출력하지 않는다.
6. HF 토큰/패스워드/비밀정보를 로그, 명령 문자열, receipt, Git 저장소에 저장하지 않는다.
7. 모든 사용법과 오류 안내는 한국어를 기본으로 하되 내부 기계적 상태 코드/CLI 인자는 영문을 유지한다.

## 2. 현재 저장소와 호환성 기준

| 대상/항목 | 검증된 사실 | 위자드 정책 |
| --- | --- | --- |
| 기본 대상 | `orca-uncensored-bf16-mtp` | 추천 설치 대상 |
| 추천 MTP | `--mtp 2` | qualified profile로 기본 선택 |
| 비 MTP 원본 | `orca-uncensored` | MTP=0 강제 |
| 다른 타깃 | `inferact`, `radixark` | runtime-unvalidated 표기 및 명시 선택 요구 |
| 모델 출처 | `compatibility.json`의 revision-pinned Hugging Face repos | 임의 model/ref 입력 금지 |
| MTP overlay | 31개 BF16 MTP 텐서와 소스 SHA-256 검사 | guard/audit 우회 금지 |
| 모델 다운로드 | HF 캐시, gated login, 디스크 gate | 기존 cache 보존, 최소 gate만으로 전체 필요량 보장하지 않음 |
| 이미지 | `docker build -t qwen38-flash-dgx .` | 이미지 존재/출처와 빌드 성공 여부 검사 |
| 포트 | `127.0.0.1:18300` (컨테이너 8000) | loopback 유지, 네트워크 자동 개방 금지 |
| 컨텍스트 | `262144` | qualified 기본값 |
| GPU memory | `0.80` | qualified 기본값 |
| 동시 시퀀스 | `8` | qualified 기본값 |
| PLE/KV | BF16 PLE mmap, BF16 KV, PIECEWISE, prewarm=0 | 검증된 옵션 고정 |
| 기존 교체 | `serve --replace`: 라벨 검사 후 기존 컨테이너 제거 → 재시작 | 다운타임, rollback 및 검증 설계 필수 |

원본 `README.md`의 clone 주소와 Docker LABEL은 YSLAB-ai를 가리킨다. Fork 전용 배포 안내에서는 원본과 개인 Fork를 명확히 구분한다.

## 3. 최종 예정 파일 구성

```text
scripts/
  install.sh                         # 설치·준비·활성화/상태 위자드 (예정)
  uninstall.sh                       # 정지·제거 위자드 (예정)
  qwen38-dgx-spark                   # 기존 CLI 유지
  INSTALL-UNINSTALL-WIZARD-PLAN.md  # 본 계획서 (현재 작성)
  README-WIZARDS.md                 # 향후 사용법·복구 절차 (예정)

src/recipe/
  wizard.py                         # 메뉴/옵션/실행 단계 (예정)
  wizard_checks.py                  # 사전검사: 읽기 전용 (예정)
  wizard_actions.py                 # 제한된 작업과 결과 검증 (예정)
  wizard_state.py                   # 상태 receipt, 소유권 및 복구 (예정)

tests/
  test_wizard_*.py                  # 실제 Docker 없이 mock 기반 검증 (예정)
```

- Bash wrapper는 `set -Eeuo pipefail` + Python 위자드 진입으로 최소화한다.
- 메뉴는 숫자 입력, 현재 선택 요약, 이전 단계/취소/종료를 지원한다. `whiptail` 등 외부 TUI 도구를 필수로 요구하지 않는다.
- 비TTY 환경에서 필요한 인자가 없으면 입력 대기 없이 종료 코드와 정확한 오류를 출력한다.
- subprocess는 argv 리스트를 사용하며 `shell=True`, `eval` 및 입력의 셸 문자열 실행을 금지한다.
- 단계별 함수들은 test runner/가짜 Docker 호출을 주입해 독립적으로 검증할 수 있도록 구현한다.
- 인자를 parse하는 작업, 플랜 생성, 읽기 전용 preflight, 실행, readiness를 명확히 분리한다.

## 4. 설치 위자드 UX 및 CLI 계약(제안·미구현)

### 대화형 사용

```bash
scripts/install.sh
# [1] 기본 MTP2 설치  [2] 다른 target  [3] 이미 있는 자산 활성화
# [4] 이미지 빌드만  [5] 모델 준비만  [6] 상태 확인  [0] 종료
```

### 비대화형 명령 예시

```bash
scripts/install.sh --target orca-uncensored-bf16-mtp --mtp 2 --dry-run
scripts/install.sh --target orca-uncensored-bf16-mtp --mtp 2 --activate-only
scripts/install.sh --target orca-uncensored-bf16-mtp --mtp 2 --prepare-only
scripts/install.sh --target orca-uncensored-bf16-mtp --mtp 2 --build-only
scripts/install.sh --target orca-uncensored-bf16-mtp --mtp 2 --replace
scripts/install.sh --status
```

> **위 명령은 인터페이스 설계용 예시다. 아직 install.sh는 존재하지 않으며 실행할 수 없다.**

| 옵션 | 계약 |
| --- | --- |
| `--interactive` | TTY 메뉴 강제 |
| `--target NAME` | `compatibility.json`의 허용된 target alias만 |
| `--mtp N` | MTP overlay에서만 허용, 기본 권장 depth 2 |
| `--build-only` | Docker 이미지 빌드/patch 검사까지만 |
| `--prepare-only` | 필요한 인증/다운로드/체크포인트 audit까지만 |
| `--activate-only` | 기존 이미지 + 기존 checkpoint/view만 검사하여 서비스 시작 |
| `--replace` | 해당 target에 속하는 **검증된 recipe 컨테이너**만 교체 |
| `--dry-run` | 모든 mutation 차단, 계획/검사/UNKNOWN 표시 |
| `--status` | 이미지, target/container, checkpoint, readiness 상태 조회 |
| `--cache PATH` | 캐시 경로 지정, 안전한 canonical path 검사 |
| `--image NAME` | 이미지 선택/출처 검사 |
| `--port PORT` | 기본 18300; 포트 소유권/충돌 검사 |
| `--help` | 명령별 위험과 상태 반환값 안내 |

모드 충돌 시 중단한다. `--yes`는 향후 추가하더라도 모델/데이터 삭제나 기존 컨테이너 교체를 단독으로 승인하지 못한다. `--unsafe-override`는 기본 wizard에 제공하지 않으며, 별도 실험 모드로만 검토한다.

### 설치 공통 단계

```text
선택 → 읽기 전용 Preflight → 정확한 변경 미리보기 → 승인
   → 이미지 build/reuse (해당 모드만)
   → 인증·다운로드·prepare·audit (해당 모드만)
   → 기존 recipe 컨테이너 소유권·교체 승인 확인
   → 컨테이너 시작 → readiness 판정
   → 최종 receipt/복구 정보 출력
                  실패 시: 변경 범위 + 원인 + 안전한 복구 절차 기록
```

#### 필수 사전 검사

- 호스트 OS/아키텍처(리눅스 ARM64), Docker Engine 사용 가능 여부, NVIDIA GPU/runtime.
- 디스크/메모리 가용성, 저장 위치가 실제 NVMe인지 확인 가능한 정보, 이미지/체크포인트 존재.
- 캐시 및 recipe-view canonical path, 마운트, symlink 탈출 여부.
- gated HF 접근 조건과 인증; 불필요한 다운로드·로그인을 요구하지 않도록 상태 확인.
- `compatibility.json` 고정 revision 및 checkpoint 구조/PLE tensor audit.
- MTP overlay의 31/31 BF16 tensor·source shard size/hash 및 오버레이 index/config 검사.
- 기존 포트 18300(또는 지정값) 충돌, 컨테이너 이름·target label, 타 서비스 보존.
- 선택한 모델의 runtime qualified / unvalidated 상태 표시.
- 기존 100 GiB 디스크 gate는 다운로드 총 요구 공간의 보증이 아니라는 사실을 안내하고, 재사용 캐시와 신규 다운로드 예상 크기를 따로 계산하도록 설계한다.

#### `--activate-only`에서 반드시 보장할 것

1. 새로운 이미지 빌드와 네트워크 다운로드, HF 로그인, view 재구성 금지.
2. 기존 image/cache/view 존재를 요구하고 audit 실패 시 serve를 시작하지 않는다.
3. 실행 옵션은 target과 일치해야 하며 MTP 없는 원본에서 depth>0을 거부한다.
4. 기존 이름이 같은 컨테이너라도 `--replace`가 없으면 자동 삭제 금지.
5. 컨테이너 생성과 실제 모델 ready를 명확히 구분한다.

#### Readiness 게이트

```text
docker run 성공
 → container 상태 running
 → HTTP GET /health 성공
 → GET /v1/models에 정확한 served-model alias 존재
 → 짧은 chat completion 요청 정상(옵션: 기본 활성화)
 → READY 판정/기록
```

완전 cold-start는 오래 걸릴 수 있으므로 기본 timeout은 현행 문서 권장 약 15분을 참고해 **사용자가 조정 가능한 제한**으로 설계한다. 실제 readiness가 확인되기 전에는 성공으로 알리지 않는다.

## 5. 제거 위자드 UX 및 CLI 계약(제안·미구현)

```bash
scripts/uninstall.sh
# [1] 상태 확인 [2] 지정 target 정지 [3] 지정 target 컨테이너 제거
# [4] 사용되지 않는 recipe 이미지 제거 [0] 취소/종료

scripts/uninstall.sh --status
scripts/uninstall.sh --target orca-uncensored-bf16-mtp --stop-only
scripts/uninstall.sh --target orca-uncensored-bf16-mtp --remove-container
scripts/uninstall.sh --target orca-uncensored-bf16-mtp --remove-image
scripts/uninstall.sh --target orca-uncensored-bf16-mtp --remove-container --dry-run
```

**기본 제거는 컨테이너만 대상으로 하며 모델 데이터를 보존한다.**

- `--stop-only`: 지정 target의 검증된 recipe 컨테이너만 정지하고 컨테이너는 유지.
- `--remove-container`: 정확한 container ID/name/recipe label/target label 검증 후 해당 하나만 제거.
- `--remove-image`: 정확한 관리 대상 image ID/출처 검증. 다른 실행·중지 컨테이너에서 쓰는 이미지라면 삭제 거부; 이미지 옵션만으로 컨테이너를 제거하지 않는다.
- `--status`와 `--dry-run`은 상태 조회 외 부작용이 없어야 한다.
- Hugging Face cache, 로그인 token, 원본 checkpoint, 모델 가중치, 공용 cache, 다른 프로젝트의 image/volume, 사용자 파일은 기본값에서 모두 보존.
- `docker system prune`, 광범위한 `docker image prune` 및 와일드카드 `rm -rf` 사용 금지.
- 데이터 `--purge`는 첫 구현에서 **제외**한다. 나중에 추가한다면 백업/용량/경로 소유권/심볼릭 링크 검사/대상 직접 입력 확인/별도 승인 및 테스트를 완료한 뒤 독립 PR로 개발한다.
- 일부 제거에 실패하면 즉시 중단하고 완료/미완료 대상과 오류를 구분해 출력한다.

## 6. Docker 소유권, 복구 및 receipt

### 소유권 확인 규칙

- 컨테이너 이름 일치만으로 삭제·교체하지 않는다. `docker inspect`의 container ID, `ai.yslab.recipe=qwen38-flash-next-bf16-ple` 및 `ai.yslab.target=...` labels, 이미지 참조를 교차 검증한다.
- 기존 컨테이너의 실제 Docker inspect 정보가 GitHub 계획서보다 우선이다. label 불일치 또는 inspect 실패는 삭제 거부.
- 다른 서비스가 사용 중인 이미지, 포트, GPU 자원을 임의로 비우지 않는다.
- 사용자 지정 cache 디렉터리나 symlink 대상은 코드가 관리한다고 가정하지 않는다.

### 상태 기록안

상태 위치 제안: `XDG_STATE_HOME/qwen38-flash-dgx/wizard-state.json` (XDG_STATE_HOME 미설정 시 `~/.local/state/qwen38-flash-dgx/wizard-state.json`).

- receipt 포함 정보: operation ID, timestamp, target/revision, image ID/digest, container ID, 선택 옵션, 상태(PLANNED/PREPARED/STARTED/READY/FAILED/ROLLED_BACK), 로그 경로(비밀정보 제외).
- receipt 파일 권한 0600, 상태 폴더 권한 0700.
- receipt는 운영 기록일 뿐 단독 삭제 허가 증거가 아니다. 실제 Docker 상태와 반드시 대조한다.
- 토큰, 비밀번호, credential, 상세 민감 환경 변수 값은 절대 기록하지 않는다.

### 교체 및 실패 복구 정책

기존 `src/recipe/runtime.py`의 `start_container`는 `--replace` 시 기존 컨테이너를 제거한 다음 환경을 검증한다. 단일 Spark에서는 두 모델을 동시에 올릴 메모리가 없을 수 있어 제거 순서 자체는 일부 필요하지만, **중간 실패 시 기존 서비스가 없어지는 위험**이 있다.

| 상황 | 위자드 필수 처리 |
| --- | --- |
| 사전 검사/명령 생성 실패 | mutation 수행 전 중단 |
| 새 이미지 빌드 실패 | 기존 서비스/기존 태그 보존 가능한 경로 우선 |
| HF 다운로드/인증 실패 | 오류 출력, 데이터 보존, 재시도 안내 |
| checkpoint audit 실패 | serve 차단, 파일 자동 수정/삭제 금지 |
| view 생성 실패 | final view에 부분 결과 노출 금지, 잔여 temporary 복구 안내 |
| 교체 대상 label 불일치 | 즉시 중단, 타 컨테이너 손대지 않음 |
| 기존 컨테이너 제거 뒤 새 시작 실패 | 이전 이미지/명령/볼륨/옵션 복구 시도, 결과 기록 |
| readiness timeout | READY 표시 금지, Docker logs/정확한 상태 안내 |
| rollback 실패 | 정확한 남은 상태와 안전한 수동 복구 안내 |

무중단 교체를 보장하지 않는다. rollback은 필요한 이전 컨테이너 설정을 **비밀정보 없이 안전하게 재구성할 수 있는 범위**에서만 수행하며 무리한 자동 재시작을 반복하지 않는다. 삭제 전 확인과 rollback 능력의 한계를 사용자에게 명확히 제시한다.

## 7. 안전 정책

1. 기존 `compatibility.json`의 repo/revision, Dockerfile base digest, PLE mmap, MTP load guard, BF16 KV, PIECEWISE 설정을 임의 수정하지 않는다.
2. 실행은 항상 정확한 CLI 인자 배열로 구성하고 셸 문자열 조합 실행을 피한다.
3. 삭제할 파일 경로를 다룰 경우 realpath 및 승인된 root를 검사하고 symlink 탈출과 시스템 경로를 거부한다.
4. `--dry-run`은 mutation 0회(사용자 파일 기록 포함)로 테스트하고, 오프라인이라 확인하지 못한 내용은 UNKNOWN이라고 표시한다.
5. 위자드는 외부 방화벽/네트워크/SSH 설정을 자동 변경하지 않는다. Windows 클라이언트는 필요한 경우 SSH 포트 포워딩을 별도로 안내한다.
6. OpenAI-compatible API는 기본적으로 loopback에 바인드하고 무인증 외부 노출을 기본 경로로 만들지 않는다.
7. 권한 상승(`sudo`)과 강제 정리(`rm -rf` 등)는 정상 설치/제거의 기본 경로에 포함하지 않는다.

## 8. 검증 및 시험 계획

### CI/오프라인(필수)

- `bash -n`, 실행 권한 검사, `--help`, 비TTY 동작, 옵션 충돌/취소/출력 및 종료 코드.
- 전용 테스트의 fake runner를 통한 설치/제거 command sequence 검증.
- `--dry-run`의 외부 mutation 0회, `--activate-only`의 build/download/login 호출 0회.
- 기존 target/타겟 label 불일치, 타 프로젝트 컨테이너, 공유 중인 이미지, 포트 충돌, symlink 탈출, 잘못된 경로 거부.
- 중간 빌드/다운로드/audit/시작/readiness 실패 및 부분 완료/rollback 분기 검사.
- receipt와 로그의 secret 누출 차단.
- 추천 MTP=2와 262144/8/0.80/BF16 KV/PIECEWISE/loopback 설정 유지.
- 기존 120개 테스트 함수 및 신규 위자드 테스트 통과, `tools/audit_publication.py` 통과.

### DGX Spark 통합 시험(별도 수행)

- 이미지 신규 빌드 및 Docker patch/CPU mmap 시험.
- 기존 cache 재사용 vs 신규 prepare, HF gated-auth 오류, MTP 31/31 audit.
- `--activate-only`의 재다운로드/재빌드 없는 기동 확인.
- API `/health`, `/v1/models`, 실제 chat completion 검증.
- 정상 교체, 포트 충돌, 잘못된 label, 새 시작 실패에서 복구 확인.
- `--stop-only`/`--remove-container`/`--remove-image` 실행 후 HF 가중치·타 서비스 보존 검증.
- 8K/32K/240K 컨텍스트, NVMe page cache cold/warm, 동시성 및 장시간 가동 성능 시험은 설치 성공과 분리해 보고.

### Definition of Done

- 새 사용자가 설치/활성화/제거를 위자드 한 개의 진입점으로 안전하게 수행할 수 있다.
- 명령은 문서로 재현 가능하고 잘못된 상태에서 안전하게 실패한다.
- 기존 인프라 소유권 검사, 허용 범위 제한, 데이터 보존, 실패 복구 동작이 테스트된다.
- readiness와 실제 모델 alias/API 응답 성공을 확인한다.
- CI PASS 및 DGX 실제 기본 시나리오 PASS가 없으면 운영 검증 완료라고 표시하지 않는다.

## 9. 구현 단계, 커밋 계획, GitHub 협업

| 단계 | 산출물 | 주요 합격 조건 |
| --- | --- | --- |
| **P0 현재** | feature branch + 본 `scripts/` 계획서 | 원격 브랜치/파일 조회 |
| P1 | wizard 입력, plan, preflight, 상태·receipt | fake runner 및 dry-run |
| P2 | `install.sh`, build/prepare/activate | 모드 분리, audit, 안전 확인 |
| P3 | readiness, guarded replace, rollback | 실패/복원 시나리오 |
| P4 | `uninstall.sh`, stop/remove/image 처리 | 강한 소유권 검증, 데이터 보존 |
| P5 | 사용자 매뉴얼, CI, DGX 실측 운영 시험 | DoD 모두 PASS |
| P6 | 코드 검토 PR 및 승인 병합 | diff/CI/작업 이력 확인 |

커밋 단위 제안:

```text
docs(scripts): plan guarded installation and removal wizards
feat(wizard): implement interactive planning and preflight
feat(scripts): implement guarded install wizard
feat(wizard): add readiness and rollback safeguards
feat(scripts): implement safe uninstall wizard
test(wizard): cover modes, ownership, failure and rollback
docs(scripts): publish wizard operating and recovery guide
```

### 다음 대화/작업 재개 규칙

1. `feature/install-uninstall-wizard-20261026`의 HEAD/차이를 확인하고 이 문서를 우선 읽는다.
2. `README.md`, `docs/{HOW-IT-WORKS,COMPATIBILITY,TROUBLESHOOTING}.md`, `src/recipe/{cli,runtime,download,audit,mtp}.py`의 최신 내용을 확인한다.
3. `main`, 상위 YSLAB-ai 저장소 또는 다른 프로젝트의 코드를 덮어쓰지 않는다.
4. 기능 구현은 P1→P5 단계별로 진행하고 단위테스트/정적 검사를 기록한다.
5. 실제 DGX 상태는 GitHub 소스만으로 알 수 없으므로 확인되지 않은 사항은 `NOT TESTED`로 표기한다.
6. 사용자 지시 없는 모델 자산 삭제, Docker 강제 종료, PR merge는 수행하지 않는다.

---

**상태 요약:** 계획 문서만 완성한 단계. `scripts/install.sh` 및 `scripts/uninstall.sh`는 아직 구현되지 않았다.
