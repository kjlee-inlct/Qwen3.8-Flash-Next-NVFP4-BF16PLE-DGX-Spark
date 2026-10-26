# 위자드 검증 계획 (아직 실행하지 않음)

> **NOT TESTED.** 사용자의 지시에 따라 이 변경에서는 테스트, Docker build, 다운로드, 실제 설치/제거 명령을 실행하지 않는다. GitHub의 자동 CI가 실행되더라도 결과를 확인하기 전에는 PASS로 기록하지 않는다.

## 새로운 소스 상태 무결성 검사 (사용자 실행용 / 이번 커밋에서 미실행)

```bash
scripts/verify-source-state.sh --strict
scripts/verify-source-state.sh --strict --json
scripts/manifest.sh validate
```

`source-state-manifest.json`은 소스 파일 blob SHA/mode/branch/origin을 검증하며,
**실 DGX 테스트 또는 Docker 동작을 실행하지 않습니다.**
변경/누락/신규 Git 추적 파일이나 잘못된 Git origin을 fail로 판정하는 사례를
추후 fake checkout에서 별도 시험합니다. [전체 순서](VERIFY-FROM-GIT-PULL.md).

## 정적 검사 예정

- `python3 -m py_compile scripts/wizard/*.py`
- `bash -n scripts/{install,uninstall,status,adopt-legacy,manifest,doctor,prepare,activate,stop}.sh`
- `python3 tools/audit_publication.py`
- `PYTHONPATH=src:. python3 -m unittest discover -s tests -v`
- 변경된 README/상위 README 간 문서 계약 및 Git diff 확인

## Fake Docker/Git runner 단위 시험

| 그룹 | 테스트 벡터 | 기대 결과 |
| --- | --- | --- |
| Manifest | 잘못된 schema/target/MTP/options | 거부 |
| 상태 파일 | 미존재/손상/권한 과다/symlink/atomic replace | 안전한 상태 유지 |
| Legacy | origin/HEAD/path/image/container ID/label/port 일부 불일치 | `verified=false` |
| Adoption | 정확한 full container ID 없이 요청 | 거부 |
| Adoption | 모든 값 일치 | 읽기 전용 기록만 생성; 레거시 state 변경 0 |
| Dry-run | install/uninstall/prepare/build | Docker writes 0, 상태 파일 writes 0 |
| Activate-only | 이미지 또는 model 미준비 | build/download/login 0, 오류 |
| Collision | YSLAB과 동일 Docker target name | 기존 서비스 그대로, 시작 거부 |
| Reuse | image tag와 recorded ID 일치 | 불필요한 rebuild 0 |
| Build | image tag 사전 점유/recorded ID 불일치 | 이미지 덮어쓰기 거부 |
| Runtime | host port occupied/invalid target | 시작 거부 |
| Ownership | 삭제 대상 이름 일치, image ID/label 불일치 | stop/rm 금지 |
| Image | 타 컨테이너가 이미지 ID 참조 | image rm 금지 |
| Readiness | health PASS, models 누락 또는 chat 실패 | READY 불가 |
| Secrets | stderr/stdout/receipt | 토큰 노출 없음 |

## DGX Spark 실기기 예정

- 사전 snapshot: legacy state, Docker inspect IDs, port 8000 운영 여부 기록.
- 읽기 전용 조회/adoption이 기존 API, OpenWebUI, Ollama, 네트워크 설정과 모델 파일을 변경하지 않는지 확인.
- 신규 이미지 빌드, patch 검증, 모델 audit(31/31), cache 재사용, 실패 시 데이터 보존 확인.
- 레거시 container name 충돌 보호 확인; 기존 컨테이너 삭제/중지 없음.
- 신규 독립 target의 기동 및 `/health`, `/v1/models`, 실제 chat API 확인(충돌 해결 전 같은 target으로 무리하게 실행 금지).
- 신규 wizard receipt가 있는 환경에서 정확한 stop/rm/image rm의 소유권 검증, 파일 보존 확인.
- 240K long-context 및 MTP 성능/동시성/장시간 안정성은 별도 성능 QA로 분리.

## 합격 기준

기존 서비스·가중치 파일 보존이 최우선이다. 테스트 모두 통과하고 실제 DGX의 안전한 신규 배포/제거 시나리오가 확인되기 전에는 `main` 병합 또는 운영 검증 완료로 표시하지 않는다.
