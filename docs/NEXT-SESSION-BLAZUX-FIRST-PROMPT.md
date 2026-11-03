# 새 대화 인수인계 프롬프트 — Blazux-first Orcarouter 적용 (2026-11-03)

다음 작업을 **즉시 실제 코드 중심으로 진행**하세요. 질문이나 반복 문서 작업부터 시작하지 마세요. 이 메시지는 새 전략을 확정하고 계속 개발하도록 하는 인수인계입니다. 대답은 한국어로 합니다.

## 1. 승인된 새 방향과 목표

기존에는 작동 중인 Qwen Preview Orcarouter에 Blazux 기능을 하나씩 포팅했지만, 턴과 source-only 검증이 지나치게 증가했습니다. 사용자가 **Blazux upstream을 기반으로 Orcarouter Uncensored를 이식하는 Blazux-first 접근으로 주력 경로를 전환할 것을 승인**했습니다. 기존 Preview 구현은 안전한 fallback으로 보존합니다.

**최종 목표:** DGX Spark에서 Orcarouter Uncensored(현재 NVFP4 routed experts + BF16 PLE 약 95.37GiB + BF16 MTP2 overlay)를 Blazux 최적화 vLLM 기반으로 구동하면서, OpenAI 호환 API `:8000/v1`, 모델 ID `qwen3.8-flash-next-orca-uncensored-bf16-mtp`, OpenWebUI/Pi Agent/Ollama 등 기존 연결을 유지하는 것입니다. 단순 원본 Blazux Qwen 모델 배포나 Preview 계측 연구가 목표가 아닙니다.

**읽어야 할 최신 정본:**
- `docs/BLAZUX-FIRST-ORCAROUTER-DECISION-20261103.md` — 새 방향, upstream 비교, B0–B5 호환성 판정, 실행·안전·GO/NO-GO 기준 **최우선**
- `docs/SESSION-HANDOFF-PROMPT.md` — 변하지 않는 운영 규칙과 역사적 증거. 오래된 단계의 “다음에 실행할 명령”은 새 결정으로 대체
- `docs/P2-P3-SCOPE-REALIGNMENT-20261103.md` — 이전 Preview-first P2/P3 개정안, 새 결정에 밀려 우선순위가 바뀜
- `docs/BLAZUX-PHASE6-RESULTS.md`, `docs/P2-ORCAROUTER-ADOPTION-ROADMAP-20261103.md`, `docs/BLAZUX-UPSTREAM-COMPARISON-20261029.md` — 필요한 세부 증거를 참조할 때만
- upstream `https://github.com/blazux/qwen3.8-Flash-DGX`의 실제 소스/README/Dockerfile/`docs/VLLM-032.md`/`src/vllm_ple_mmap.py`

**고정 비교점(새 대화에서 현재 HEAD 먼저 재확인):**
- Blazux main: `b0aa8b77604139557169387b2fa8386355d8b651` (2026-11-02 UTC 확인)
- 기존 개발 Repo: `kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark`; 브랜치 `feature/blazux-phase6-runtime-gates`; 전략 변경 직전 HEAD `a88a951d9e6b3ad34deef6ccef8a215cd08b8c96`. 이후 문서 전환 PR HEAD는 최신 GitHub에서 확인. `main`은 작업 대상이 아님.
- 실제 Orcarouter는 Preview vLLM `0.1.dev20073`; Blazux 기준은 공식 vLLM `0.32.0`. upstream의 기본 NVIDIA NVFP4/약 48GiB FP8 PLE와 Orcarouter의 BF16 PLE/Uncensored 체크포인트는 별개입니다.

## 2. 이미 확인된 사실 — 불필요한 재작업 금지

