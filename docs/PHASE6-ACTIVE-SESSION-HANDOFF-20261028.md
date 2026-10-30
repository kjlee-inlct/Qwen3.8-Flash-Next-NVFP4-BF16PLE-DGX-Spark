# P1 Prefix-cache — 현재 진행 작업 인수인계 (2026-10-29)

> **2026-10-30 P1 3rd DGX GPU result and next source-only diagnostic (new HEAD GPU NOT_RUN):** feature HEAD ce046bdc420cc94818cdfa018564cd5d0bb94af8 CPU **110/110 PASS**, Source **277/277 PASS**; candidate HIT [0,6400,6400,6400], identical output tokens, MTP accepted +400; state **24 events/96 samples**, 4 windows each 4 events/16 samples; aggregate 4 SHA matches, zero mismatches but pooled HIT comparison insufficient. Strict Cold/HIT max **0.0003418332780711353** > 1e-4; no-HIT control/control max **0.00005613901885226369** <= 1e-4; GPU exit2, original same-ID HTTP **RESTORED_PASS**. New feature commit adds per-HIT fail-closed comparison + existing-log read-only per-token drift audit, 10 CPU negative tests, expected 120 targeted CPU tests. **Do not launch GPU again** until these existing-log diagnostics are reviewed. P1 BLOCKED on strict numeric + full GDN/PLE live reuse provenance. [Ledger](BLAZUX-PHASE6-RESULTS.md).\n\n> **2026-10-30 두 번째 DGX GPU 실제 결과 (4d4afb3):** 105/105 CPU PASS, Source 277/277 PASS, Cache HIT 요청2~4 각 6400, 출력 Token IDs 동일, MTP accepted +400. 상태 스냅샷은 네 요청 **모두 0 events**, 실제 상태 불일치 증거 아님. Strict Cold/HIT max **0.00015660659119021147**, 무 HIT control max **0.0001164395798696205** > 0.0001; GPU exit 2. 원본 같은 ID/HTTP **RESTORED_PASS**. 요청 순번 8 초과 시 전면 차단하는 코드 가드가 원인 **후보**이며 실제 호출/diag 관측 없이 확정하지 않음. 다음 기능 브랜치 수정에서 anon epoch 상한65535 vs 실제 snapshot 40개 제한 분리, 사유별 bounded 상태 진단 및 >8 warmup CPU 반례 추가. 신규 HEAD GPU/CPU NOT_RUN; strict 1e-4 유지, 본 운영 서비스/Stage 수정 금지. [실측 결과 및 후속](BLAZUX-PHASE6-RESULTS.md).

> **2026-10-30 실제 DGX GPU 진단·원본 복구 결과:** `d0f87f279cada71f9d8bbb15f581106b827e8334`에서 CPU 100/100 PASS, Source 277/277 PASS, 후보 GPU HTTP ready, Prefix HIT [0,6400,6400,6400], 150 token IDs 동일, MTP2 +400, 물리 40/40, GPU SHA 샘플 16 events/64 states (오류0). **모두 Cold 1번 요청에서 소진**되어 요청2~4 HIT SHA 샘플 0; CPU probe global cap 8/phase가 원인, Cold/HIT 내용 정합성 아직 미입증. Cold/HIT max logprob 0.000291454, HIT/HIT 0.000342304, 무 HIT control/control 0.000280119 모두 strict 1e-4 초과. GPU exit 2, `INCONCLUSIVE_LOGPROB_DIFF_EXCEEDS_STRICT_GATE`; 원본 same-ID HTTP **RESTORED_PASS**. 다음 feature commit에서 add_request epoch별 2/phase(최대 8 epochs/40 global)로 샘플 예산 재분배, 추가 CPU 반례. 새로운 DGX GPU 재실행은 NOT_RUN, 무단 재실행 금지. [Evidence Ledger](BLAZUX-PHASE6-RESULTS.md).

> **2026-10-30 P1 실제 후보 단일 GPU 진단 준비 (new HEAD DGX NOT_RUN):** candidate-only Mamba state SHA probe now samples the actual 6400-token cache boundary in both 9503-token Cold and 6400-token HIT paths; GPU host oracle captures per-request worker snapshot log deltas for four serialized requests, then compares selected physical cache block + layer hashes without promoting P1 PASS. Snapshot 9 tests, GPU-window now 39 tests, total targeted 100 CPU tests expected. Exact original receipt-ID confirmation, source/Stage SHA, original Running, robust cleanup and same-ID restore still mandatory. Strict logprob 1e-4 unchanged. Details docs/P1-CANDIDATE-STATE-SNAPSHOT-20261030.md.

> **2026-10-30 user-approved P1 completion work / actual candidate snapshot hook (new HEAD DGX NOT_RUN):** Source bundle included exact installed _memcpy_u64_tiled and Stage pre/post methods. Implemented opt-in candidate-only GPU-state SHA256 snapshot hooks at initialized _ensure_align_ctx (before forward) and after postprocess_state, with capped per-state natural byte reads, CUDA synchronization, anonymized physical identity, event retention in oracle result and fail-closed CPU mocks. Pinned original service and host Stage unchanged; live Cold/HIT provenance and all GDN/PLE coverage NOT_PROVEN, strict 1e-4 numerical gate NOT_SATISFIED. Next DGX read-only prep (100 targeted tests) then approved single GPU window with explicit receipt ID and original same-ID restore. Details docs/P1-CANDIDATE-STATE-SNAPSHOT-20261030.md.

