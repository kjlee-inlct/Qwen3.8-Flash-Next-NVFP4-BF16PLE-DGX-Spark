# P1 Preview Tool/Responses + QSA combined image (CPU-only)

Purpose: materially integrate P1 Blazux parser/Responses functionality into
the existing pinned Prefix ON + QSA candidate image, rather than adding
another synthetic gate.

2026-10-31 correction: first DGX build at 969bc377 failed closed with
PREVIEW_PATCH_CONTEXT_MISMATCH_1 because the initial builder invoked the
v0.32 patch family on Preview sources. The revised builder uses the already
implemented Preview-native marker -> schema -> Responses patches, keeping the
strict source pins. The failed build did not stop the original. No P2/P3 work or vLLM 0.32 migration.

## Components and exact parent

- Parent: kjlee-qwen38-p1-qsa-exact:3852995a19f4, image
  sha256:56b9df34daa5207956ded935f38ee900a44c4f8a737302b18abb03a58e46c518.
- Existing two-file Prefix cache fixes and opt-in QSA exact top-k remain
  in parent; this build does not modify their layers.
- Source: three pinned Preview-native patches (marker, schema, Responses) already
  verified by the existing Preview Parser/Responses CPU integration.
- Rebase against original Preview Python parser/Responses source from
  read-only docker cp, then apply with patch --fuzz=0 in private temp context.
- All observed Preview source SHA pins and native patch SHA pins are checked
  via src/preview_p1_real_parser_cpu.py::_stage, then AST parsing.
  The v0.32-only qwen-tool-preamble.patch bundle is NOT applied.
- One Docker COPY layer of only the touched allowlisted Python source files.
All staged Python files are chmod 0644 and subdirectories 0755 before COPY;
any unexpected patch artifact is rejected, including with operator umask 077.
- No RUN, import vllm, Docker exec, stop, GPU, model or HTTP requests.

## PLE mmap compatibility

The installed vllm_ple_mmap.py in the original container is SHA compared
against repository src/vllm_ple_mmap.py. This stage never replaces the PLE
module or turns on VLLM_PLE_PHASE_STATS. Status SAME means the repository
module is already installed; DIFFERENT or MISSING requires an explicit
source-ABI/delta decision before PLE stats integration. Do not silently
overwrite the BF16 mmap implementation currently serving the live model.

## DGX CPU-only build (after exact feature branch sync)

    cd ~/Workspace/llm/blazux-phase6-gates
    HEAD=$(git rev-parse HEAD)
    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v tests.test_p1_preview_tool_qsa_image
    PYTHONDONTWRITEBYTECODE=1 python3 -m src.p1_preview_tool_qsa_image --expected-head "$HEAD" --build

CPU-only image build and source staging are not runtime verification.
The candidate has no approved GPU launch/restore path; do not run it using
the existing two-file P1 Prefix release launcher. Tool/Responses API and
strict logprob numeric parity remain NOT_VERIFIED. No deployment to port8000.
