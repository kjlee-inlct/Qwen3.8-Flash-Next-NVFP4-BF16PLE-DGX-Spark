#!/usr/bin/env bash
# P2 integrated CPU/source batch. No Docker, model, GPU, HTTP, CI or stage.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"
[[ "$#" -eq 0 ]] || { echo "Usage: bash scripts/p2-batch-dgx.sh" >&2; exit 2; }
HEAD="$(git rev-parse HEAD)"
export PYTHONDONTWRITEBYTECODE=1
export CUDA_VISIBLE_DEVICES=-1
# Existing exact fork/branch/clean-tree and source-manifest preflight.
python3 -m src.p2_numeric_dgx_prepare --expected-head "$HEAD" --check
python3 - <<'PY'
import ast
from pathlib import Path
for name in (
    "src/vllm_ple_mmap.py",
    "src/p2_mtp_draft_vocab.py",
    "src/p2_numeric_report.py",
    "src/p2_numeric_boundary.py",
    "src/p2_numeric_sampler_witness.py",
):
    ast.parse(Path(name).read_text(encoding="utf-8"), filename=name)
print("P2_BATCH_SOURCE_AST_PASS")
PY
PYTHONPATH=src:. python3 -m unittest -v \
  tests.test_p2_numeric_boundary \
  tests.test_p2_numeric_sampler_witness \
  tests.test_p2_numeric_dgx_prepare \
  tests.test_p2_mtp_draft_vocab \
  tests.test_p2_numeric_report \
  tests.test_p2_ple_unique_h2d
bash -n scripts/p2-batch-dgx.sh scripts/p2-numeric-dgx.sh
# No artifacts, files or untracked cache may be produced.
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] || {
  echo "P2_BATCH_SOURCE_TREE_DIRTY_STOP" >&2; exit 2;
}
[[ "$(git rev-parse HEAD)" == "$HEAD" ]] || { echo "HEAD_MOVED_STOP" >&2; exit 2; }
echo "P2_BATCH_CPU_SOURCE_DONE HEAD=$HEAD NO_DOCKER_NO_GPU_NO_HTTP"