> 2026-10-30 P1 actual source analysis, CPU-only preparatory code (new HEAD DGX_NOT_RUN): User uploaded pinned Preview mamba_utils.py source SHA256 25254d005f42b64dd55d15a5c646018f5599d971c23e7ca395eb5acaf4f41ed3. Exact SD/DS conv and temporal byte-copy semantics modeled in standalone CPU contract and ten negative/control tests. Image scanner now pins the entire installed source SHA and captures optional _memcpy_u64_tiled helper; closure-prep saves pinned Stage worker source too. Expected 83 targeted tests, unexecuted. No candidate GPU checksum hook yet, no new GPU window, no original service/Stage changes. physical_mapping_and_reuse_verified remains false, strict 1e-4 unchanged. See docs/P1-PREFIX-BLAZUX-UPSTREAM-COMPARISON-20261029.md.

> **최신 DGX 실측 CPU-only 증거 — 2026-10-29:** `c6aa0a84546aa54111aa58051e09a62afb8aa626`에서 31+14+14+10+2 = **71/71 PASS**, Source **272/272 PASS**, pinned Stage/read-only preflight PASS, 기존 `original_state=running`, GPU 실행 없음. 운영 이미지 `vllm/v1/worker/mamba_utils.py` 실제 SHA256 `25254d005f42b64dd55d15a5c646018f5599d971c23e7ca395eb5acaf4f41ed3` 및 7개 함수/커널 ABI PASS. Source-only observability는 true이나 **real_live_state_hash_captured=false**, **state_content_reuse_verified=false**. 정확한 원문은 DGX 파일 `/tmp/p1-closure-abi.MOxSlTwv.log`; 해당 원문 없이 GPU checksum hook 확정/최종 P1 PASS 불가. 신규 GPU 창 사용하지 않았으며 기존 서비스 중지·복구 없음. [상세 장부](BLAZUX-PHASE6-RESULTS.md).

> **2026-10-29 최신 DGX CPU 테스트 피드백 및 픽스처 수정 (새 HEAD 미검증):** `56c62b5474278b24a70d4fbbd390e3857279f289`에서 targeted GPU-window **31/31 PASS**, Live observer **14/14 PASS**, state reuse contract **14/14 PASS**; image ABI mock suite **8/9 PASS**, `test_copy_source_hints_always_not_runtime_reuse_proof` 1 FAIL. 원인은 mock `_populate_metadata()`에 `self.state_base_addrs`가 없는데 해당 함수의 attribute AST 요약을 True로 요구한 **테스트 fixture 불일치**. 실제 Mamba ABI 결함/실제 GPU 결과 아님. fixture에 참조 추가 및 **다른 메서드만 참조하는 경우 false**를 요구하는 반례시험 1개 추가. 프로덕션/Stage/합격 게이트/모델 hook 코드 변경 없음. 해당 실패로 일괄 스크립트의 새 Source/이미지 검사 단계는 이번 실행에서 **NOT_RUN**. 신규 HEAD targeted CPU 예상 **31+14+14+10+2=71 tests**, 실제 DGX 결과 대기. [관련 비교 문서](P1-PREFIX-BLAZUX-UPSTREAM-COMPARISON-20261029.md).

> **2026-10-29 P1 최종 묶음 준비 (신규 코드 DGX_NOT_RUN):** 사용자 최신 실제 DGX HEAD `9ce2af1e40255f116fc83447a8c97d49d349108c`의 CPU image probe 8/8 PASS, source 270/270 PASS, 원본 running; 정확한 설치 Mamba ABI 7개 함수/커널 확인. 저장·복구 커널 *본문*은 로컬 `/tmp/p1-mamba-abi.dxc4R4kv.log`에만 있고 대화에 미공유. 무 HIT numerical baseline 분리 분석, 복사 경로 source-evidence summary, 1회 CPU-only closure prep script 및 반례시험 추가 후 새 HEAD의 DGX NOT_RUN. GPU checksum hook과 strict full P1 PASS는 준비 전이므로 GPU/운영서비스 실행하지 않음. [비교 및 후속 기술 작업](P1-PREFIX-BLAZUX-UPSTREAM-COMPARISON-20261029.md).

> **2026-10-29 현재 CPU-only 차단 수정:** 최신 사용자 DGX 로그에서 `ac3830f4d603a9a0ad6f721020d10a9b4a780816`의 검사기 단위시험 **6/7 PASS, 1 FAIL**. `test_direct_script_invocation_imports_project_package_without_docker`가 발생시킨 실제 예외는 `src.p1_legacy_service_window.Blocked("DOCKER_INSPECT_FAILED")`; 기존은 `window.Blocked`만 포착. 따라서 오류는 P1 이미지 분석 시작 이전의 **예외 타입 누락**, 실제 운영 컨테이너/GPU 장애 아님. 후속 브랜치에 두 예외 타입 처리 + legacy error 모의 반례시험 추가 (검사기 8개 정의). 이 변경 DGX_NOT_RUN. 읽기 전용 ABI 검사 및 stage checksum gate/P1 GPU gate 유지, 원본 stop/start 및 신규 GPU 실행 미승인. [세부 비교·증거](P1-PREFIX-BLAZUX-UPSTREAM-COMPARISON-20261029.md).

