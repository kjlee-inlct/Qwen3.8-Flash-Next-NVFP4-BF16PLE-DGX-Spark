# Track A Phase 5 — Mamba physical-address grouped Gate / Phase 6 readiness

## 2026-10-28 Phase6 P6-A3a DGX 실측 및 다음 진입 경계 — 최신

- **DGX 사용자가 실제 실행한 SHA**: `100ffb3ab3a4f0ca8edd6c201ec5af9fdc3b9ff1`; 전용 `~/Workspace/llm/blazux-phase6-gates` checkout fast-forward 후 Phase6 unittest **28/28 PASS**, Source Manifest **190/190 PASS**, `PHASE6_PREPARATION_OFFLINE_PASS_RUNTIME_NOT_RUN`. 읽기 전용 자원 관찰 결과 `PHASE6_A3A_PASSIVE_RESOURCE_OBSERVATION_COMPLETED_NOT_GPU_CERTIFIED`, 최종 `PHASE6_A3A_DGX_OBSERVATION_COMPLETED`.
- **A3a 관측값 (snapshot)**: 운영 컨테이너 running=true, pinned image digest match=true, Docker 명시적 memory limit 없음(`null`); 호스트 `MemTotal=124543 MiB`, `MemAvailable=14085 MiB`, `SwapTotal=16383 MiB`, `SwapFree=8735 MiB`. GPU NVML은 단일 device에서 `utilization=0.0%`, `temperature=35°C`, `memory.total/free/used=N/A`여서 GPU telemetry `PARTIAL`. 순간적으로 관측한 숫자이며 별도 GPU/모델을 띄울 수 있는 용량·운영 간섭 부재를 증명하지 않음. `explicit_container_memory_limit_mib=null`은 무제한 물리 GPU 메모리 증거가 아님.
- **정확한 상태 구분**: P6-A3a `OBSERVED_METADATA_ONLY`, P6-A 활성 Scheduler/CacheConfig/MambaSpec/physical block-table/state pointers **NOT_OBSERVED/BLOCKED**; P6-B/C/D `NOT_RUN/BLOCKED`; 기존 운영 서비스 변경, GPU 계산, 신규 모델 load, HTTP, CI, benchmark, blazux patch/PR/merge **실행하지 않음**. 이전 A2 baseline raw result/runner SHA PASS, 기존 Gutenberg cache SHA `8a2f79a2f4601cfe6e25830c29c1a25c7a3d906285a989948117568f8077ab2c`; baseline 당시 corpus SHA·sampling/KV 동일성 여전히 미확정 → P6-D 차단.
- **다음은 P6-A3b 관찰 방법 승인 설계**: 기존 비침습 인터페이스로 활성 객체를 노출하는지 먼저 확인(관측 가능한 부분만); 불가능하면 PIN된 이미지를 사용한 격리 CPU-only 구성 재현은 별도 `docker run` 승인과 자원 제한 필요(재현된 구성은 운영 프로세스 실측이 아님). 실제 block-table/tensor ptr·stride는 별도 GPU/model 실행 또는 지원되는 관측기 없이는 검증 불가. 이번 메모리 snapshot만으로 단일 DGX에서 GPU 모델 동시 실행 승인 금지; 기존 서비스에 attach/ptrace/debug/exec 금지. [A3 관찰 및 승인 결정](BLAZUX-PHASE6-A3-RESOURCE-OBSERVATION.md).
- 이번 후속 정본/Manifest 커밋은 **문서 전용, DGX 신규 시험 NOT_RUN**. **28/28·190/190은 오직 위 정확한 소스 SHA에 귀속**. `main`/P0/Phase1–5 및 PR#5 벤치 원본 불변; 신규 PR/Merge/CI 없음.


## 2026-10-28 이전 P6-A3a 준비 계획 (역사적 기록; 실측 완료)

