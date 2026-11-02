# P2 numeric — DGX Git pull 실행 지침 (2026-11-02)

이 문서는 실제 DGX에서 수행하는 **소스 준비 작업**의 정본이다. GitHub에서 코드를 완성하고, DGX에서는 `git pull` 후 하나의 스크립트만 호출한다. 두 모드는 **GPU/모델/HTTP 추론·Docker build/run/start/stop/exec·운영 설정 변경을 수행하지 않는다.** P1 기존 서비스와 pinned Stage는 보존한다.

## 기존 P2 Fork checkout에서 실행

```bash
cd ~/Workspace/llm/blazux-phase6-gates
# 이 세 값이 예상과 다르거나 로컬 변경이 있으면 STOP (reset/clean 금지)
git remote get-url origin
git branch --show-current
git status --short
# origin=kjlee-inlct 개인 Fork, 브랜치=feature/blazux-phase6-runtime-gates 확인 후:
git pull --ff-only origin feature/blazux-phase6-runtime-gates
bash scripts/p2-numeric-dgx.sh --check
```

`--check`는 현재 정확한 Git HEAD, 개인 Fork origin, P2 브랜치, 깨끗한 Git 상태, 전체 Source Manifest 무결성 및 P2 대상 CPU-only 단위시험을 검증한다. 원본 Docker에 접근하지 않는다. 이는 GPU/API/실모델 PASS가 아니다. P2 개발 브랜치에서는 기존 `scripts/verify-source-state.sh --strict`가 브랜치 제한으로 실패하므로 **정상적인 P2 검사에는 사용하지 않는다**. 비-strict 검사는 `src.p1_preview_qsa_exact_topk.preflight()`에서 실행된다.

## 필요할 때만, 원본의 설치된 Sampler 소스 읽기 및 패치 준비

```bash
bash scripts/p2-numeric-dgx.sh --stage
```

`--stage`는 `--check`와 동일한 검증을 먼저 시행한 뒤, 고정 원본 Docker 컨테이너에 대해 **read-only inspect / docker cp**를 수행한다. 원본 full ID, image ID, StartedAt, 이미지 태그 및 설치된 `sampler.py` SHA256·AST anchor가 정확히 일치해야만 새 **개인 `/tmp/p2-numeric-witness-.../`**에 `sampler.py`, `Dockerfile` 두 파일을 작성한다. `VLLM_P2_NUMERIC_WITNESS=0` 기본값으로 준비되며, 이 단계는 **이미지를 빌드하거나 실행하지 않는다.** 원본이 중지됐거나 SHA/ID/StartedAt가 다르면 `P2_DGX_SOURCE_PREP_BLOCKED`와 exit 2로 중단한다. 소스 파일 원문이나 모델 데이터를 stdout에 출력하지 않는다.

`--stage`의 `/tmp` 출력 디렉터리는 운영 원본이나 P1 pinned Stage가 아니며 자동 재실행·삭제·덮어쓰기를 하지 않는다. 이미 준비된 동일 stage가 존재해도 스크립트는 새로운 이름을 사용한다. 실 GPU 계측·API 요청·운영 중단은 **별도 사용자 명시 승인** 및 전용 안전 런처가 마련될 때까지 금지한다. 이 스크립트는 `--execute`와 같은 실행 모드를 제공하지 않는다.

### 결과 해석

- `P2_SOURCE_PREFLIGHT_PASS_NO_DOCKER_OR_GPU`: Git 소스 검증만 성공
- `P2_WITNESS_SOURCE_STAGED_NOT_BUILT_NOT_RUN`: 고정 원본의 소스 SHA 검증 및 CPU 파일 준비 성공; GPU 계측 성공 아님
- `P2_DGX_SOURCE_PREP_BLOCKED`: 기준과 다름. 강제 진행, 원본 재시작·교체, SHA 무력화 금지
- `P2_DGX_SOURCE_ONLY_DONE`: 해당 모드 종료. P1 출시 차단과 P2 strict `1e-4` 문제는 변함없음

실행 후에는 **출력된 HEAD, 검사 PASS/FAIL, stage 상태, SHA 및 exit code**만 공유한다. 원본 가중치, 사용자가 입력한 prompt, 전체 logits/토큰 또는 Docker 환경변수·비밀정보를 공유하지 않는다.