1. 기존 Preview P1 세 기능(BF16 PLE phase stats, Prefix Cache/GDN 부분 state, Tools/Responses)은 실제 DGX 제한적 `P1_FUNCTIONAL_VERIFIED=BOUNDED_PASS`. HIT `[0,6400,6400,6400]`, accepted MTP +400, 선택 state SHA 12/12, Tool→result→final 등을 확인했지만 **전체 출시 PASS·운영 배포 아님**.
2. 원본 Prefix OFF, MTP OFF에서도 반복 API first-token logprob 쌍의 abs delta가 `1e-4`를 초과. strict 수치 원인 미해결. P1_RELEASE_BLOCKED / DEPLOYED=FALSE 유지. **이 심층 RCA는 P3로 미룰 수 있지만 기존 배포 Gate는 그대로**입니다. 새 Blazux 후보가 동일 문제를 해결했다고 추정하지 마세요.
3. 기존 Numeric-only GPU 정비창 두 번은 후보 HTTP_READY와 원본 동일-ID/HTTP 복구에 성공했으나 Sampler Witness가 없어서 Numeric first-divergence를 특정하지 못했습니다. `WITNESS_NO_EVENTS_IN_BOUNDED_LOG_TAIL`. 이전 2차 창 승인은 소진됐고 **3차 GPU 실행에 재사용 불가**. 마지막 실제 원본 Sampler byte-exact 감사 7/7 PASS at `1f98a43b...`; 그 뒤 AST 10-test source 추가는 DGX 검증 결과가 보고되지 않았습니다. 이 정적 감사를 다시 첫 작업으로 반복하지 마세요.
4. 기존 `src/vllm_ple_mmap.py`의 BF16 mmap·unique-only H2D opt-in, `src/p2_mtp_candidate_overlay.py`, MTP draft vocab 65,536 asset 및 4-COPY stage 등은 Preview 경로 자산. 전체 GPU 적용/성능 PASS는 아니며 필요한 adapter 관련 부분만 선택적으로 참조합니다.
5. **새로 확인한 중요한 사실:** Blazux 원본 `src/vllm_ple_mmap.py`는 이미 `BF16`/`F16` dtype과 scale-free 16-bit PLE 경로를 지원합니다. 그러나 upstream `Qwen4ExpNGramEmbedding / ngram_embedding.py`와 Orcarouter Preview `Qwen3_8FlashNextNGramEmbedding / ple_layer.py`의 클래스·loader·weight keys/forward ABI 차이를 먼저 검증해야 합니다. **BF16 지원 존재 = Orcarouter 호환 보장 아님**.

## 3. 지금 수행할 작업 — 한 대화에 최대한 묶기

**A. Source 기반 빠른 호환성 GO/NO-GO 판정 (B0–B5):**
- 실제 upstream v0.32 Dockerfile/patch/main 모델 클래스와 Orcarouter Preview loader/config/Uncensored checkpoint의 이름·shapes·quantization 비교.
- BF16 PLE 약 95.37GiB의 shard naming, layout, hash, scale-free, mmap lookup/custom-op, Torch compile/CUDA graph 동등성 분석.
- NVFP4 routed expert/QSA 및 deterministic top-k path, BF16 MTP **31 tensor overlay**와 v0.32 draft/spec decode/aux outputs 정합성. MTP OFF 후보와 MTP2 목표를 구분.
- Chat/Responses/tool/stream contract, served model name/port, 128GB unified RAM/weights/KV memory budget.
- 결과를 **“재사용 가능 / 최소 adapter 필요 / 실제 blocker / runtime 미검증”** 매트릭스로 기록하고, GO_TO_MINIMAL_CANDIDATE 또는 NO_GO_KEEP_PREVIEW_TRACK_A를 근거로 판단합니다. 소스 근거 없이 가능하다고 말하지 않습니다.

**B. 가능하면 바로 구현:** upstream 원본을 기반으로 별도 격리 Track B adapter와 꼭 필요한 소규모 CPU·source 테스트를 실제 작성하세요. upstream 기존 구현을 다시 포팅/재개발하지 말고 BF16 PLE/Orcarouter Loader/MTP 호환 차이만 수정합니다. 가능하면 한 번에 후보 파일·최소 검증·빌드 준비를 만드세요. v0.32 branch/worktree는 원래 Preview checkout을 덮어쓰지 않게 구성하고, GitHub 브랜치 history/merge 가능성부터 확인합니다. **별도 GitHub 저장소 신설이나 원본 upstream 직접 push는 임의로 하지 마세요**. 접근·브랜치 전략이 불가능하면 그 정확한 기술적 blocker와 선택지만 알려주세요.