- **가장 최근 실제 DGX 테스트 SHA**: `0513b118260047b9965e16b20bdadf690c112c5d` — Phase6 offline **15/15 PASS**, full Source **186/186 PASS**; A2 preflight pinned running Docker image PASS, baseline original SHA256 및 llama-benchy runner SHA PASS. Current Gutenberg cache SHA `8a2f79a2f4601cfe6e25830c29c1a25c7a3d906285a989948117568f8077ab2c`; historical corpus SHA unavailable and sampling/KV unknown, strict A/B BLOCKED. Subsequent `be7a463274765627d0fd0da3a9d70907c5f0cf83` is **docs/Manifest-only** and NOT separately DGX tested.
- **이 커밋의 신규 P6-A3a**: `scripts/phase6-a3-readonly-resources.sh` + `src/phase6_a3_readonly_resources.py` + 13개 stdlib regression + [A3 read-only Gate/decision](BLAZUX-PHASE6-A3-RESOURCE-OBSERVATION.md). Old 15 + new 13 = **28 expected** Phase6 tests, full **190 expected tracked source files**; both counts NOT_RUN on new commit until operator DGX log. Existing operational container identity via `docker inspect`, host `/proc/meminfo`, optional `nvidia-smi` passive NVML metrics only. `nvidia-smi` N/A on unified-memory DGX is PARTIAL/UNAVAILABLE, **not** zero or sufficient GPU headroom.
- **Gate boundary**: A3a completed metadata never equals P6-A runtime PASS. Actual selected Scheduler object, effective CacheConfig/MambaSpec block sizes, Mamba group table and physical GPU tensor allocations/pointers are still `NOT_OBSERVED`; P6-A/B/C/D runtime BLOCKED. CPU-only configured reproduction or isolated GPU/model inspection requires separate scoped approval, startup memory budget and zero legacy interference proof. No `docker exec/run`, live process attach/ptrace, model start, GPU computation, HTTP, benchmark, CI, blazux patch, PR or merge under this approval.
- Only Phase6 GitHub branch may change; `main`, P0, Phase1–5 and original benchmark baseline remain immutable. Same commit updates handoff + adoption + exit boundary + Phase6 results/plan + all-tree Source Manifest. Latest GitHub commit SHA of this documentation update is not a new DGX-tested commit.


## 2026-10-28 Phase6 A2 DGX verified — earlier checkpoint

- **Exact DGX operator-tested SHA** `0513b118260047b9965e16b20bdadf690c112c5d`, dedicated `~/Workspace/llm/blazux-phase6-gates` checkout, ff-only fast-forward from `c7f4ca7`. Bash syntax passed; Phase6 unittest **15/15 PASS**; `PASS_SOURCE_ONLY: 186 tracked file(s)` at exact SHA, `PHASE6_PREPARATION_OFFLINE_PASS_RUNTIME_NOT_RUN`. Read-only preflight ended `PHASE6_A2_READONLY_PREFLIGHT_COMPLETED_NOT_RUNTIME_CERTIFIED` and user shell `PHASE6_A2_PREFLIGHT_DGX_COMPLETED`.
- **Observed deployment-only evidence**: pinned image digest match=true, running=true; allowlisted launch flags `--gpu-memory-utilization=0.8`, `--max-model-len=262144`, `--max-num-batched-tokens=8192`, `--max-num-seqs=8`. `deployment.status=PASS` applies solely to Docker metadata; it does **not** verify process-selected Scheduler class/CacheConfig, MambaSpec blocks/groups or physical GPU state.
- **Benchmark evidence**: baseline raw result SHA256 match=true; pinned llama-benchy runner Git SHA match=true; cached Gutenberg corpus SHA256 `8a2f79a2f4601cfe6e25830c29c1a25c7a3d906285a989948117568f8077ab2c`, but **historical corpus SHA not available** and `historical_corpus_matches_current=null`; sampling/KV equivalence `UNVERIFIED`. The cached bytes' current hash does not prove what was used during the historical 2026-10-26/27 baseline. No P6-D comparison, benchmark execution, regression thresholds, or throughput claim authorized. [Benchmark rules](BLAZUX-PHASE6-BENCHMARK-GATE-RULES.md).
- **Gate classification**: `P6-A2 passive preflight=COMPLETED` with deployment PASS and benchmark PARTIAL, but `P6-A REAL ACTIVE RUNTIME=BLOCKED`; `P6-B/C/D=NOT_RUN/BLOCKED`. Next decision: distinguish (A3a) non-intrusive source/launch metadata, which cannot certify active Python objects, from (A3b) active Scheduler/Mamba/group/pointer observation that requires a separately authorized, safe and feasible observer/isolated GPU plan. Do not attach/deploy/instrument the running service or invoke Docker exec/run, live model, GPU, HTTP, CI or benchmark under existing approval.
- Historical Phase5 DGX-tested code SHA remains `780b780fc7572226a6a9ff2e52cd8e1921c8738b`; previous Phase6 offline exact SHA `c7f4ca71c4c5e54bea849e90c962e56ab24e9b8b`. This follow-up **documentation/manifest commit is not DGX-tested**; a new HEAD does not inherit the 15/15 run. main/P0/Phase1–5 protected; no patch/PR/merge.


