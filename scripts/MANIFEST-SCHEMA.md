# Manifest 3종: 모델 호환성 / 배포 정책 / 소스 상태 (및 로컬 receipt)

## 1. 반드시 분리해야 하는 정보

| 파일 | 목적 | Git 추적 | 수정 주의 |
| --- | --- | --- | --- |
| `compatibility.json` | Hugging Face target/revision, PLE/MTP tensor shape/source hash | Yes | **원본 모델 계약. 위자드에서 수정하지 않음** |
| `scripts/source-state-manifest.json` | Git 브랜치의 추적 파일 전체 blob SHA/mode 스냅샷, 검증기 버전 및 **미시험 상태** | Yes | 자체 해시는 HEAD Git object로 별도 검증. 배포 소유권을 표시하지 않음 |
| `scripts/deployment-manifest.json` | 새 설치 기본 profile, image/port, legacy 감지 fingerprint, 안전 정책 | Yes | 코드 검토 후 변경 |
| `~/.local/state/qwen38-flash-dgx/deployment-state.json` | 새 위자드가 생성한 실제 image/container ID와 legacy 관찰 기록 | **No** | 0600, atomic write, 백업 시 보안 검토 |
| `~/.local/state/yslab-qwen38-bf16ple/*` | 기존 참조 설치 스크립트의 소유권 ID 기록 | **No** | **읽기 전용**, 새 위자드가 기록/수정 금지 |

Manifest에 Docker 리소스의 **현재 소유권을 고정 기록하면 안 된다**. Git의 선언형 정책과 로컬의 동적 ID를 분리해야 두 체크아웃 간 충돌을 예방할 수 있다.

## 2. deployment-manifest.json 필드

- `schema_version=1` / `policy_id`: 호환성 식별자.
- `origin`: 이 Fork/원본과 참조 시점 기준 commit SHA. 현재 실행한 checkout의 SHA와 혼동하지 않는다.
- `service`: MTP2 추천 target, image tag, `127.0.0.1:18300`, context `262144`, seqs `8`, memory `0.80`, readiness 상한.
- `legacy`: 이미 사용된 YSLAB 배포를 **관찰**하기 위한 상대 경로, legacy 이미지/컨테이너/포트, 정확한 PIN과 Docker recipe label.
- `policies`: 모델·cache·인증·타 서비스 보존, legacy read-only adoption, 명시적 소유권 요구, API 외부 노출 제한.

`scripts/manifest.sh validate`는 선언형 정책을 정적으로 검사한다. 최신 Docker/가중치 상태를 검증하는 것은 `scripts/status.sh`, `scripts/doctor.sh`, 모델 `scripts/qwen38-dgx-spark audit`의 역할이다.

## 3. 상태 파일과 소유권 증거

새 위자드 상태 형식(개념적 예시):

```json
{
  "schema_version": 1,
  "image": {"tag": "kjlee-qwen38-bf16ple-wizard:9492b78c", "id": "sha256:<64-hex>", "source": "wizard-build"},
  "containers": {
    "qwen38-flash-orca-uncensored-bf16-mtp": {
      "id": "<64-hex>",
      "target": "orca-uncensored-bf16-mtp",
      "image_id": "sha256:<64-hex>",
      "port": 18300,
      "bind": "127.0.0.1",
      "mtp": 2,
      "ready": true
    }
  },
  "legacy_observation": null
}
```

위 ID들은 **설명용 자리표시자이며 실측 값이 아니다**. `legacy_observation`이 채워져도 이는 *관리자 소유 리소스*가 아니라 읽기 전용 기록이다. 삭제 시에는 신규 `containers`/`image` receipt와 현재 Docker ID/labels를 모두 재검사한다.

## 4. Manifest 관리 규칙

1. `compatibility.json`의 SHA/PLE/MTP 수치를 위자드 편의로 수정하지 않는다.
2. `deployment-manifest.json`에 비밀번호, 토큰, 사용자의 실제 Docker ID, 절대 개인경로 또는 개인 API endpoint를 커밋하지 않는다.
3. 정책 변경은 브랜치/PR에서 검토하고 관련 사용 설명서를 같이 수정한다.
4. Legacy fingerprint 변경은 가벼운 설정 변경이 아니라 **새 레거시 호환성 정의**로 다룬다.
5. 상태 파일이 없거나 일치하지 않으면 임의 Docker 컨테이너/이미지 삭제 대신 실패한다.


## 5. source-state-manifest.json 운영 및 검증

`scripts/source-state-manifest.json`은 선언형 정책이 아니라
**특정 Git source snapshot**을 보존하는 별도 파일입니다.

- `source_creation_parent_commit`: snapshot 작성 **직전** feature 브랜치의 SHA.
  새 Manifest 커밋의 HEAD와 같아야 하는 값이 아닙니다.
- `base_main_commit_at_creation`: 최초 기준 `main` SHA(후일 `main` HEAD 갱신을 강제하지 않음).
- `files[]`: 저장소에 추적되는 파일의 path / Git blob SHA-1 / executable mode.
  소스 Manifest **자기 자신은 제외**해 해시 순환을 피합니다.
- 검증기는 Git HEAD 트리, 실제 working-tree bytes, 관리 Fork origin 및 feature
  branch를 대조하며 Manifest 자체는 별도로 HEAD blob과 비교합니다.
- `validation_at_creation`은 GitHub 관찰 사실과 구분해
  `tests=NOT_RUN`, `host_runtime=NOT_OBSERVED`를 명시합니다.
- **커밋으로 파일이 바뀌면 Manifest를 재생성해 함께 검토해야 합니다.**
  이를 회피하려고 Git 태그/force push/reset으로 변경 이력을 덮어쓰지 않습니다.
- 명령과 안전 가이드는 [Git pull부터 검증까지](VERIFY-FROM-GIT-PULL.md)를 따릅니다.


## 6. 설치 이력 변경과 Docker 소유권의 분리

2026-10-26 운영자 DGX 출력에서 **기존 참조 스크립트가 설치한 동일 디렉터리**의
Git origin/HEAD만 변경된 사례를 확인했습니다. 이 경우:

- `legacy.checks.recorded_paths/image_identity/container_identity/docker_labels/port_binding/model_mounts`
  모두 일치해야 `identity_verified`가 true입니다.
- `legacy.checkout.origin_matches_install` 및
  `legacy.checkout.head_matches_install_pin`은 false일 수 있으며
  `checkout_warnings`으로 보고됩니다.
- `legacy.checkout.install_pin_available`은 예전 commit이 로컬 Git에 남아 있는지
  나타냅니다. 이미지가 그 소스에서 만들어졌다는 암호학적 증거는 아닙니다.
- `legacy.api.health/models`는 read-only localhost HTTP 확인일 뿐,
  실제 생성 추론 또는 파괴적 조작 권한과 무관합니다.
- `legacy.management_authority=OBSERVE_ONLY`와
  `legacy.read_only=true`는 이 모든 조건에서 유지됩니다.
- 기존 container/image ID는 **로컬 상태 파일에만 유지**, Git Manifest에는
  개인 환경의 실제 Docker ID를 추가하지 않습니다.

자세한 근거는 [운영자 관찰 기록](LEGACY-OBSERVATION-20261026.md)입니다.
