# Git Pull부터 상태 Manifest 검증까지 (DGX Spark / Bash)

> 대상 브랜치: `feature/install-uninstall-wizard-20261026`  
> **Git 소스 검증 ≠ 설치·Docker·GPU·모델 추론 검증.**  
> 모든 명령은 새 **kjlee-inlct Fork checkout**에서 실행합니다. 기존
> `$HOME/Workspace/llm/yslab-qwen38-bf16ple-dgx-spark` YSLAB checkout에서는
> `git switch` 또는 `git pull` 하지 마세요.
>
> 여기에는 **실행 가능한 검증 절차**를 제공하지만, 이 문서 작성/커밋 과정에서
> DGX 실기기 테스트, Docker 작업 및 위자드 실행은 **실시하지 않았습니다**.

## 0. 작업 위치 확인 — 기존 설치 보호

터미널에서 **이미 존재하는 Fork checkout**으로 이동하세요. 폴더가 없다면
기존 YSLAB repo를 개조하지 말고 Fork를 별도 경로로 새로 clone하십시오.

```bash
cd "/절대경로/본인_Fork_체크아웃"  # 실제 kjlee-inlct Fork 경로로 변경
pwd
git remote -v
git status --short
```

origin이 사용자 Fork인지 확인합니다. 기존 작업물/변경 사항이 있다면 우선
백업·정리하십시오. `git reset --hard`, `git clean -fd`는 실행하지 않습니다.

## 1. Git fetch → 브랜치 이동 → git pull (fast-forward only)

```bash
set -Eeuo pipefail
BRANCH="feature/install-uninstall-wizard-20261026"
EXPECTED="kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark"

# 반드시 origin이 사용자 Fork인지 검증; YSLAB 기존 checkout이면 즉시 중단
ORIGIN="$(git remote get-url origin)"
case "$ORIGIN" in
  "https://github.com/$EXPECTED"|"https://github.com/$EXPECTED.git"|"git@github.com:$EXPECTED"|"git@github.com:$EXPECTED.git"|"ssh://git@github.com/$EXPECTED"|"ssh://git@github.com/$EXPECTED.git")
    echo "OK: personal fork origin" ;;
  *) echo "STOP: origin은 사용자 Fork가 아닙니다: $ORIGIN" >&2; exit 1 ;;
esac

# 추적 파일에 로컬 수정이 있으면 중단; legacy cache를 삭제하지 않음
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "STOP: tracked files have local changes; resolve them manually" >&2
  exit 1
fi

git fetch origin "$BRANCH"
if git show-ref --quiet --verify "refs/heads/$BRANCH"; then
  git switch "$BRANCH"
else
  git switch --track "origin/$BRANCH"
fi

# 이미 이 브랜치에 있다면 아래가 실제 git pull 단계
git pull --ff-only origin "$BRANCH"
git status --short
git branch --show-current
git rev-parse HEAD
```

브랜치가 충돌하거나 fast-forward가 불가능하다면 **중단하고 diff를 먼저 검토**합니다.
자동 merge, rebase, reset, 강제 checkout을 하지 않습니다. `git status --short`에
새로 만들어진 모델 cache 또는 예전 로컬 파일이 보이면 원인을 확인하되 무조건 삭제하지 않습니다.

## 2. 소스 상태 Manifest 무결성 검증

```bash
# git에 저장된 전체 소스 file-mode / blob SHA와 실제 파일 내용을 비교
scripts/verify-source-state.sh --strict

# 동일 검사 결과를 JSON으로 표시 (호스트 모델 상태를 조회하지 않음)
scripts/verify-source-state.sh --strict --json

# 두 선언형 JSON Manifest의 형식과 구조 검사
python3 -m json.tool scripts/source-state-manifest.json >/dev/null
python3 -m json.tool scripts/deployment-manifest.json >/dev/null
python3 -m json.tool compatibility.json >/dev/null
scripts/manifest.sh validate
```

`PASS_SOURCE_ONLY`는 Manifest에 기록된 HEAD Git blob, 작업 트리 내용,
실행 권한, Fork origin, 브랜치가 일치함을 뜻합니다. **CI 통과, 보안 검증,
설치/제거 동작, 실제 모델 상태를 보증하지 않습니다.**

`source-state-manifest.json`은 저장소 파일들을 Git blob SHA로 모두 기록하며,
자기 자신의 해시는 Git HEAD의 tracked object와 별도 대조합니다.
자기 참조 가능한 고정 SHA를 억지로 만들어 넣지 않습니다.
해당 Manifest의 SHA는 HEAD 커밋에 포함되므로 `git rev-parse HEAD`로
최종 스냅샷을 식별할 수 있습니다.

## 3. Bash 및 Python 문법 정적 검사 (실행/설치/테스트 아님)

```bash
# Bash 코드를 실행하지 않고 구문만 점검
bash -n scripts/*.sh scripts/qwen38-dgx-spark

# Python 문법 검사 — bytecode/pycache를 작성하지 않음
python3 - <<'PY'
import ast
from pathlib import Path
paths = sorted(Path("scripts/wizard").glob("*.py"))
paths += [Path("scripts/verify-source-state.py")]
for path in paths:
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    print("SYNTAX OK:", path)
PY
```

