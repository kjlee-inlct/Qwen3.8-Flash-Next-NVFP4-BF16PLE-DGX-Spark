## 2026-11-03 Second approved Numeric GPU window — prevent successful diagnosis output loss

- Operator actual DGX HEAD 497056ea265825fb2e96d31fe7ba3b16fe417919: read-only preflight 20/20 PASS and offline image build PASS. Returned P2_NUMERIC_WITNESS_IMAGE_BUILT_NO_GPU, candidate tag kjlee-qwen38-p2-numeric-first-divergence:497056ea2658, original running.
- Second exclusive GPU window and temporary original-service downtime explicitly approved. Before execution, final diagnosis was found to call window.notify("P2_NUMERIC_DIAGNOSIS", **result) with result["status"], a guaranteed duplicate-key TypeError after successful measurement/restore. Fixed by result_status field and added full mocked run through restore+diagnosis JSON output test; focused 21 authored tests, new HEAD DGX/CI_NOT_RUN.
- Exact run order: git pull --ff-only origin feature/blazux-phase6-runtime-gates; bash scripts/p2-numeric-first-divergence-gpu-window.sh --preflight /tmp/p2-numeric-first-divergence-x_76hgqp; bash scripts/p2-numeric-first-divergence-gpu-window.sh --build /tmp/p2-numeric-first-divergence-x_76hgqp; verify both PASS and same original running; then approved --execute /tmp/p2-numeric-first-divergence-x_76hgqp 3fc5a3d5be1d52595602287acd87895220219bad050484251ac0408a163ffc45 sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a.
- New HEAD requires image rebuilt under new tag even if source Dockerfile unchanged. Execution produces candidate HTTP_READY, original SAME_ID_HTTP_PASS and diagnostic result_status/analysis separately. If missing witness, INCONCLUSIVE and do not repeat automatically; strict numeric release remains BLOCKED. Recover only owner-checked candidate and preserve original same-ID/container/image/weights. Maintain other published protections.

## 2026-11-03 실제 1차 GPU 정비창 결과 및 수정

- DGX HEAD `39f49210347f3d571f43e07b0ea254b8c18b15af`: 13/13 focused CPU PASS. `--preflight`·`--build` 모두 `UNCLASSIFIED_FAILURE`, 그러나 `--execute`는 원본 stop→후보 HTTP_READY→원본 same-ID HTTP_PASS 복구 성공. 진단 증거 파일에서 `WITNESS_FILE_ABSENT_OR_OVERSIZE` 발생. wrapper fail EXIT trap도 복구 PASS 재확인. **Numeric 분석 inconclusive, 원본 복구 PASS, P1/P2 출시 차단 유지**.
- 소스 고장 1: `notify(status, **facts)`에 key=`status` 중복 전달하여 Python TypeError. preflight/build 반환 상태는 `result_status` 이름으로 분리했으며 관련 테스트 추가.
- 소스 고장 2: Witness는 sampler.py에서 내부 `/tmp/p2-numeric-witness.jsonl`과 worker stderr 양쪽에 제한 JSON을 쓰도록 구현되어 있음. 이전 오류 코드는 `docker cp` 실패와 tar 과대 크기를 합쳐 실제 원인을 판별할 수 없었음. 수정본은 파일이 없을 때만 `docker logs --tail 256`의 전체 256KiB 한계 안에서 `P2_NUMERIC_WITNESS` prefix 라인만 수집. 모델 로그/텍스트는 출력하지 않음. Witness가 하나도 없다면 오류를 분명히 보고 **strict 1e-4 판정하지 않는다**. Docker exec/GPU side effects 없음.
- 사용자 다음 실행은 신규 GitHub 변경 pull 후 **`--preflight`만 먼저**, 그 후 `--build`가 exit 0과 반환 JSON을 내는지 확인한다. 1차 GPU 창은 이미 소비됐으므로 무조건 재실행하지 말고 자원/운영 복구 상태와 새 창을 별도 확인. `--execute` 성공 가능성은 새 preflight/build 및 실제 Witness 이벤트 수신이 확보되기 전에는 보장되지 않음. 신규 SHA DGX_NOT_RUN/CI_NOT_RUN.

# P2 Numeric FIRST-divergence DGX 독점 GPU 정비창 (2026-11-03)

## 승인과 보호 범위

사용자가 2026-11-03 "GPU 정비창 승인과 원본 보호·복구 절차 + 계속"이라고 명시. 범위는 같은 ID 원본 stop → 격리 GPU 후보 단독 진단 → 소유권 검증 후 후보만 제거 → 같은 ID 원본 start/health 복구. 원본 Docker container rm/recreate, weights/cache/PLE 파일 쓰기, 원본 이미지 수정, main 변경 및 운영 cutover는 금지.

## 확정된 이전 DGX 증거

- 사용자 DGX HEAD f240c29cb1c29b5d73bbebb7e0b798b6ec816c7f에서 Numeric 1-COPY source prepare 10/10 PASS SKIP0.
- 개인 candidate source stage: /tmp/p2-numeric-first-divergence-x_76hgqp (source only, Docker image 미빌드).
- Sampler SHA256 a62b7cd7f7eb637fdee7d8dd1e51b1bc47c3931bb1174f4f22280db28ccaead4
- Dockerfile SHA256 e9a988743cc7b76a7b6650c718ca852ea8cc351fb29b7b87511a7e8dd7f8df2f
- 원본 ID 3fc5a3d5be1d52595602287acd87895220219bad050484251ac0408a163ffc45
- 원본 image sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a

