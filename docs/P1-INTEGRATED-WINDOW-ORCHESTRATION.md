# P1 integrated GPU window orchestrator (2026-10-31 executed once; next window unapproved)

## 2026-11-02 최소 기능 GPU window 실행 완료 (현재 최신)

실제 DGX tested HEAD `50fc65b65d10b36804c65e8a48d06d9bf3abecfe`의 **`--minimal-functional`** 경로로 단 한 번의 승인된 정비창을 수행. CPU 20/20 PASS, 실제 Tool result roundtrip PASS, PLE phase stats 수집 PASS, Prefix HIT `[0,6400,6400,6400]`/MTP accepted +400/선택 state SHA 12/12 match. `functional_evidence_complete=true`, window exit0. 원본 SAME-ID running·original-image unchanged·candidate removed·HTTP health/model 확인 PASS.

**기능 PASS와 출시 PASS는 다름:** `P1_FUNCTIONAL_VERIFIED=BOUNDED_PASS`, `P1_RELEASE_BLOCKED=TRUE`, `P1_FINAL_PASS=FALSE`, `strict_numeric_release_pass=false`, `full_state_reuse_verified=false`. 기존 full/strict 절차와 이 최소 창의 실행 범위는 달랐으며, **이 창에서는 과거 Responses/No-HIT/strict numeric 재시험을 생략**했다. 단일 정비창 승인은 사용 완료. `--minimal-functional`이라고 해도 새 승인 없이는 재실행 불가.

복구 안전장치(정확 ID, 후보 소유권, `finally` 복구)와 10월 31일 이력은 그대로 보존한다. [상세 기능 증거](P1-INTEGRATED-EVIDENCE-20261031.md) 및 [영구 결과 장부](BLAZUX-PHASE6-RESULTS.md) 우선.

### 이하: 2026-10-31 초안·실행 당시 내역 (역사 기록)


User DGX at feature HEAD 920444f1a6f85931ffc34ff1dcd25f73674a579e
verified Source Manifest 298/298, targeted API+runtime 16/16 unit PASS,
and integrated read-only preflight on the same original service ID.

New src/p1_integrated_window.py makes a *future, explicitly approved*
single-GPU window safer. It is not permission to interrupt the user's
existing service. The operator must independently approve downtime.

CPU-only guard tests (no Docker or network used by tests):

    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v tests.test_p1_integrated_window

Ordinary invocation without --execute and exact --approval refuses to run.
Do not supply approval arguments until downtime is explicitly authorized.

Explicitly approved service-window steps in code:
1. Verify source manifest, clean HEAD, original running exact ID, no
   existing candidates, pinned integrated image and a healthy original
   Chat protocol request before stopping.
2. Stop only original via checked scripts/stop.sh, no pause or removal.
3. Launch only pinned integrated candidate at 127.0.0.1:18080, MTP2 and
   Prefix ON, using the separate guarded src.p1_integrated_runtime.
4. Run tool roundtrip, Responses non-stream and SSE, strict Prefix/MTP
   comparison plus no-HIT controls; retain failures as failures.
5. The finally block ALWAYS attempts owned-candidate cleanup and
   same-ID original restore, even after API failure or partial stop.
6. If it cannot prove candidate absence/ownership, fail closed rather
   than risk running two GPU models. SIGKILL, power loss or Docker daemon
   faults cannot be guaranteed to execute Python finally. Maintain
   independent manual recovery steps in docs/P1-INTEGRATED-RUNTIME-WINDOW.md.

On success, CPU/oracle metadata is emitted; a positive numerical result
does NOT complete P1. Full GDN/PLE state copy evidence and live PLE stats
remain outstanding. Never claim P1 final pass without them.

At the time of original preparation, this orchestrator had NOT run on DGX.
No PR, merge, production port change, P2/P3 or vLLM 0.32 migration.

## 2026-10-31 실제 정비창 후속 상태 (위 PREPARED 문구보다 우선)

사용자 명시 승인 후 이 orchestrator가 실제 DGX `6c1397d78433b1fa2082047367b042b6e372a431`에서 **1회 실행**되었다. `P1_INTEGRATED_GPU_VALIDATION_INCOMPLETE` exit 2, 통합 이미지 API/Prefix/MTP 실관측과 수치 FAIL, **same-ID 원본 running/HTTP 복구 PASS**. 다음 정비창이 승인됐다는 의미가 아니다. 실제 수치·Tool 이유 코드·원본 numeric baseline 및 정확한 이후 HEAD는 [P1 통합 실측](P1-INTEGRATED-EVIDENCE-20261031.md), [원본 기준선](P1-ORIGINAL-NUMERIC-BASELINE.md), [활성 핸드오프](PHASE6-ACTIVE-SESSION-HANDOFF-20261028.md)를 따른다. `6c1397d...` 뒤 `8c86f54d...` Tool API 검사만 보강해 CPU 27/27 PASS, GPU 재실행 NOT_RUN. 기존 원본 서비스는 그대로 유지하고, QSA-only B 실험은 다른 이미지와 별도 실행/복구 루틴 필요.
