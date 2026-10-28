# Phase6 live P6-A ABI observation and provisional PRE-B benchmark on existing service

## 2026-10-28 DGX 실제 로그 반영 — P6-A 부분 관찰 / 신규 PRE-B 1회 완료

**Status now: EXECUTED_ONCE / PROVISIONAL_36_RECORDED / P6_A_ACTIVE_ABI_BLOCKED / P6_B_C_D_NOT_RUN.** 이전 `USER_APPROVED / ... NOT_RUN` 문장은 원래 작성 시점의 이력이며 지금은 새 벤치 승인 1회가 소진됐다.

- **실제 DGX-tested SHA**: `d031d4196eab1f5f1603d6541eaf5a31b02192c0` (사용자 제공 콘솔 로그). `git pull --ff-only` 이후 `bash scripts/phase6-gate.sh`에서 **99/99 단위시험 PASS**, **Source Manifest 211/211 PASS**. 이 SHA에서 shell `bash -n` 점검도 이어서 성공했다.
- **후속 GitHub docs-only HEAD**: `13668e031992341dfde1d815ec553a6d97d29ecf` (212개 tracked file). 로그 당시 DGX checkout은 `d031d419...`이었으므로 **13668e0...의 Source212/212 및 단위시험은 DGX NOT_RUN**이다. 이후 증거/Manifest 문서 커밋 역시 DGX-tested로 간주하지 않는다.
- **P6-A live read-only 결과**: `PARTIAL_EXPOSED_RUNTIME_CACHE_METADATA`, `/v1/models`의 고정 served model ID 일치, `/metrics` `vllm:cache_config_info` 1 series: `block_size=8`, `enable_prefix_caching=false`, `gpu_memory_utilization=0.8`; 관찰 전후 pinned legacy identity=true. 이 값은 노출된 시작시 cache 메타데이터만 증명한다. 실제 Scheduler class, effective scheduler/hash block size, 그룹별 MambaSpec, block-table row/stride, GPU tensor ptr/shape/stride/allocation은 전부 `NOT_OBSERVED`; **P6-A 활성 ABI=BLOCKED**.
- **PRE-B 무부하 preflight**: `READY_FOR_APPROVED_PROVISIONAL_BENCH`, runner SHA/current cached corpus SHA 검증, original baseline 12조건/36 반복 검증, pinned image/running=true, 당시 host MemAvailable=14058MiB. Bench 시작 watch 기록 14050MiB, 이후 minute 1~15의 관측 범위 14170~14746MiB (출력된 점검치); 이것은 전체 운영 무간섭이나 OOM 방지를 증명하지 않는다.
- **승인된 단 1회 신규 벤치 완료**: `PASS_PROVISIONAL_PRE_B_36`, **12 conditions × 3 measured = 36**, 기존 서비스 대상, 원본 Baseline과 별도 private staging에 보존. 신규 `result.json` 보고된 SHA256 `35c409d6f714bbce7b9c68d9cbc5c24f5a18e64575f1842daef1dc1d64d3a80d`. 로그는 래퍼의 검증 완료 선언을 포함하지만 새 raw 파일 바이트의 독립 재해시는 이 GitHub 문서 갱신 과정에서 수행하지 않았다.
- **승인 소진**: 위 1회가 실행되었으므로 `scripts/phase6-ab-provisional-run.sh --execute` 및 레거시 benchmark 직접 호출을 **재실행하지 않는다**. 실패/재검증 명목으로 자동 추가 API/GPU 부하도 금지.
- **비교 범위**: 역사적 Gutenberg corpus 원본 SHA 및 sampling/KV/cache 동일성 미확정. 과거 pre-blazux↔금번 결과 strict A/B 성능 개선율/회귀율을 주장할 수 없다. 공식 **P6-D NOT_RUN**, **P6-B/C NOT_RUN/BLOCKED**. 결과 원본/비공개 environment/guard logs/개별 컨테이너 ID·로컬 절대경로를 공개 GitHub로 올리지 않는다.

추가 live ABI 측정을 위해 서비스 내부 객체를 관측해야 한다면 기존 HTTP startup metrics를 실제 Python 객체로 오인하지 말고 별도 안전성 평가/승인을 선행한다.

---


