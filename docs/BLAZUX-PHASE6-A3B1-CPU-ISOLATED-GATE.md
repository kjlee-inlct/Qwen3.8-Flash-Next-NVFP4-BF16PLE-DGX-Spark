# P6-A3b-1 — explicitly approved isolated CPU-only pinned-source inspection

## 2026-10-28 최신 Phase6 실제 A 관찰 시도 + 승인된 기존 서비스 벤치 스크립트 검증 — 선행 상태

- **사용자 신규 실행 승인**: 실제 P6-A ABI 검증을 시도하고 이미 과거 Baseline이 있더라도 신규 벤치를 **스크립트 검증 목적**으로 수행, 오래된 문서를 갱신. 이 승인은 운영 서비스 재시작/변경·새 GPU 모델·blazux patch/CI/PR/Merge 권한이 아님. **DGX는 사용자 조작**, GitHub가 제공하는 스크립트를 검사해 실행하고 결과를 수집한다. [현재 실행·안전 경계 정본](BLAZUX-PHASE6-LIVE-ABI-AND-PRE-B-EXECUTION-20261028.md).
- **직전 실제 DGX 통합 검사 exact SHA `fb5deae540812a300cb8404a53a202e505c40577`**: Phase6 70/70 unittest PASS, Source204/204 PASS, 기존 2026-10-26/27 llama-benchy 12×3/36 pre-blazux result SHA·runner/tokenizer/frozen matrix PASS, `PLAN_READY_NOT_EXECUTED`, `PHASE6_AB_BENCH_PLAN_DGX_VERIFIED_NO_LOAD`. 70/204는 해당 소스 SHA 전용이며 새 GitHub 코드에 자동 귀속하지 않음.
- **신규 Phase6 P6-A 실제 노출형 관찰기**: clean checkout/source manifest·Docker pinned image/StartedAt/ID 전후 확인 후 loopback `GET /v1/models`, `GET /metrics`만 조회; vLLM `vllm:cache_config_info`가 이미 제공하는 경우만 block_size/prefix_caching/gpu_utilization의 allowlist 값 표시. 이 메트릭은 **시작 시 공개된 cache-config 값**이며 실제 Scheduler class/그룹별 MambaSpec/physical table·GPU state pointers를 증명하지 못함. 이 필드의 실제 in-process 안전 observer가 없으면 `P6-A ACTIVE ABI BLOCKED` 유지. `docker exec`, ptrace, live code instrumentation, 2nd model start는 이 승인에 포함되지 않음.
- **신규 Phase6 P6-AB 실제 부하 검증**: `scripts/phase6-ab-provisional-run.sh --preflight`(무부하) 후 `--execute`(기존 `127.0.0.1:8000/v1` 모델에 **추론 부하 12조건×3회/총36회**). P6-A 여전히 BLOCKED이므로 결과를 **PROVISIONAL_PRE_B_EXISTING_SERVICE_NOT_GATE_PASS**로만 기록. Pre-blazux 원본은 불변; private staging에 별도 `phase6-pre-b-provisional` 새 결과 + SHA·36 raw repeats 및 허용된 공개용 12조건 numeric summary. Runner/head·Tokenizer·현재 corpus 해시·Docker image/StartedAt·RAM ≥8GiB preflight, 진행 중 RAM <4GiB 또는 identity drift/1시간 초과시 **벤치 자식 프로세스 그룹만 중단**, 레거시 운영 컨테이너 stop/restart/exec 절대 하지 않음. 현재 데이터만으로 정상 서비스 응답시간 불변을 보장하지 않으며 부하 시 영향 가능.
- **새 HEAD GitHub 소스 상태**: 신규 A observer 12 synthetic/offline tests + 벤치 watchdog/결과 검증 17 tests, 새 runbook 등으로 기존 70건에서 **99건 예상**, Source204에서 **211 tracked 파일 예상**. **신규 HEAD DGX NOT_RUN**이며 결과를 받기 전 PASS 주장 금지. P6-B/C/D 미실행. 과거 Baseline의 실제 corpus SHA·샘플링·KV(cache) 동일성 여전히 미확정 → 원본↔신규 strict 성능 개선율 금지; 새로운 같은 조건 PRE-B/POST-B 쌍으로만 추후 비교 가능. `main`/P0/Phase1–5, 고정 이미지/기존 서비스/원본 Baseline 보호.


## 2026-10-28 최신 결정: P6-A → P6-AB 성능 체크포인트 → P6-B (계획 승인, 추론/벤치 실행 미승인)

