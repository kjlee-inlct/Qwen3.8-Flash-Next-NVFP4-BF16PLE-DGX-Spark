#!/usr/bin/env bash
# Explicit offline authorized inputs: CPU probe / JSONL / plain text.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
cd -- "$ROOT"
[[ "$#" -ge 1 ]] || { echo "P2_TOKEN_FREQUENCY_USAGE: --check | --probe | --count (--corpus DOMAIN path.jsonl | --text DOMAIN path.txt)" >&2; exit 2; }
MODE="$1"
if [[ "$MODE" != "--check" && "$MODE" != "--probe" && "$MODE" != "--count" ]]; then
  echo "P2_TOKEN_FREQUENCY_USAGE: --check | --probe | --count (--corpus DOMAIN path.jsonl | --text DOMAIN path.txt)" >&2
  exit 2
fi
shift
if [[ ( "$MODE" == "--check" || "$MODE" == "--probe" ) && "$#" -ne 0 ]]; then exit 2; fi
export PYTHONDONTWRITEBYTECODE=1
export CUDA_VISIBLE_DEVICES=-1
HEAD="$(git rev-parse HEAD)"
python3 -m src.p2_numeric_dgx_prepare --expected-head "$HEAD" --check
python3 -m unittest -v tests.test_p2_token_frequency
if [[ "$MODE" == "--probe" || "$MODE" == "--count" ]]; then
  if [[ "$MODE" == "--count" && "$#" -lt 3 ]]; then echo "P2_CORPUS_INPUT_REQUIRED" >&2; exit 2; fi
  TOKENIZER="$HOME/Workspace/llm/yslab-qwen38-bf16ple-dgx-spark/recipe-views/orca-uncensored-bf16-mtp/ee5b6b553f1226d2/tokenizer.json"
  CONFIG="$(dirname -- "$TOKENIZER")/tokenizer_config.json"
  if [[ "$MODE" == "--probe" ]]; then
    python3 -m src.p2_token_frequency --tokenizer-json "$TOKENIZER" \
      --tokenizer-config "$CONFIG" --probe
  else
    python3 -m src.p2_token_frequency --tokenizer-json "$TOKENIZER" \
      --tokenizer-config "$CONFIG" "$@"
  fi
fi
[[ "$(git rev-parse HEAD)" == "$HEAD" ]] || { echo "P2_COUNT_HEAD_CHANGED" >&2; exit 2; }
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] || { echo "P2_COUNT_SOURCE_DIRTY" >&2; exit 2; }
echo "P2_TOKEN_FREQUENCY_SOURCE_COMPLETE HEAD=$HEAD MODE=$MODE NO_DOCKER_NO_GPU_NO_API"
