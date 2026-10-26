# DGX Spark: 스냅샷 비교·상태 표시·읽기 전용 Health

> **현재 구현은 기존 설치를 변경하지 않고 조회합니다.**
> 사용자 제공 실기기 출력(2026-10-26)에서 6/6 신원 검사,
> HTTP health/models PASS, 읽기 전용 legacy adoption 성공을 확인했습니다.
> 본 기능의 **모의 테스트 결과와 DGX 실기기 재확인 결과는 구분**해야 합니다.

## 기존 checkout에서 업데이트

```bash
cd "$HOME/Workspace/llm/yslab-qwen38-bf16ple-dgx-spark"
git status --short
git pull --ff-only origin feature/install-uninstall-wizard-20261026
scripts/verify-source-state.sh --strict
scripts/manifest.sh validate
```

기존에 **같은 checkout에 설치된** 레거시 컨테이너, 모델 cache,
`recipe-views`, 이미지, API 포트 8000을 변경하지 않습니다.

## 새 상태/비교 명령

```bash
scripts/status.sh                    # 요약 6줄 내외
scripts/status.sh --json             # 기존 상세 JSON 및 비교 필드
scripts/compare-state.sh             # 등록 당시 vs 현재, 변화한 필드 표시
scripts/compare-state.sh --json      # 전체 차이 데이터
scripts/health.sh                    # Health: 컨테이너·HTTP·모델·용량·메모리
scripts/health.sh --json             # 기계 처리용 상세 JSON
scripts/doctor.sh                    # Manifest 검사 + 상태 변화 + Health
scripts/status.sh --health --compare --strict
```

마지막 `--strict`는 설치 정체성 변경, 현재 조회 실패, 신원 검증 실패,
API/Health FAIL 또는 UNKNOWN에서 비영(1)을 반환합니다.
단순 Git HEAD 변경과 저장 공간 LOW_SPACE 경고는 관찰 가능하게 표시하되
그 자체로 기존 컨테이너의 소유권이 변경된 것으로 취급하지 않습니다.

## 등록 당시와 현재 비교 결과

`scripts/adopt-legacy.sh`가 사용자 지정 전체 Docker ID로 등록한 관찰
snapshot은 `~/.local/state/qwen38-flash-dgx/deployment-state.json`의
`legacy_observation`에 보존됩니다. 비교 명령은 이 파일을 **읽기만** 합니다.

| 결과 | 의미 |
| --- | --- |
| `UNCHANGED` | 비교 대상으로 정의된 신원·Health·Git 필드가 일치 |
| `CHANGED` | Docker ID, cache 경로, mount source, checks 또는 관리 권한 등 신원 변경 |
| `HEALTH_CHANGED` | 컨테이너 상태나 API Health/모델 목록 변화 (신원 변화보다 낮은 우선순위) |
| `GIT_CHANGED` | 현재 checkout HEAD/origin/cleanliness만 달라짐 (관찰 정보) |
| `UNREGISTERED` | 이전 관찰 snapshot 없음; 자동 저장/등록하지 않음 |
| `UNKNOWN` | 이전 기록이 손상되거나 필드/현재 관찰을 확인할 수 없음 |

결과에는 `counts.identity/health/git`과 `differences[]` 목록이 포함되며
`--compare`는 달라진 필드만 출력합니다. 이전 snapshot에 없던 필드를
임의로 변경(`CHANGED`)이라고 간주하지 않고 `unknown[]`에 기록합니다.
이전 snapshot을 자동으로 덮어쓰지 않으므로 Git HEAD 변경 이력도 남습니다.

**중요:** Snapshot이 일치한다는 사실만으로 Docker 삭제나
기존 레거시 자산 takeover 권한을 부여하지 않습니다.
`read_only=true` / `management_authority=OBSERVE_ONLY`를 유지합니다.

## 읽기 전용 Health 검사 범위

| 항목 | 정보 출처 | 결과 |
| --- | --- | --- |
| 이미지/컨테이너 ID·label·mount·port | Docker inspect와 legacy receipt | PASS / FAIL |
| 현재 컨테이너 running 상태 | Docker inspect | PASS / FAIL |
| API HTTP health | `GET 127.0.0.1:8000/health` | PASS / UNAVAILABLE |
| 모델 존재 | `GET /v1/models`, expected alias 비교 | PASS / MODEL_ID_NOT_FOUND / UNAVAILABLE |
| HF cache 파일시스템 여유 | `shutil.disk_usage` | PASS / LOW_SPACE / UNKNOWN |
| recipe-views 여유 공간 | `shutil.disk_usage` | PASS / LOW_SPACE / UNKNOWN |
| MemAvailable | `/proc/meminfo` | OBSERVED / UNKNOWN |

기본 disk 경고 임계값은 100 GiB입니다. **기존 서버가 이미 실행 중일 때
100 GiB 미만이라는 이유만으로 API가 고장 났다고 볼 수 없습니다.**
파일시스템 여유가 적으면 `WARN`을 표시할 뿐 자동 정리하지 않습니다.
상태 조회는 실 모델 inference, Docker build/rm/stop, 모델 다운로드, GPU
benchmark, 이미지/모델 무결성 전수감사를 수행하지 않습니다.

## Test: 실제 Docker를 사용하지 않는 모의 환경

```bash
# 모의 Docker/Git, tempfile 내 레거시 state, HTTP 응답 모킹
scripts/run-mock-tests.sh    # offline fake Docker/Git/HTTP tests
PYTHONPATH=src:. python3 -m unittest discover -s tests -p 'test_wizard_*.py' -v

# 저장소 전체 기존 테스트도 실행
PYTHONPATH=src:. python3 -m unittest discover -s tests -v

# 정적 구문 검사 및 공개물 보안 감사
bash -n scripts/*.sh scripts/qwen38-dgx-spark
python3 tools/audit_publication.py
```

테스트는 `tests/test_wizard_monitor.py`와 `tests/test_wizard_safety.py`에
정의했으며, 모든 파괴적 action은 `unittest.mock.patch`로 대체하고
실제 HTTP/gated HF/download/Docker 엔진을 호출하지 않습니다.
사용자 DGX의 실제 모델 성능이나 설치·제거 성공을 검증했다고 표현하지 마세요.

## 안전상 제약

- 기존 YSLAB과 신규 wizard는 동일 모델 target일 때 Docker **컨테이너 이름이 중복**됩니다.
  새 설치 활성화를 강행하지 마세요.
- `scripts/uninstall.sh`는 **wizard가 신규 생성해서 receipt에 기록한** 컨테이너만
  소유권을 검증한 뒤 삭제하도록 설계되었습니다.
  legacy adoption은 삭제 소유권을 넘기지 않습니다.
- 로컬 wizard receipt는 Git에 커밋하지 않고, 검사만으로 재작성하지 않습니다.
- `0.0.0.0:8000` 직접 노출 API는 방화벽 접근 제한을 계속 유지해야 합니다.

관련 내용: [기존 설치 증거](LEGACY-OBSERVATION-20261026.md) ·
[기존 설치 보호](LEGACY-INSTALLATION.md) ·
[시험 계획](TEST-PLAN.md) ·
[Git Pull부터 검증까지](VERIFY-FROM-GIT-PULL.md).