## 신규 구현 설계

src/p2_numeric_first_divergence_window.py / tests/test_p2_numeric_first_divergence_window.py / scripts/p2-numeric-first-divergence-gpu-window.sh.

- --preflight (읽기 전용): 정확한 개인 1-COPY stage, 0700/0600 권한, Sampler/Dockerfile SHA, receipt, 원본 ID/Image/StartedAt, Prefix OFF/MTP2, 다른 후보 부재 및 P1 launch template 검증. Docker build, GPU/API 실행 없음.
- --build: network=none, pull=false, no-cache, Sampler만 ONE COPY한 이미지를 기존 pinned 원본 image 위에 빌드. 기존 서비스 무중단; Docker child RootFS parent prefix + 정확히 1 레이어, 출처 labels, startup defaults, 진단 opt-in 기본 OFF 확인.
- --execute: full pinned original ID와 image ID 요구. 원본 HTTP health 확인 후 scripts/stop.sh 기반 stop, 절대 원본 rm 안 함. stop 후 MemAvailable >=96GiB 안전 하한 확인; 아니면 후보 GPU launch 없이 원본 restore. 격리 후보는 loopback 127.0.0.1:18080, read-only 캐시/recipe mounts, restart=no, 112GiB memory cap, Prefix OFF, MTP OFF, 원래 BF16 PLE, stock QSA, Witness=1, raw_logprobs mode. 4개 직렬 synthetic Chat 1-token response (seed 42, temperature 0, logprobs와 token_ids), 후보 내부 개인 worker jsonl만 docker cp로 회수, src/p2_numeric_report.py에서 API와 witness 결합 및 최초 로그 확률 차이 구간 분류.
- --recover: 후보 이름/ID/image/라벨/마운트/포트 검증 후 후보만 삭제, 같은 원본 ID를 restart하고 HTTP /health + /v1/models로 확인. 본 실행은 try/finally 및 외부 shell EXIT trap으로 복구 재확인. SIGKILL/호스트 다운의 자동 복구는 보장되지 않음. 후보 소유권 불명 또는 두 GPU 모델의 동시 기동 우려 발생 시 fail-closed 및 수동 조치.

## DGX 순서 (각 단계 결과를 다음 단계 전에 확인)

Phase A: latest commit / read-only GPU-window preflight. 이 단계 원본 무중단.

~~~bash
cd ~/Workspace/llm/blazux-phase6-gates
git pull --ff-only origin feature/blazux-phase6-runtime-gates
bash scripts/p2-numeric-first-divergence-gpu-window.sh --preflight /tmp/p2-numeric-first-divergence-x_76hgqp
~~~

Phase B: A 성공 시 오프라인 이미지 빌드만, GPU/운영 중단 없음.

~~~bash
bash scripts/p2-numeric-first-divergence-gpu-window.sh --build /tmp/p2-numeric-first-divergence-x_76hgqp
~~~

Phase C: B 성공 및 정비창 영향 인지 후 승인된 독점 GPU 측정, 반드시 복구 영수증 확인.

~~~bash
bash scripts/p2-numeric-first-divergence-gpu-window.sh --execute /tmp/p2-numeric-first-divergence-x_76hgqp 3fc5a3d5be1d52595602287acd87895220219bad050484251ac0408a163ffc45 sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a
~~~

Phase D: 복구 마커 미수신 또는 비정상 종료 시 (소유권 검증 가능할 때만) 추가 recover.

~~~bash
bash scripts/p2-numeric-first-divergence-gpu-window.sh --recover 3fc5a3d5be1d52595602287acd87895220219bad050484251ac0408a163ffc45 sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a
~~~

반드시 P2_NUMERIC_CANDIDATE_REMOVED_ORIGINAL_SAME_ID_HTTP_PASS 영수증 확인. exit2는 진단 실패나 BLOCKED와 원본 복구 성공 여부가 구분됨. 절대 원본 docker rm, git reset --hard, 사전검사 해제, 임의 두 모델 동시 실행 금지.

## 분석 해석 및 미완료

RAW_LOGITS_OR_UPSTREAM / LOGPROBS_COMPUTATION_OR_PRE_GATHER / POST_SAMPLER_OR_API / NO_STRICT_API_FAILURE_IN_SAMPLE / INCONCLUSIVE 는 최초 관측 차이의 분류지 물리 root cause 확정이 아님. 현재 strict 1e-4 미해결, Reduced MTP GPU acceptance NOT_RUN, BF16 PLE Unique H2D CUDA 완료 미검증, 최종 운영 출시 BLOCKED. 기존 QSA-only / MTP OFF A/B 실패를 단순 반복하지 않음. 4개 첫 토큰에서 1e-4 이하가 나오더라도 이전 150 token failure 해결 증거가 아님. 이번 코드 GitHub만 준비, 사용자 GPU 실제 실행 전 DGX_NOT_RUN/CI_NOT_RUN.

## 중단 조건

원본 ID/Image/StartedAt drift, source SHA mismatch, layer/label mismatch, 다른 candidate, 8000 HTTP unready, stop 후 MemAvailable 부족, port/mount/CLI/runtime worker mismatch, candidate startup timeout/OOM, witness 없음/분석 불일치, original same-ID restore HTTP 미확인. 상황별 status와 운영 복구 확인을 별도 기록하며 불명확하면 승격/추가실험 금지.
