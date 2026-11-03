# Blazux-first → Orcarouter 호환성 우선 전환 결정 (2026-11-03)

> **승인된 의사결정**: 사용자가 기존 Preview에 Blazux 패치를 역포팅하던 경로보다, **Blazux upstream을 기반으로 Orcarouter를 이식하는 경로를 먼저 검증**하자고 승인했다. 이 문서는 새 개발 주력 경로와 검증 범위에 대한 승인이다. **운영 원본 중단·교체, GPU 모델 구동/추론/성능부하, 신규 production cutover, 기존 strict 수치 gate 면제 승인이 아니다.** 아래 호환성 검토 결과가 좋지 않으면 Preview Track A로 복귀한다.

## 0. 현재 단 하나의 최종 목표

**DGX Spark에서 현재 OpenAI-compatible Orcarouter Uncensored 모델을 안정적으로 운영하되, Blazux가 이미 구현한 최적화를 최대한 직접 재사용**한다. 이전 활동의 목적은 Blazux 소스 이식 자체가 아니라 Orcarouter 사용자 기능·속도·정확성·API 호환성이다.

기존 Preview/Track A는 **동작 확인된 fallback으로 동결**하고, 새로운 Blazux 기반 Track B를 최소한의 Orcarouter adapter로 평가한다. 기존 Track A의 코드·시험·영수증은 삭제/되돌리지 않는다. 2026-11-03의 P2/P3 범위 재편 제안`docs/P2-P3-SCOPE-REALIGNMENT-20261103.md`은 **이 결정에 의해 우선순위가 대체**된다. 이식이 성공할지 아직 확정되지 않았으므로 기능 완료나 Blazux 적용 성공으로 표현하지 않는다.

## 1. 정확한 출발점 (변경된 SHA는 재확인 후 새 체크포인트에 기록)

| 구분 | 저장소/커밋 | 범위 |
| --- | --- | --- |
| 기능 구현 기준 | https://github.com/blazux/qwen3.8-Flash-DGX/tree/b0aa8b77604139557169387b2fa8386355d8b651 | upstream `main` 2026-11-02 UTC. 공식 vLLM 0.32 기반 23개 패치, NVFP4 + PLE mmap + QSA/Prefix + Parser/Responses + MTP + 옵션 Hybrid/DFlash |
| 현재 개발 코드/이력 | https://github.com/kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark/tree/a88a951d9e6b3ad34deef6ccef8a215cd08b8c96 | `feature/blazux-phase6-runtime-gates`의 결정 전 HEAD. Preview 0.1.dev20073, Orcarouter BF16 PLE/MTP overlay 및 검증용 코드 |
| 보호할 main | `b0c7d9067c555dd43a31b49bca9be75664c06c97` | 작업 대상 아님 |
| 원본 운영 컨테이너 (실측 고정 ID) | `qwen38-flash-orca-uncensored-bf16-mtp` / `3fc5a3d5be1d52595602287acd87895220219bad050484251ac0408a163ffc45` | 동일 ID/이미지/StartedAt 검사. Never rm/recreate/edit |
| 원본 이미지 digest | `sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a` | Docker original image/weights/PLE mmap/HF cache 변경 금지 |
| 유지할 클라이언트 계약 | `http://10.221.50.65:8000/v1` 또는 현 OpenAI-compatible `:8000/v1`, 모델 ID `qwen3.8-flash-next-orca-uncensored-bf16-mtp` | 외부 OpenWebUI / Pi Agent / 기존 Ollama 등의 연결 보호. 주소/ID 변경이 필요한 경우 cutover 설계 필요 |

**업스트림 차이:** Blazux의 기본 설정은 NVIDIA NVFP4 checkpoint, 약 48GiB FP8 PLE, vLLM 0.32, API `:18300`, served model `qwen3.8-flash-next`. Orcarouter는 Uncensored checkpoint, 약 **95.37GiB BF16 PLE**, Preview 전용 loader, 31 BF16 MTP tensor overlay(MTP2), 운영 API `:8000`다. 업스트림 프로파일/벤치 수치를 Orcarouter 실측으로 사용하면 안 된다.

**중요한 출발점 정정:** upstream `src/vllm_ple_mmap.py`에는 이미 `BF16`/`F16` dtype, 16-bit scale-free path가 구현돼 있다. 따라서 “Blazux PLE는 FP8만 가능”이라고 단정하지 않는다. 다만 **Blazux 구현이 맞는 모델 `Qwen4ExpNGramEmbedding` / `ngram_embedding.py`와 Orcarouter Preview의 `Qwen3_8FlashNextNGramEmbedding` / `ple_layer.py`는 서로 다른 모델·Loader 경로**다. BF16 지원 자체와 **Orcarouter weight names/dimensions/load_weights/mmap/forward + vLLM0.32 ABI** 호환성은 별개다.

