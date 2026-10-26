# 2026-10-26 DGX Spark 검증 증거 및 PR 기록 (시점별)

> **출처:** 사용자가 전달한 DGX Spark 터미널 로그. GPT/GitHub 연결은
> DGX에 원격 로그인하여 이 명령들을 직접 실행하지 않았습니다.
> 아래 수치는 **당시 커밋** `3b00eafc44ebf5fa6e16134f30fb4be2679c0978`
> 의 운영자 실행 결과이며, 이후 수정된 커밋에 대한 재실행 결과가 아닙니다.


## 최신 DGX main 검증 — 2026-10-26 (PR #3 병합 이후)

> **출처:** 사용자 제공 `scripts/verify-main-readonly.sh` 전체 281줄 실행 로그.
> 실제 DGX를 사용자가 조작했으며 ChatGPT/GitHub는 서버에서 명령을 직접 실행하지 않았다.
> 이 증거는 `main` **`66051cdcd4b2c5766de55421579867c195fe4084`** 한 커밋에 한정된다.
> 그 뒤 문서 커밋 및 PR merge SHA에는 자동 승계하지 않는다.

| 검증 항목 | 실제 DGX 실행 결과 |
| --- | --- |
| HEAD/브랜치 | `main`, `66051cdcd4b2c5766de55421579867c195fe4084`, local `origin/main` 일치 |
| Source state | `scripts/verify-source-state.sh --strict` → **PASS_SOURCE_ONLY: 114 tracked file(s)** |
| Deployment policy | **PASS**, 4 target(s) |
| Wizard offline mock | `scripts/run-mock-tests.sh` → **38/38 PASS**, 실패 0 |
| Full unit | `PYTHONPATH=src:. python3 -m unittest discover -s tests -v` → **172/172 PASS**, 실패 0 |
| Static/publish | wrapper의 Bash syntax 및 `tools/audit_publication.py` 단계 통과; 실행 전체가 마지막 PASS까지 종료 |
| Legacy identity | **PASS**, 불일치 0, 컨테이너 running |
| Legacy API | Health PASS, 모델 목록 PASS |
| Saved vs current | `GIT_CHANGED`: 설치정체성 0, 서비스 0, Git HEAD 1 |
| Git drift | recorded `3522190192da605c17709bede32a0df98d0ed406` → current `66051cdcd4b2c5766de55421579867c195fe4084`; 2건 informational warning |
| Read-only Health | **PASS**, cache/view 여유 공간 각 539.74 GiB |
| MemAvailable | 약 14.24~14.30 GiB (관찰 시점별 변동) |
| Legacy authority | `OBSERVE_ONLY`, 신규 설치·제거 **미실행** |
| Wrapper terminal result | `PASS: local source/tests/observations; real new deployment NOT_TESTED` |
| GitHub CI | GitHub Actions workflow runs=0, commit check runs=0 — **CI_NOT_VERIFIED / 사용자 결정으로 보류** |

### 판단

1. **P0-3 완료:** DGX 실호스트의 `main` 전환 및 후속 읽기 전용 검증은 위
   SHA에서 성공. 소스 manifest, 정책, offline mock, unit, 상태 조회 증거가 있다.
2. **P0-2 코드/Mock 단계 완료:** 신규 Wizard 별도 이름, 전용 owner marker, strict receipt,
   레거시 running일 때 GPU 기동 차단 회귀시험이 위 38/38·172/172에 포함됨.
   실제 새 컨테이너 start/stop/remove나 장시간 inference 시험은 수행하지 않음.
3. **P0-1 의도적 연기:** Actions run/check 0건 원인 조사 및 CI 정상화는
   사용자 요청에 따라 **별도 차후 과제**, 이번 docs-only PR 범위에 포함하지 않음.
4. **기존 서비스 보호:** ID/상태/Health 변경 0건, `GIT_CHANGED`는 Git checkout drift다.
   저장공간은 양호하지만 메모리 약 14 GiB로 **단일 GB10 추가 GPU 배포 금지**를 유지.
5. 이번 결과 기록은 **문서만 수정**하고 PR/merge한다. 새로운 merge SHA에 대한
   DGX source strict/full tests/Health 재실행 증거는 아직 별도로 필요하다.

### 누락된 실기기 시험

신규 위자드 Docker build, checkpoint prepare/audit, cache 재사용,
신규 activate 및 chat completions, 오너 자산 stop/remove/image rm, 복구·rollback,
240K/MTP 성능/동시성, 모델 파일 무결성의 신규 전체 검사는 **NOT_TESTED**.
이전 기능 SHA `3b00eaf...`의 156/156 및 `25949fd...`의 163/163은
**과거 증거로만 유지**한다.

---

## 과거 실행한 명령과 확인한 결과

