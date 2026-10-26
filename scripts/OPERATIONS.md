# 운영 시나리오 / 체크리스트

> 최신 신규 Wizard 전용 이름은 `qwen38-wizard-<target>`; owner marker와 정확한
> Docker ID/image ID/receipt를 함께 확인한다. 레거시 컨테이너가 가동 중이면
> 단일 GB10 신규 GPU 서비스는 동시 시작하지 않는다.

> 신규: [git pull부터 검증 명령 전체](VERIFY-FROM-GIT-PULL.md). 기존 YSLAB 저장소에서 git pull을 실행하지 않고, 소스 해시 검증을 먼저 수행합니다.


## 저장된 관찰 기록과 현재 상태 비교 (신규)

```bash
scripts/status.sh
scripts/compare-state.sh
scripts/health.sh
scripts/doctor.sh
scripts/status.sh --json --health
```

`UNCHANGED`, `CHANGED`, `HEALTH_CHANGED`, `GIT_CHANGED`,
`UNREGISTERED`, `UNKNOWN`을 구분합니다.
Docker ID/mount/port 변화는 Git HEAD 변화보다 우선하며,
저장 공간 부족은 경고로 표시하고 자동 삭제하지 않습니다.
[검증 순서와 결과 해석](STATUS-COMPARE-AND-HEALTH.md).

## 현재 실환경: 같은 checkout의 origin/HEAD 변경

[DGX 사용자 관찰 결과](LEGACY-OBSERVATION-20261026.md):
모델 cache·recipe-views Docker 마운트/레거시 ID 기록 일치,
port `0.0.0.0:8000`, 현재 checkout origin/HEAD 변경.
이제 `identity_verified`는 Docker ID/mount/port 기반으로,
checkout drift는 별도 `checkout_warnings`으로 표시합니다.
현재 서빙 유지가 최우선이므로 uninstall/purge/rebuild/replace 명령을
기존 설치 대상으로 실행하지 않습니다.

## A. 현재 운용 중인 YSLAB 모델을 그대로 관리하기 시작

```bash
# 대상 checkout을 이동하지 않으며 아래 동작은 읽기 전용
scripts/manifest.sh validate
scripts/status.sh
scripts/doctor.sh

# status의 legacy.verified == true, recorded ID == observed ID인 경우에만:
scripts/adopt-legacy.sh --confirm-container-id FULL_ID --yes
```

완료 기준은 **레거시 설치 상태의 관찰 기록**이며, 신규 설치/동작 변경이 아니다. 기존 포트 8000, OpenWebUI, Ollama, 다른 컨테이너, HF cache를 유지한다.

## B. 신규 타깃 배포 계획

```bash
scripts/install.sh --dry-run
scripts/install.sh --prepare-only --dry-run
scripts/install.sh --activate-only --dry-run
```

체크리스트: 분리된 Wizard 전용 Docker 이름(`qwen38-wizard-<target>`) 및 marker, 레거시 컨테이너 running 상태에서 단일 GB10 GPU 동시 활성화 차단, 디스크/메모리 여유, 포트 18300 점유 여부, 이미지 소유권, cache 재사용/추가 다운로드, 모델 게이트 승인 확인.

## C. 신규 설치 (기존 레거시와 별개)

```bash
scripts/install.sh --build-only --yes
scripts/install.sh --prepare-only --skip-login --yes
scripts/install.sh --activate-only --yes
```

최초 이미지만 빌드해도 안전 운영이 검증된 것은 아니다. 이름은 분리되었지만 **기존 레거시 컨테이너가 running이면 단일 GB10 신규 GPU 활성화는 거부된다.** 실제 신규 배포는 별도 승인/실기기 검증 전 금지. **문서화를 이유로 기존 서비스를 중단하지 않는다**.

## D. 신규 위자드가 생성한 자산만 정지·삭제

```bash
scripts/uninstall.sh --target orca-uncensored-bf16-mtp --stop-only --dry-run
scripts/uninstall.sh --target orca-uncensored-bf16-mtp --stop-only --yes
scripts/uninstall.sh --target orca-uncensored-bf16-mtp --remove-container --yes
scripts/uninstall.sh --remove-image --yes
```

이 명령은 Docker의 실 ID와 신규 로컬 receipt 검사를 통과해야 하며 **기존 레거시 관찰 기록만으로는 절대 성공하지 않는다**. 데이터를 제거하지 않으므로 필요하면 모델을 다시 준비하지 않고 사용할 수 있는지 개별 audit로 재평가한다.

## E. 작업 기록

매 작업마다 날짜, 대상 Fork commit SHA, `deployment-manifest.json` 버전, 호스트 Docker 및 드라이버 버전, 작업 명령, 실행 전후 실제 Docker ID, API readiness 결과, 오류 코드/복구 결과를 작성한다. 이 중 계정 토큰과 민감 환경변수는 수집하지 않는다.

2026-10-26 **최신 DGX `main=66051cdc...`** 사용자 로그에서 source 114/114,
Wizard mock **38/38 PASS**, 전체 unit **172/172 PASS**, 레거시 identity/API/Health
PASS를 확인했습니다. 이전 36/36·156/156 또는 163/163은 각각 과거 HEAD에 대한
증거입니다. [시점별 검증 기록](VALIDATION-RESULTS-20261026.md).
새 Wizard 실제 설치·제거/rollback·성능은 미시험이며 CI는 사용자 요청으로 보류 중입니다.

## main 로컬 소스/서비스 조회 전용 검증 (DGX 실행 후에만 유효)

`scripts/verify-main-readonly.sh`는 포트 8000/기존 모델/컨테이너를 변경하지 않고
main Fork origin·working tree·local origin/main 동일성을 먼저 확인한 뒤
정적/모의/전체 테스트와 legacy status/health/doctor를 **조회만** 수행한다.

```bash
cd "$HOME/Workspace/llm/yslab-qwen38-bf16ple-dgx-spark"
git remote get-url origin
git status --short
git branch -vv
# 원격과 clean 상태를 확인한 뒤 별도 작업:
git fetch origin main
git switch main  # 로컬 main이 없으면 git switch --track origin/main
git merge --ff-only origin/main
scripts/verify-main-readonly.sh
```

`git switch`/merge는 checkout을 실제로 바꾸므로 사전 확인 후 사용자가 DGX에서 수행한다.
충돌/dirty/remote 불일치 시 중단하고 reset/clean/강제 교체를 하지 않는다.

## 2026-10-26 기록 이후 운영 작업 우선순위

- **현재 완료:** 검증 대상 `main=66051cdc...`의 실 DGX read-only 일괄 검증, mock 38/38, full 172/172, 레거시 Health PASS.
- **차후 보류:** GitHub Actions 원인 조사/CI 정상화. workflow/settings 변경은 이 docs-only PR에 포함하지 않는다.
- **다음 개발:** 레거시와 격리된 신규 자산에 대한 모의 실패 복구/rollback,
  중복 checkpoint 다운로드 회피. 실제 GPU 가동 시험은 별도 승인 필요.
- **구분:** docs-only merge의 새로운 HEAD는 DGX에서 재실행하지 않았다.
  `scripts/verify-main-readonly.sh`를 안전한 시점에 새 `main`에서 재실행한다.
