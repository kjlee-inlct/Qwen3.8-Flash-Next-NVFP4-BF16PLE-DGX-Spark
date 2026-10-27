#!/usr/bin/env bash
# Reproduce the pre-blazux llama-benchy performance matrix on the DGX host.
# The old Docker service is only observed, never stopped/rebuilt/restarted.
# Produces private evidence locally; no Git or GitHub publication.
# HISTORICAL PR#5: this script was source-only/NOT_RUN in the original PR.
# 2026-10-28: operator approved one Phase6 existing-service script validation.
# Never call this legacy launcher directly for Phase6: use the resource/identity-
# monitored scripts/phase6-ab-provisional-run.sh --execute entrypoint instead.
# Original pre-blazux result bytes and default execution parameters are unchanged.
set -Eeuo pipefail

main() {
  local runner api container model source_sha tok_sha phase out_root book_url
  local model_json served_model model_root view_host tok_file book_cache corpus_sha
  local docker_id image_id checkout_sha out_dir started_utc
  runner="${LLAMA_BENCHY_RUNNER:-$HOME/Workspace/llm/llama-benchy-runner}"
  api="${LLAMA_BENCHY_API:-http://127.0.0.1:8000/v1}"
  container="${LLAMA_BENCHY_CONTAINER:-qwen38-flash-orca-uncensored-bf16-mtp}"
  model="${LLAMA_BENCHY_MODEL:-qwen3.8-flash-next-orca-uncensored-bf16-mtp}"
  out_root="${LLAMA_BENCHY_RESULTS_ROOT:-$HOME/Workspace/llm/bench-results-staging}"
  # Pre-blazux is the historical default; Phase6 guard overrides the phase to
  # a separate unique provisional PRE-B directory, never the archived dataset.
  phase="${LLAMA_BENCHY_PHASE:-pre-blazux}"
  source_sha="e9be344578cec17745066b220798b80a0d2686d3"
  tok_sha="06b9509352d2af50381ab2247e083b80d32d5c0aba91c272ca9ff729b6a0e523"
  book_url="https://www.gutenberg.org/files/1661/1661-0.txt"
  started_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

  [[ "$phase" =~ ^[a-z0-9_-]+$ ]] || { echo "Invalid phase" >&2; return 1; }
  for command_name in git docker curl python3 sha256sum mktemp date free tee awk; do
    command -v "$command_name" >/dev/null || { echo "Missing: $command_name" >&2; return 1; }
  done
  [[ -x "$runner/.venv/bin/python" ]] || { echo "Runner environment missing" >&2; return 1; }
  [[ "$(git -C "$runner" rev-parse HEAD)" == "$source_sha" ]] || { echo "Wrong llama-benchy SHA" >&2; return 1; }
  [[ "$(docker inspect -f '{{.State.Running}}' "$container")" == true ]] || { echo "Legacy model not running" >&2; return 1; }

  model_json="$(curl -fsS --max-time 15 "$api/models")"
  served_model="$(printf '%s' "$model_json" | python3 -c 'import json,sys; x=json.load(sys.stdin)["data"]; assert len(x)==1; print(x[0]["id"])')"
  model_root="$(printf '%s' "$model_json" | python3 -c 'import json,sys; x=json.load(sys.stdin)["data"]; assert len(x)==1; print(x[0]["root"])')"
  [[ "$served_model" == "$model" && "$model_root" == /recipe/recipe-views/* ]] ||
    { echo "Wrong served model/root" >&2; return 1; }
  view_host="$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/recipe/recipe-views"}}{{.Source}}{{end}}{{end}}' "$container")"
  [[ -n "$view_host" && -d "$view_host" ]] || { echo "Missing model-view mount" >&2; return 1; }
  tok_file="$view_host/${model_root#/recipe/recipe-views/}/tokenizer.json"
  [[ -f "$tok_file" ]] || { echo "Missing tokenizer" >&2; return 1; }
  [[ "$(sha256sum "$tok_file" | awk '{print $1}')" == "$tok_sha" ]] ||
    { echo "Tokenizer SHA mismatch" >&2; return 1; }

  # Require already cached Gutenberg corpus; do not silently download a different text.
  book_cache="$HOME/.cache/llama-benchy/$(python3 -c 'import hashlib,sys; print(hashlib.md5(sys.argv[1].encode()).hexdigest())' "$book_url").txt"
  [[ -s "$book_cache" ]] || { echo "Gutenberg corpus cache absent; STOP" >&2; return 1; }
  corpus_sha="$(sha256sum "$book_cache" | awk '{print $1}')"

  docker_id="$(docker inspect -f '{{.Id}}' "$container")"
  image_id="$(docker inspect -f '{{.Image}}' "$container")"
  checkout_sha="$(git -C "$(dirname -- "${BASH_SOURCE[0]}")/../.." rev-parse HEAD)"

  umask 077
  mkdir -p -- "$out_root"
  out_dir="$(mktemp -d -- "$out_root/$(date -u +%Y%m%dT%H%M%SZ)-$phase-XXXXXX")"
  echo "BENCH_OUTPUT_DIR=$out_dir"

  # This file contains full Docker IDs and must never be committed publicly.
  python3 - "$out_dir/environment.private.json" "$started_utc" "$source_sha" \
    "$served_model" "$tok_sha" "$book_url" "$corpus_sha" \
    "$docker_id" "$image_id" "$checkout_sha" "$phase" <<'PY'
import json
import pathlib
import sys
(path, started, tool_sha, model, tok_sha, book_url, book_sha,
 docker_id, image_id, checkout_sha, phase) = sys.argv[1:]
evidence = {
    "visibility": "PRIVATE_DO_NOT_COMMIT",
    "phase": phase,
    "created_utc": started,
    "tool": "eugr/llama-benchy",
    "tool_git_sha": tool_sha,
    "served_model": model,
    "tokenizer_sha256": tok_sha,
    "book_url": book_url,
    "book_sha256": book_sha,
    "container_id": docker_id,
    "image_id": image_id,
    "model_repository_git_sha": checkout_sha,
    "prompt_rng_seed": 20261027,
    "parameters": {
        "pp": [2048, 8192], "tg": [128, 256],
        "depth": [0, 4096, 16384], "concurrency": [1],
        "runs": 3, "warmup_runs": 1, "exact_tg": True,
        "latency_mode": "generation",
        "save_total_throughput_timeseries": True
    },
}
pathlib.Path(path).write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
PY
  free -h > "$out_dir/memory-before.txt"
  if ! nvidia-smi > "$out_dir/gpu-before.txt" 2>&1; then
    echo "NOTE: nvidia-smi before snapshot unavailable" >&2
  fi
  (
    cd "$runner"
    .venv/bin/python -c '
import numpy as np
np.random.seed(20261027)
from llama_benchy.__main__ import main
main()
' \
      --base-url "$api" --model "$served_model" --served-model-name "$served_model" \
      --tokenizer "$tok_file" --book-url "$book_url" \
      --pp 2048 8192 --tg 128 256 --depth 0 4096 16384 \
      --concurrency 1 --runs 3 --warmup-runs 1 \
      --latency-mode generation --exact-tg \
      --format json --save-result "$out_dir/result.json" \
      --emit-progress "$out_dir/progress.jsonl" \
      --save-total-throughput-timeseries --exit-on-first-fail \
      2>&1 | tee "$out_dir/run.log"
  )
  free -h > "$out_dir/memory-after.txt"
  if ! nvidia-smi > "$out_dir/gpu-after.txt" 2>&1; then
    echo "NOTE: nvidia-smi after snapshot unavailable" >&2
  fi
  if command -v uv >/dev/null; then
    uv pip freeze --python "$runner/.venv/bin/python" > "$out_dir/python-packages.txt"
  else
    echo "uv unavailable; packages not recorded" > "$out_dir/python-packages.txt"
  fi
  # These assertions run only during a FUTURE operator execution, not this PR.
  python3 - "$out_dir/result.json" <<'PY'
import itertools
import json
import sys
with open(sys.argv[1], encoding="utf-8") as stream:
    data = json.load(stream)
expected = set(itertools.product((2048, 8192), (128, 256), (0, 4096, 16384)))
rows = data.get("benchmarks", [])
actual = {(x.get("prompt_size"), x.get("response_size"), x.get("context_size")) for x in rows}
if len(rows) != 12 or actual != expected:
    raise SystemExit("FAIL: incomplete benchmark combinations")
for row in rows:
    for key in ("pp_throughput", "tg_throughput", "e2e_ttft"):
        if len((row.get(key) or {}).get("values", [])) != 3:
            raise SystemExit("FAIL: incomplete measurement repeats")
print("RESULT_MATRIX=12/12; MEASURED_RUNS=36")
PY
  (cd "$out_dir"; sha256sum result.json progress.jsonl run.log environment.private.json \
     memory-before.txt gpu-before.txt memory-after.txt gpu-after.txt \
     python-packages.txt > SHA256SUMS)
  printf 'PASS: baseline completed; files stored locally, NOT published.\nRESULT_DIR=%s\n' "$out_dir"
}
main "$@"