Status: USER_APPROVED / GITHUB_SOURCE_PREPARED / NEW_DGX_HEAD_NOT_RUN / ACTUAL_P6_A_ABI_NOT_PROVEN. The user explicitly requested actual P6-A ABI verification and a fresh benchmark even though an archived baseline exists, to validate the benchmark script. This approval covers the existing pinned model's read-only HTTP metadata probe and one bounded 12×3 generation benchmark through its existing loopback API. It does NOT authorize server stop/restart, image/model changes, Docker exec, process attach, ptrace, patch, new GPU model, CI, PR or merge.

## Actual evidence already verified

- Most recent **operator-tested exact source SHA** `fb5deae540812a300cb8404a53a202e505c40577`: 70/70 Phase6 offline unit tests, Source204/204, immutable historic 12×3 raw result SHA/runner/tokenizer and 36 repeats verified. Marker `PHASE6_AB_BENCH_PLAN_DGX_VERIFIED_NO_LOAD`; absolutely **no fresh benchmark was conducted** at that SHA.
- Earlier `0ad5e62caab2e95c57813cc6401d2f00622f3f4f`: one approved CPU-only pinned image source scan passed (7 historical file SHA, 8 AST component anchors), operating legacy container same pinned state before/after. Source/AST is not proof of effective live runtime Scheduler or GPU state.
- The original baseline source `results/llama-benchy/baseline/pre-blazux/20261026T221925Z/result.json` is immutable, SHA256 `25f6abf3968efbf94cf08b02297140f7be2e8b29f8f2192b1d246e7432959edf`.

## 1. P6-A true live observation: possible and impossible with currently exposed interfaces

`scripts/phase6-a-live-observe.sh` checks clean dedicated Phase6 branch, Source Manifest, immutable image and running legacy identity BEFORE/AFTER. Requests only the existing fixed loopback `GET /v1/models` and `GET /metrics`. Restricts HTTP response bytes/time and forbids redirects, stderr/environment/log/id leaks. vLLM 0.32 may expose `vllm:cache_config_info{block_size="...", enable_prefix_caching="...", gpu_memory_utilization="..."}`; output copies **only** validated numeric/boolean allowlisted fields. This metric is startup-advertised engine cache metadata; it does not resolve actual Python object pointers. If missing, report `ABI_METRICS_NOT_USABLE` or `NOT_EXPOSED`, NOT a fabricated default.

Crucially, no ordinary HTTP/Prometheus metric can certify the active selected Scheduler class, effective scheduler/hash/group MambaSpec block sizes, real block-table geometry, physical pointer/stride/tensor allocation, kernel bounds or G1–G8 correctness. Those remain `NOT_OBSERVED` and real P6-A ABI `BLOCKED` even if cache info is observed. No in-process debug hook, `docker exec`, ptrace, instrumented code or second GPU model is authorized by this workflow. A full P6-A PASS would require a separately implemented safe live observer or proven isolated GPU/ABI evidence; no such observer has been run. The read-only check is an **actual attempt**, not an assertion that full ABI was verified.

## 2. Approved fresh performance measurement despite still-BLOCKED P6-A

`scripts/phase6-ab-provisional-run.sh --preflight` does **no inference**; `--execute` is the user's explicitly authorized one bounded run of `scripts/benchmark/run-llama-benchy.sh` against the already running `http://127.0.0.1:8000/v1` model. Use the checkout's version of that legacy launcher but **never invoke it directly** (it omits independent guard and can default to `pre-blazux` output label). This test is `PHASE6_AB_PROVISIONAL_ON_EXISTING_SERVICE`, strictly **not** gate-qualified `P6_AB_PERF_SNAPSHOT_CAPTURED`, not P6-A PASS, not final P6-D regression.