- **사용자 요청**: P6-A에서 P6-B로 이동하기 전 벤치마크를 남겨 추후 B/C 개선·회귀를 판단할 기준점 확보. [P6-A→B 벤치 체크포인트 정본](BLAZUX-PHASE6-A-TO-B-BENCH-CHECKPOINT.md)을 신설; **옵션/권장 중간 성능 기록**이며 A/B/C correctness 및 P6-D 공식 성능 Gate를 대체하지 않음.
- **최근 DGX 사용자 실제 확인 SHA** `0ad5e62caab2e95c57813cc6401d2f00622f3f4f`: Phase6 57/57 unittest PASS, Source200/200 PASS, CPU-only 1회 고정 이미지 소스 AST 8컴포넌트·역사적 SHA 7개 검증 `PASS_PINNED_SOURCE_AST_ONLY`, 운영 컨테이너 실행/고정 이미지 동일성 전후 PASS, 호스트 MemAvailable=14064MiB, `PHASE6_A3B1_DGX_SOURCE_PROBE_COMPLETED`. **실제 활성 Scheduler/CacheConfig/MambaSpec/물리 table/state pointer는 미관측**, P6-A 실제 ABI `BLOCKED`; P6-B/C/D NOT_RUN.
- **지금 구현한 중간 단계 P6-AB-0**: 최초 pre-blazux `result.json` SHA256 `25f6abf3968efbf94cf08b02297140f7be2e8b29f8f2192b1d246e7432959edf`와 12조건×3회 원본 숫자, `environment.public.json`의 runner/tokenizer 및 반복·seed를 검증하는 `scripts/phase6-ab-benchmark-plan.sh` 및 CPU stdlib 계약 검사만 포함. **신규 추론·벤치 측정은 하지 않음**; 이번 코드 HEAD는 DGX NOT_RUN, 신규 **13 unittest/4 tracked files**, 다음 기대 총 Phase6 **70 tests / Source204** (실제 DGX PASS는 아직 아님).
- **향후 진짜 PRE-B 재측정 P6-AB-1**: P6-A 실제 PASS, 격리 후보 또는 운영 API 대상의 구체적 HTTP/GPU 부하 및 모델 접근 승인, 동일 12×3·1 warmup·3 repeats, runner/tokenizer/corpus SHA, 샘플링·KV/cache 및 컨테이너 환경·자원 기록을 조건으로 별도 36회; 기존 `scripts/benchmark/run-llama-benchy.sh`는 운영 `127.0.0.1:8000`을 대상으로 하므로 **허가 없이 실행 금지**. 원본 pre-blazux 실측과 새 PRE-B 결과는 독립 저장, 과거 corpus/sampler/KV 동등성이 없으면 **strict A/B 비교 BLOCKED**; 대신 향후 동일 조건의 pre-B/post-B 신규 쌍으로 비교할 것. 임계값은 사전 승인 전 미확정. P6-AB-1 벤치 실행 자체는 이번 메시지의 계획 요청으로 별도 명시 승인된 것이 아님.
- main/P0/Phase1–5, PR#5 원본 baseline, 기존 DGX 운영 Docker/서비스/포트/HF cache 불변; blazux 패치, 모델/GPU 벤치 실행, CI, PR, Merge 없음. 신규 문서/Source Manifest를 동일 Phase6 브랜치 단일 커밋으로 맞추고, 정확한 마지막 DGX-tested SHA와 후속 문서/소스 HEAD 구분.


Status: USER_APPROVED_CPU_ONLY_ONCE / GITHUB_IMPLEMENTATION_PREPARED / DGX_NEW_SHA_NOT_RUN / ACTIVE_P6_A_BLOCKED. No approval for real Config/Scheduler construction, GPU, model load, HTTP, inference benchmark, CI, patch, PR or merge.

## Approval and verified prerequisite

- User explicitly replied `승인` after requesting a bounded P6-A3b-1 transient CPU-only container check. This approval covers **one** pinned-image ephemeral `docker run` to inspect source SHA/AST; it is not a general authorization for model/container experiments.
- Last DGX-measured Phase6 source HEAD `7dc77164447bdd272b3ff791341d8ec5379a1edd`: 45/45 offline tests PASS, 196/196 full tracked manifest PASS, synthetic CPU fixture group LCM=32/GCD=16, `PHASE6_A3B_CPU_PREP_DONE_NO_DOCKER_OR_ACTIVE_RUNTIME`, `PHASE6_A3B0_DGX_PREPARATION_VERIFIED_NO_RUNTIME`. Synthetic block 16 vs 32 does **not** prove actual mismatch or runtime defect.
- Earlier A3a snapshot: host MemAvailable 14,085 MiB, SwapFree 8,735 MiB, GPU memory counters unavailable; this is not current memory or safe GPU/model concurrency evidence. Recheck current `/proc/meminfo` immediately before CPU-only invocation; STOP below 4 GiB available.
- Next code commit is distinct from DGX-tested `7dc771...` and must remain NOT_RUN until user supplies its terminal output.

## New tracked entrypoint

`scripts/phase6-a3b1-cpu-container-gate.sh --execute` requires the exact Phase6 branch, clean dedicated checkout and complete Source Manifest, then checks current host MemAvailable, the operational container's pinned running identity, and local immutable Docker image ID before any `docker run`.