**C. 실행·검증:** 호환성 검증과 CPU/offline tests 및 무중단 image build 단계까지만 승인 범위를 지키세요. 기존 Docker/weights/HF cache/serving에 영향 있는 Docker build/run/exec/stop 또는 GPU/API 추론/벤치는 사전에 해당 명령과 영향 범위 확인이 필요합니다. GPU 후보 진입은 **별도 명시 승인된 독점 정비창**과 original same-ID HTTP recovery script가 있을 때만. 원본과 두 번째 대형 GPU 모델 동시 기동은 금지합니다. 모델 성능/정확성은 실제 DGX 실행 전 PASS로 기록하지 않습니다.

**D. GitHub에서 직접 완료:** 연결된 GitHub 도구로 코드와 최소 tests 작성, 정본 문서 1~2개만 갱신, Source Manifest SHA/mode/파일 수 검증, 개발 브랜치로 commit/PR 생성, diff/CI/충돌 검토, merge 및 최종 HEAD 재검증까지 수행하세요. 사용자가 이미 승인한 통상적 GitHub 개발 작업을 반복 확인하지 마세요. CI_NOT_RUN/DGX_NOT_RUN과 실제 실행 PASS는 분리하세요.

**E. DGX 핸드오프:** 한 번에 묶인 copy-paste 명령 한 블록만 제시하고 expected output marker·실패 시 STOP을 설명하세요. 사용자는 DGX에서 직접 명령을 실행하고 로그를 회신합니다. 반복되는 “이제 --preflight?” “이제 --build?” 턴을 최소화하세요. 미승인 GPU/서비스 중단 명령을 체인으로 포함하면 안 됩니다.

## 4. 반드시 보존할 운영 원본 및 금지 동작

- 원본 컨테이너 이름: `qwen38-flash-orca-uncensored-bf16-mtp`
- 고정 full ID: `3fc5a3d5be1d52595602287acd87895220219bad050484251ac0408a163ffc45`
- 원본 image: `sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a`
- 기존 Preview checkout: `~/Workspace/llm/blazux-phase6-gates` (Track A 유지).
- 원본 ID·image·StartedAt, weights, BF16 PLE shards, HF cache, compile cache, running `:8000/v1`, 기존 OpenWebUI/Pi Agent/Ollama 연결을 변경·삭제·덮어쓰기 금지. `docker rm`, 운영 컨테이너 `exec`/patch, model asset conversion, 원본 재시작, main 수정 금지.
- 원본 컨테이너가 복구돼야 하는 창에서는 항상 owner-checked 후보 제거 후 원본 **동일 ID + HTTP** 복구를 독립적으로 검증. 성공 증거 없으면 BLOCKED.
- Privacy: prompt/token IDs/full logits/개인정보/비밀 Docker ENV 출력 금지; bounded sanitized stats와 SHA만 기록.
- 새 전략은 **개발 방향 승인**이지 GPU/운영 cutover/strict `1e-4` release waiver 승인이 아닙니다.

## 5. 작업 방식과 최종 보고 형식

- 사용자는 **턴 과다, 반복 Gate/문서/합성시험**을 원치 않습니다. 같은 evidence에서 실질 구현 없이 작은 PR을 연속 생성하는 방식을 중단하세요. 계획 설명만 하지 말고 현재 권한 안에서 구현까지 진행하세요.
- 불명확한 부분이 있더라도 이미 있는 문서·GitHub 파일·사용자 제공 로그로 먼저 조사하고, **정확히 차단되는 경우에만 핵심 질문 하나**를 하세요. 테스트 fail이라면 같은 턴에서 원인 수정 및 관련 테스트까지 묶으세요. 실제 실행하지 않은 테스트 PASS 주장 금지.
- 응답은 간결하게 **(1) GO/NO-GO/이유와 구체적 호환성 차이 (2) 구현 변경과 검증 상태 (3) GitHub PR/HEAD (4) DGX에서 실행할 단 하나의 안전 명령 또는 필요한 승인 경계 (5) P3 백로그와 출시 차단 상태**를 전달하세요.
- 중간에 요청이 없는 이상 P1 Numeric 실험을 다시 시작하거나, Preview 경로에 Blazux 코드를 계속 역포팅하지 마세요. **Orcarouter를 Blazux에 적용하는 것이 이번 대화의 핵심입니다.**