> 최신 DGX 결과: 01d6e7af382815b6fea18a8bed0b8556bbdcb6ab에서 CPU 61/61 PASS, Source270/270 PASS, 원본 running 및 Stage preflight PASS. 직접 CLI 모듈 경로 오류로 Mamba utils 실제 이미지 ABI는 아직 미수집. 후속 HEAD에서 direct CLI sys.path 및 blocked preflight 처리 + CPU tests 2개 수정, 새 DGX CPU/GPU NOT_RUN. 권장 명령: python3 -m src.p1_prefix_mamba_utils_probe --inspect-image --show-source. GPU 정비창 추가 승인 없음.

> **최신 진행 (2026-10-29, 새 코드 DGX_NOT_RUN):** 직전 HEAD `c9351e8af2620b4037cf319989f1e37c0cfad1e1`에서 DGX CPU **55/55 PASS**, Source268/268 PASS, pinned Stage read-only AST/source preflight PASS, 원본 running. 실제 Stage의 `preprocess_state → ctx.run_fused_precopy`, `postprocess_state → ctx.run_fused_postprocess_align`를 확인했다. 그러나 메서드 호출과 실제 block copy는 별개다. 고정 Preview 운영 이미지 `vllm/v1/worker/mamba_utils.py`의 **정확한 SHA·kernel 구현/버퍼 ABI**를 CPU-only sandbox에서 읽는 scanner와 mock 5개를 추가했다. 이 변경은 GPU 검증/운영 반영이 아니다. 자세한 사용/차단 조건: [Blazux 비교 및 다음 근거](P1-PREFIX-BLAZUX-UPSTREAM-COMPARISON-20261029.md).

> **Blazux 최신 공개 원본과 P1 비교/상태 검증 계약 추가 — 새 코드 DGX_NOT_RUN:** `blazux/qwen3.8-Flash-DGX` `main` HEAD `7e63dbe5761448ea833ed28781c1d32ce0d56f4c`의 실제 Mamba 2-site 수정과 GDN/PLE 체크섬 검증 근거를 비교했다. P1은 물리 ID 표본 40개를 확보했으나 **full-state content cold-capture→hit-restore checksum 증거 없음**. 신규 CPU 계약 및 Stage SHA read-only inspector와 반례 unit tests를 추가했다. 기존 strict 1e-4/운영 스크립트는 그대로, GPU 및 운영 서비스 신규 실행 없음. 세부 문서: [P1/Blazux 비교](P1-PREFIX-BLAZUX-UPSTREAM-COMPARISON-20261029.md). 아래 실제 GPU 마지막 영수증 SHA는 `f5bcbb...`로 유지.

> **가장 최신 실제 GPU 영수증 — 2026-10-29, 시험 HEAD `f5bcbbfee72a0d8212eb40a786fa1321e5d01efa` (아래 이전 스냅샷보다 우선):** DGX CPU 42/42·Source265/265·preflight PASS 후 1회 승인 후보 GPU 실행. Prefix HIT [0,6400,6400,6400], 150 token IDs 동일, MTP accepted +400. 실제 Mamba preprocess batch→slot 10회 및 physical entry 표본 40개, `physical_mapping_observed_partial=true`; **state-content reuse 미증명**. 무 HIT 대조군 2회에서도 logprob 최대 차이 0.000331826으로 strict 1e-4 초과; Cold↔HIT 최대 0.000446234 및 HIT↔HIT 최대 0.000449569. 따라서 **strict gate INCONCLUSIVE / exit2**, Prefix 특이 수치 버그 단정 불가. **기존 원본 동일 ID·running·HTTP 복구 PASS 및 후보 제거**. 추가 GPU 정비창·원본 재시작·운영 반영 미승인. [상세 실증 장부](BLAZUX-PHASE6-RESULTS.md). 아래 과거 `NOT_RUN` 표기는 기록 당시 상태다.

> **최신 P1 실 DGX 결과 — 2026-10-29, 영수증 SHA `14075d6a413d002d6c8c97f78b175a7f40d015eb` (아래 이전 스냅샷보다 우선):** targeted CPU 24+10/34 PASS, Source265/265 PASS, Stage ABI/read-only preflight PASS. 단일 승인 후보 GPU HTTP PASS, 9,503 prompt 토큰 Cold+HIT 3회, queries [9503×4], HIT [0,6400,6400,6400], 출력 text/150 token IDs 동일. 실제 MTP accepted token counter +400, Scheduler/Mamba add/align 이벤트 각 12회, active scheduler block 1600 / mamba block 1600 / cache block 8 / num_gpu_blocks 360. 그러나 physical mapping group tables 관측 **0개**, seed -1, strict logprob 최대 Cold→Repeat 0.000159494 및 Repeat→Repeat 0.000231789 > 1e-4. 최종 `INCONCLUSIVE_LOGPROB_DIFF_EXCEEDS_STRICT_GATE`, exit 2. **후보 cleanup + 기존 원본 동일 ID/HTTP 복구 PASS**. 현재 운영 서비스 추가 start/recover 불필요. 추가 GPU 윈도 승인 전 Stage의 실제 table/group 자료구조를 읽기 전용 분석해야 함. 상세 영수증은 [결과 장부](BLAZUX-PHASE6-RESULTS.md). 문서 반영 HEAD는 새 GPU 검증 아님.

