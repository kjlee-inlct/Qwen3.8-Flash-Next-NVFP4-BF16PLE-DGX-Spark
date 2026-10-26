# 안전 모델 / 실패 복구 가이드

> 신규 Wizard Docker는 `qwen38-wizard-<target>` 이름/전용 ownership label을 사용한다.
> 기존 `qwen38-flash-<target>`은 불변이며, 이름 충돌 해소와 GPU 동시 운용 승인은 다르다.
> 레거시 running 상태에서 새로운 GPU 활성화는 거부한다.

> 이번 커밋의 위자드는 **테스트 미실행** 상태다. 실제 DGX 서비스 교체나 삭제를 실행하기 전에 별도 검증이 필요하다.

## 사전 예방 규칙

- 기본 host endpoint는 `127.0.0.1:18300`이며, 기존 port 8000/OpenWebUI/Ollama를 자동 변경하지 않는다.
- 운영 중인 컨테이너의 이름이 겹치면 정확한 대상이라도 **교체하지 않는다**. `--replace`는 구현·검증된 rollback이 없으므로 거부한다.
- 참조 legacy state의 경로/이미지 ID/컨테이너 ID는 모두 확인하지만 **새 소유권으로 승격하지 않는다**.
- 신규 Docker image tag는 YSLAB의 `yslab-qwen38-bf16ple:9492b78c`와 다르다. 기존 tag를 덮어쓰지 않는다.
- `--activate-only`는 다운로드·빌드·HF 로그인 금지. 기존 파일이 없으면 오류로 종료한다.
- 모델 파일, cache, Git checkout, HF token은 제거 기능에서 절대 삭제하지 않는다.
- `--dry-run`은 외부 mutation 및 신규 상태 파일 작성 없음.
- 필요 최소 작업만 실행: `stop`은 stop만, `remove-container`는 해당 ID만, `remove-image`는 사용 여부를 검사한 해당 image tag만.

## 장애 처리

| 증상 | 대응 |
| --- | --- |
| 레거시 상태 불일치 | `scripts/status.sh` 및 기존 YSLAB state 파일/원격 origin/HEAD 확인. 자동 수정 금지 |
| 컨테이너 이름 충돌 | 레거시가 운영 중일 수 있음. 새 위자드가 강제 종료하지 않음 |
| 새 이미지 태그 충돌 | state의 image ID 일치 여부 검토. 이미지 강제 태그 변경 금지 |
| disk/memory gate | 실제 `df`/`MemAvailable` 확인. 위험한 `--unsafe-override` 자동 선택 금지 |
| gated HF access | 동일 계정의 브라우저 승인/recipe cache 로그인 확인 |
| MTP load guard 오류 | 31/31 검증 실패면 serve 금지. 원본 shard/hash 확인 |
| 컨테이너 시작 후 readiness 오류 | 컨테이너가 진단용으로 남을 수 있음. `status`와 Docker logs 조사 |
| 삭제 시 receipt 없음 | 강제 삭제하지 않는다. 관리 범위/레거시 여부 재확인 |
| 이미지 사용 중 | 실행/정지 상태를 포함한 Docker 참조를 해제한 뒤 재검토 |

## 사용자가 직접 확인할 진단 명령 (조회 전용)

```bash
scripts/doctor.sh
docker ps -a --no-trunc
docker image ls
docker container inspect qwen38-flash-orca-uncensored-bf16-mtp
docker logs --tail 120 qwen38-flash-orca-uncensored-bf16-mtp
```

실제 컨테이너가 존재하지 않으면 `docker inspect/logs`가 실패할 수 있다. 이는 조회 오류이지 새로운 서비스 실패의 증거가 아니다.

## 현재 구현에서 제한된 복구 능력

- 신규 서비스 시작 명령 후 readiness가 실패하면 container ID를 먼저 wizard receipt에 기록하고 컨테이너를 남긴다. **자동으로 이전 서비스를 재시작하지 않는다**.
- 새 위자드는 기존 서비스를 제거한 상태에서 작업하지 않으므로 이전 서비스 rollback이 필요한 교체 경로 자체를 차단한다.
- 이미지 빌드/다운로드 중간 실패와 임시 checkpoint view에 대한 완전한 자동 cleanup/rollback은 미구현이다. 정리보다 **데이터 보존**을 우선한다.
- 복구와 서비스 전환은 GPU 실환경 시험 및 별도 승인 후 추가 구현한다.

## 변경된 삭제 소유권 조건

이름만 맞아도 삭제를 허용하지 않는다. Wizard가 관리하는 자산의
전체 Docker ID, 이미지 ID, recipe/target label, Docker Name,
`ai.kjlee.wizard` label, 전용 receipt가 일치할 때만 정지/삭제 요청을 허용한다.
`legacy.adoption=OBSERVE_ONLY`은 삭제 권한이 아니며 신규 실기기 검증은 아직 미실행이다.
