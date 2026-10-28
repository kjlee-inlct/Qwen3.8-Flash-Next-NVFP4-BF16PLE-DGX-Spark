# 2026-10-28 blazux 적용 목표 이탈 — 원인 분석 및 재발 방지 정본

## 무엇이 잘못됐는가

**사용자의 실제 목표:** Orcarouter BF16 PLE + BF16 MTP 기반 추론 환경에 유용한 blazux 기능을 안전하게 적용하고, Pi Agent Tool Calling/Responses 신뢰성, PLE 성능과 Mamba/Prefix-cache 정확성의 실질 개선을 검증하는 것.

**어시스턴트의 작업 관리 실패:** 실제 기능 코드와 실사용 검증보다 소스 조사, CPU-only 합성 오라클, 별도 A/B 세부 Gate, Source Manifest/핸드오프 커밋을 연속해서 늘렸다. P6-A 활성 ABI가 기존 비침습 인터페이스만으로 관측 불가능하다는 사실을 확인한 뒤에도 B0, B1a와 추가 B1b 합성 시험 설계로 넘어갔다. 각 작업은 제한된 범위에서 의미가 있었지만, 실제 기능 적용 가능성과 GPU 정합성의 증거 공백을 좁히는 데 충분한 진전이 없었다. 어시스턴트가 이 교착을 조기에 중단하고 사용자에게 기능 구현 중심의 대안을 제안하지 못한 것이 핵심 실수다.

**정확한 실측과 미완료의 구분:**
- Phase 4: 기본 OFF PLE Fast Gather 및 per-table gather stats 옵션 코드/소형 CPU byte-exact 시험 PASS. 실제 전 과정 wait/dedup/gather/stage 계측, 운영 엔진 적용, TPS 개선은 확인되지 않았다.
- Phase 5: Prefix-cache/Mamba, Tool/Responses, reduced draft vocab의 합성 계약/소스 조사 PASS. 실제 cold/cache-hit 정합성, Preview Parser 서버 동작, reduced vocab 적용·acceptance는 미실행.
- Phase 6 B0: DGX 소스 SHA 3aa40292f96427d3592ebdba971b31484c2a6079에서 124/124 unit·Source220/220·targeted 25/25 CPU 합성 PASS.
- Phase 6 B1a: DGX 소스 SHA 37b883793bdd33f8aa2d4810947a94fef3aa5c20에서 147/147 unit·Source224/224, 고정 Docker identity stable, host MemAvailable 14620→14609 MiB, NVML PARTIAL. 성공 상태는 PASSIVE_METADATA_COLLECTED_NOT_GPU_READY일 뿐이다.
- P6-A 실제 active Scheduler/Mamba/physical memory ABI는 BLOCKED_MISSING_IN_PROCESS_EVIDENCE. B1 실제 CUDA/Triton, P6-B 정식 PASS, P6-C/D 미실행. 두 번째 모델 GPU 안전 공존성도 입증되지 않았다. PRE-B 잠정 벤치 36회 원본은 보존됐으며 재실행 승인은 소진됐다.
- **현재 8개 blazux 신규 기능의 운영 적용 성공 증거는 0개.** 기존 BF16 PLE 및 BF16 MTP=2의 runtime 구동 증거가 있더라도 새로운 blazux 기능 적용 완료로 합산하지 않는다.
- 어떤 GitHub docs/manifest HEAD가 어떤 DGX source SHA의 합격 영수증을 기록했는지 구분한다. 단위시험 147개나 Manifest 224개는 사용자 기능 완성률/성능개선율이 아니다.

## 반드시 지킬 작업 방향 교정 규칙

