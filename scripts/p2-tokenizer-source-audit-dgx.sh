#!/usr/bin/env bash
# Read-only Orcarouter recipe-view vs target-snapshot tokenizer byte identity.
# No original-container access, Docker, GPU, API, model or changes on disk.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
cd -- "$ROOT"
[[ "$#" -eq 1 && ( "$1" == "--check" || "$1" == "--audit" ) ]] || {
  echo "P2_TOKENIZER_USAGE: --check|--audit" >&2
  exit 2
}
HEAD="$(git rev-parse HEAD)"
export PYTHONDONTWRITEBYTECODE=1
export CUDA_VISIBLE_DEVICES=-1
python3 -m src.p2_numeric_dgx_prepare --expected-head "$HEAD" --check
python3 -m unittest -v tests.test_p2_tokenizer_source_audit
if [[ "$1" == "--audit" ]]; then
  python3 -m src.p2_tokenizer_source_audit \
    --recipe-tokenizer "$HOME/Workspace/llm/yslab-qwen38-bf16ple-dgx-spark/recipe-views/orca-uncensored-bf16-mtp/ee5b6b553f1226d2/tokenizer.json" \
    --orcarouter-snapshot-tokenizer "$HOME/Workspace/llm/yslab-qwen38-bf16ple-dgx-spark/hf-cache/hub/models--orcarouter--Qwen3.8-Flash-Next-Uncensored-NVFP4/snapshots/3a3b63161c0745390e5270179af42e46efc70799/tokenizer.json"
fi
[[ "$(git rev-parse HEAD)" == "$HEAD" ]] || {
  echo "P2_TOKENIZER_HEAD_CHANGED" >&2; exit 2;
}
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] || {
  echo "P2_TOKENIZER_DIRTY_SOURCE" >&2; exit 2;
}
echo "P2_TOKENIZER_SOURCE_AUDIT_COMPLETE HEAD=$HEAD MODE=$1 NO_GPU_NO_API_NO_WRITES"
