# P1 integrated Preview image — BF16 PLE mmap and opt-in phase stats

## 2026-11-02 PLE 단계별 계측 실제 확인 완료 (현재 최신)

후보 계측은 pinned integrated Docker 이미지를 **재빌드하지 않고**, 소유권 검증된 중지 상태의 격리 컨테이너 writable layer에만 opt-in으로 삽입한 뒤 실행했다. tested HEAD `50fc65b65d10b36804c65e8a48d06d9bf3abecfe`, DGX `ple_phase_stats_observed=true`, gather calls=1, forward_calls=1, rows=131072. Forward 16.106ms, Dedup 4.266ms, CPU gather worker 누적 21.772ms, Wait 1.026ms, Stage 3.143ms, device-copy **호출** 0.824ms.

**P1 기능:** BF16 실모델 CPU phase 계측 출력 PASS. 병렬 `gather_work_s`와 inclusive Forward는 합산 불가; `device_copy_call_s`는 CUDA DMA 완료시간이 아니며 `gpu_dma_verified=false`. 실제 H2D/GPU 완료·NVMe 물리 bytes 및 최적화는 P2에 남긴다. 동일 이미지에서 기본 `VLLM_PLE_PHASE_STATS=0` 유지, 원본 서비스 변경 없음. 자세한 증거는 [P1 통합 GPU 영수증](P1-INTEGRATED-EVIDENCE-20261031.md)과 [Phase6 결과 장부](BLAZUX-PHASE6-RESULTS.md)를 따른다.

아래 CPU-only 이미지 빌드 당시의 `NOT_VERIFIED` 및 'GPU work before' 구절은 **2026-10-31 시점 기록**이며 현행 상태를 나타내지 않는다. 현재 기능 결과가 운영 출시 승인으로 바뀌는 것은 아니다.

### 이하: 이미지 생성 당시 구현/시험 기록 (역사 기록)


Objective: keep Orcarouter BF16 PLE and MTP2 while integrating existing
Blazux P1 Prefix-cache, QSA exact top-k experiment, Preview-native
Tool/Responses patches, and an instrumentable PLE mmap module.

## Grounded PLE provenance

Existing original DGX image PLE SHA256 =
91f17b6203f402785279836c479ead347416da4394049850a47f0ba347649b48.
That is exactly the source at Git commit
9492b78c6bc04638587b42f2ffeb0680b0fcb3ef,
src/vllm_ple_mmap.py (matched via GitHub raw source SHA256).
Current feature implementation SHA256 =
9c13cf71001618838532ee9145443647a09a087f68ef82e2c3909028b893617e.
History adds BF16 shard duplicate fail-closed check, default-OFF Fast Gather,
per-table gather/forward CPU-phase stats. CPU timers do not measure
asynchronous H2D completion, GPU time, or physical NVMe bytes.

## Candidate construction

Parent pinned image: kjlee-qwen38-p1-tool-qsa:b89641b4fb52
ID: sha256:e01dffd7542432476d81635e38a706fd73942c7f0832d8eacab34e9d2518cc66.
New image adds only a single COPY of the feature-branch PLE Python module.
Exact original and new PLE SHA256 are checked before local CPU-only build.
Original running container must retain its receipt ID; source HEAD, branch,
clean tree, remote and full Source Manifest are verified.

VLLM_PLE_PHASE_STATS and VLLM_PLE_FAST_GATHER remain OFF by default.
Stats must be enabled only in a separately authorized runtime candidate.
The image does not activate, restart, stop, or mutate the operating service.

## After exact HEAD fast-forward on DGX

    cd ~/Workspace/llm/blazux-phase6-gates
    HEAD=$(git rev-parse HEAD)
    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v tests.test_p1_preview_ple_integrated_image
    PYTHONDONTWRITEBYTECODE=1 python3 -m src.p1_preview_ple_integrated_image --expected-head "$HEAD" --build

Source CPU behavior regressions from src/test_ple_phase_stats_cpu.py,
src/test_ple_phase4_cpu.py and src/test_ple_mmap_cpu.py should also be run
using the existing isolated CPU-only test harness before GPU work.

Image build success means only CPU/source integration is ready.
GPU loading, PLE timing, actual Tool/Responses HTTP, Prefix-cache strict
1e-4 logprob and complete GDN/PLE state reuse are all NOT_VERIFIED.
Do NOT use the prior two-file Prefix release launcher with this image;
a separately reviewed same-ID restore workflow and explicit new GPU
maintenance authorization are required.