| 대상 | 명령 | 사용자 제공 로그의 결과 |
| --- | --- | --- |
| Git source inventory | `scripts/verify-source-state.sh --strict` | `PASS_SOURCE_ONLY: 109 tracked file(s)` |
| Deployment Manifest | `scripts/manifest.sh validate` | `manifest OK`, model target 4종 |
| Wizard mock unit tests | `scripts/run-mock-tests.sh` | **36 tests, OK** |
| Full repository tests | `PYTHONPATH=src:. python3 -m unittest discover -s tests -v` | **156 tests, OK** |
| Bash syntax | `bash -n scripts/*.sh scripts/qwen38-dgx-spark` | 출력된 구문 오류 없음 |
| Publication audit | `python3 tools/audit_publication.py` | 출력된 진단 메시지 없음; 명시적인 exit-code 캡처는 없음 |
| Legacy identity | `scripts/status.sh` | **6/6 PASS**, Docker 컨테이너 `running` |
| Legacy API | `GET /health` 및 `/v1/models` | **PASS/PASS** |
| Saved-vs-live comparison | `scripts/compare-state.sh` | `GIT_CHANGED`, identity 0 / health 0 / Git 1 |
| Read-only Health | `scripts/health.sh`, `scripts/doctor.sh` | **Health PASS** |
| Storage | 호스트 disk probe | cache/view 각 **539.75 GiB free** 보고 |
| Memory | MemAvailable | 약 **14.3 GiB** (시점별 변동) |
| Legacy rights | wizard status | `OBSERVE_ONLY`, 기존 컨테이너 교체 없음 |

**모의 시험은 실제 Docker를 생성/정지/삭제하지 않고 Mock 대상으로 로직을
검증합니다.** 기존 레거시 이미지/컨테이너/모델은 계속 유지되었습니다.
실제 신규 위자드 이미지 빌드, 모델 재다운로드, 신규 설치·제거·rollback,
실제 Chat Completion inference는 이 일괄 검증의 대상이 **아닙니다**.

## 이 커밋에서 새로 작업한 내용 (별도 재검증 필요)

- 소스 검증 `--strict`의 허용 브랜치를
  `feature/install-uninstall-wizard-20261026`과 `main`으로 제한했습니다.
- `tests/test_source_state_release_branches.py`: 임시 Git repository로
  feature/main 허용, 비허용 브랜치 거부, SHA 다른 커밋에서도 동일 tree 허용,
  tracked blob 변조 검출, manifest allowlist 오염 차단을 시험하도록 추가했습니다.
- GitHub 파일 해시/메타데이터 확인과 **이 테스트의 실 실행**은 별개의 단계입니다.
  추가한 테스트는 새 HEAD에서 다시 수행해야 합니다. 이전
  **156/156** 결과를 새 커밋의 테스트 성공으로 자동 승계하지 않습니다.

## GitHub PR 머지 관련 무결성 계약

- 소스 Manifest의 `branch`는 스냅샷 **생성 출처**(기능 브랜치)입니다.
- `allowed_branches`는 `--strict` 허용 브랜치 2개만 고정적으로 선언합니다.
  검증기 코드도 이 정확한 allowlist를 확인합니다.
- Git merge commit, fast-forward merge, squash merge에서 **전체 tracked file
  blob/mode와 manifest blob이 동일하면** 새 커밋 SHA와 무관하게 검증 가능합니다.
- 머지 중 README/워크플로/코드/추적 파일을 바꾸거나 `main`의 tree가
  추가로 변경되면 Manifest를 같은 변경에 맞춰 재생성해야 합니다.
  검사 실패를 무시하거나 `--strict`만 꺼서 해결하지 않습니다.
- 체크아웃은 `main`/기능 브랜치 중 하나이며 origin은 반드시 개인 Fork여야 합니다.
  기존 YSLAB 자산의 소유권/삭제 권한은 바뀌지 않습니다.

## 과거 재검증 예시 (기능 브랜치 당시 명령, 최신 권장 경로 아님)

```bash
git status --short
git pull --ff-only origin feature/install-uninstall-wizard-20261026
scripts/verify-source-state.sh --strict
scripts/manifest.sh validate
scripts/run-mock-tests.sh
PYTHONPATH=src:. python3 -m unittest discover -s tests -v
bash -n scripts/*.sh scripts/qwen38-dgx-spark
python3 tools/audit_publication.py
scripts/status.sh
scripts/doctor.sh
```

실제 `main` 병합 전에는 PR diff/상태 검사, 이 검증기 테스트의 실제 실행과
기존 설치 Health의 변화가 없는지 재확인하세요. **PR 생성·머지는 별도 작업**입니다.

## 신규 `main` 검증 표준 명령

개인 Fork origin, 깨끗한 작업 트리, 최신 `main` 및 local `origin/main`
일치를 확인한 후 `scripts/verify-main-readonly.sh`를 사용한다.
기존 컨테이너 및 모델을 변경하지 않으며, 새 커밋이 생길 때마다 최신
소스 SHA/Health를 재확인한다. CI는 사용자 재개 요청 전 보류한다.
