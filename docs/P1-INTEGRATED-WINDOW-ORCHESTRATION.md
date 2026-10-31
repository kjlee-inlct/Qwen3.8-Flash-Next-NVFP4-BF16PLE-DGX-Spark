# P1 integrated GPU window orchestrator (PREPARED, NOT EXECUTED)

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

This orchestrator has NOT been executed on DGX GPU or with original stopped.
No PR, merge, production port change, P2/P3 or vLLM 0.32 migration.
