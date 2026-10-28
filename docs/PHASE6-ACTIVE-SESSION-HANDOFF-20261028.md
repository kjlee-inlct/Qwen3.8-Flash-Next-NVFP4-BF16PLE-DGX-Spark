# P1 현재 진행 작업 전용 인수인계 — 2026-10-28

이 문서는 **현재 진행 중인 작업만** 다룬다. 확정/완료/영구 규칙/과거 DGX 증거를 다시 설명하지 않고 해당 정본을 읽는다.

- 영구 규칙: main의 docs/SESSION-HANDOFF-PROMPT.md (docs-only PR #6, merge b0c7d9067c555dd43a31b49bca9be75664c06c97). 이 문서에 P1 완료 뒤 **P2 자동 전환 금지**와 레거시 Docker 종료·신규 Wizard 중지 절차 분리 규칙이 확정됐다.
- Phase6 기능 브랜치의 자세한 영구 규칙: docs/SESSION-HANDOFF-PROMPT.md, docs/BLAZUX-DELIVERY-DRIFT-POSTMORTEM-AND-GUARDRAILS-20261028.md. 검증 이력과 정확한 SHA: docs/BLAZUX-PHASE6-RESULTS.md.
- 저장소 kjlee-inlct/Qwen3.8-Flash-Next-NVFP4-BF16PLE-DGX-Spark, 브랜치 feature/blazux-phase6-runtime-gates, 실제 DGX checkout $HOME/Workspace/llm/blazux-phase6-gates.

## 현재 사용자 기능 목표

단일 DGX Spark에서 Orcarouter BF16 PLE + BF16 MTP(2)를 유지하며, **P1 Preview-native Qwen3 Tool Calling/Responses 신뢰성**을 실제 Parser→Serving 출력/스트리밍 경로에서 확인·수정한다. 완성된 Tool Call을 정식 Responses FunctionCall로 전달하고, JSON Schema 위반·미등록 함수·빈 stop 및 종료 오류를 성공으로 오인하지 않도록 한다. 모델 토큰 입력은 격리 CPU fixture. 실제 모델/GPU/API/HTTP/배포 인증은 아님. P1 PLE 단계별 계측 및 Prefix-cache/활성 Mamba ABI는 각 영구 정본에 남긴 별도의 미완료/차단 과제이며 현 세션의 주된 작업이 아님.

## 작업 코드와 마지막 실제 증거

- 세 SHA-pinned Preview native 패치: src/preview_p1_patches/qwen-preview-native-marker.patch, qwen-preview-native-schema.patch, qwen-preview-native-responses.patch. 설치 vLLM 원본 9파일과 SHA를 확인해 임시 복사본에서만 marker→schema→responses 순서로 --fuzz=0 적용. 실제 설치나 운영에는 적용하지 않는다.
- src/preview_p1_real_parser_cpu.py: 실제 Preview Qwen3 Parser import, XML/schema/청크 스트리밍 CPU 사례; DGX SHA fd544615c370dd1cbb1ad0764388c3d21f9b465c에서 **6/6 PASS**.
- src/preview_p1_real_responses_cpu.py: 실제 Preview OpenAIServingResponses/Pydantic 이벤트. DGX SHA 9011910bd369ce6d685a1c453e5c6a9a8fdd70dc에서 독립 완료/미완료/실패 이벤트 **6/6 PASS**. 그 뒤 동일 스크립트에 **Parser→Serving 연결 8사례 추가**(예상 합계 14): 정식 ResponsesRequest, 정상/위반/미등록 XML 함수, 최종 ResponseFunctionToolCall/wire, 텍스트 보존, SSE 성공/실패.
- **마지막 실제 사용자 DGX 실행 SHA 041d5871249746cf029f1e453ec9fab2a4d56d3e**: Phase6 전체 단위시험 **181/181 PASS**, Source Manifest **247/247 PASS**, PLE synthetic byte-exact, Phase4 flags 4/4, Phase5 synthetic 14/14 PASS. 그러나 **새 Parser→Serving 연결 검사는 FAIL**: {"status":"BLOCKED_NOT_APPLIED","reason":"REAL_RESPONSES_EVENT_BEHAVIOR_FAILED"}; runner 최종 STOP: isolated CPU test failed (exit=2). 성공 완료 마커 미출력, 실제 기능 통합 성공 주장은 금지. 증거: 사용자 첨부 붙여넣은 텍스트(1)(20261028-070407).txt, 결과 장부에도 기록.
- **최신 기능 코드 커밋 e8070dcbb69742a50f963b66b70ed08799a83e01**: 위 불명확한 오류를 좁히도록 기존 src/preview_p1_real_responses_cpu.py의 검사 문턱은 유지하고 8개 실패 단계와 허용목록 예외 클래스만 출력. 오류는 REAL_RESPONSES_<STAGE>_<CLASS>_BLOCKED, 비밀/입력/모델 내용/stack/파일경로 출력 금지. **e8070dc는 아직 DGX NOT_RUN**.
- 이 인수인계 **docs-only 기능 브랜치 커밋 때문에 최종 GitHub feature HEAD는 e8070dc 이후로 한 번 더 진행**한다. 따라서 e8070dc를 다음 실행의 --expected-head로 재사용하지 말고, 새로운 정확한 feature SHA를 재조회한다. docs-only HEAD도 DGX NOT_RUN.
- Runner scripts/ple-phase-stats-cpu-container.sh, --bundle p1-real-responses 재사용. Source Manifest 247개. CI/실모델/API 구동 미인증.

## 마지막 GitHub 상태 (2026-10-28 조회)

- feature/blazux-phase6-runtime-gates: 기능 코드 SHA e8070dcbb69742a50f963b66b70ed08799a83e01 + 본 인수인계 docs-only 커밋(다음 세션 HEAD 재조회). 현재 활성 P1 기능 PR **없음**, 미완료 P1 코드는 main에 들어가지 않았다.
- main: **b0c7d9067c555dd43a31b49bca9be75664c06c97**, 문서-only PR #6 (P1/P2 수동 경계 및 레거시 서비스 보호)를 검토, comment review, **MERGED**. main 파일 119개 전체 Source Manifest Git 트리 비교 정확 PASS, **DGX/CI 미시험인 docs-only SHA**.
- GitHub Actions workflow runs 0, PR check runs 0, commit status contexts 0(기본 표시 pending). **CI_NOT_VERIFIED ≠ PASS**. 사용자 새 CI 실행 승인 없음. PR #6만 이번 인수인계 요청에서 처리, 기능 브랜치 PR/merge는 하지 않음.

## 다음 대화 첫 행동과 우선순위

1. GitHub 커넥터로 최신 feature HEAD/PR/CI 및 본 문서, 영구 규칙, results, source manifest를 읽고 source/dgx-tested SHA를 구분한다. 사용자에게 기능 변경의 가치/최소 독립 검증/미해결 차단을 짧게 제시한다.
2. **현재 P1 오류를 가장 먼저 재현·분리**: 사용자 DGX에서 feature checkout을 git pull --ff-only하고 정확히 확인한 40자리 신규 HEAD로 아래 기존 명령을 1회 실행하도록 안내한다. CPU-only isolated runc/no network/no GPU; 기존 레거시 Docker 실행 상태 보존.
   bash scripts/ple-phase-stats-cpu-container.sh --expected-head <GITHUB_LATEST_FEATURE_HEAD> --bundle p1-real-responses --execute
3. 로그의 REAL_RESPONSES_<STAGE>_<CLASS>_BLOCKED를 기준으로 **정확히 어느 handoff 단계인지** 식별. 실제 Parser/Serving 결함과 시험 fixture의 API 사용 오류를 분리. 필요하면 정해진 실제 소스 preimage와 패치만 참조해 작은 코드 수정; 기존 안전 성공 기준을 완화하거나 시험 패키지/새 Gate를 늘리지 말 것.
4. 변경 코드·테스트·문서·Manifest를 전 파일 path/mode/blob SHA까지 동기화하고 기능 브랜치 HEAD CAS 커밋. 이후 사용자 DGX 실행 로그에서 동일 CPU-only bundle PASS 여부 확인. 새 HEAD에 대한 검증 로그가 없으면 NOT_RUN.
5. CPU 통합이 PASS여도 실제 HTTP/API/GPU/model/운영 검증은 별도 승인과 격리·rollback 준비 이전에 착수하지 않는다. 다른 P1 미완료 과제(PLE 단계별 계측, Prefix-cache 실물 ABI)는 기존 정본 참조. **P1 완료 후 보고하고 멈춘다. P2는 별도의 명시적 사용자 지시 전 시작 금지.**

## 이 현재 세션에서만 적용되는 임시 규칙/금지

- 기존 레거시 Docker qwen38-flash-orca-uncensored-bf16-mtp, 포트 8000, 모델 image/cache/가중치·벤치 원본 보존. CPU runner는 기존 컨테이너 running/StartedAt·ID가 불변인지 검사한다. 운영 container를 먼저 끄면 runner가 차단될 수 있음.
- 기존 scripts/status.sh, doctor.sh, health.sh와 Wizard install/activate를 훗날 별도 승인된 운영 전환 사전점검에 재사용. **scripts/stop.sh 및 Wizard uninstall.sh는 신규 Wizard 소유 컨테이너만** 정지/제거한다. 레거시 운영 서비스 정지/전환·rollback에는 추가 사용자 승인 필요.
- 모델/GPU/HTTP 추론/벤치/운영 patch/stop/새 Docker GPU/CI 수정 또는 실행/기능 PR·main merge를 이번 문서-only PR 승인으로 확장하지 않는다. 반복적인 합성 CPU Gate, 형식적 문서/테스트 수 증식 금지; 진단→기능 수정→DGX 실제 증거 순서만.
