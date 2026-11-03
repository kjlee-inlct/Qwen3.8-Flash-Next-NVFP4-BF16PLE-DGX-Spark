# Orcarouter용 Blazux 도입 P2/P3 재편안 (2026-11-03)

> **상태: 제안 / 기존 배포 Gate 변경 승인 아님.** 사용자 문제제기: P1에서 P2로 넘긴 미완료 항목처럼, P2 미완료 항목도 P3로 분리할 수 있다. 최종 목표는 Blazux 레시피 전체 복제가 아니라 **현재 DGX Spark Orcarouter Uncensored에 유효한 기능 적용**이다. 이 문서는 기능 범위/작업 순서를 재설계한 것이며 GPU 창, 운영 cutover, 기존 strict 출시 Gate 변경을 승인하지 않는다.

## 비교 기준 (고정 SHA)

| 항목 | Blazux upstream | 현재 Orcarouter |
| --- | --- | --- |
| 저장소/HEAD | [blazux/qwen3.8-Flash-DGX @ b0aa8b77](https://github.com/blazux/qwen3.8-Flash-DGX/tree/b0aa8b77604139557169387b2fa8386355d8b651), 2026-11-02 UTC | [kjlee-inlct/... @ fa46304b](https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark/tree/fa46304b0b3edd031be3da45d5aca7c646e08ede), 2026-11-03 UTC |
| Base runtime | 공식 vLLM **v0.32.0** 이미지 | 설치 Qwen Preview **0.1.dev20073**, 고정 원본 Docker |
| PLE/weights | NVIDIA NVFP4 기본, 약 48 GiB FP8 PLE mmap; Hybrid FP8 side layers 옵션 | Orcarouter Uncensored NVFP4 routed experts + 약 **95.37 GiB BF16 PLE mmap**, 별도 BF16 MTP overlay |
| 서비스 계약 | `./flash` command/profiles, API 기본 :18300, served name qwen3.8-flash-next | 원본 OpenAI-compatible **:8000/v1**, 모델 ID `qwen3.8-flash-next-orca-uncensored-bf16-mtp` 및 OpenWebUI/Pi Agent 유지 |
| 기능 검증 | 원본의 공개 GX10/v0.32 구성에 대한 throughput/500k/FP8/Greedy 측정 | P1 제한된 Preview GPU 검증; P2는 CPU/asset/stage, 두 번의 Numeric candidate GPU HTTP+원본 복구만 확인, strict logprob 문제 미해결 |

**서로 동일하지 않은 메모리 레이아웃/체크포인트/Preview ABI**이므로 upstream의 속도, 메모리, 문맥 길이, 수치 결과를 Orcarouter에 그대로 적용한 것으로 간주하지 않는다. upstream `flash setup`/`serve`를 운영 서버에 그대로 실행하지 않는다.

근거:
- upstream [README](https://github.com/blazux/qwen3.8-Flash-DGX/blob/b0aa8b77604139557169387b2fa8386355d8b651/README.md), [v0.32 이식](https://github.com/blazux/qwen3.8-Flash-DGX/blob/b0aa8b77604139557169387b2fa8386355d8b651/docs/VLLM-032.md), [profiles/default.env](https://github.com/blazux/qwen3.8-Flash-DGX/blob/b0aa8b77604139557169387b2fa8386355d8b651/profiles/default.env), [profiles/dflash.env](https://github.com/blazux/qwen3.8-Flash-DGX/blob/b0aa8b77604139557169387b2fa8386355d8b651/profiles/dflash.env), [serve.sh](https://github.com/blazux/qwen3.8-Flash-DGX/blob/b0aa8b77604139557169387b2fa8386355d8b651/scripts/serve.sh).
- 내부 [현행 8항목 로드맵](P2-ORCAROUTER-ADOPTION-ROADMAP-20261103.md), [P1/P2 기능 결과](BLAZUX-UPSTREAM-COMPARISON-20261029.md), [P2 통합 후보](P2-BATCH-IMPLEMENTATION-20261102.md), [P2 정비창 결과](P2-NUMERIC-GPU-WINDOW-20261103.md), [결과 장부](BLAZUX-PHASE6-RESULTS.md).

## 업스트림 기능 대비 적용 현황 (8개 원래 목표 + 신규 선택 사항)

| 원래 영역 | Blazux upstream b0aa8b77 | Orcarouter 실증 상태 | 이번 재편 제안 |
| --- | --- | --- | --- |
| P1 PLE 계측 | mmap/lookup 통계 및 성능 경로 | BF16 PLE phase opt-in 모델 관측 **bounded PASS**; GPU 완료시각/성능 full proof 아님 | **P1 완료(기능 한정)**; 정밀 DMA 계측은 P3 진단 옵션 |
| P1 Prefix Cache/GDN state | Mamba state/caching fix, Greedy deterministic top-k | P1 후보 실제 HIT `[0,6400,6400,6400]`, MTP accepted +400, 선택 state SHA 12/12; 전 계층 physical copy 미확인 | **P1 완료(기능 한정)**; 전계층 물리 감사 P3 |
| P1 Tools/Responses | parser·literal tool marker·schema/stream fixes, v0.32 실제 API 검증 | Preview 후보 tool-call→result→final 실제 왕복 등 **bounded PASS** | **P1 완료(기능 한정)**; Orcarouter API 회귀를 P2 통합 Gate에 유지 |
| P2 PLE unique/H2D | dedup→CPU stage→H2D→GPU inverse, profile tunables | `VLLM_PLE_UNIQUE_H2D` opt-in source/CPU byte contract; **Orcarouter GPU 성능/graph 미검증** | **P2 핵심 최적화 후보**. 성능·정확성 불충족 시 OFF로 봉인하고 P3 연기 가능 |
| P2 MTP reduced 65,536 | upstream `DRAFT_VOCAB=1` 기본, 해당 GX10 성능 보고 | upstream 65,536 ID & tokenizer 호환 SHA 검증, Preview BF16 MTP source overlay와 4-COPY stage 준비; **실 GPU acceptance/속도 NOT_RUN** | **기본 P3 이관**. P2 필수 완료 조건에서 제외, stock MTP2 유지 |
| P2 vLLM 0.32 Track B | 공식 0.32 port, Mamba/QSA/PLE/parser/MTP ABI 패치 포함 | Preview 기반의 별도 Track B 계획/정적 자료만; **Orcarouter BF16 PLE/MTP 0.32 GPU NOT_RUN** | **P3 이관**. P2 Preview Track A를 흔들지 않음 |
| P3 YaRN 500K/M-RoPE | 원본 FP8-hybrid long-context 498,994 token synthetic probe, MTP cache fix | Orcarouter 500K runtime/VRAM/정확성 미검증 | **P3 유지** |
| P3 Hybrid FP8 side layers | NVIDIA checkpoint side layers hybrid, 원본 일부 throughput 향상 | Orcarouter Uncensored BF16 PLE와 bitwise 동등 모델 자산 아님, 분리 사본/검증 필요 | **P3 유지** |
| 추가 DFlash2 | 2026-10-28 patch23 + `dflash` profile (별도 draft model) | Orcarouter Preview/31 BF16 MTP tensor와 native ABI 미확정 | **P3 선택 과제**; 핵심 8개에 자동 추가 금지 |

## 제안 P1 → P2 → P3 완료 기준

### P1 — 기능 한정 완료(과거 증거 보존)
- 핵심 3기능의 실제 DGX 좁은 범위 검증 `P1_FUNCTIONAL_VERIFIED=BOUNDED_PASS`는 유지. 원본이 `Prefix OFF`/`MTP OFF`에서도 strict abs logprob `1e-4`를 초과한 기록을 삭제하지 않는다.
- `P1_FINAL_PASS=FALSE`, `P1_RELEASE_BLOCKED=TRUE`, `DEPLOYED=FALSE`는 그대로 유지. P1의 기능 PASS를 전체 수치/출시 PASS라고 쓰지 않는다.

### P2 — Preview Track A의 **Orcarouter 사용 가능한 후보** 완성
P2에서 제공할 최종 산출물은 업스트림 기능을 나열하는 문서가 아니라 **실제 Orcarouter 호환 이미지를 안전하게 검증하고 선택할 수 있는 후보/시험/복구 묶음**이다.

1. **P2-A Preview 통합 후보**: 현재 모델/로더/95.37GiB BF16 PLE + stock BF16 MTP2를 보존하고 P1 PLE 계측, Prefix/GDN 개선, Tools/Responses 경로를 한 후보로 통합. 현재 4-COPY stage는 source 준비이지 GPU 통합 PASS가 아니다. 비활성 기능(default OFF)부터 독립적인 옵션 Gate.
2. **P2-B PLE unique H2D 선택적 검증**: 이미 구현한 BF16 opt-in source를 같은 환경에서 성능/정확성 비교. 중복률, H2D 완료시간, TTFT/prefill, TPS, CUDA graph, memory/IO를 실측. 이득이 없다면 option OFF로 두고 **P2 기능 완료를 방해하지 않음**, 개선 자체는 P3 backlog로 넘긴다.
3. **P2-C 통합 프로토콜/운영 복구**: Chat/Responses, 실제 tool call/result/final, 스트리밍, Prefix hit 및 선택 상태, MTP2 acceptance, startup/port 8000/model ID, OpenWebUI·Pi Agent 호환, 명확한 owner-checked 후보 제거→원본 same-ID HTTP 복구. 외부 baseline과 직접 비교 가능한 설정만 A/B.
4. **P2 종료 정의**: (a) P1 기능 범위의 실제 통합 GPU+API 증거 (b) opt-in ON/OFF 비교 및 negative 결과도 기록 (c) 후보 이미지/스크립트/근거/복구 재현 (d) 남은 사항 P3 백로그로 정확히 넘김. **운영 cutover는 P2 기능 완료와 별도 승인**.

※ 기존 2회의 Numeric-only GPU 창은 candidate HTTP_READY와 원본 동일 ID/HTTP 복구만 입증했고, Sampler Witness 부재로 수치 원인 분석을 완료하지 못했다. 해당 결과로 P2 통합 GPU 검증을 대체하지 않는다.

### P3 — 고위험/신규 기반 최적화, Numeric 심화
- **P3-N Numeric first divergence/RCA**: pinned Sampler source/AST와 두 번의 무증거 GPU 계측 기록 보존. Worker import/env/logprobs_mode/processed_logprobs 등 source-only 정적 게이트와 실제 실행 분기를 구분하는 별도 좁은 진단. 무분별한 3차 GPU 창 반복 금지. 원본 자체 strict 문제이므로 Blazux 후보만의 결함으로 단정 금지.
- **P3-M MTP reduced 65,536**: 65,536 ID source·asset/ABI 증거 재사용하되 target head 248,320/31 BF16 tensor/acceptance 검증 후에만 별도 GPU 후보, stock MTP2 대비 같은 조건 성능·품질 확인. C++/Preview remapping·대용량 메모리 위험시 skip.
- **P3-V vLLM 0.32 Track B**: 원본 v0.32 기법을 Preview에서 직접 섞지 않는다. BF16 PLE 95.37GiB/Loader/MTP/QSA/Cache/Parser 포팅 계획을 독립 source/build/runtime 실증. upstream v0.32의 성공은 우리 모델 ABI 성공을 증명하지 않는다.
- **P3-L long-context/Hybrid/선택 DFlash**: 500K M-RoPE, Hybrid FP8, DFlash2 각각 독립 옵션과 변경된 checkpoint/model license/quality 검증. 기본 P2 완료 의존성에서 제외.

### 출시 수치 규칙: **P2 개발 완료와 출시 승인은 반드시 분리**

- `strict logprob abs <= 1e-4`는 기존 합의된 **release gate**이며, 단지 P3로 진단을 넘겼다는 이유만으로 PASS, waiver, 제한값 완화로 변경하지 않는다. 기존 원본도 이 조건을 위반했기 때문에 수정·정확한 원인 분리·또는 사용자의 명시적 **정책 재정의**가 전제될 때까지 **P1_RELEASE_BLOCKED / P2_DEPLOYED=FALSE**.
- Upstream “deterministic greedy decoding”은 *토큰 결정성* 관련 주장이다. 모든 반복 쌍에서 API logprob 절댓값이 1e-4 이하라는 뜻이 아니다. 두 기준을 혼동하지 않는다.
- 앞으로 표기: `P2_FEATURE_CANDIDATE_READY`(소스+통합 후보 기능), `P2_RUNTIME_VALIDATED`(실제 BF16 Orcarouter GPU/API), `P2_RELEASE_APPROVED`(정책·복구·성능/품질·승인), `P3_DEFERRED_OPEN`(미완료 계획) **서로 독립**, 승인/검증 전 TRUE로 쓰지 않는다.

## 다음 작업 우선순위 — 사용자 턴과 DGX 중단을 줄이기 위한 묶음

| 순서 | 작업/산출물 | 실행 경계 | 실패/연기 결정 |
| --- | --- | --- | --- |
| 1 | P1 기능 + 기존 P2 4-COPY source/asset 현황 인벤토리, 현재 Preview 타깃에 필요한 COPY/ENV/CLI 간소화한 **Orcarouter 기능 후보** 정의 | GitHub source/CPU test 우선. 운영 원본 변경 없음 | 소스 stage ≠ GPU 성공; SHA/ABI drift는 원인만 기록 |
| 2 | PLE Unique-H2D를 **독립 opt-in** A/B 대상으로 정리, 정확성/성능 기준과 endpoint 영향 예측을 문서화 | CPU·candidate source only; 실제 GPU/HTTP는 별도 승인 | 이득 없거나 ABI 불확실하면 P3 연기, P2 기본 OFF |
| 3 | 실제 P2 통합 GPU 창(사용자 별도 승인 시): 후보 단독 실행 → protocol/cache/MTP2 smoke → optional PLE Gather A/B → 복구 확인 | 기존 원본 same-ID stop/start, 이미지/weights/cache 불변, 포트/API 계약 보존. 두 모델 동시 실행 금지 | 정상 복구·프로토콜 실패 시 기능 PASS 아님; 자동 재시도 금지 |
| 4 | P2 근거 보고 + P3 백로그/릴리즈 게이트 분리 | PR/문서·Manifest 동기화. 증거 SHA 고정 | strict numeric 해결 없이 배포 PASS 절대 선언 금지 |
| 5 | P3-N/M/V/L은 독립 acceptance 기준/승인으로 후속 진행 | P2 종료의 필수 사전 조건에서 제외 | ROI 불분명·리스크 큰 항목은 optional 유지 |

**단기 STOP 규칙:** 같은 source-only 감사/테스트 개수 증가만 반복해도 실제 적용 기능이 늘지 않는다면 중단하고 후보 통합/실측 준비로 전환한다. 원본 컨테이너/이미지/PLE/HF cache 변경, `main` 수정, 외부 포트/모델명 변경, GPU 창 재사용은 여전히 금지다.

## 판정 및 승인 경계

이 문서는 *개정 권고안*이며 기존 장부의 P1/P2/P3 역사적 수량·SHA·증거를 삭제하거나 실제 상태를 소급하지 않는다. 사용자 최종 확정 전 기능 우선순위 및 P2 종료 기준에 관한 의견 초안으로 취급한다. 문서용 PR/merge는 런타임과 운영 실행 승인 또는 출시 게이트 변경이 아니다.
