# Phase6 A3b-0 CPU-only configuration-reproduction preparation (no execution approval)

## 2026-10-28 최신: 사용자 P6-A3b-1 격리 CPU-only 소스 조사 1회 명시 승인 (아직 DGX 실행 전)

- **사용자 승인 범위**: 기존 고정 이미지 ID로 일회용 `docker run --rm` **1회**, CPU-only 설치 vLLM 소스 SHA256/AST 확인만 승인. `scripts/phase6-a3b1-cpu-container-gate.sh --execute`가 유일한 승인된 진입점. GPU/모델·가중치/HF 캐시/운영 Docker stop/restart/exec/HTTP/벤치/CI/패치/PR/merge 및 실제 Scheduler/CacheConfig/MambaSpec 객체 생성은 승인하지 않음. 기존 preview 스크립트는 계속 비실행. [안전 실행 정본](BLAZUX-PHASE6-A3B1-CPU-ISOLATED-GATE.md).
- **직전 실제 DGX 테스트 코드 SHA** `7dc77164447bdd272b3ff791341d8ec5379a1edd`: Phase6 오프라인 테스트 **45/45 PASS**, Source Manifest **196/196 PASS**, P6-A3b-0 CPU 합성 그룹 LCM32/GCD16·가상 Mamba32/cache16, `PHASE6_A3B_CPU_PREP_DONE_NO_DOCKER_OR_ACTIVE_RUNTIME` 및 `PHASE6_A3B0_DGX_PREPARATION_VERIFIED_NO_RUNTIME`. 32/16은 실제 운영값이 아니며 patch/bug 증거도 아님. 새 GitHub 커밋의 코드는 DGX NOT_RUN; 목표 **57 test·200 source 파일은 기대값**, 새 HEAD의 검증 결과를 만들지 말 것.
- **새 A3b-1 fail-closed 경계**: clean Phase6 전용 checkout/전체 Manifest, `MemAvailable>=4GiB` 현재값, 운영 컨테이너 running 및 pinned digest 실행 전후 검증, 로컬 이미지 고정, `runc`, CPU 1/메모리 512MiB/total memory+swap 512MiB(별도 swap 불가), 네트워크·GPU·파일쓰기 제한, nonroot UID65534, drop ALL caps, no-new-privileges, HF offline. vLLM import/실제 config constructor 금지. 표준출력은 Python 독립 오라클로 8개 AST anchor+**7개 historical SHA 일치**만 allowlist 판정. KV resolver의 소스 SHA는 이번 검사에서 **미고정**(AST anchor만), 과대 표기 금지. 부적합 시 BLOCKED, 보안 완화·root fallback·자동 재시도 금지.
- **Gate 상태**: A3b-1 최종 PASS가 나와도 `PASS_PINNED_SOURCE_AST_ONLY` 한정. 실제 운영 중인 Scheduler 선택 클래스/CacheConfig·Mamba 그룹별 block_size/물리 block-table 및 CUDA 상태 주소 `NOT_OBSERVED`; **P6-A 실제 런타임 BLOCKED**, P6-B/C/D NOT_RUN/BLOCKED. 이전 A3a 호스트 MemAvailable 14085MiB, NVML GPU 메모리 N/A는 새로운 GPU 안전성 증거 아님. Pre-blazux 12×3 baseline/원본 보존, 역사적 corpus SHA/sampler/KV 비교 미확정, P6-D 여전히 BLOCKED. main/P0/Phase1~5 불변.


Status: HOST_STDLIB_PREPARATION_ONLY / CONTAINER_CPU_PROPOSAL_ONLY / P6-A_ACTIVE_RUNTIME_BLOCKED / GPU_MODEL_HTTP_BENCH_CI_NOT_RUN.

## Why this is a preparatory Gate

- DGX A3a measured `100ffb3ab3a4f0ca8edd6c201ec5af9fdc3b9ff1`: Phase6 28/28 unittest, Source190/190; image running and pinned; host MemAvailable 14,085 MiB; NVML memory total/free/used unavailable; GPU utilization 0%, temperature 35°C at one moment. These **do not establish extra GPU memory headroom**.
- Historical baseline runner/result SHA PASS, but corpus historical SHA, sampler and KV/cache parity remain unknown; P6-D stays BLOCKED.
- Previous DGX Phase5 inspected pinned preview source and Scheduler/Mamba contract. Its source SHA pins are reused; new image import-free AST probe is a *future* drift check, not active configuration recovery.

## Files and safe host run

