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
