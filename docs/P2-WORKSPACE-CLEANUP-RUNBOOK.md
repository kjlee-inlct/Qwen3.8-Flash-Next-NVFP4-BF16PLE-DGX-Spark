# DGX Spark Workspace/llm 디렉터리 정리 — Read-only inventory (2026-11-02)

**원칙:** 신규 Phase 별 `git clone`/폴더 증식을 중단하고, 계속 개발할 P2/P3 작업 경로는 `~/Workspace/llm/blazux-phase6-gates`로 유지. 기존 운영 관련 `yslab-qwen38-bf16ple-dgx-spark`, 모델/캐시 가능성이 있는 `qwen38-orca-uncensored`, 실측 근거 `bench-results-staging`은 삭제·이동 금지. 기존 원본 컨테이너, Docker 볼륨/바인드 마운트, 모델/weights/HF 캐시 및 pinned Stage 변경 금지.

## DGX에서 수행

```bash
cd ~/Workspace/llm/blazux-phase6-gates
git remote get-url origin
git branch --show-current
git status --short
# origin이 본인 kjlee-inlct Fork, branch가 feature/blazux-phase6-runtime-gates이고
# 추적 파일 변경이 없는 것을 확인한 후에만:
git pull --ff-only origin feature/blazux-phase6-runtime-gates
bash scripts/p2-workspace-inventory.sh
# 구조화된 결과가 필요하다면:
bash scripts/p2-workspace-inventory.sh --json
```

명령은 **폴더의 직접 자식 디렉터리만 목록화**하며 Git 메타데이터, tracked/untracked 변경 유무, 다른 Git worktree 등록 여부, 현재 및 중지된 Docker 컨테이너의 bind source와 겹침 여부를 읽기 전용으로 점검한다. `docker container ls -aq`와 `docker container inspect`만 조회하고 `git status`에는 `GIT_OPTIONAL_LOCKS=0`를 설정한다. 파일 크기 계산, 전체 모델 파일 순회, GPU 추론, Docker 실행·중단, HTTP 호출, 삭제·이동·압축·백업·새 폴더 생성은 하지 않는다. 출력에 Git 원격의 비밀정보/개인 토큰, Docker mount 원경로 및 model contents는 포함하지 않는다.

## 분류 해석

- `RETAIN_PROTECTED`: 현 P2 체크아웃, 운영 원본/증거/모델 관련 경로, 또는 Docker bind source가 내부/상위에 있어 겹치는 경로. 이동·삭제 금지.
- `HOLD_REFERENCE`: 별도 벤치 프로젝트, 심볼릭 링크, linked worktree, 로컬 tracked/untracked 변경 또는 알려지지 않은 의존성. 이동·삭제 금지.
- `REVIEW_FOR_ARCHIVE`: Phase 1~5로 보이는 과거 체크아웃 중 Git 변경과 Docker bind 겹침이 검출되지 않은 후보. **삭제/이동해도 안전하다는 증거가 아니다.** 해당 checkout에서 참조 중인 스크립트·백업·절대 경로·작업 스케줄러·프로세스·외부 마운트·Git worktree 등록을 별도로 확인한 뒤 보관 계획 승인 필요. Docker 조회 실패 시 `DOCKER_MOUNTS_UNVERIFIED` 표시.

아직 이전 작업 트리, 벤치 결과, 모델 파일 등을 하나로 합치거나 이동하지 않는다. 실제 결과를 확인한 뒤 보존 대상은 그대로 두고 나머지만 `archive`/`historical` 같은 목적별 경로로 **별도 승인된 이동 스크립트**를 작성한다. `rm -rf`, `git clean -fd`, `git reset --hard`, 운영 컨테이너 변경은 이 절차에서 사용하지 않는다.

## 2026-11-02 기존 P2 실행 영수증

사용자 DGX 로그에서 P2 개발 통합 `3e4492c73ce95f8129e99b1f21f4a67252e8891f`로 fast-forward 완료, `scripts/p2-numeric-dgx.sh --check`/`--stage` 두 모드 모두 P2 CPU unittest **24/24 PASS**. 설치된 Sampler 원본 SHA256 `f95805b2c6d06218c724826aa5f881a606e8d0a534a566aee7c85948520dd216` 확인, 패치 SHA256 `a62b7cd7f7eb637fdee7d8dd1e51b1bc47c3931bb1174f4f22280db28ccaead4`, 개인 stage `/tmp/p2-numeric-witness-_w30fuax`. 원본 컨테이너 ID/이미지·시작 시각 불변 검사 성공. **이미지 build, GPU, API 미실행**. Numeric root cause OPEN, strict tolerance `1e-4` 출시 차단 불변. 이후 repo HEAD가 달라져도 이 영수증의 tested HEAD는 바뀌지 않는다.
