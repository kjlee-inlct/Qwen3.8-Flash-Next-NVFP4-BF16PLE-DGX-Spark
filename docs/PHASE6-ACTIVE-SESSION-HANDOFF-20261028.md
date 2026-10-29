# P1 Prefix-cache — 현재 진행 작업 인수인계 (2026-10-29)

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
