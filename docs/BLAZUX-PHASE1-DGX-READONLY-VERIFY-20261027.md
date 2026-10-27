# Track A Phase 1 — DGX 소스 Pull 및 오프라인 검증 (운영 서비스 변경 금지)

> 기준: 2026-10-27. 실기기 검증 **절차**만 제공한다. 이 문서와 commit 작성 시 **실제 DGX 실행: NOT_RUN**, GPU A/B: NOT_RUN, CI: CI_NOT_VERIFIED. Phase 1 자체에는 blazux 추론 최적화 코드가 적용되지 않았으므로 이 시험은 **blazux 성능 시험이 아니다**.
>
> 원본: 개인 저장소 [kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark](https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark), Phase 1 `feature/blazux-phase1-source-compare` ← P0 `966ec7cf0741734b844b1cea938d56678a756469`; 비교 외부 [blazux/qwen3.8-Flash-DGX](https://github.com/blazux/qwen3.8-Flash-DGX/tree/8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa) commit `8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa`.

## 1. 검토 결론 및 시험 가능 범위

- **추가 최적화 구현: 필요 없음 (Phase 1 범위).** Gate 1은 [함수·데이터 계약 정적 비교 보고서](BLAZUX-PHASE1-GATE1-SOURCE-COMPARE-20261027.md)로 완료. PLE small-batch gather·pinned H2D·GPU inverse·계측 기능은 아직 포팅/활성화하지 않았고 후속 Phase에서 flag OFF 및 fixture로 검증할 사안이다.
- 현재 저장소에 **이미 존재**하는 `scripts/verify-source-state.py` (비 strict), `scripts/run-mock-tests.sh`, `tests/test_mtp_load_guard_patch.py`, `src/test_ple_mmap_cpu.py`, `tools/audit_publication.py`를 재사용한다. 검증기를 신규 브랜치까지 strict 허용하도록 수정하지 않는다.
- `scripts/verify-source-state.sh --strict`는 현재 허용된 `main` 및 기존 Wizard 브랜치 외의 이름을 의도적으로 거부한다. **Phase 1에서는 반드시 `--strict`를 빼되**, 다음 명령으로 정확한 `branch/origin/HEAD`를 먼저 확인한다. non-strict도 Git tree, worktree, 모드, Blob SHA, manifest 자체 Blob, fork origin 일치 여부를 검사한다.
- `scripts/verify-main-readonly.sh`는 **main 전용**이라 Phase 1에서 실행 금지. `scripts/benchmark/run-llama-benchy.sh`, `scripts/serve.sh`, `install.sh`, `uninstall.sh`, `activate*.sh`, `stop*.sh`, `prepare*.sh` 등을 이 절차에 섞지 않는다.
- 테스트 suite는 별도 clone에서 실행한다. 호스트 Python 패키지와 임시 디렉터리 사용은 가능하지만, Docker stop/rm/restart/run/build, HF 모델 수정, 운영 port 8000/18300 변경, snapshot·receipt 정리는 **하지 않는다**.

## 2. 격리된 소스 체크아웃 생성 또는 안전하게 Git Pull

**주의:** 실제 모델이 기동된 기존 YSLAB/운영 Checkout을 `git switch`하거나 `git pull`하지 않는다. 개인 Fork 전용 소스 사본을 `$HOME/Workspace/llm/blazux-phase1-source-compare`에 둔다. 이미 사용 중인 디렉터리가 존재하면 깨끗한 Phase 1 브랜치인지 검증 후에만 pull하며, 그 외 상태는 **즉시 STOP**한다.

```bash
set -Eeuo pipefail

REPO="kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark"
BRANCH="feature/blazux-phase1-source-compare"
SRC="$HOME/Workspace/llm/blazux-phase1-source-compare"

if [[ ! -e "$SRC" ]]; then
  mkdir -p -- "$(dirname -- "$SRC")"
  git clone --single-branch --branch "$BRANCH" \
    "https://github.com/$REPO.git" "$SRC"
fi
[[ -d "$SRC/.git" ]] || { echo "STOP: unexpected source directory" >&2; exit 2; }
cd -- "$SRC"

ORIGIN="$(git remote get-url origin)"
case "$ORIGIN" in
  "https://github.com/$REPO"|"https://github.com/$REPO.git"|"git@github.com:$REPO"|"git@github.com:$REPO.git"|"ssh://git@github.com/$REPO"|"ssh://git@github.com/$REPO.git") ;;
  *) echo "STOP: unexpected origin" >&2; exit 2 ;;
esac
[[ "$(git symbolic-ref --quiet --short HEAD)" == "$BRANCH" ]] || {
  echo "STOP: checkout must already be the dedicated Phase 1 branch" >&2; exit 2;
}
[[ -z "$(git status --porcelain=v1 --untracked-files=normal)" ]] || {
  echo "STOP: local changes/untracked files; never reset or clean" >&2; exit 2;
}

git fetch --no-tags origin "$BRANCH"
git pull --ff-only origin "$BRANCH"

HEAD_SHA="$(git rev-parse HEAD)"
TRACKING_SHA="$(git rev-parse "refs/remotes/origin/$BRANCH")"
[[ "$HEAD_SHA" == "$TRACKING_SHA" ]] || {
  echo "STOP: checkout does not match fetched Phase 1 tip" >&2; exit 2;
}
[[ "$(git rev-parse "$HEAD_SHA^")" != "" ]] || exit 2
git merge-base --is-ancestor \
  966ec7cf0741734b844b1cea938d56678a756469 HEAD || {
    echo "STOP: P0 is not an ancestor" >&2; exit 2;
  }

echo "PHASE1_SOURCE_HEAD=$HEAD_SHA"
echo "GIT_HEAD_MATCHES_FETCHED_PHASE1=YES"
echo "NOTE: Git SHA 검증은 DGX 서비스/컨테이너 상태 검증이 아님"
```

`PHASE1_SOURCE_HEAD`가 GitHub에서 확인한 **현재 Phase 1 확정 HEAD**와 같은지 대조하고, 다르면 이후 시험을 중단한다. 이 문서는 자기 자신을 포함한 HEAD SHA를 고정하지 않는다(순환 참조 방지).

## 3. source-only 및 오프라인 회귀 시험

위 source-only 체크아웃에서 실행한다. **이 단계는 기존 GPU 모델 추론/성능 시험이 아님**. 테스트 중 `tempfile` fixture는 임시 저장소를 사용할 수 있지만 운영 HF cache·recipe views는 수정하지 않는다.

```bash
set -Eeuo pipefail
export PYTHONDONTWRITEBYTECODE=1
# 오직 Phase 1 소스에서 실행했는지 확인
test "$(git symbolic-ref --quiet --short HEAD)" = "feature/blazux-phase1-source-compare"

# non-strict라도 origin + Git blob + 작업 트리/파일 모드 + manifest 자기 blob을 모두 검사
scripts/verify-source-state.sh
python3 -m json.tool scripts/source-state-manifest.json >/dev/null
python3 -m json.tool scripts/deployment-manifest.json >/dev/null
python3 -m json.tool compatibility.json >/dev/null
scripts/manifest.sh validate

# 실제 Docker 작업 없음: fake Docker/Git/HTTP 모의 시험 + 저장소 CPU 단위시험
scripts/run-mock-tests.sh
PYTHONPATH=src:. python3 -m unittest discover -s tests -v

# Python 실행 없이 Bash 문법, 공개 추적 파일 감사
bash -n scripts/*.sh scripts/qwen38-dgx-spark
python3 tools/audit_publication.py

# Unit/mock 실행 이후 소스 추적 파일 변조 여부 재확인
scripts/verify-source-state.sh
test -z "$(git status --porcelain=v1 --untracked-files=normal)"
echo "PASS: Phase 1 source integrity / offline mock / unit tests (if all commands returned zero)"
echo "NOT_RUN: legacy container lifecycle, new GPU model, llama-benchy A/B, CI"
```

### PLE BF16 CPU fixture — 선택 실행 (Torch + NumPy 사용 가능한 경우)

`src/test_ple_mmap_cpu.py`는 기존 PLE CPU 테스트로, BF16 byte offset/gather, shard layout 및 일부 vLLM patch fixture를 검사한다. 호스트에 `torch`/ `numpy`가 없으면 **DEPENDENCY_UNAVAILABLE**로 분리 기록하고, 기존 서비스 컨테이너에서 `docker run`하지 않는다.

```bash
export PYTHONDONTWRITEBYTECODE=1
CUDA_VISIBLE_DEVICES="" python3 -c 'import numpy, torch'
CUDA_VISIBLE_DEVICES="" python3 src/test_ple_mmap_cpu.py
```

이 시험이 통과해도 blazux의 pinned/H2D/graph/API 경로는 시험되지 않은 상태다. 기존 소스의 정합성을 확인할 뿐이다.

## 4. 수집할 로그와 금지 사항

결과에 `PHASE1_SOURCE_HEAD`, source validator checked-file count, deployment-manifest 결과, mock `N/N`, repository unittest `N/N`, Bash syntax/publication audit 종료 코드, 선택 PLE CPU 결과, 실행 시각/환경을 남긴다. 공개 Git에 호스트 절대 경로/credential/container ID/비공개 환경 파일을 커밋하지 않는다. 결과 원문을 공유할 때 비밀 값 제거 필요.

- **실패 시:** `FAIL`/실제 예외를 보존하고 중단한다. 무조건 `PASS`로 정리하거나 `--strict` 검증기 허용 목록을 변경하지 않는다. `git reset --hard`, `git clean`, `docker stop/rm`, 이미지 삭제 또는 기존 모델 재시작으로 '복구'하지 않는다.
- **완료 판단:** Phase 1 정적 검토의 로컬 재현 결과만 PASS 가능. Phase 2의 BF16 소형 합성 fixture는 **새 브랜치**에서 구현, 별도 CPU 테스트를 실행해야 한다.
- **브랜치 정책:** P0/Phase 1과 `main`의 HEAD 보호, blazux→main 모든 PR/merge/cherry-pick/rebase/squash 금지, Track B 별도 승인 후만 분기.