> **이 문서는 현재 진행 중인 P1 Prefix-cache 작업만 다룬다.** 과거 DGX 실행 영수증은 [Phase 6 결과 장부](BLAZUX-PHASE6-RESULTS.md), 변하지 않는 결정·운영 규칙·완료 작업은 [영구 핸드오프](SESSION-HANDOFF-PROMPT.md), 기존 서비스 stop/restore 절차는 [P1 정비창](P1-PREFIX-LIVE-SERVICE-WINDOW-20261029.md), 불필요한 Gate 확장 금지는 [재발 방지 정본](BLAZUX-DELIVERY-DRIFT-POSTMORTEM-AND-GUARDRAILS-20261028.md)을 직접 읽는다. 해당 내용을 다시 작성하지 않는다. 본 파일과 영구 문서의 과거 `NOT_RUN`·과거 SHA 표기는 당시 시점의 기록이다.

## 현재 작업과 목표

- 단일 DGX Spark의 기존 Orcarouter Qwen3.8 Flash Next **BF16 PLE + BF16 MTP=2** 운영 모델을 보존하면서, 독립 GPU 후보의 **Prefix-cache ON** 동작이 실제 Mamba/KV 내부 상태까지 정합적인지 확인한다.
- **완료 판정이 필요한 지점:** 실제 cache-hit와 비어 있지 않은 출력 토큰의 일치 외에, 엄격한 logprob 수치 차이 원인과 실제 Scheduler/Mamba block/group, state-slot seed/physical layout/stride 및 MTP acceptance 증거를 확보한다. 실제 원본 운영 Prefix-cache는 **OFF**이며 운영 반영은 미승인/미실행이다.

## 마지막 실제 DGX 실측 — 후속 GitHub 변경과 엄격히 구분

- **실제 사용자 DGX-tested 코드 SHA:** `c342e033c6e601f374520eefb6a9d0e9277b54ef`, `feature/blazux-phase6-runtime-gates`; targeted CPU **20/20 PASS**, Source Manifest **263/263 PASS**.
- `P1_PREFIX_ORIGINAL_CHAT_ORACLE_INTERFACE_PASS_BEFORE_STOP`, `P1_PREFIX_CANDIDATE_STOPPED_PATCH_SHA256_VERIFIED_NOT_GPU`, `P1_PREFIX_CANDIDATE_HTTP_READY_NOT_CORRECTNESS_PASS`. 후보 단독 GPU 기동이 성공했다.
- 9,492 prompt tokens, thinking OFF, **Cold + Repeat 3회(총 4회)**: `vllm:prefix_cache_queries_total` 요청별 증가 **[9492,9492,9492,9492]**; `vllm:prefix_cache_hits_total` 증가 **[0,6400,6400,6400]**. **실 Prefix HIT 증거 확보**. 6,400 = 1,600 × 4이지만 이 수치만으로 실제 Mamba block size 1,600을 확정할 수는 없다.
- 네 응답의 최종 출력 텍스트는 **비어 있지 않고 동일**, 실제 token IDs **각 3개 모두 동일**, finish reason 동일. 전체 logprob은 비교 가능하지만 **최대 절대차 `0.0033205938525497913` > strict `0.0001`**, `P1_PREFIX_GPU_ORACLE_INCONCLUSIVE_LOGPROB_DIFF_EXCEEDS_STRICT_GATE`, 최종 **exit 2**. **캐시 HIT PASS ≠ P1 수치/상태 정합성 PASS**.
- `active_mamba_physical_mapping_observed=false`; MTP speculative token **설정값 2 보존**은 확인했으나 실제 수락률/경로는 미계측.
- 후보 cleanup 후 `P1_PREFIX_ORIGINAL_SAME_ID_HTTP_RESTORED`가 출력됐다. 이전 run `0168cee...`도 이후 사용자가 원본 동일-ID 복구 로그 및 exit2를 제공했으며 결과 장부에 정정했다.
- **현재 운영 상태:** 마지막 DGX 종료 시 원본 `qwen38-flash-orca-uncensored-bf16-mtp`가 **동일 ID/HTTP 준비 상태로 복구됨**. 현재 시점의 Docker 상태는 새 세션에서 직접 확인해야 한다. 정상 running이면 **재시작하지 말 것**.

## 현재 코드·GitHub 진행 상태