소스 근거:
- https://github.com/blazux/qwen3.8-Flash-DGX/blob/b0aa8b77604139557169387b2fa8386355d8b651/src/vllm_ple_mmap.py
- https://github.com/blazux/qwen3.8-Flash-DGX/blob/b0aa8b77604139557169387b2fa8386355d8b651/Dockerfile
- https://github.com/blazux/qwen3.8-Flash-DGX/blob/b0aa8b77604139557169387b2fa8386355d8b651/docs/VLLM-032.md
- 현재 `src/vllm_ple_mmap.py`, `src/p2_mtp_candidate_overlay.py`, `src/p2_functional_bundle.py`, `docs/BLAZUX-UPSTREAM-COMPARISON-20261029.md`.

## 2. 기존 증거를 보존하고 불필요한 재검증 중단

- **P1 기능 한정**: Preview 후보에서 PLE phase stats, Prefix Cache HIT `[0,6400,6400,6400]`, MTP acceptance +400, 선택 상태 SHA 12/12, Tool call→tool result→final 실경로 **BOUNDED_PASS**. 전체 물리 state correctness/배포 승인 아님.
- **P1 strict Numeric**: Prefix OFF/MTP OFF 포함 반복 first-token API logprob absolute drift `1e-4` 초과 실측. Prefix caching만의 문제 아님. QSA/Prefix/MTP 조합 재실험 반복 금지.
- **P2 source assets**: BF16 PLE unique-H2D opt-in, pinned tokenizer+업스트림 65,536 draft IDs, CPU reduced-head/helper, Preview MTP adapter overlay, stage/rollback 유틸은 **기존 구현/준비 자산**이다. Blazux-first 경로에 직접 유효한 것만 재사용.
- **Numeric witness**: 두 번의 독점 GPU 정비창에서 후보 HTTP_READY 및 원본 **same-ID HTTP 복구 PASS**, 그러나 `WITNESS_NO_EVENTS_IN_BOUNDED_LOG_TAIL`로 최초 차이 미관측. 원본 Sampler SHA `f95805b2...20dd216`, 변환 Stage SHA `a62b7cd7...ccaead4` byte-exact read-only 감사 **7/7 PASS**, 실제 worker runtime 조건 미검증. 최근 AST 10-test 확장 source HEAD `fa46304b...`는 사용자 DGX 검증 로그 없음.
- **증거 범위**: Preview에서의 P1 실측은 vLLM 0.32 후보의 PASS로 소급하지 않는다. 저장소 문서/코드 커밋도 실제 DGX/GPU 결과로 기록하지 않는다.
- 상세 역사: `docs/SESSION-HANDOFF-PROMPT.md`, `docs/BLAZUX-PHASE6-RESULTS.md`, `docs/P2-ACTIVE-SESSION-HANDOFF-20261102.md`. 필요할 때만 읽고, 이전 Numeric Source Audit 작업을 다음 첫 작업으로 재개하지 않는다.

## 3. 새 주력 Track B: 빠른 GO/NO-GO 호환성 결정

대규모 Gate·문서 작성 전에 다음 **실제 차단점**을 upstream 원본 소스 기준으로 확인한다.

