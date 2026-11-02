#!/usr/bin/env bash
# Explicit offline JSONL -> token frequency. No Docker, GPU, HTTP, install.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
cd -- "$ROOT"
[[ "$#" -ge 1 ]] || { echo "P2_TOKEN_FREQUENCY_USAGE: --check | --count --corpus DOMAIN /absolute/path.jsonl" >&2; exit 2; }
MODE="$1"
if [[ "$MODE" != "--check" && "$MODE" != "--count" ]]; then
  echo "P2_TOKEN_FREQUENCY_USAGE: --check | --count --corpus DOMAIN /absolute/path.jsonl" >&2
  exit 2
fi
shift
if [[ "$MODE" == "--check" && "$#" -ne 0 ]]; then exit 2; fi
export PYTHONDONTWRITEBYTECODE=1
export CUDA_VISIBLE_DEVICES=-1
HEAD="$(git rev-parse HEAD)"
python3 -m src.p2_numeric_dgx_prepare --expected-head "$HEAD" --check
python3 -m unittest -v tests.test_p2_token_frequency
if [[ "$MODE" == "--count" ]]; then
  [[ "$#" -ge 3 ]] || { echo "P2_CORPUS_INPUT_REQUIRED" >&2; exit 2; }
  TOKENIZER="$HOME/Workspace/llm/yslab-qwen38-bf16ple-dgx-spark/recipe-views/orca-uncensored-bf16-mtp/ee5b6b553f1226d2/tokenizer.json"
  CONFIG="$(dirname -- "$TOKENIZER")/tokenizer_config.json"
  python3 -m src.p2_token_frequency --tokenizer-json "$TOKENIZER" \
    --tokenizer-config "$CONFIG" "$@"
fi
[[ "$(git rev-parse HEAD)" == "$HEAD" ]] || { echo "P2_COUNT_HEAD_CHANGED" >&2; exit 2; }
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] || { echo "P2_COUNT_SOURCE_DIRTY" >&2; exit 2; }
echo "P2_TOKEN_FREQUENCY_SOURCE_COMPLETE HEAD=$HEAD MODE=$MODE NO_DOCKER_NO_GPU_NO_API"
