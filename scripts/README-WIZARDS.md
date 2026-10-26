# DGX Spark 설치·제거 위자드 사용 안내

> **2026-10-26: 구현 작성 완료, 테스트 미실행(NOT TESTED).**
> 대상: `feature/install-uninstall-wizard-20261026`. `main` 및 상위 YSLAB-ai 코드를 변경하지 않는다.
> 위자드는 기존에 참조 `install.sh`로 설치한 YSLAB 서비스를 **자동 이관하거나 재설치하지 않는다**.

## Git pull → 소스 상태 Manifest 검증

**[실행 명령 전체 보기](VERIFY-FROM-GIT-PULL.md)**: 사용자 Fork origin 확인, 브랜치 pull
(`--ff-only`), 모든 추적 파일의 blob SHA/mode 검증, 선언형 정책 검증,
레거시 설치 읽기 전용 점검 순서로 실행합니다.

- `scripts/source-state-manifest.json`: 현재 개발 브랜치에서 커밋한 **소스 파일 전체의 버전 지문**.
- `scripts/verify-source-state.sh --strict`: Git HEAD 및 작업 디렉터리 파일 해시 검증.
- `scripts/deployment-manifest.json`: 설치 기본값/정책.
- `compatibility.json`: 모델 revision, PLE/MTP tensor 호환성.

**검증기 성공 문구 `PASS_SOURCE_ONLY`는 실제 설치/모델 테스트 성공이 아닙니다.**
기존 YSLAB checkout에서 pull/checkout/레포지터리 재설정을 수행하지 않습니다.

## 현재 실 DGX 확인 사항 (레거시 설치 유지)

[2026-10-26 사용자 제공 DGX 출력](LEGACY-OBSERVATION-20261026.md)에 따르면
기존 YSLAB 설치와 현재 Fork는 **동일한 checkout 경로**를 사용합니다.
컨테이너/이미지 ID, label, 마운트, port 8000은 legacy 기록과 일치하고,
현재 origin/HEAD는 설치 당시와 다릅니다.

업데이트한 `scripts/status.sh`는 Docker ID·port·mount 기반
`identity_verified`와 Git checkout drift를 별도 필드로 보고합니다.
변경된 origin/HEAD를 원래대로 돌리려고 `git reset`,
`git checkout --detach`, 재다운로드 또는 레거시 이미지 재빌드를 하지 마세요.

다음 명령만 사용해 현재 상태를 읽기 전용으로 확인하세요.

```bash
git pull --ff-only origin feature/install-uninstall-wizard-20261026
scripts/verify-source-state.sh --strict
scripts/status.sh
scripts/doctor.sh
```

**현재 모델 컨테이너와 모델 캐시는 그대로 보존됩니다.**

## 먼저 알아야 할 점

1. Git에 추적되는 선언형 구성은 `scripts/deployment-manifest.json`이고, 모델 출처/텐서 호환성의 유일한 기준은 기존 `compatibility.json`이다.
2. 실제 Docker container ID, image ID, 활성화 상태 및 legacy observation은 **로컬** `${XDG_STATE_HOME:-$HOME/.local/state}/qwen38-flash-dgx/deployment-state.json`에 0600 권한으로 기록한다. Git에 커밋하지 않는다.
3. 이미 설치한 YSLAB 서비스는 기본적으로 `:8000`, 이미지 `yslab-qwen38-bf16ple:9492b78c`, 컨테이너 `qwen38-flash-orca-uncensored-bf16-mtp`이다. 새 위자드는 이를 자동 정지·삭제·수정하지 않는다.
4. 새 위자드의 독립 이미지 태그는 `kjlee-qwen38-bf16ple-wizard:9492b78c`, 기본 호스트 API는 `127.0.0.1:18300`이다. 그러나 **동일 target의 Docker 컨테이너 이름이 기존 것과 충돌**하므로 레거시가 남아 있으면 새 활성화는 안전하게 실패한다.
5. 별도의 설치 디렉터리 클론을 자동으로 만들지 않는다. 이미 사용 중인 저장소와 혼동하지 않도록 **위자드 코드를 실행하는 Fork checkout**을 사용한다.
6. 본 구현은 아직 동작 시험, 실 DGX GPU 시험 또는 CI 검증을 하지 않았다. 중요 서비스가 사용 중이면 먼저 `status`와 `dry-run`만 이용한다.

## 빠른 시작: 읽기 전용