| 우선 | 검증할 호환성 | PASS에 필요한 반증 가능 증거 | FAIL/대응 |
| --- | --- | --- | --- |
| B0 | **vLLM 0.32 모델 Config/Arch/Checkpoint Loader** | Orcarouter config.json/weight key/quant config와 upstream Qwen4Exp loader의 class/path/tensor 이름을 구체적으로 매핑. 전체 source SHA/version anchor 기록 | 구조적으로 맞지 않으면 그 차이만 adapter로 구현; 무한 이미지 빌드 반복 금지 |
| B1 | **BF16 PLE 약 95.37GiB** | upstream BF16/F16 support + Orcarouter 16-head/shard/weight naming/shape/scale-free/PLE hash/forward/custom-op ABI를 상호 대응, 전체 테이블 RAM 상주 회피 | false loading/shape/scale/API 변경 시 STOP, Preview BF16 구현을 최소 adapter로 참고 |
| B2 | **NVFP4 routed experts/QSA/quantization** | Uncensored checkpoint의 측면 tensor naming, quant config, indexer projection 및 exact top-k/patch compatibility 실제 manifest 기준 | “NVIDIA published=Orcarouter Uncensored” 가정 금지 |
| B3 | **BF16 MTP 31-tensor overlay** | target↔draft layer/weight load, compute_logits, aux output, MTP2/spec decode ABI 정합성. 먼저 **MTP OFF 최소 모델**로 타깃 기동 가능성 분리 | MTP ABI 차단이면 먼저 MTP OFF candidate만 진행 가능(사용자에게 기능 제한 명시), MTP2 배포 완료 아님 |
| B4 | **운영 API 품질** | Chat + Responses + actual tool roundtrip/stream/finish_reason/model ID 보존 설계, worker version | schema/parser 차이를 dedicated adapter로 분리 |
| B5 | **128GB unified memory + 성능** | image build 메모리·disk/loader·KV headroom 추정. CPU/source만으로 GPU 성능이나 실제 토큰 품질 PASS 주장 금지 | BF16 PLE/weight residency 로드가 안전하지 않으면 소형 CPU 통합 뒤 정지. 원본과 **두 모델 동시 기동 금지** |

**빠른 결정 규칙**: Track B가 가능한 최소 호환 adapter의 명확한 규모·근거와 non-mutating CPU test, isolated image 계획을 제공하면 `GO_TO_MINIMAL_CANDIDATE`. 핵심 Model Loader/PLE/MTP ABI가 광범위하게 깨지고 유지관리 비용이 Preview 포팅보다 높다는 소스 증거가 있으면 `NO_GO_KEEP_PREVIEW_TRACK_A`. 모호한 상태는 `BLOCKED_NEEDS_EXACT_EVIDENCE`로 남기되, 같은 파일/AST/테스트를 다시 조사하는 루프는 금지한다.

## 4. 최소 구현 순서 (최대 실질 변경을 한 번에 묶음)

1. **읽기 전용 비교+adapter 판정**: 최신 upstream HEAD·우리 HEAD를 다시 pin, exact source files/Config/Tokenizer/Loader/PLE/MTP mismatch를 기능 매트릭스로 작성. GPU/모델/API 부하 없음. 라이선스·원본 출처를 준수.
2. **Blazux upstream 기반의 격리 Track B 작업 트리**: 기존 Preview 브랜치에 v0.32 패치를 덮어쓰지 말고 upstream SHA를 baseline으로 사용. 별도 repo/branch/worktree 경로를 정할 때 GitHub 공통 git history/merge feasibility를 먼저 검증한다. 기존 저장소와 history가 달라 부적합하면 새 저장소를 임의 생성하지 않고 사용자에게 정확한 branch/fork 결정을 요청. 원본 upstream에 직접 push 금지.
3. **Orcarouter 최소 adapter**: 모델 등록·config/loader/weight compatibility, BF16 PLE lookup, NVFP4 QSA, MTP2 overlay 중 **실제 필요한 변경만**. upstream 기능을 재구현하지 않는다. 파일 개수를 늘리는 것보다 좁은 diff 선호. PLE opt-in/검증 기능은 기본 안전 OFF. MTP OFF부터 기능 분리 가능하지만 MTP2는 최종 사용 요구로 기록.
4. **묶음 CPU/소스/이미지 빌드**: 정확한 installed ABI/임시 synthetic fixture와 주요 실제 weight metadata 범위에서 수용·거부 시험. CPU/Source PASS != 런타임 GPU PASS. networkless image build 가능 시에만 실행; 원본 이미지/컨테이너/캐시·weights 불변, 불명확한 Docker 작업 자동 실행 금지.
5. **향후 별도 승인된 1회 독점 GPU 후보 창**: 동일 ID 원본 보호/복구, 후보 단독 기동 및 모델 ID/API, Prefix, Tools/Responses, BF16 PLE, MTP2(opt-in), TTFT/TPS/Memory를 **하나의 통합 검증**으로 수집. Source-only 상태에서 “이미 GPU 통합 완료” 금지. 이전 2차 Numeric 창 승인을 새 창 승인으로 재사용하지 않는다.
6. **판정**: 결과가 좋으면 Track B를 주력 후보로 선택. 부적합하면 Preview fallback 유지하고 잘 만든 adapter 자산만 회수. 운영 cutover는 별도 요청·승인 후.

## 5. P1/P2/P3 재구성