1. **기능 결과 우선:** 새 작업을 시작하기 전에 (a) 사용자에게 제공될 기능·운영 가치, (b) 변경될 실제 코드/경로, (c) 최소의 독립 검증, (d) 사용 가능해지기 위해 남는 차단 요소를 4항목으로 적는다. 실질 기능·통합을 전진시키지 않는 단순 검증 추가는 자동 선택하지 않는다.
2. **검증 Gate는 산출물이 아니라 수단:** source AST, synthetic CPU, 테스트 개수, Manifest PASS, 문서 커밋은 각각 그 범위로만 보고한다. 기능별 상태는 별도로 SOURCE_REVIEWED / IMPLEMENTED_OFFLINE / CPU_VERIFIED / GPU_VERIFIED / API_VERIFIED / DEPLOYED_VERIFIED로 기록하고, 임의 퍼센트·막대나 Phase 완료를 기능 적용률로 표시하지 않는다. 옵션 기본 OFF와 실제 서빙 적용은 별개다.
3. **증거 없는 교착 STOP:** 동일한 원인이 반복되고 새로운 관측 경로·승인·실험 실행 환경이 없다면 같은 ABI/메모리 자원 자료를 이름만 바꿔 다시 수집하거나 A3/A5/B1a/B1b 후속 세부 Gate를 무한히 만들지 않는다. BLOCKED의 정확한 이유와 필요한 새 증거·승인·자원 조건을 한 번 기록하고 해당 작업을 DEFERRED_BY_EVIDENCE로 전환한다. 그 사이 독립적인 P1 기능 구현/오프라인 시험을 진행하도록 우선권을 이동한다.
4. **한 묶음의 완료 기준을 먼저 고정:** 작업마다 실제 코드 변경, 실패 가능한 품질 오라클, 독립 실행 명령, 정확한 SHA, 보존된 실패/rollback, 합격/차단 판정이 있어야 한다. 합성 증거만 가능한 경우 CPU_VERIFIED까지만 완료로 표시하고 다음 실환경 Gate가 무엇인지 명시한다. 별도 Gate·Phase·브랜치는 새로운 위험/승인/산출물이 있을 때만 만든다.
5. **작업-가치 검토:** 작업마다 다음 사용자 가치까지의 거리가 가까워졌는지 묻는다. 연속 두 작업에서 유의미한 기능 코드·독립 실행 경로·새 실제 증거가 증가하지 않으면, 다음 Gate 생성 전에 반드시 방향을 재평가한다. 사용자가 계속 진행하라고 해도 현재 목표를 먼저 재확인하고 불필요한 반복을 피한다. 중단/재우선순위 제안은 사용자 승인을 요구하는 GPU/운영변경을 자동 실행한다는 뜻이 아니다.
6. **안전과 성과는 동시에 지킨다:** 단일 DGX 운영 컨테이너·이미지·model view·가중치·포트·기존 벤치 원본 변경, 비승인 Docker run/exec/attach, GPU 커널/새 모델, 실서비스 inference/benchmark, CI/PR/merge 및 runtime patch 무단 실행 금지. 하지만 이 금지가 독립적인 CPU/source 수준 실제 기능 구현을 막는 이유가 되어서는 안 된다. 기능 준비는 별도 소유 경로와 기본 OFF·fail-closed 형태로 진행할 수 있으며, 설치·시작·통합은 별도의 정확한 승인과 확인을 받는다.
7. **기록 절약/정본화:** 중복된 영수증·동일 문구를 매 세션의 여러 문서에 길게 복제하지 않는다. 이 교정 원칙은 본 문서를 정본으로 하고, 영구 핸드오프·현재 핸드오프에는 짧게 링크하며, 결과 증거는 기존 Phase별 results의 SHA로 연결한다. Source Manifest는 변경된 모든 tracked path/mode/blob SHA를 빠짐없이 반영한다. 기록-only SHA를 실 DGX PASS라 주장하지 않는다.
8. **사용자 목표 목록을 유지:** P1 세 가지(PLE 단계별 계측, Prefix-cache 정확성, Tool Calling/Responses), P2 세 가지(MTP reduced draft vocab, PLE Gather, 별도 vLLM 0.32), P3 두 가지(YaRN 500K, Hybrid FP8)의 기능별 상태를 각각 보존한다. Track A와 vLLM 0.32 별도 Track B는 혼동하지 않는다. P3 우선순위를 이유 없이 올리지 않는다.

## 다음 대화의 실천 우선순위

**기능 구현에 집중.** 먼저 P1에서 기존 구현 자산을 살리는 가장 작은 실제 기능 단위로 PLE CPU 단계별 계측(wait/dedup/gather/stage)의 누락된 부분을 분석·구현하고, 기본 OFF·정확성·오버헤드 CPU 오라클을 제공하는 것을 우선 후보로 삼는다. 동시에 Pi Agent를 위한 Tool/Responses Preview Parser 호환성의 독립적인 소스/모의 API 시험 코드 준비는 병행 후보이다. 실제 Prefix-cache 검증이나 B1 GPU work는 현재 증거/승인 불충분 상태를 유지하고, 새로운 승인과 충분한 실행 가능성이 생길 때만 재개한다. PLE Gather 기존 Fast 옵션의 실모델 성능, MTP reduced vocabulary, 공식 vLLM v0.32, YaRN 500K, Hybrid FP8은 각 해당 Gate와 별도 결정에 따른다.

**이번 요청의 권한 범위:** 이 문서와 인수인계 운영 규칙 기록만. 기능 구현·실행, GPU·운영·HTTP·벤치·CI·PR/merge 승인을 새로 제공한 것이 아니다. 기존 P6-B1b draft/계획을 자동 커밋·실행하지 말고, 다음 작업은 위 우선순위에 따른 기능 단위로 재평가한다.

## 다음 작업 보고 템플릿

- **사용자 기능 목표:** 어떤 사용 시나리오가 달라지는가?
- **이번에 실제 바뀐 코드:** 파일/함수/옵션, 기본값 OFF 여부
- **검증 범위/증거:** CPU/source/GPU/API/운영을 분리, 정확 SHA
- **운영 적용 상태:** NOT_APPLIED / 준비됨 / 별도 승인 후 검증 완료
- **차단 및 다음 한 걸음:** 새 실제 증거를 얻거나 구현을 전진시킬 가장 작은 작업 하나

위 내용을 먼저 작성한 다음에만 테스트·실행 계획·새 Gate를 제안한다.