## 2026-10-28 Phase6 A1/A2 previous checkpoint

- **DGX measured exact Phase6 code SHA** `c7f4ca71c4c5e54bea849e90c962e56ab24e9b8b`: dedicated `~/Workspace/llm/blazux-phase6-gates` clean checkout, 7/7 Phase6 unittest PASS, 182/182 Source Manifest PASS, `PHASE6_PREPARATION_OFFLINE_PASS_RUNTIME_NOT_RUN`, final `PHASE6_DGX_OFFLINE_GATE_COMPLETED`. The same SHA operator's **A1 source-only** log ended `PHASE6_A1_READONLY_SOURCE_INVENTORY_COMPLETED`; image tag `yslab-qwen38-bf16ple:9492b78c`, image ID short `b0984c4b724b`; `P6_A_RUNTIME_STATUS=BLOCKED`. Do not attribute these DGX results to the newer GitHub commit.
- **Next bundled step** on dedicated DGX checkout after `git pull --ff-only`: `bash scripts/phase6-gate.sh` (new offline unit suite+manifest) followed by `bash scripts/phase6-readonly-preflight.sh` (Docker `inspect` metadata ONLY + fixed pre-blazux result SHA, bench runner SHA, cached current Gutenberg corpus hash and optional historical private corpus SHA, no private raw data output). The latter prints `PHASE6_A2_READONLY_PREFLIGHT_COMPLETED_NOT_RUNTIME_CERTIFIED`. Its deployment `PASS` is solely pin/running metadata, not active Scheduler, MambaSpec/group, tensor pointer/stride, actual GPU address, or active config correctness. P6-A overall stays **BLOCKED**.
- [Frozen Phase6 benchmark comparison rules](BLAZUX-PHASE6-BENCHMARK-GATE-RULES.md) require original 12×3 immutable raw Baseline, runner and tokenizer/seed, corpus and sampler parity, equivalent cache/KV/environment, correctness P6-A/B/C, and preapproved regression thresholds. Legacy `scripts/benchmark/run-llama-benchy.sh` targets production port 8000 and has NOT_RUN wrapper status: **do not execute** for Phase6 without separate benchmark/isolation approval.
- User has not authorized DGX GPU, real model loading, HTTP/benchmark, CI, operational change, any blazux runtime patch, PR, or merge. A2 is explicit user-operated read-only observation, NOT permission to launch new compute; all new Phase6 code on the fresh commit is NOT_RUN until operator log. Main/P0/Phase1–5 remain untouched. Update these canonical docs and entire Source Manifest together.