- **P1 — 기록 동결**: Preview에서 검증한 핵심 3기능 bounded PASS. strict Numeric FAIL 및 P1_RELEASE_BLOCKED는 그대로 보존.
- **P2 — Blazux-first 호환성 판정 + Orcarouter 최소 기능 후보**: 상기 B0–B5 차단점 해소, 원본 Blazux 기능 재사용, Orcarouter Uncensored BF16 PLE/stock MTP2(초기 분리 가능), API 계약 및 원본 복구. **소스 준비→runtime validated→release 각각 별도 상태**.
- **P3 — 후속·고급 및 독립 연구**: reduced 65,536 MTP vocab, BF16 unique H2D 성능 ROI·CUDA/DMA 심층, vLLM0.32 이상의 추가 엔진 업그레이드, 500K/YaRN/M-RoPE, Hybrid FP8, 선택 DFlash2, first-divergence Numeric 심층 RCA/전계층 physical state. 다만 **vLLM0.32 기반 호환성 자체는 P2 Track B 필수 기반**이 됨(기존 문서에서 “v0.32는 무조건 P3”라는 권고는 더 이상 적용되지 않음).
- **출시 Gate 유지**: 사용자가 정한 logprob pairwise abs ≤`1e-4`는 기존 release criterion. 원본도 실패한 이유를 명확히 분리해 기록하되, P3로 RCA를 미뤘다는 이유로 strict 조건이 PASS/면제되는 것은 아니다. 정책 수정은 명시적 별도 결정. `P2_FEATURE_IMPLEMENTED` / `P2_GPU_VALIDATED` / `RELEASE_APPROVED` / `DEPLOYED` 명확히 분리.

## 6. 효율·GitHub·DGX 운영 규칙

- **동일 SHA의 단순 static audit 재반복, 테스트 건수 부풀리기, 영구 문서 중복, 한 줄 수정마다 PR, 끝없는 예비분석 반복 금지.** 실제 적용 가능한 adapter 구현과 반증 가능한 검증/막힌 원인을 우선한다.
- 한 대화에서 **소스 조회 → adapter 코드·최소 테스트 → 영구 문서 한 번 갱신 → Source Manifest 정합성 → GitHub commit/PR/코드 검토/merge → DGX에 단일 묶음 명령**까지 가능한 것은 완료한다. GPU나 운영 리소스가 필요할 때만 별도 승인 요청.
- GitHub 연결 도구로 실제 read/write 가능. 작업 브랜치, base HEAD, commit SHA, PR URL, check-runs, merge 결과/manifest 일치를 검증한다. `main` 보호; PR merge 대상은 승인된 개발 브랜치. CI_NOT_RUN과 DGX_NOT_RUN을 PASS로 표기하지 않는다.
- 사용자 DGX 프로젝트 checkout `~/Workspace/llm/blazux-phase6-gates`는 Preview Track A 전용으로 보존. 신규 upstream Track B worktree는 **원본 checkout/운영 경로를 덮어쓰지 않는** 별도 디렉터리에서만 준비. 현존 자산 재사용, stage 자동 재생성/삭제 금지.
- 원본 Docker `3fc5...` rm/recreate/exec/patch 금지, 이미지 digest와 StartedAt 검증; 보호된 weights/HF cache/PLE/기존 서비스 포트 변경 금지. **DGX는 사용자가 직접 명령 실행**하므로 명령은 사전·사후 검증을 포함하는 하나의 명확한 복사 블록으로 제공한다. 사용자에게 매번 같은 승인 질문/정보 요청 금지.
- 현재는 **개발 방향/문서 정리만 승인된 상태**. 3차 Numeric GPU 창, 새 Blazux GPU 창, 서비스 중단/운영 cutover 모두 아직 승인 안 됨.
- 결과는 “완료한 실제 코드/실측”, “미검증/차단”, “다음 1회 명령 또는 결정”만 간결하게 보고한다.

## 7. 새 대화 인수인계

다음 새 대화에서 **`docs/NEXT-SESSION-BLAZUX-FIRST-PROMPT.md` 전체를 붙여넣고**, 최신 GitHub의 이 문서 및 `docs/SESSION-HANDOFF-PROMPT.md`를 읽는다. 과거 세부 규칙이 새 결정과 충돌한다면 **운영 안전·출시 Gate는 유지**하고, 작업 **우선순위는 이 문서가 우선**한다. 다음 어시스턴트는 문서만 추가하고 종료하지 말고 B0–B5와 실제 최소 adapter까지 가능한 범위에서 한 번에 진행한다.