- 저장소: `kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark`; 작업 브랜치: `feature/blazux-phase6-runtime-gates`; DGX 전용 checkout: `~/Workspace/llm/blazux-phase6-gates`.
- **마지막 기능 코드 추가 SHA:** `05ee525e19553f46b0b5634f839e58d96ba1357a`. `src/p1_prefix_gpu_oracle.py`에 **Cold→Repeat와 Repeat→Repeat, 출력 토큰별 logprob delta의 숫자형 분해** 추가 및 CPU mock 1개 추가. **이 변경을 적용한 DGX CPU/GPU 결과는 아직 없음.** 이후 `9d0f3986e1885838b70967098579c88113c4d2c1`은 7개 주요 문서·Source Manifest 동기화 커밋으로 **새 GPU 검증이 아님**.
- 브랜치의 **실제 최신 HEAD는 반드시 GitHub ref를 다시 조회**한다. 문서에 기록된 기능 SHA나 문서-only SHA를 현재 HEAD 또는 실기 검증 SHA와 혼동하지 말 것. 작업 지침·원본 SHA와 stage digests는 해당 정본을 사용한다.
- **2026-10-29 문서 인계 직전 GitHub 검사:** open PR **0**, 마지막 `9d0f398...` check runs **0**, workflow runs **0**, commit statuses **0**. **CI PASS가 아님**. 본 핸드오프의 후속 PR/merge가 있었다면 이 숫자는 갱신해서 다시 확인해야 한다.
- 원래 운영 컨테이너 이미지는 `sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a`; 운영 포트 `8000`, 후보 전용 `127.0.0.1:18080`. 기존 host private Stage `/tmp/p1-prefix-stage.2dSPVPR6`의 0700 디렉터리 및 0600 소스는 **재생성·chmod 금지**, SHA 일치 여부 확인 후 후보 stopped writable overlay에만 검증된 두 파일을 `docker cp`로 복사/확인. 자세한 SHA 및 restore는 [P1 정비창](P1-PREFIX-LIVE-SERVICE-WINDOW-20261029.md) 참조.

## 미완료·차단 및 다음 대화 우선순위

1. **읽기 전용 시작 검사:** GitHub 최신 branch/HEAD/PR/CI, Source Manifest, DGX 기존 서비스 `container-id` 영수증 ↔ 실제 Docker ID, `running`/port 8000 `/health`와 `/v1/models`, 후보 부재. 정상 운용 중이면 stop/start를 하지 않는다.
2. **실효성 높은 코드 구현 우선:** 기존 `src/p1_prefix_gpu_window.py`, `src/p1_prefix_gpu_oracle.py`, `src/preview_p1_prefix_candidate.py`를 검토하고, **후보 컨테이너 내부에서만** 실 Scheduler/CacheConfig/Mamba group block size, alignment/mapping 및 state-slot 물리 stride·allocation bounds를 적절히 비식별화해 계측할 최소 observer 설계/구현. 원본 서비스나 원본 vLLM 파일을 덮어쓰지 말 것. 단순 기존 metadata/AST 조사 반복 금지.
3. **수치 오차 원인 분리:** 신규 logprob drift diagnostics를 CPU-only 회귀로 먼저 검증. Cold↔HIT와 HIT↔HIT 분포를 분리하고 strict `1e-4` 기준 **근거 없는 완화 금지**. 필요 시 충분히 긴 생성 및 서로 다른 prefix 길이를 하나의 GPU 시험에서 재현하도록 설계.
4. **MTP=2 확인:** CLI 설정 보존이 아닌 실제 acceptance/관련 메트릭 증거가 가능한지 먼저 검토하되 비검증 주장은 금지. 모델 정확성, source mapping, state restore를 별도 판정한다.
5. **GPU 유지보수 재실행은 새 대화 시작만으로 자동 허가되지 않음.** 비용/다운타임·fail-closed·restore를 포함해 사용자 승인 후 한 번의 후보 GPU 시험으로 통합. exact HEAD와 clean tree 및 Source Manifest 확인, 패치 SHA/권한 검증, 원본 중지는 승인된 `scripts/stop.sh`로만, 완료 후 후보 제거 → 원래 동일 ID `scripts/start.sh` → HTTP까지 확인. 결과는 정확한 DGX SHA와 함께 [결과 장부](BLAZUX-PHASE6-RESULTS.md)에 반영한다.

## 현재 작업에만 적용하는 추가 지침

- **범위 제한:** 현재는 P1 Prefix-cache만 진행. P1 PLE 계측이나 Tool/Responses 등 이미 별도 정본이 있는 기능의 이전 성과를 본 작업에 반복하지 않는다. P2/P3 자동 착수, 운영 적용, main 변경, 모델·원본 이미지·영수증 삭제/재생성은 하지 않는다.
- **추가 임시 규칙:** 사용자는 tmux에서 콘솔 복사·붙여넣기가 불편하다고 했으므로 **tmux를 필수 조건으로 강제하지 않는다**. 일반 SSH 셸에서 `( set -Eeuo pipefail; ... )` **서브셸**로 실행하여 중간 실패 시 로그인 셸 전체가 종료되지 않도록 한다. 명령은 안전한 독립 확인을 합쳐 왕복을 최소화하되 최종 운영 복구는 항상 별도 확인한다.
- 대화가 새로 시작됐다는 이유로 P1 메트릭 oracles, docs, source manifest, tests를 단순 반복 생성하지 않는다. **실제 기능 증거가 증가하는 작업만** 우선한다.
- **PR/merge 권한 경계:** 이번 사용자 요청의 문서 인계 PR 처리처럼 명시적으로 요청된 경우에도 **`main`에 기능 코드·실험 후보를 병합하지 않는다**. 현재 P1 기능은 배포 미승인이다. 다음 세션에 자동 PR/merge/CI 실행 권한이 부여되는 것은 아니다.