- `src/phase6_a3b_cpu_config.py --fixture tests/fixtures/phase6_a3b_synthetic.json`: bounded strict-schema stdlib CPU arithmetic. Computes naive group LCM/GCD and flags conditional Mamba/CacheConfig block-size sensitivity. **The actual vLLM resolver has conditional early returns, group-specific DCP/hash/prefix rules**; the naive numbers are diagnostics, NOT predictions or expected runtime values. Synthetic fixture cannot prove the real running Scheduler class or block size.
- `scripts/phase6-a3b-cpu-prepare.sh`: exact Phase6 branch/clean checkout, Source Manifest, synthetic contract, safe Docker command preview. Never starts Docker/model/GPU.
- `scripts/phase6-a3b-container-preview.sh --preview`: **prints only** bounded proposed isolation. `--execute` or other flags fail CLOSED; there is no `docker run` execution path in the script. At A3b-0 preparation time there was no execution approval. User later explicitly approved **one** bounded P6-A3b-1 CPU-only SHA/AST source probe; see [new runbook](BLAZUX-PHASE6-A3B1-CPU-ISOLATED-GATE.md). The preview script stays inert.
- `tests/test_blazux_phase6_a3b_cpu.py`: strict/fail-closed synthetic fixture, missing data, mismatches, size bounds, symlinks, pinned source guard, and no-active-certification regressions.
- `src/phase6_a3b_cpu_config.py --installed-source-only`: prepared for a later separately approved CPU-only container. Uses Python stdlib `importlib.util.find_spec('vllm')` (does not import vLLM), source SHA256 and AST class/function anchors only. Never constructs CacheConfig, Scheduler, MambaSpec or GPU tensor. **It is not, by itself, a genuine config-construction reproducer.**

## Proposed separate CPU-only container authorization

Even CPU-only `docker run` can consume DGX RAM and interact with daemon state. The user has subsequently approved **one** bounded pinned-image CPU-only source probe via the separate audited A3b-1 gate. The original isolation proposal is retained below:

- `--runtime=runc`, `--pull=never`, immutable locally pinned digest, `--network=none`, `--read-only`, `--cap-drop=ALL`, `--security-opt=no-new-privileges`, `--user=65534:65534`.
- `--cpus=1`, `--memory=512m`, `--memory-swap=512m`, `--pids-limit=64`, temp writable tmpfs (max 64 MiB), **only** dedicated Phase6 checkout mounted read-only; no weights, GPU, HF cache, Docker socket, host process mount, privileged mode or operating ports.
- `CUDA_VISIBLE_DEVICES=-1`, `NVIDIA_VISIBLE_DEVICES=void`, offline HF/Transformers, Python bytecode off and explicit `PHASE6_A3B_CPU_INSPECTION_ONLY=1`. Run only allowlisted source SHA/AST verification, no imports or model constructors; on source drift/exception, BLOCKED.
- Verify existing legacy container still running with exact digest before and after future probe, and stop if free system memory, service health, isolation controls or source pins drift. Do not guess a safe allocation based on old A3a telemetry.

## What would be required for actual CPU config-constructor reconstruction?

Separately: full launch/config provenance (including custom Scheduler override and model-dependent grouped KV specs); inspect installed constructor/dependency side effects before importing vLLM or building configs; guarantee offline no HF model reads/writes and bounded host memory; compare default/AsyncScheduler factory branch, CacheConfig and per-group MambaSpec exact values with independent oracle. If input or constructor branches are incomplete, STOP/BLOCKED. A reconstructed CPU config from a different process is **not** evidence of the active legacy process or real GPU group tables and pointers. P6-A itself cannot PASS until those actual runtime values and block/state bounds are independently observed.

## Stop and evidence classification

Host synthetic output marker `PHASE6_A3B_CPU_PREP_DONE_NO_DOCKER_OR_ACTIVE_RUNTIME` is only prep completion. Image source marker `PHASE6_A3B_CPU_PREPARATION_ONLY_NOT_ACTIVE_CONFIG_VERIFIED` (future run, if approved) means pinned source anchor audit only. Neither constitutes `P6-A PASS` or approval for P6-B/C/D, patch, benchmark, CI, PR or merge. Source drift, missing fixture, wrong branch, dirty tree, or any attempt to run Docker without approval must STOP. Keep `main`, P0, Phase1–5 and pre-blazux baseline unchanged.

## Later A3b-0 DGX result and A3b-1 authorization

Actual A3b-0 DGX-tested SHA `7dc77164447bdd272b3ff791341d8ec5379a1edd`: 45/45 unittest, Source196/196, source-only fixture and Docker preview only. One separate `--execute` source SHA/AST CPU inspection has now been approved, with current resource/provenance preconditions. New 57/200 are expected, not DGX verified. See [P6-A3b-1 runbook](BLAZUX-PHASE6-A3B1-CPU-ISOLATED-GATE.md). Neither a source AST match nor a synthetic fixture reconstructs active Scheduler or GPU state.
