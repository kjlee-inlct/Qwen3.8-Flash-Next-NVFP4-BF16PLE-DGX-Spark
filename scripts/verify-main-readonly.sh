#!/usr/bin/env bash
# 기존 DGX 서비스를 보존하는 main HEAD/소스/시험/상태 조회 전용.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
expected="kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark"
origin="$(git remote get-url origin)"
case "$origin" in
  "https://github.com/$expected"|"https://github.com/$expected.git"|"git@github.com:$expected"|"git@github.com:$expected.git"|"ssh://git@github.com/$expected"|"ssh://git@github.com/$expected.git") ;;
  *) echo "STOP: unexpected origin; personal fork required" >&2; exit 2 ;;
esac
branch="$(git symbolic-ref --quiet --short HEAD)" || { echo "STOP: detached HEAD" >&2; exit 2; }
[[ "$branch" == main ]] || { echo "STOP: expected main; currently $branch" >&2; exit 2; }
[[ -z "$(git status --porcelain=v1 --untracked-files=normal)" ]] || {
  echo "STOP: local changes/untracked files; no reset or clean permitted" >&2
  exit 2
}
git show-ref --verify --quiet refs/remotes/origin/main || {
  echo "STOP: origin/main absent; verify origin and fetch main separately" >&2
  exit 2
}
local_head="$(git rev-parse HEAD)"
remote_tracking="$(git rev-parse refs/remotes/origin/main)"
[[ "$local_head" == "$remote_tracking" ]] || {
  echo "STOP: main differs from local origin/main; update separately with fast-forward" >&2
  exit 2
}
echo "SOURCE_HEAD=$local_head (matches local origin/main; remote freshness NOT proven)"
export PYTHONDONTWRITEBYTECODE=1
scripts/verify-source-state.sh --strict
scripts/manifest.sh validate
scripts/run-mock-tests.sh
PYTHONPATH=src:. python3 -m unittest discover -s tests -v
bash -n scripts/*.sh scripts/qwen38-dgx-spark
python3 tools/audit_publication.py
# HTTP 조회(GET) 및 Docker inspect만 수행; stop/rm/run/chat inference 없음.
scripts/status.sh
scripts/compare-state.sh
scripts/health.sh
scripts/doctor.sh
echo "PASS: local source/tests/observations; real new deployment NOT_TESTED"