## 2026-10-29 — 후보 전용 P1 active ABI observer 소스 준비 (신규 HEAD DGX_NOT_RUN)

- 원래 `/tmp/p1-prefix-stage.2dSPVPR6`의 두 소스 SHA·0700/0600을 유지한다. `src/p1_prefix_live_observer.py`를 정지한 후보 컨테이너의 `vllm/_p1_prefix_live_observer.py`로만 복사하며, 기존 Stage 코드에 메서드 후처리 hook을 추가한 후보별 사본 두 개의 SHA를 Docker readback으로 별도 검증한다. 원본 운영/이미지에 hook을 설치하지 않는다.
- 실제 실행 시 `Scheduler._mamba_block_aligned_split`, `MambaHybridModelState.add_request` 호출 이후 런타임 인스턴스의 block-size/group 메타데이터, state-index GPU 텐서 shape/stride/storage bounds 및 제한된 slot seed 스칼라를 모델 텍스트 없이 Docker stdout에서 계측한다. scalar `.item()`은 후보 GPU 동기화를 동반하므로 **candidate-only diagnostic**이고 성능 벤치에 사용하면 안 된다. 단발성 수집 및 최대 12 이벤트/프로세스 제한.
- 로그로부터 집계하는 `read_candidate_observer()`는 실제 후보 프로세스 이벤트 유무를 구분한다. sampled seed + tensor layout은 **전체 logical→physical block table의 내용·재사용 보존·group별 state allocation bounds를 증명하지 못함**. Physical mapping과 MTP acceptance는 계속 false로 반환하며, API 오라클만 PASS여도 P1 전체 return 0을 막는다. 이 한계를 해결할 추가 vLLM 내부 table 및 speculative acceptance hook은 실제 런타임 증거에 따라 설계해야 한다.
- 신규 소스와 CPU mock 시험은 GitHub 코드 준비일 뿐 현재 DGX CPU/GPU/HTTP **NOT_RUN**. 마지막 실 GPU 검증 SHA는 계속 `c342e033c6e601f374520eefb6a9d0e9277b54ef`; 사용자의 새 운영 중지 승인 없이 `--execute` 하지 않는다. `main` 및 기존 운영 미변경.

### 다음 단일 GPU 창 통합 진단 보강 — 이번 코드 DGX_NOT_RUN

- 동일 합성 9,492 토큰급 prompt에 대해 최종 질문은 1~40 정수 나열, 후보 max_tokens=256으로 장문 출력을 요구한다. 각 4회 출력이 **최소 24 token IDs** 미만이면 `INCONCLUSIVE_GENERATION_TOO_SHORT_FOR_LONG_DECODE` 처리한다. 원본 사전 Chat 프로토콜 probe(짧은 질문)는 그대로 유지.
- Cold↔HIT/HIT↔HIT 숫자 분해(기존 코드)를 유지한다. /metrics에 노출되는 `spec_decode` metric을 prefix counter와 함께 읽되, MTP=2 구성만으로 acceptance를 주장하지 않는다. 정확히 `vllm:spec_decode_num_accepted_tokens_total` 의 positive delta가 있는 경우에만 해당 메트릭 기준으로 `mtp_acceptance_observed=true`. 없는 경우 `false`이며 미계측으로 취급한다. 해당 지표가 Preview에 제공되는지는 미확인.
- 모든 변경은 코드 준비/신규 CPU mock 수준이고 DGX CPU/GPU 테스트 미실행. 물리 Mamba logical→physical block mapping의 실제 재사용 정합성은 계속 차단 상태.

### 다음 단계: 후보 물리 블록 표본 계측 (신규 변경 DGX_NOT_RUN)

- **기존 CPU 검증 사용자 DGX 로그:** 정확 SHA `6f018dd283aea95f9babb0c3473d9cca0400725e`에서 GPU-window mock 23/23, live-observer mock 3/3, Source Manifest 265/265 PASS. 이는 실제 컨테이너 실행이 아닌 CPU 계약 검증이다.
- 후보의 동일 `mamba_hybrid.py` 사본에 `initialize_kv_cache` 후처리 hook을 추가한다. **정지한 후보에만 설치**, 원래 두 Stage SHA/소유권 유지. CPU 소스 AST로 메서드 존재를 GPU/원본 중지 전에 거부한다. 실제 Mamba group id에 해당하는 persistent state-slot block table tensor 참조/shape/row stride를 준비하고, `add_request(req_index,new_req_data)`에서 `(num_computed_tokens-1)//mamba_block_size` 예상 seed와 실제 GPU seed 및 해당 `[req_index, seed]` 물리 block-id 표본을 대조한다. 표본 GPU scalar read는 동기화가 있을 수 있으므로 후보 디버그 한정, 요청별 최대 12번. 일치하는 group spec block-size 여부와 row/column bounds 포함, 사용자 프롬프트·가중치·절대 GPU 주소 출력 금지.
- 이 값들은 **실제 프로세스 표본 관측이 실행되어야만 의미**가 있다. block table의 physical id가 유효해도 실제 state-content가 HIT에서 정확히 재사용/보존됐다는 증명이 아니므로 `physical_mapping_and_reuse_verified=false`는 그대로 유지. `active_mamba_physical_mapping_observed`를 전체 PASS로 잘못 승격하지 않는다. 정확한 실기 검증 및 후속 state-content/inference parity는 미완료. GPU 실행·운영 중단 새 승인 필요.