```bash
# 새로운 Fork checkout의 루트에서 실행
scripts/manifest.sh validate
scripts/status.sh
scripts/doctor.sh
scripts/install.sh --dry-run
scripts/uninstall.sh --remove-container --dry-run
```

`uninstall --dry-run`에도 정확한 wizard ownership receipt가 있어야 한다. 없으면 안전하게 거부한다.

## 기존에 설치한 YSLAB 서비스 조회·등록

```bash
scripts/status.sh
# 상태에서 legacy.verified=true이고 observed_container_id가 있으면,
scripts/adopt-legacy.sh --confirm-container-id FULL_64_CHARACTER_CONTAINER_ID --yes
scripts/status.sh
```

`adopt-legacy.sh`는 레거시의 `paths`, `image-id`, `container-id`, Git origin/HEAD, Docker ID, label/target/포트를 대조한 후 **상태 관찰 정보만** 신규 wizard-state에 기록한다. 기존 레거시 state나 Docker에는 쓰지 않는다. 이 등록만으로 레거시의 정지·제거 권한이 생기지 않는다.

상태를 검증할 수 없으면 자동 adoption은 중단된다. `YSLAB_STATE_DIR`은 레거시 기록 위치가 다른 경우 조회 대상 지정에 사용할 수 있지만, 기록 자체를 임의로 신뢰하지 않는다.

## 신규 설치: 레거시와 별개

```bash
# 사전 계획, 실제 변경 없음
scripts/install.sh --target orca-uncensored-bf16-mtp --mtp 2 --dry-run

# 설치 이미지만 빌드 (권한 확인 필수)
scripts/install.sh --build-only --yes

# 준비된 이미지를 사용해 체크포인트 준비·audit
scripts/prepare.sh --skip-login --yes

# 기존 신규 위자드 캐시가 완비된 경우에만 시작
scripts/activate.sh --yes

# 신규 이미지 빌드 + 준비 + 서비스 시작
scripts/install.sh --skip-login --yes
```

**주의:** 사용자 계정에 기존 YSLAB 컨테이너가 있으면 신규 위자드 활성화를 시도하기 전에 이름 충돌을 감지하고 종료한다. 새로운 이미지를 빌드하는 작업은 별도로 가능하지만 기존 모델이 이미 설치되어 있다면 재다운로드 전에 용량과 공유 전략을 검토해야 한다.

`--skip-login`은 HF 인증을 우회하지 않는다. 필요한 로그인/게이트 승인이 이미 완료된 사용자 캐시를 활용하겠다는 뜻이다. 새 Fork checkout의 HF 캐시는 기존 YSLAB checkout과 분리되어 있으므로 무조건 동일한 인증·다운로드를 재사용한다고 가정할 수 없다.

`scripts/install.sh` 또는 `scripts/uninstall.sh`만 실행하면 TTY에서 숫자 메뉴를 사용한다. 비대화형 환경에서는 모드 옵션과 `--yes`를 명시한다. `--dry-run`과 상태 조회는 확인 없이 실행 가능하다.

## 신규 자산만 제거

```bash
scripts/stop.sh --yes
scripts/uninstall.sh --remove-container --yes
scripts/uninstall.sh --remove-image --yes
```

`--remove-image`는 중지된 컨테이너까지 포함해 해당 image ID를 사용하는 자산이 존재하면 실패한다. 기본 제거는 체크포인트, HF cache, 인증, 저장소, legacy state, 다른 컨테이너를 삭제하지 않는다. `--purge-cache` / `--purge-repo` 옵션은 **지원하지 않는다**.

## 위자드가 일부러 지원하지 않는 기능

- 기존 YSLAB 컨테이너의 자동 takeover/upgrade/replace/uninstall
- `--replace`를 통한 기존 서비스 강제 삭제 (rollback 검증 전까지 차단)
- 무인증 API를 `0.0.0.0:8000`에 자동 공개하거나 방화벽 변경
- HF cache 공유/이동, 기존 checkout 덮어쓰기, Git reset/clone, 무단 이미지 태그 변경
- 모델 체크포인트의 임의 변경, 사전 검증 없는 MTP 적용

## 관련 문서

- [Manifest 구조](MANIFEST-SCHEMA.md)
- [레거시 설치 보호·관찰](LEGACY-INSTALLATION.md)
- [보안 및 장애 대응](SAFETY-AND-RECOVERY.md)
- [운영 순서](OPERATIONS.md)
- [향후 시험 계획](TEST-PLAN.md)
- [최초 계획 및 작업 단계](INSTALL-UNINSTALL-WIZARD-PLAN.md)