## 2026-10-28 Phase6 implementation-preparation approval (current)
- User approved **new Phase6 branch + offline Gate scripts/tests/docs + GitHub commit only**. DGX/GPU/CI/operational service/model/patch/PR/merge are NOT approved.
- Phase6 branch `feature/blazux-phase6-runtime-gates` starts from Phase5 docs-only `11fd777e2c49c030eee671133ab0af3a3ca9c26d`. Phase5 tested SHA remains `780b780fc7572226a6a9ff2e52cd8e1921c8738b` (G1–G8 source/CPU PASS). No Phase5 repeat.
- [Phase6 gate plan](BLAZUX-PHASE6-GATE-PLAN.md) and [Phase6 result ledger](BLAZUX-PHASE6-RESULTS.md) are canonical. `scripts/phase6-gate.sh` is offline-only; supplied JSON fixture PASS is **not** active DGX P6-A PASS. Runtime P6-A/B/C/D remain BLOCKED. Separate explicit approvals required for every runtime scope.
- Phase6 implementation and documentation plus full Source Manifest are one commit on Phase6 only. Preserve main/P0/Phase1–5 heads, no PR/merge. No DGX test claim on documentation/implementation SHA.


## 2026-10-28 현재 이관 상태 (Phase6 실행 미승인)

- Phase5 source/CPU offline scope는 exact DGX-tested `780b780fc7572226a6a9ff2e52cd8e1921c8738b` (310/310 XFAIL0, Source177, G1–G8)에서 종료되었다. Phase5 종료 재시험 계획 없음; 새 대화는 [SESSION-HANDOFF-PROMPT.md](SESSION-HANDOFF-PROMPT.md)의 최신 **Phase6 범위 확정만 진행** 진입점부터 시작할 것.
- 남은 일은 P6-A 실제 설정/ABI, P6-B 격리 GPU state/prefix, P6-C real MTP/Parser/Tool/Responses, P6-D 정확성 후 TPS/메모리/안정성의 묶음 검증 설계와 승인 요건이다. 모두 **NOT_RUN/BLOCKED**, blazux 패치 승인 없음. 운영 서비스/모델/GPU/CI/Phase6 branch/PR/merge는 명시적 승인 전 수행 금지.
- 2026-10-28 확인: Phase5 선행 문서 HEAD `a205a3f958c250e2e30cb20fc99424666b2e0ff5`, open PR 0, Actions run 0, commit statuses 0. 후속 docs-only HEAD를 DGX-tested SHA로 귀속하지 말 것.


## 2026-10-28 Exit decision (CURRENT): Phase5 SOURCE/CPU OFFLINE PASS, Phase6 runtime NOT_RUN

- **DGX tested code `780b780fc7572226a6a9ff2e52cd8e1921c8738b`**: Manifest **177/177**, Wizard **38/38**, unit **310/310 XFAIL0**, AST/offline wrapper PASS, source/CPU G1–G8 PASS, G8 **13,824 synthetic configurations / 23,552 spans**, embedded `25528` checks, required final shell marker PASS. This resolves the *historical* `ff1f66a7928aa5191d9574ccb4fbcba8c6f4d6f5` G8 descriptor FAIL. [Newest evidence](BLAZUX-PHASE5-DGX-GROUPED-GATE-RESULTS-20261028.md).
- **Phase5 offline exit status: PASS, scoped only to pinned preview source contracts and CPU synthetic oracles.** Original physical GPU buffer access, actual config equality/group/slot bounds, real speculative state and prefix hits, HTTP/MTP/Parser/Responses, performance and CI remain NOT_RUN/BLOCKED. Neither patches nor Phase6 GPU testing are approved by this evidence.
- **Phase6 grouped entry plan awaiting separate scope approval**: P6-A read-only active config/block size/group/ABI observation; P6-B guarded GPU Mamba state rollback/prefix correctness on isolated reproducer; P6-C real MTP acceptance and Tool/Responses protocol; P6-D benchmark regression/stability only after correctness. Define PASS/FAIL/BLOCKED/NOT_RUN + exact model/runtime/image fingerprint; do not mistake static/synthetic for runtime. Never create Phase6 branch or alter serving/GPU/weights/CI/PR before explicit approval.
- **Persistent operating rule**: any new rule, result, error and handoff delta must be committed together to source manifest, handoff, adoption plan, this exit gate, and authoritative evidence on current approved branch. Do not force user to download tools; GitHub CAS commit then dedicated checkout fast-forward pull. Keep tested SHA vs later documentation-only SHA separate and protect main/P0/Phase1–4.