- 실제 `vllm_config.compilation_config.static_forward_context`에 노출된 group별 layer `kv_cache` 텐서의 shape/stride/storage bounds를 후보 초기화 시 읽어 `state_allocation_blocks` 최솟값과 표본 physical ID를 비교한다. 필요한 하나라도 확인되지 않으면 `allocation_complete=false`, `physical_id_within_state_allocation=null` 처리한다. 상태 텐서 내용을 해시하거나 메모리를 읽어 동일성 입증한 것이 아니며, CPU mock 통과만으로 엔진 호환성/물리 재사용 정합성 PASS 아님.

### Runtime observer 자료형 정합성 수정 (DGX 신규 코드 NOT_RUN)

- 마지막 사용자 실제 CPU 증거는 SHA `6f018dd283aea95f9babb0c3473d9cca0400725e`의 23+3 mock/265 Manifest PASS로 한정. 이후 물리 mapping 계측 코드는 **GPU/CPU 미실행**.
- `vars(obj)` 단독 접근은 실제 `__slots__` 구성 데이터 및 클래스 속성 구현의 유효한 `num_computed_tokens`, `mamba_block_size`, `kv_cache`를 누락시킬 수 있다. 승인된 수치/구조 필드 whitelist로만 `getattr` fallback을 제한해 진단을 보정했다. `UniformTypeKVCacheSpecs.kv_cache_specs` layer mapping을 실제 layer 이름 순서로 해석해 Mamba spec block-size를 읽는다. spec 누락은 `unknown`이며 잘못된 mismatch/physical PASS가 아니다.
- CPU-only 신규 mock은 slots + Uniform wrapper 및 unknown block-size 삼상값을 검증하도록 추가했다. 신규 코드는 GitHub 소스 준비뿐이며 DGX CPU/GPU/HTTP 시험, active physical table 값, state-content reuse 모두 **NOT_RUN/UNVERIFIED**이다.

### 2026-10-29 실제 Stage ABI 확인 및 GPU 사전 차단

- 사용자 DGX 최신 확인: HEAD b0ccbe8d206a4ba8023fcf63dd65f1b06f74508c 에서 CPU mock 32/32, Source265/265 PASS. 승인된 GPU window는 원본 HTTP probe 정상 후 ACTIVE_OBSERVER_METHOD_NOT_IN_STAGE_MAMBA_HYBRID 로 exit 2, 원본 동일 컨테이너 Running + port 8000 HTTP PASS, 후보 부재. GPU 기동·원본 중지 없음. 복구 명령 불필요.
- 실제 private Stage 두 파일 SHA 검증 후 AST에서 MambaHybridModelState에는 initialize_kv_cache가 없고 _ensure_align_ctx(self, kv_cache_config, mamba_group_ids, block_tables), add_request(self, req_index, new_req_data)가 존재함을 사용자 확인. Scheduler._mamba_block_aligned_split 메서드도 실제 signature를 확인.
- 본 후속 변경은 _ensure_align_ctx + add_request와 Scheduler만 후보에 hook, group_ids를 실제 인자로 읽고, Stage signature 검증을 read-only preflight 단계에서 실행. add_request가 align ctx 이전 호출될 때는 제한된 최근 slot 표본을 이후 align ctx에서 재관측. 원본 모델 instance에 observer 필드를 쓰지 않고 모듈 전용 저장소 사용. 물리/재사용 완전 검증은 계속 false. 새로운 HEAD 자체 CPU/GPU 시험은 NOT_RUN; 신규 GPU 윈도 승인으로 확대하지 않음.

### 2026-10-29 실제 Stage 코드 확인 후 observer tensor ABI 교정 (새 코드 DGX_NOT_RUN)

