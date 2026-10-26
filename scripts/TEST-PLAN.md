# 위자드 검증 계획 및 운영자 시험 결과 (2026-10-26)

> **사용자 제공 DGX 로그:** 이전 기능 브랜치 HEAD
> `3b00eafc44ebf5fa6e16134f30fb4be2679c0978`에서
> **위자드 모의 시험 36/36 PASS, 전체 저장소 단위 시험 156/156 PASS**.
> Source Manifest 109개 파일 통과, Legacy 6/6, API/Health PASS.
> [상세 검증 증거](VALIDATION-RESULTS-20261026.md).
>
> **별개:** 이번 소스 검증기(main 호환) 변경과 신규 회귀 테스트는
> 아직 재실행 결과가 없으며, 실제 **신규 설치·제거·rollback** 시험은 미실행.
> 자동 CI 결과도 개별 확인이 필요합니다.

## 최신 근거 및 CI 보류

- 2026-10-26 사용자 DGX 실호스트 `main=66051cdcd4b2c5766de55421579867c195fe4084`
  읽기 전용 일괄 검증 완료: `PASS_SOURCE_ONLY 114`, policy 4/4,
  Wizard 모의 **38/38 PASS**, 전체 unit **172/172 PASS**.
- 기존 레거시 컨테이너 running, identity/API/Health PASS, 변경은
  `GIT_CHANGED`(Git HEAD 1건)뿐; 레거시 관리 권한 `OBSERVE_ONLY`.
- CI 미검증: Actions 실행/체크 0건. **사용자 요청으로 정상화/원인 조사를 차후 연기**한다.
- 이 문서 및 Manifest 동기화에 따른 새 소스 커밋은 이전 HEAD의 DGX 시험을
  자동 승계하지 않는다. 실 신규 build/activate/remove/rollback/240K 검증도 미실행.

## 소스 상태 무결성 검사 — feature/main 공통

```bash
scripts/verify-source-state.sh --strict
scripts/verify-source-state.sh --strict --json
scripts/manifest.sh validate
```

`source-state-manifest.json`은 소스 파일 blob SHA/mode/branch/origin을 검증하며,
**실 DGX 테스트 또는 Docker 동작을 실행하지 않습니다.**
변경/누락/신규 Git 추적 파일이나 잘못된 Git origin을 fail로 판정하는
`tests/test_source_state_release_branches.py` 회귀 시험은 최신 DGX 전체
172/172에 포함되어 PASS했습니다. 이후 docs-only 커밋은 별도 재검증이 필요합니다.
[전체 순서](VERIFY-FROM-GIT-PULL.md).

## 정적 검사 (사용자 로그에 문법/공개물 진단 출력 없음)

- `python3 -m py_compile scripts/wizard/*.py`
- `bash -n scripts/{install,uninstall,status,adopt-legacy,manifest,doctor,prepare,activate,stop}.sh`
- `python3 tools/audit_publication.py`
- `PYTHONPATH=src:. python3 -m unittest discover -s tests -v`
- 변경된 README/상위 README 간 문서 계약 및 Git diff 확인

## 오프라인 모의 시험 코드 및 확인된 38/38 PASS (최신 검증 HEAD)

- `tests/test_wizard_monitor.py`: 이전 snapshot 비교, identity/Git/Health 변화,
  누락된 snapshot, 간결한 상태/JSON/strict 상태 코드 및 storage 경고.
- `tests/test_wizard_safety.py`: 임시 레거시 state, 가짜 Docker inspect/Git,
  정확한 ID/마운트/포트 증거, 읽기 전용 등록, 보호 대상 삭제 및
  동일 이름 컨테이너 활성화 거부.
- `PYTHONPATH=src:. python3 -m unittest discover -s tests -p 'test_wizard_*.py' -v`
  실행 시 실제 Docker·HTTP·HF를 호출하지 않습니다.
- `.github/workflows/test.yml`에 이 모의 테스트 단계를 추가합니다.
- **실 DGX 신규 설치·제거 테스트는 별도**이며 모의 시험 성공과 동일시하지 않습니다.

## 신규 레거시 재검증 시험 항목 (기존 모의 시험 포함)

- 설치 당시 PIN이 Git에 남아 있고 origin/HEAD가 개인 Fork로 변경되었지만,
  레거시 `paths`, image/container IDs, labels, port 및 mount가 일치하는 경우
  **`identity_verified=true`, checkout drift 경고, `read_only=true`**.
- image ID 또는 container ID 불일치: `identity_verified=false`.
- 모델 cache 또는 recipe-view bind mount 출처 불일치: 실패, 자동 경로 변경 없음.
- `0.0.0.0:8000`과 다른 publish HostIp/HostPort: 실패.
- `/health` 또는 `/v1/models` API 실패: status에 건강 상태만 별도 보고,
  일치하는 Docker 소유권 증거를 강제로 무효화하지 않음.
- `adopt-legacy`는 완전 일치와 64자리 ID 확인 시 새 local receipt에
  **읽기 전용 observation만 기록**하며 Docker stop/rm/change 0회.
- 신규 Wizard 컨테이너는 레거시와 이름을 분리하며, 동일한 신규 이름 충돌은 거부한다. 레거시 running 중 단일 GB10에서 새 GPU 활성화도 거부한다.
- 개발자가 사용자 DGX의 실제 Container ID를 source Manifest나 Git에 커밋하지 않음.

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
| Collision | Wizard 전용 이름 점유 또는 레거시 running에 따른 GPU 동시 실행 | 기존 서비스 그대로, 시작 거부 |
| Reuse | image tag와 recorded ID 일치 | 불필요한 rebuild 0 |
| Build | image tag 사전 점유/recorded ID 불일치 | 이미지 덮어쓰기 거부 |
| Runtime | host port occupied/invalid target | 시작 거부 |
| Ownership | 삭제 대상 이름 일치, image ID/label 불일치 | stop/rm 금지 |
| Image | 타 컨테이너가 이미지 ID 참조 | image rm 금지 |
| Readiness | health PASS, models 누락 또는 chat 실패 | READY 불가 |
| Secrets | stderr/stdout/receipt | 토큰 노출 없음 |

## DGX Spark 실기기 신규 배포·제거 시험 예정

- 사전 snapshot: legacy state, Docker inspect IDs, port 8000 운영 여부 기록.
- 읽기 전용 조회/adoption이 기존 API, OpenWebUI, Ollama, 네트워크 설정과 모델 파일을 변경하지 않는지 확인.
- 신규 이미지 빌드, patch 검증, 모델 audit(31/31), cache 재사용, 실패 시 데이터 보존 확인.
- 레거시 container name 충돌 보호 확인; 기존 컨테이너 삭제/중지 없음.
- 신규 독립 target의 기동 및 `/health`, `/v1/models`, 실제 chat API 확인(충돌 해결 전 같은 target으로 무리하게 실행 금지).
- 신규 wizard receipt가 있는 환경에서 정확한 stop/rm/image rm의 소유권 검증, 파일 보존 확인.
- 240K long-context 및 MTP 성능/동시성/장시간 안정성은 별도 성능 QA로 분리.

## 합격 기준

기존 서비스·가중치 파일 보존이 최우선입니다. **소스 코드의 PR 머지**는 변경된 소스 Manifest 및 단위/모의 테스트를 다시 검증한 후 별도로 판단할 수 있지만, 이를 **신규 배포·제거 기능의 실기기 운영 검증 완료**로 표시해서는 안 됩니다. 실제 운영 승인 전에는 신규 설치·제거/rollback 실기기 시험이 필요합니다.
