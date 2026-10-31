# P1 Preview QSA exact top-k candidate (source-only)

Current running DGX Preview QSA path: models/qwen3_8_flash_next/nvidia/ops/qsa.py.
Exact source SHA256: c4ffe3674cafa0ce2dabc39a39f0ddbb4b594bc358ad210ffce9d04383350c7f.
On GB10 the original cooperative top-k path is excluded; persistent_topk is selected.
Blazux 0.32 QSA patch targets ops/qsa_indexer.py, but this Preview uses ops/qsa.py.

New src/p1_preview_qsa_exact_topk.py is a SHA- and anchor-checked opt-in port.
It masks uninitialized out-of-range logits and invokes torch.topk when
VLLM_QSA_EXACT_TOPK=1. The default QSA kernel branch remains unchanged.
torch.topk does not guarantee stable indices among exact ties; numerical
determinism and performance are NOT proven by static source inspection.

CPU-only operator commands after exact feature branch checkout:

    cd ~/Workspace/llm/blazux-phase6-gates
    HEAD=$(git rev-parse HEAD)
    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v tests.test_p1_preview_qsa_exact_topk
    PYTHONDONTWRITEBYTECODE=1 python3 -m src.p1_preview_qsa_exact_topk --expected-head "$HEAD" --build

The build derives a separate image from the pinned two-COPY Prefix ON release
c0160408ab22 (image ID sha256:85f2ac46b780c6e3079fdec577dff38104473871e5a1390e4c83239152b52aba),
with one additional COPY qsa.py and an ENV flag. No RUN, CUDA, weight mounts,
Stage modifications, container exec, inference, or original service stop.
Build result is not a license to launch: future runtime must have an
independently reviewed stop/restore lifecycle and new GPU service-window approval.

Current P1 status: release HTTP GPU smoke PASS, same-ID original restore PASS;
instrumented candidate Prefix HIT [0,6400,6400,6400], MTP accepted +400,
selected state SHA 12/12, 150 identical token IDs; strict logprob 1e-4 FAIL.
Full GDN/PLE state copy NOT verified. This QSA code is NOT_GPU_TESTED.
PLE stats and Tool/Responses integration are independent P1 workstreams;
do not claim either is included in this QSA-only candidate image.
