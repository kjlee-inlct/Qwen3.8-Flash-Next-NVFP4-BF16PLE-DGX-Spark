# 운영 시나리오 / 체크리스트

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

체크리스트: 현 YSLAB 컨테이너와 **같은 target name 충돌**, 디스크/메모리 여유, 포트 18300 점유 여부, 이미지 태그의 기존 소유권, cache 재사용/추가 다운로드, 모델 게이트 승인 확인.

## C. 신규 설치 (기존 레거시와 별개)

```bash
scripts/install.sh --build-only --yes
scripts/install.sh --prepare-only --skip-login --yes
scripts/install.sh --activate-only --yes
```

최초 이미지만 빌드해도 테스트 전에는 안전한 운영이 검증된 것으로 볼 수 없다. 동일 target legacy 컨테이너가 존재하면 마지막 활성화 단계가 거부된다. **문서화를 이유로 기존 서비스를 중단하지 않는다**.

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

2026-10-26 사용자 제공 로그 기준 **기존 HEAD에서 모의 36/36·전체 156/156 PASS**,
legacy 6/6 및 API Health PASS입니다. [검증 기록](VALIDATION-RESULTS-20261026.md).
다만 새로운 소스 검증기 테스트는 재실행이 필요하며 실제 신규 설치·제거
성공 및 성능은 미확인입니다.