- Preflight: historical raw baseline source SHA/provenance pass, separate llama-benchy git pin `e9be344578cec17745066b220798b80a0d2686d3`, runner virtualenv present, unchanged local Gutenberg cache SHA256 `8a2f79a2f4601cfe6e25830c29c1a25c7a3d906285a989948117568f8077ab2c`, exact pinned running Docker `sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a`, dedicated private staging root, and **fresh host MemAvailable≥8192 MiB**. No duplicate wrapper via advisory lock.
- Load: original runner, no source/model modification, PP[2048,8192] × TG[128,256] × depth[0,4096,16384], concurrency 1, 1 warmup and 3 measured repeats each = 12×3 = 36 measured, generation latency mode, exact-TG and NumPy seed 20261027, progress log and throughput time series. Normal inference changes the running service's transient scheduler/cache state and may contend with other clients: benchmark **may temporarily reduce service responsiveness**. No service health/zero-interference guarantee is claimed; the user approved this bounded load.
- Watchdog: monitor current `MemAvailable` every 10 sec and STOP benchmark child process group only if below **4096 MiB**, if the exact running Docker ID+image+start timestamp drifts, or if one hour passes. Existing operational server is **never** signaled/killed/restarted/stopped or reconfigured. Container identity also checked after the bench. The monitoring floor reduces risk but is not an OOM or no-interference guarantee; on abnormal memory condition stop and keep partial private files.
- Private output: new unique directories under `$HOME/Workspace/llm/bench-results-staging/` with `phase6-pre-b-provisional` label; separate `phase6-ab-guard-*` user-only control log. Never overwrite the old pre-blazux Git-tracked 36-run result. The source runner's `environment.private.json` may contain full Docker IDs/model-view details; raw logs must not go to GitHub. On completion, independently verify output matrix + all 36 repeats, private provenance including cached corpus SHA, SHA256SUMS for all nine original raw files, then emit sanitized 12-condition mean PP estimate / TG decode / E2E TTFT and independent new `result.json` SHA. `P6_AB_BENCH_STATUS=RUNNING_APPROVED_EXISTING_SERVICE_LOAD`, final `PHASE6_AB_NEW_12X3_BENCH_RECORDED_EXISTING_SERVICE_NOT_A_PASS` only on complete success.
- Warning: the archived **2026-10-26/27** original corpus byte SHA and exact sampler/KV/cache conditions were not proven. Even if candidate ran identical static flags, declare strict old-vs-new improvement `UNVERIFIED`; use fresh matched pre-B/post-B later, and predefine regression thresholds prior to formal P6-D. The new run is for runner-validation and provisional reference, **not** for numerical blazux gain claims.

## Gate/status and stop conditions

| Component | PASS evidence | Missing / blocked |
| --- | --- | --- |
| Phase6 offline sources | New branch-specific unittest and Source Manifest PASS at exact tested SHA | New code is NOT_RUN until DGX operator log |
| P6-A live exposed metric | `PARTIAL_EXPOSED_RUNTIME_CACHE_METADATA` if published, otherwise `ABI_METRICS_NOT_USABLE` | Actual Scheduler/Mamba/group/table/GPU pointers always NOT_OBSERVED, P6-A `BLOCKED` |
| 12×3 script validation | `PASS_PROVISIONAL_PRE_B_36` with 36 measurements, 9 files SHA ledger + immutable baseline separate | Timeout, low RAM, identity drift, results incomplete = `INCOMPLETE` or `BLOCKED`, no automatic retry |
| P6-A→B official transition | **NOT** advanced by this run | Real P6-A ABI proof missing -> B `BLOCKED` |
| P6-D formal comparison | NOT_RUN | historic corpus/sampling/KV and accuracy/stability gates unresolved |

## Required DGX execution order (no remote access by assistant)

1. Pull `feature/blazux-phase6-runtime-gates` in dedicated clean `$HOME/Workspace/llm/blazux-phase6-gates` checkout; verify exact GitHub SHA (supplied after commit), source manifest and shell syntax.
2. `bash scripts/phase6-gate.sh` — CPU/offline regression only.
3. `bash scripts/phase6-a-live-observe.sh` — GET metadata only; its full A verdict stays BLOCKED, but must verify pinned identity and served ID.
4. `bash scripts/phase6-ab-provisional-run.sh --preflight` — no inference, verifies local baseline/runner/corpus/deployment/memory and staging.
5. `bash scripts/phase6-ab-provisional-run.sh --execute` — one approved bounded live 12×3 run. This sends real inference requests to the existing server, monitored, and never modifies container configuration.

Do not run under external client traffic or when operator knows service is under deadline/production load. Once stage 4 or stage 5 returns BLOCKED/INCOMPLETE, STOP and inspect only private local staged evidence. Never loosen guards silently, repeat failed runs automatically, delete partials, or publish unreviewed private files. Leave main/P0/Phase1–5 and all original benchmark inputs/results intact.
