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


## 2026-11-02 실제 DGX inventory 실측 및 추가 참조 확인

- **DGX-tested source HEAD:** `384eaa12e30b1dfd4605050fc11be3f7f79540e4`. `git pull --ff-only` 성공, `bash scripts/p2-workspace-inventory.sh` 출력 `WORKSPACE_INVENTORY_READ_ONLY` / `docker=AVAILABLE` / `NO_FILES_MOVED_OR_DELETED`.
- **15개 폴더:** 보호 5개(bench-results-staging, blazux-phase6-gates, open-webui, qwen38-orca-uncensored, yslab-qwen38-bf16ple-dgx-spark), 추가 확인 5개(llama-benchy, llama-benchy-runner, spark-stack, spark-vllm-docker, stack), 잠정 보관 후보 5개(blazux-phase1~phase5). `open-webui` Docker bind overlap 확인; spark-stack/spark-vllm-docker/stack에는 로컬 변경 또는 미추적 파일 존재.
- 기존 분류기의 PhaseN 이름 기반 보관 후보 판정은 Git 상태 UNKNOWN/비 Git 폴더에도 부정확하게 적용될 수 있으므로, **Git 확정 상태 없이는 HOLD_REFERENCE**로 판정하도록 보강.
- 신규 `--references` 옵션은 활성 checkout과 일부 별도 프로젝트의 Python/Shell/설정/문서 소스에서 Phase1~5 폴더 이름의 **경로 참조 여부만** 제한된 크기/파일 수 내에서 읽기 전용으로 검사. 실제 파일 내용·환경 비밀은 출력하지 않으며 문서상 언급과 스크립트 참조를 구분한다.

```bash
cd ~/Workspace/llm/blazux-phase6-gates
git pull --ff-only origin feature/blazux-phase6-runtime-gates
bash scripts/p2-workspace-inventory.sh --references
# 선택적 구조화 출력: bash scripts/p2-workspace-inventory.sh --references --json
```

`REFERENCE_AUDIT_READ_ONLY` 표시와 대상별 `references=N`을 확인한다. `COMPLETE_SCOPED_SCAN`은 *스코프 내의 정적 텍스트 검색* 완료만 뜻한다. 프로세스 cwd/열린 파일, 시스템 서비스, 외부 절대 경로, 실제 활성 런처, 무시된 캐시/대용량 파일까지 증명하지 않으므로 **참조 0건도 이동·삭제 허가가 아니다.** 실제 archive 작업은 사용자 별도 승인 및 복구계획 후 수행한다.

## 2026-11-02 DGX 최신 참조 감사 실측 — 스크립트명과 폴더 경로 구분

- **실측 소스 HEAD:** `3dccb50e6f9528fea8a7b4cd799b2e2fdcfe3d09` (개인 Fork P2 개발 브랜치). `git pull --ff-only` 성공. `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v tests.test_p2_workspace_inventory` **15/15 PASS (실제 DGX Python CPU)**.
- `bash scripts/p2-workspace-inventory.sh --references`: `WORKSPACE_INVENTORY_READ_ONLY`, `docker=AVAILABLE`, `REFERENCE_AUDIT_READ_ONLY COMPLETE_SCOPED_SCAN scanned=1119`, 삭제·이동 **0회**. 15개 폴더 중 보호 5, HOLD 5, Phase1~5 REVIEW 5. 과거 Phase1~5 참조 횟수 각각 **9 / 10 / 7 / 9 / 19**. 각 hit는 경로 문자열 1회/파일 수준 카운트이며 물리 디렉터리 의존성 수가 아님.
- **GitHub 실제 소스 검토:** `scripts/phase2-check-offline.sh`, `phase3-check-offline.sh`, `phase4-check-offline.sh`, `phase5-check-offline.sh`, `phase5-mamba-batch-check.sh`에서 해당 PhaseN 문자열은 `BRANCH="feature/blazux-phaseN-..."` 형태의 **Git 브랜치 검사**이며, `ROOT="$(cd ... dirname ... && pwd)"`로 현재 스크립트 위치를 기준으로 실행한다. 이 5개 파일의 검색 hit만으로 **기존 `~/Workspace/llm/blazux-phaseN-...` 절대 디렉터리를 필요로 한다는 것은 입증되지 않음**. 단, 각 checkout의 브랜치/부모 commit과 전체 Git 상태는 보존해야 역사적 시험 재현 가능.
- 검색된 `tests/test_p2_workspace_inventory.py` 및 `scripts/source-state-manifest.json` 등도 **시험 fixture·Git blob 기록의 문자열**일 수 있으며, 문서상의 PhaseN 참조는 당시의 재현 절차·역사적 경로 설명일 수 있다. **실제 경로를 쓰는 스크립트와 정적 문자열은 분리 판단**해야 하며, 0건도 경로 안전성 증명이 아님. `phase5`는 추가 7건 이상 결과 생략(`EXTRA_REFERENCE_MATCHES_TRUNCATED`).
- **현재 허용된 조치:** 결과 분류 및 보관 설계만. 실제 폴더 archive/move/delete, symlink 갱신, `git reset --hard`, `git clean -fd`, 원본 컨테이너 변경은 미실행·별도 승인 필요. 별도 이동계획은 현재 활성 P2 checkout·보호 폴더를 제외한 깨끗한 Phase1~5만 대상으로, 각 Git identity/working tree, 실행 중 프로세스 cwd/open files 및 외부 systemd/cron/절대 경로 참조 확인, 이름 충돌·백업·원복 경로를 먼저 설계한다.