이 단계도 코드의 런타임 안정성이나 설치 성공을 확인하지 않습니다.
실제 mock 테스트, 단위 테스트, GPU 시험은 `scripts/TEST-PLAN.md`대로 별도 시행합니다.

## 4. 기존 YSLAB 설치 읽기 전용 조회

현재 작업 경로가 처음 설치한 YSLAB 디렉터리여도 origin이 개인 Fork로
바뀌어 있을 수 있습니다. 2026-10-26 운영자 로그에서 이 상태가 확인되었습니다.
이 경우 ID/mount/port가 일치하면
`legacy.identity_verified=true`이고 `checkout_warnings`에는
Git origin/HEAD 변경이 별도 보고될 수 있습니다.

기존 컨테이너를 살리려고 과거 PIN으로 checkout을 강제 되돌리지 마세요.
이전 PIN 객체가 Git에 남아 있는지 여부는 읽기 전용 검사 항목입니다.



```bash
# 선언형 정책 + 현재 호스트 관찰 정보를 조회
scripts/status.sh
scripts/doctor.sh

# 기존 설치의 Docker ID/label/status 수동 점검 (값을 변경하지 않음)
docker container inspect qwen38-flash-orca-uncensored-bf16-mtp \
  --format 'ID={{.Id}} state={{.State.Status}} image={{.Image}} recipe={{index .Config.Labels "ai.yslab.recipe"}} target={{index .Config.Labels "ai.yslab.target"}}'

# 참조 설치의 이미지 태그가 존재하는지 조회
docker image inspect yslab-qwen38-bf16ple:9492b78c \
  --format 'legacy image={{.Id}}'

# 포트 8000이 현재 정상 응답하는 경우에만 건강 응답 확인
curl -fsS --max-time 5 http://127.0.0.1:8000/health
curl -fsS --max-time 10 http://127.0.0.1:8000/v1/models | python3 -m json.tool
```

포트, 컨테이너, 이미지가 현재 실행 중이라는 정보는 Git 소스만으로
확인할 수 없습니다. `legacy.verified`가 false라면 기존 state receipt,
ID, Git HEAD 또는 포트가 참조 기준과 다를 수 있습니다. **자동으로 고치지 마세요.**
기존 API가 응답하지 않는 경우 `curl`은 실패하지만, 소스 Manifest 검증
실패나 다른 서비스 장애를 의미하는 것은 아닙니다.

**주의:** 새 위자드의 `status`는 기존 설치의 레거시 기록을 읽기만 합니다.
기존 설치를 신규 관리 상태로 *등록*하는 `adopt-legacy.sh`는 로컬
wizard state에 기록하므로 위의 읽기 전용 단계에 포함하지 않았습니다.

## 5. 등록 기록 비교와 읽기 전용 Health 확인

```bash
scripts/status.sh                 # 기본은 요약; 상세 JSON은 --json
scripts/compare-state.sh          # snapshot vs current
scripts/health.sh                 # 컨테이너·API·모델·저장공간·메모리
scripts/doctor.sh                 # 선언형 Manifest + 비교 + Health
```

기존 문서의 status 예시 JSON 필드는 이제 `scripts/status.sh --json`에서
그대로 확인할 수 있습니다.
[출력 상태 및 경고 해석](STATUS-COMPARE-AND-HEALTH.md).

## 6. 선택적 안전 계획 확인 (위자드 호출; Docker 변경 없음)

```bash
scripts/install.sh --target orca-uncensored-bf16-mtp --mtp 2 --dry-run
```

`--dry-run`은 코드를 실제 실행하므로 **정적 검증만 원하는 경우 생략**합니다.
기존 YSLAB의 이미 실행 중인 컨테이너를 변경하지 않아야 합니다.

## 6. 확인해야 할 최종 상태

| 항목 | 판단 기준 |
| --- | --- |
| 원격 브랜치 | `feature/install-uninstall-wizard-20261026` |
| Git 파일 검증 | `PASS_SOURCE_ONLY`; missing/changed files 0 |
| 기준 checkpoint Manifest | `compatibility.json` 형식 및 target 4종 |
| 신규 배포 정책 | `scripts/deployment-manifest.json`, port 18300 |
| 기존 배포 | legacy state + 실 Docker 상태 별도 확인, port 8000 |
| 위자드 설치/제거 | **NOT TESTED**, 이 절차에서 실행하지 않음 |
| 삭제/교체 | **0회**, `main` 및 기존 YSLAB source 변경 없음 |

## 7. 문제 발생 시 안전 대응

- `wrong branch`: 올바른 Fork origin/브랜치인지 확인 후 `git fetch`/
  `git switch`; 변경사항이 있으면 안전하게 백업 및 검토.
- `working-tree blob differs`: 로컬 변경, 파일 손상 또는 line ending 변환
  가능. 차이를 확인하고 무단 reset 금지.
- `unmanifested tracked path`: 누군가 새 파일을 커밋했으나 스냅샷
  Manifest가 갱신되지 않음. Manifest·문서를 함께 검토 후 재생성.
- `origin is not ... fork`: 즉시 중단. **기존 YSLAB origin을 변경하지 않음**.
- `legacy.verified=false`: 레거시 state / Docker ID 증거를 우선 확인.
  legacy 서비스 정지·삭제 금지.
- `Docker command unavailable`: Git 소스 검증은 독립적으로 판정;
  실 호스트 관찰은 별도로 실패 표시.
