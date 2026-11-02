# P1 integrated image: guarded GPU-window lifecycle

## 2026-11-02 P1 단일 통합 정비창 종료 영수증 (현재 상태)

기존 `src.p1_integrated_window --minimal-functional` 경로는 사용자 승인된 DGX 정비창 **1회 실행 완료(exit 0)**. tested HEAD `50fc65b65d10b36804c65e8a48d06d9bf3abecfe`, 기존 이미지 `sha256:1a8b53fc06faaab809f3691c6e69cc9268327277ae46e108f3d9549f01a8271d`. Tool 왕복, PLE opt-in CPU 단계 계측, Prefix HIT+MTP2+선택 SHA 12/12 각각 **범위 한정 PASS**. 최종 상태 `P1_FUNCTIONAL_BOUNDED_EVIDENCE_PASS_NOT_RELEASE`, **출시 차단 유지**.

출시 strict `1e-4` 미해결, `full_state_reuse_verified=false`; 이미지 배포·원본 덮어쓰기/재실행 없음. 실행 후 exact original ID/이미지/running 및 port8000 `/health`, `/v1/models`, 후보 부재 확인 모두 PASS. 따라서 **현재 `start.sh`, `--launch`, `--restore`, stop 명령을 추가로 실행할 이유 없음**. 복구 실패 시에만 독립 소유권 검증 후 안전 절차 검토; 사용자 신규 승인 전 정비창 재개 금지.

지금의 증거·제약: [종료 결과 장부](BLAZUX-PHASE6-RESULTS.md) / [현재 P1 인수인계](PHASE6-ACTIVE-SESSION-HANDOFF-20261028.md). 아래 10월 31일의 'READ-ONLY NEXT STEP', 'FUTURE GPU SERVICE WINDOW'는 당시 절차 예시이며 지금 수행할 항목이 아니다.

### 이하: 2026-10-31 구축 시점 런처/복구 참고 절차 (역사 기록)


Exact integrated P1 image built by operator on DGX (2026-10-31):
kjlee-qwen38-p1-integrated:bf80867dc5be
sha256:1a8b53fc06faaab809f3691c6e69cc9268327277ae46e108f3d9549f01a8271d
Contains Prefix ON changes, QSA exact top-k experiment, Preview-native
Tool/Responses patch, and opt-in BF16 PLE phase stats (OFF by default).
Original full-ID service port 8000 remained running and HTTP healthy.

src/p1_integrated_runtime.py is distinct from the original two-file
scripts/p1-prefix-release.sh. Never mix these two release controllers.

READ-ONLY NEXT STEP, NO GPU ALLOCATION OR SERVICE MODIFICATION:
  HEAD=$(git rev-parse HEAD)
  PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v tests.test_p1_integrated_runtime
  PYTHONDONTWRITEBYTECODE=1 python3 -m src.p1_integrated_runtime --expected-head "$HEAD" --preflight

Independent BF16 PLE CPU fixture regression, using the existing restricted
one-shot Docker CPU-only runc test harness (does not enter legacy service):
  bash scripts/ple-phase-stats-cpu-container.sh --expected-head "$HEAD" --execute

FUTURE GPU SERVICE WINDOW: NOT AUTHORIZED by this implementation or image build.
After an explicitly approved maintenance window and pinned full original ID,
stop only via existing scripts/stop.sh --expected-head and --confirm-id --execute.
Only after original is verified EXITED may the integrated controller launch
with --launch --confirm-original-id FULL64. Launch uses port 127.0.0.1:18080
and preserved MTP2/Prefix ON, never binds port 8000 or stops original.
To clean up, use --restore --confirm-original-id FULL64
--confirm-candidate-id FULL64 (the ID returned by launch). This removes
only the exact label-owned candidate and restores the same original ID
using scripts/start.sh, then verifies port-8000 health and model ID.
Launch failure attempts owned cleanup before original recovery; uncertain
ownership or cleanup fails closed to avoid two models on the single GPU.

At future runtime: verify Chat/Responses/API, tool calls and streaming;
cold/hit HIT telemetry + MTP acceptance, strict logprob absolute 1e-4
without relaxation, and GDN/PLE full-state evidence separately. The
un-instrumented integrated release does not by itself prove full state reuse.
Do not auto-promote to production, alter P2/P3, PR/merge or main.
