# 두 종류의 Manifest: 선언형 정책과 모델 호환성

## 1. 반드시 분리해야 하는 정보

| 파일 | 목적 | Git 추적 | 수정 주의 |
| --- | --- | --- | --- |
| `compatibility.json` | Hugging Face target/revision, PLE/MTP tensor shape/source hash | Yes | **원본 모델 계약. 위자드에서 수정하지 않음** |
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