## 2026-10-28 G8 fail-closed 및 새 영구 문서 규칙

`ff1f66a7928aa5191d9574ccb4fbcba8c6f4d6f5`의 첫 G8 DGX 시도: Source177/177와 Wizard38/38 PASS, 전체 310 unittest는 **FAILED(errors=15)**; Python descriptor 함수 바인딩 `cls.f`에 암묵적 `self` 전달된 신규 테스트 코드 오류. **Group B/G1–G8 NOT_RUN**. 같은 Phase5에서 `staticmethod`로 수정, 기존 test에서 descriptor를 검사하도록 보강. 로컬 참고값 13,824/13,824 synthetic fixture PASS는 **DGX 전체 Gate PASS가 아님**. 완료된 마지막 실제 DGX 전부 PASS `3c364209`: 300/300, Source176, G1–G7. 신규 Github 수정 HEAD 재실행 전 Phase5 G8 종료 주장 금지.

신규 운영 규칙: 규칙/증거/오류/핸드오프 누락 확인 시, **SESSION-HANDOFF-PROMPT.md + 적용 계획 + 해당 정본 보고서/종료기준 + Full Source Manifest를 항상 같은 Phase5 브랜치의 동일 커밋에서 동기화**. 다음 실행은 Github 직접 커밋→DGX 별도 Phase5 checkout의 `git pull --ff-only`→**통합 Gate 한 번**. Phase6 새 브랜치/PR/Merge 및 실 GPU/운영/patch 변경은 별도 승인 전 금지.


> **G1–G7 DGX PASS at 3c364209 / first G8 ff1f66a DGX FAIL / fixed HEAD DGX NOT_RUN / GPU-RUNTIME NOT_CERTIFIED / PATCH_APPROVAL ZERO.** This is a Phase 5 check and does not itself authorize a new phase, real GPU/model access, CI, or runtime patching.

## Evidence provenance

- Last actual full DGX Gate PASS remains **tested code HEAD `3c36420998061f7a3e656eb77390c04b7d2ef935`**, unit **300/300**, XFAIL=0, source **176/176**, G1–G7 PASS. Later source `ff1f66a` **FAILED 310 unittest** because of new G8 Python descriptor binding; Group B/G1–G8 NOT_RUN at that SHA. The new binding fix HEAD has not been fully DGX tested yet.
- User DGX source-only evidence in [fused-kernel body report](BLAZUX-PHASE5-DGX-MAMBA-FUSED-KERNEL-BODIES-RESULTS-20261027.md) and [physical state/metadata report](BLAZUX-PHASE5-DGX-PHYSICAL-STATE-METADATA-RESULTS-20261028.md). Installed `v1/worker/mamba_utils.py` pinned SHA256 `25254d005f42b64dd55d15a5c646018f5599d971c23e7ca395eb5acaf4f41ed3`, physical helper lines 122–252, metadata lines 843–957.
- This commit introduces `scripts/phase5-mamba-batch-check.sh` and `tests/test_blazux_phase5_mamba_batch_gate.py` (24 locally executed synthetic/unit cases, **not** full DGX run). A pinned installed vLLM source SHA drift blocks verification.

## One pull, one bundled command

Use only the separate dedicated Phase 5 checkout; never pull in the operational `yslab-qwen38-bf16ple-dgx-spark` checkout. After guarded `git pull --ff-only`, run:

```bash
scripts/phase5-mamba-batch-check.sh
```

