# Phase 6 provisional PRE-B benchmark — 2026-10-27 UTC

This is the one user-approved **existing-service** 12 conditions × 3 measured repeats benchmark at exact source SHA `d031d4196eab1f5f1603d6541eaf5a31b02192c0`. The 2026-10-28 operator console reported `PASS_PROVISIONAL_PRE_B_36`; the one-time benchmark authorization **has been consumed. Do not re-run**.

## Current publication status

- [summary.public.json](summary.public.json) contains all 12 **console-reported** condition-level numerical summaries, reproducibility pins, run classification and the reported SHA256 for the full result. This is **not** the 36-repeat raw dataset, standard deviation, or time series.
- [result.json](result.json) is now the exact original 533,082-byte full 36-repeat raw dataset, including each repetition's throughput time series. Original SHA256 `35c409d6f714bbce7b9c68d9cbc5c24f5a18e64575f1842daef1dc1d64d3a80d` and Git blob SHA1 `f963d6003f954bbc90c650a92104fddb34b38bbf` were independently verified against the uploaded bytes.
- The original private DGX staging directory and original checksum ledger remain private. Neither private environment, raw execution log, Docker IDs nor private telemetry were published. JSON keys and contents were reviewed for personal text and credentials before archiving.
- The 2026-10-28 follow-up DGX log reports `99/99` tests + `212/212` source manifest PASS at exact follow-up commit `882b590119afcdadb06afe9938c7f3e10c866656`; **this archival commit itself is not operator DGX tested**.

This dataset is a provisional **pre-B existing-service** reference only, **not** P6-A physical ABI PASS, P6-B/C/D PASS, or formal P6-D performance benchmarking. Historical pre-blazux baseline corpus/sampling/KV/cache equivalence has not been established; no strict A/B improvement/regression rate is justified.

Historical immutable baseline (unchanged): `results/llama-benchy/baseline/pre-blazux/20261026T221925Z/`.

See `docs/BLAZUX-PHASE6-RESULTS.md` for observation boundaries and operator evidence.
