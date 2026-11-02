#!/usr/bin/env bash
# P2: pinned upstream Blazux 65536-ID asset -> real Orcarouter tokenizer audit.
# --stage: produce a private candidate; NEVER build/enable a model or use Docker.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
cd -- "$ROOT"
[[ "$#" -eq 1 && ( "$1" == "--audit" || "$1" == "--stage" ) ]] || {
  echo "P2_UPSTREAM_VOCAB_USAGE: --audit|--stage" >&2; exit 2;
}
MODE="$1"
export PYTHONDONTWRITEBYTECODE=1
export CUDA_VISIBLE_DEVICES=-1
readonly HEAD="$(git rev-parse HEAD)"
python3 -m src.p2_numeric_dgx_prepare --expected-head "$HEAD" --check
python3 -m unittest -v tests.test_p2_upstream_draft_asset
readonly ASSET="$ROOT/assets/blazux/draft_vocab_65536.npy"
readonly METADATA="$HOME/Workspace/llm/yslab-qwen38-bf16ple-dgx-spark/recipe-views/orca-uncensored-bf16-mtp/ee5b6b553f1226d2"
python3 -m src.p2_upstream_draft_asset "$MODE" \
    --asset "$ASSET" \
    --tokenizer-json "$METADATA/tokenizer.json" \
    --tokenizer-config "$METADATA/tokenizer_config.json"
[[ "$(git rev-parse HEAD)" == "$HEAD" ]] || {
  echo "P2_UPSTREAM_VOCAB_HEAD_DRIFT" >&2; exit 2;
}
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] || {
  echo "P2_UPSTREAM_VOCAB_SOURCE_DIRTY" >&2; exit 2;
}
echo "P2_UPSTREAM_VOCAB_DGX_COMPLETE HEAD=$HEAD MODE=$MODE NO_CORPUS_NO_DOCKER_NO_GPU_NO_API"