The tracked script rejects wrong origin/branch, dirty checkout and missing Phase 4 ancestor. GROUP A runs `scripts/phase5-check-offline.sh` (manifest, wizard mocks, **all** unittest, AST, shell syntax and publication audit). GROUP B uses `docker inspect` only for an existing serving container's image ID, then starts a **disposable**, network-none, read-only, no-GPU, runc, CPU-limited container without serving/model mounts, for G1–G7:

| Group | Coverage | Certification boundary |
|---|---|---|
| G1 | Installed Python source hashes for four pinned files, AST parse | Original version identity only |
| G2 | Copy/helper, group block table, metadata, context, pre/postprocess original source anchors | Source contract, not a CUDA run |
| G3 | V1/V2 batch-row vs request-slot, negative sentinel, fresh/same-column | Synthetic/source checks |
| G4 | Multiple Mamba group table selection, int32 element offset, int64 physical ID, byte stride | Synthetic physical arithmetic |
| G5 | SD/DS conv accepted bias, temporal selection, page padding/natural payload | Synthetic byte-copy |
| G6 | B_cache=B_mamba and unequal, zero, resumed, boundary and partial-tail | Math sensitivity, **not an observed bug** |
| G8 | 8×8 source/destination alignment, u64 head/body/tail vs byte fallback; 13,824 synthetic tile-partition combinations, no gaps/overlap | CPU proof only; not actual Triton GPU memcpy |
| G7 | Spec acceptance, self-column+bias, zero/negative/OOB and partial tail | Stronger CPU oracle bounds, **not Triton guards** |

The bounded `_memcpy_u64_tiled` original function **body** is also printed; synthetic byte-tail PASS alone does **not** certify Triton uint64 alignment, masking, aliasing or tiled runtime correctness. The final expected marker is `PASS: PHASE5_BATCH_OFFLINE_AND_PINNED_SOURCE_EXECUTED_NOT_CERTIFIED`. Every earlier group must finish for the wrapper to print it. Record actual test count, Source Manifest count and source SHA from output; never pre-label new HEAD as DGX PASS.

## Exit criteria and Phase 6 no-omission handoff

Evaluate each as **PASS / FAIL / BLOCKED / NOT_RUN**, rather than allowing empty items to appear as passes.

1. Repository: same Phase 5 branch, full path/mode/blob Source Manifest matching Tree, approved origin and clean checkout, protected main/P0/Phase1–4 unchanged, no Phase 5 PR/Merge. Preserve separately the **DGX-tested code SHA** and later **docs-only commit SHA**.
2. Offline Gate: manifest, all unit/XFAIL0, mock and source AST, shell syntax and publication audit, plus pinned installed source/fused helpers printed without truncation.
3. Mamba contract: CacheConfig seed/Scheduler split vs MambaSpec/context/align block size semantics; V1/V2 batch-row and request slot mapping, sentinel; group-local table base; physical ID and byte offsets; DS/SD conv/temporal, speculative bias, tiling and negative boundary cases.
4. CPU oracle: equal/unequal blocks, fresh/resumed, exact boundary, partial tail, zero, same-column/bias, multi-group and page strides, OOB reference check. **Synthetic checks never prove GPU correctness.**
5. **Explicitly NOT verified** by this batch: active running CacheConfig and MambaSpec values, actual group inventory and branch reachability, concrete state tensor physical bounds, CUDA copy/rollback/prefix cache hit, real inference or MTP acceptance, Parser/Responses, TPS and CI. These remain visible requirements if Phase 6 scope needs them.
6. **Phase 6 boundary**: completion of this Phase 5 source/CPU suite means only that those *offline* gates are ready. Do not create Phase 6 or launch real model/GPU/CI/tests, deploy patches, modify service/weights/cache, or alter protected refs without separate explicit user authorization of that scope.

The full G1–G8 offline DGX log has now been recorded at exact tested SHA 780b780f (310/310, Source177, G8 13,824). Future runs should be Phase6 scope-approved and grouped, not redundant Phase5 source/CPU reruns. Keep remaining risks visible, do not make duplicate evidence commits.