Only one ephemeral container is started. It uses the existing pinned image **by image ID** `sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a`; `--pull=never --rm --runtime=runc --network=none --read-only --cap-drop=ALL --security-opt=no-new-privileges --cpus=1 --memory=512m --memory-swap=512m --pids-limit=64 --user=65534:65534`, a bounded `/tmp` tmpfs and **only** the clean dedicated Phase6 checkout bind-mounted read-only. No mounts for weights, HF cache, Docker socket, host process namespace or GPU devices; no `--gpus`, ports, privileged mode, pull, exec, stop or restart of legacy. HF/Transformers offline, CUDA/NVIDIA visible devices off, Python bytecode off. Docker incurs temporary daemon/container overhead; `--rm` removes this ephemeral container at normal exit.

The container executes **only** `src/phase6_a3b_cpu_config.py --installed-source-only` with stdlib import-free AST. It does not import vLLM, initialize CacheConfig or Scheduler, create real MambaSpecs, load checkpoint/GPU memory, perform inference or call HTTP. The probe compares **7 installed source file hashes** against previously captured Phase5 DGX SHA256 and checks **8 AST components** including the KV block-size resolver method (whose file SHA is **not pinned** by this probe). Class/function NAME anchors do not establish correct runtime branch binding.

`src/phase6_a3b1_evidence.py` independently requires the exact audit JSON schema, all eight components, seven pinned SHA matches, non-executed `vllm_modules_imported=false`, and the explicit sentinel. Raw container stdout is not echoed; Docker stderr is suppressed. `BLOCKED` on drift, missing image, missing permissions, unexpected output, or incomplete contract. No automatic root fallback or rerun.

The script checks the original legacy container's pinned running identity **again after** the disposable run, even if the probe failed. An unchanged identity is a necessary guard, not a proof that inference quality and availability were unaffected. A new container start or Docker daemon action does not happen under the original `scripts/phase6-a3b-container-preview.sh`: that preview remains inert.

## PASS/FAIL/BLOCKED classification

| Observed operator marker | Meaning |
| --- | --- |
| `PASS_SOURCE_ONLY: 200 tracked file(s)` | Expected new full source-tree integrity check at new SHA; not a runtime test |
| `Ran 57 tests` / `OK` | Expected previous 45 + 12 new synthetic/static tests, not yet DGX verified |
| `P6-A3B1_BEFORE=PINNED_LEGACY_RUNNING`, `P6-A3B1_AFTER=PINNED_LEGACY_RUNNING` | Legacy metadata identity preserved across the bounded probe |
| `status=PASS_PINNED_SOURCE_AST_ONLY` and 8 components / 7 historic hashes | Source SHA/AST probe PASS, **not** actual active Scheduler/Mamba/cache configuration |
| `PHASE6_A3B1_CPU_ISOLATED_PINNED_SOURCE_PASS_NOT_ACTIVE_RUNTIME` | The one approved isolated CPU inspection completed normally |
| `BLOCKED` or no final marker | Do **not** claim success or retry by weakening security; investigate read-only with operator evidence |

Strict active P6-A stays **BLOCKED** until real selected Scheduler class/CacheConfig, MambaSpec group blocks, live block-table and physical GPU tensor bounds have an approved independent observer. P6-B/C/D remain NOT_RUN/BLOCKED. The pre-blazux 12x3 baseline, historic corpus mismatch unknown, sampling/KV comparability and P6-D threshold approval are unchanged. CI, patch, PR/merge and main/P0/Phase1–5 are protected.

## Approved DGX execution sequence

Use exact new GitHub SHA (to be supplied after atomic commit) and the dedicated checkout only; check clean branch before `git pull --ff-only`. Run `bash scripts/phase6-gate.sh` once, then `bash scripts/phase6-a3b1-cpu-container-gate.sh --execute`. Never execute the old preview as if it were the approval-gated run.

## Operator A3b-1 result, successor performance-freeze plan

The user actually ran the approved CPU source scan at exact Phase6 SHA `0ad5e62caab2e95c57813cc6401d2f00622f3f4f`: 57/57 unittest and Source200/200 PASS; legacy running identity matched before/after, host MemAvailable 14064 MiB, `PASS_PINNED_SOURCE_AST_ONLY`, 8 source AST components and 7 historical SHA matches. CPU-only inspection was successful within source scope; **active Scheduler/cache/Mamba/group/physical state unobserved** and P6-A real ABI remains BLOCKED. Following user request, a [pre-B benchmark reference plan](BLAZUX-PHASE6-A-TO-B-BENCH-CHECKPOINT.md) is added, but no new inference/benchmark execution is authorized.

## Successor phase6 live observation / benchmark approval — current status

A3b-1 original SHA `0ad5e62caab2e95c57813cc6401d2f00622f3f4f` was operator-confirmed 57/57 and Source200/200, pinned CPU AST source only. More recently Phase6 P6-AB-0 at `fb5deae540812a300cb8404a53a202e505c40577` verified 70/70 and Source204/204, frozen old baseline 36x numeric matrix. New user-approved P6-A *actual exposed metric* read-only attempt and a monitored single 12×3/36 live benchmark on the existing service are documented in [runbook](BLAZUX-PHASE6-LIVE-ABI-AND-PRE-B-EXECUTION-20261028.md). They do not imply ability to observe real Python scheduler class, per-group MambaSpec, physical pointers, nor permit GPU model start/restart/patch/CI/B or C.