- 사용자가 Stage SHA 고정 실제 `_get_mamba_group_info` 및 `_ensure_align_ctx` 원문을 제공했다. `_ensure_align_ctx(self, kv_cache_config, mamba_group_ids: list[int], block_tables: tuple[torch.Tensor, ...])`; 실제 엔진은 `[block_tables[gid] for gid in mamba_group_ids]`로 GPU context에 배치순서 테이블 텐서 슬라이스를 전달한다. 구 observer의 `block_tables[gid].gpu` 접근은 실제 tensor에 맞지 않아 그룹 수가 0으로 기록됐다.
- 수정은 direct `torch.Tensor`의 metadata(shape/strides/storage offset/capacity) 수집을 허용하고, 초기화 시점을 지나도 표본을 볼 수 있도록 observer 로그 12회 예산을 startup 1~4 및 8/16/32/... 호출 순서로 분산한다. 그러나 실제 block table **행은 batch-order**, `add_request(req_index)`의 request-slot과 동일하다는 증거가 없으므로 direct tensor는 `BATCH_ORDER_ROW_UNRESOLVED`로 표시, `[req_index, column]` GPU scalar read를 **수행하지 않고** block-ID/상태 재사용 PASS를 금지한다. 실제 batch index ↔ request slot 연결을 증명할 자료는 후속 `preprocess_state`/input-batch ABI 관측이 필요하다. Stage와 운영 컨테이너 변경 없음.
- 신규 CPU mock은 direct tuple tensor와 초기/후기 이벤트 sampling을 추가했지만 신규 HEAD **DGX CPU/GPU NOT_RUN**. 기존 원본 HTTP 복구 PASS와 별도로 새로운 GPU 시험 승인은 없음.

### 2026-10-29 DGX Stage `add_request/preprocess_state` 읽기 전용 근거와 후보 계측 코드 준비

- 실제 사용자 DGX에서 기능 브랜치 `d73aa76ab41ab4a3755c4c5aa1aa9d9e7f9a7d2b`의 CPU 24+12/36 PASS, Source265/265 PASS, `P1_PREFIX_GPU_PREFLIGHT_SOURCE_CPU_PROBE_PASS_NOT_GPU` 확인. `add_request`는 `(num_computed_tokens-1)//mamba_block_size`로 slot seed를 기록. `preprocess_state`는 batch `input_batch.num_reqs`, `input_batch.idx_mapping`, `block_tables:tuple[torch.Tensor,...]`을 `preprocess_mamba_align_fused_kernel`에 전달하고 `ctx.run_fused_precopy(..., input_batch.idx_mapping)` 호출. 따라서 batch row와 persistent slot은 같다고 가정할 수 없으며 실제 idx_mapping tensor로만 연결해야 함.
- 후속 변경은 후보에서만 `preprocess_state` 후처리 hook 추가, 최대 8개 배치 행의 `idx_mapping[row]`와 persistent `_mamba_state_idx_gpu[slot]` 제한된 scalar 표본을 읽고, 정확히 매칭된 `block_tables[gid][batch_row,state_col]`만 조회하도록 구성. 수치와 shape/stride/bounds만 기록, 문자열 request ID/model payload/주소는 출력하지 않음. idx/column 범위 밖이면 skip·unknown. 실제 state contents의 cache-hit 재사용 증명 및 P1 full PASS는 여전히 false. 사용자 GPU 재실행 승인 없음.
- 후속 GitHub 코드/단위시험/Manifest 커밋은 새로운 **DGX CPU/GPU/HTTP NOT_RUN** 상태. 이전 실 GPU HIT+MTP와 1e-4 logprob 미충족 및 동일 ID HTTP 복구 영수증은 변경하지 않음.

### 2026-10-29 통합 P1 진단: 동일 후보 GPU 윈도 내 무 HIT 대조군 준비 (신규 코드 DGX_NOT_RUN)

- 사용자 SHA `9aed4966c45c86481479634183cd346417b37cbb`: DGX targeted CPU **25+14=39/39 PASS**, Source Manifest **265/265 PASS**, Stage SHA + ABI CPU-only preflight PASS, 운영 원본 Running. 이는 신규 GPU 시험이 아님.
- 이전 실제 GPU SHA `14075d6a...`에서 Cold→HIT 최대 logprob 0.000159494, HIT→HIT 최대 0.000231789로 strict 1e-4 실패. 이를 캐시 전용 변화로 성급히 단정하지 않도록, **기존 하나의 GPU 후보 실행에서** 동일 synthetic prompt, 고정 decoding을 쓰되 요청마다 비밀 난수 cache_salt(32 bytes)를 달리한 추가 2회 대조군을 진단한다. 고정 Preview에서 cache_salt 미지원 또는 해당 대조군 metrics unavailable이면 unknown/INCONCLUSIVE, 성공 주장은 하지 않는다. 각 추가 요청의 실제 `vllm:prefix_cache_hits_total` delta=0 및 queries>0 확인 후에만 No-HIT sample로 비교한다. 토큰 ID 일치 여부, Cold0↔ColdControls, Control↔Control 최대 logprob 절대차를 출력하고 원본 threshold 1e-4 및 oracle P1 PASS gate를 변경하지 않는다. 비밀 salt 값·모델 텍스트를 출력하거나 영구 저장하지 않는다.
- `preprocess` 계측 이벤트의 수집 call ordinal 및 제한된 실패 이유 카운트도 기존 GPU 결과와 함께 반환한다. 후보 후처리 + CPU mock/Source Manifest 작업만 수행하며 **이 변경은 GPU/DGX NOT_RUN**, 기존 운영 중지 신규 승인 없음. 현재 P1 full physical state-content reuse gate는 계속 false. CLI `--execute`는 이전 승인으로 자동 재실행 금지.
