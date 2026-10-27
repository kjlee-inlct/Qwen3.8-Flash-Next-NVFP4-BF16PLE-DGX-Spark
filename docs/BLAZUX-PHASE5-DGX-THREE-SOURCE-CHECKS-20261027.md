# Track A Phase 5 — DGX 읽기 전용 3항목 소스 조사 실측 결과

> 2026-10-27 (Asia/Seoul) · **CHECK1/2/3 SOURCE_INSPECTION_DONE / Scheduler config factory identified / KV resolver branches and DCP confirmed / Mamba state slot units still unverified / PATCH APPROVAL 0 / GPU & runtime NOT_CERTIFIED**.
>
> 사용자 제공 `붙여넣은 텍스트(1)(20261027-114116).txt`, 원래 검사 출력 `CHECK1_SOURCE_INSPECTION_DONE`, `CHECK2_SOURCE_INSPECTION_DONE`, `CHECK3_SOURCE_INSPECTION_DONE`. 운영 컨테이너에서 이미지 ID를 **조회만** 하고 읽기 전용/`--network=none`/`--runtime=runc`/`CUDA_VISIBLE_DEVICES=-1`, `NVIDIA_VISIBLE_DEVICES=void` 임시 컨테이너에서 **vLLM Python 소스**를 AST로 검사했다. 사용된 기존 이미지 `sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a`.
>
> **실측 소스·커밋 구분:** 직전 전체 DGX offline Gate는 코드 `bc89de6288889943b50090ac9638ee95c2434a79`에서 Source164/164, Wizard Mock38/38, unittest259/259 XFAIL0 PASS. 직전 보고서 docs-only HEAD는 `17cfbc5b087a9245e2645a44131bd35f47dd7f40`. 이번 3개 소스 검사 로그는 **별도 read-only 소스 조회 성공**이며 unit259/Source164를 재실행했다는 뜻이 아니고, 이를 보고서에 추가하는 새 docs-only SHA 역시 DGX에서 시험하지 않았다.
>
> 고정 blazux upstream `8bb7a7179c6844839d9de8eda4dec6ec07e3b4fa`. source-only 확인은 실제 serving/GPU/prefix-cache hit/SSM state restore/Tool·Responses/MTP acceptance/PLE TPS/TTFT/CI/ABI certification이 아니다.

## 1. CHECK1 — Scheduler import가 아닌 동적 설정 Factory

- `v1/engine/core.py` SHA256 `f4b1e07b6d91fac1549bc74a5c804e5a88793d663b5dc045c9e455db6550f5ad`.
- `EngineCore.__init__:148` 에서 **`Scheduler = vllm_config.scheduler_config.get_scheduler_cls()`**. 즉 기존 `engine_static_imports_scheduler=false`는 기대했던 `from vllm.v1.core.sched.scheduler import Scheduler` 패턴 **대신 동적 factory 결과를 지역 Scheduler 이름으로 바인딩**하기 때문. 이는 실제 import 결함을 의미하지 않는다.
- `EngineCore.__init__:157–159` `scheduler_block_size, hash_block_size = resolve_kv_cache_block_sizes(kv_cache_config, vllm_config)`; `:161` `self.scheduler: SchedulerInterface = Scheduler(..., block_size=scheduler_block_size,hash_block_size=hash_block_size)`.
- **미확인:** `get_scheduler_cls()`의 default/override 반환 조건 및 실제 active configuration에서 반환되는 class, custom scheduler 여부, 해당 class의 constructor signature와 block size 의미. 직접 import 검사를 느슨하게 고쳐 억지로 6/6 PASS로 만들지 않는다.

## 2. CHECK2 — KV 그룹/LCM/GCD/DCP의 실제 조건

- `v1/core/kv_cache_utils.py` SHA256 `f6643bad29b7b3cb044482b6736a042afa91a4f43a11f034317a8e8029d3a8a4`.
- 함수 `resolve_kv_cache_block_sizes`(608–673), 627행 `dcp = vllm_config.parallel_config.decode_context_parallel_size`.
- **그룹 수 0 또는 1** (630–632): `bs = cache_config.block_size * dcp`, `return bs,bs`. 이 경우 별도의 그룹 LCM·GCD 계산 없음. 이 분기 자체는 Mamba 여부에 따른 그룹별 조건을 적용하지 않음.
- **그룹 수 2 이상** (634–640): `AttentionSpec`이면 `g.kv_cache_spec.block_size*dcp`, 그 외 group은 `g.kv_cache_spec.block_size` 그대로 리스트 생성, `scheduler_block_size=math.lcm(*group_block_sizes)`.
- **prefix caching과 KV connector 모두 비활성** (645–647): `return scheduler_block_size,scheduler_block_size`.
- **MambaSpec 중 cache mode가 align이 아닌 그룹 존재** (652–657): 역시 `return scheduler_block_size,scheduler_block_size`. Mamba align 사용하지 않을 때 hash GCD 경로에 들어간다고 주장하면 안 된다.
- **그 외** (659–673): `hashing_sizes = [block_size for group,block_size in zip(groups,group_block_sizes) if group.kv_cache_spec.prefix_cacheable] or group_block_sizes`. `requested=cache_config.prefix_match_unit`; 요청 있으면 그대로, 없으면 `math.gcd(*hashing_sizes)`. 666행 `any(bs % hash_block_size != 0 for bs in hashing_sizes)`이면 ValueError.
- **정확한 guard 범위:** divisibility 검사는 전체 `group_block_sizes`가 아니라 실제로 선택된 **`hashing_sizes` 리스트**에 수행. 함수는 632/647/657행의 **early return**과 673행의 일반 반환이 공존하여 언제나 LCM/GCD를 계산하는 것이 아님.
- **미확인:** 실제 모델의 KV group 수/타입·dcp값·prefix_match_unit·cache mode·사용자 설정. 다중 그룹의 Mamba block은 DCP로 스케일되지 않지만 single-group 분기는 `cache_config.block_size*dcp` 사용하므로 실제 적용 조건을 구분해야 한다.

## 3. CHECK3 — Mamba initial seed와 align kernel의 블록 크기 출처

| 설치 vLLM Python 소스 | 참조/정적 동작 | 증거 |
|---|---|---|
| `v1/worker/gpu/model_states/mamba_hybrid.py:109–117` | `_align_mode`일 때 `_mamba_state_idx_gpu[req_index]`에 `(num_computed_tokens-1)//self.cache_config.block_size` 기록 | Seed 계산 |
| 같은 파일 :119–133 | 모든 Mamba group의 `spec.block_size`, `num_speculative_blocks`, `mamba_cache_mode` 동일 여부 검사 후 spec/group IDs 사용 | 그룹 내 일관성만 확인 |
| 같은 파일 :177–224 | `_align_mode`에서 group spec·align context, `preprocess_mamba_align_fused_kernel(...,MAMBA_BLOCK_SIZE=mamba_spec.block_size)`, `ctx.run_fused_precopy(...)` | Pre-copy 크기 기준 |
| 같은 파일 :306–345 | `_align_mode`와 computed tokens/context 존재 시 `ctx.run_fused_postprocess_align(...)` | Post-process 저장/복원 세부 미검증 |
| `v1/core/sched/scheduler.py:366–441` | `block_size=self.cache_config.block_size` 기준 align/split/last cache/shared prefix 경계; **tail hash**는 별도 `self.hash_block_size` | Scheduler chunk |
| `v1/attention/backends/mamba_attn.py:433–690` | all mode에선 `mamba_block_size=self.kv_cache_spec.block_size` 및 fallback index, 다른 모드는 spec 기반 `mamba_get_block_table_tensor`; ReplaySSM align decode에 spec block_size | Attention metadata |

파일 SHA256: `mamba_hybrid.py` = `2e65f1da0a440f11a784bd36afe9206a7a2f674d522c047b838ad604e4c6acc0`; `scheduler.py` = `c710f49e41e974e5b7b8f1cd2f5fb9722523f4da0165252e16351199ebd03124`; `mamba_attn.py` = `9658330915daf4f8019a214317eb4be366eb52fd75fce8075cbb80d9ed7d3f6c`.

**엄격한 결론:** Worker seed와 Scheduler align은 `cache_config.block_size`, Mamba pre-copy는 `mamba_spec.block_size`, backend는 `kv_cache_spec.block_size`를 참조한다. **서로 다른 필드 이름/소스 경로라는 사실은 확인**됐으나 해당 활성 모델에서 숫자 값이 다른지, 그 경우 state slot copy가 어긋나는지, 실 prefix hit 오류가 있는지는 전혀 측정되지 않았다. `_align_mode`/Mamba cache mode, `_ensure_align_ctx`·kernel slot 인덱싱, restore/rollback contract를 함께 확인해야 한다. 지금 곧바로 blazux `patch_mamba_block_size.py`를 적용하면 안 된다.

## 4. 다음 같은 Phase5의 정확한 우선순위

1. `config/scheduler.py:get_scheduler_cls()`의 소스 정의/조건/default/custom 경로 및 반환 클래스 시그니처를 import-free로 추적해 기존 `engine_static_imports_scheduler=false`의 **동적 factory**를 정확한 계약으로 모델링한다.
2. 합성 CPU fixtures에서 0/1 vs multi group, AttentionSpec DCP scaling vs Mamba unscaled, prefix off/connector off, non-align Mamba early return, hash override/GCD/invalid divisibility를 소스와 일치하게 구분한다. Runtime 모델 설정을 추정·대입하지 않는다.
3. KV CacheConfig block, `MambaSpec.block_size`, backend spec, Scheduler LCM/hash block, state slot seed/copy/restore를 **실제 설정 필드 생성 소스 + kernel 경계**에 연결하고 synthetic token boundaries/COW/partial-prefill/acceptance fixture로 검증한다. **실제 운영/GPU는 승인 전 금지**.

blazux Mamba/Prefix, Tool Argument/Literal Marker/Responses, reduced MTP draft vocab 패치 계열 **적용 승인 0건**. 새 Phase를 만들지 말고 Phase5 CPU/source-only 안전 범위에서 계속. `main`·P0·Phase1~4는 immutable, PR/Merge 없음, 운영 Docker/모델/weights/HF cache/ports/GPU/HTTP/TPS/CI 미변경.

## 5. 결과 귀속 / 브랜치 불변

- 직전 전체 unit/source 실기 PASS는 **`bc89de6288889943b50090ac9638ee95c2434a79` 소스**에만 귀속. 이번 source-inspection 명령 3개는 별도 source proof이며 새 docs-only 커밋의 unit을 시험하지 않음.
- `main@2847e39b4131eb8aff78bf86ffce98892401722a`, P0 `966ec7cf0741734b844b1cea938d56678a756469`, Phase1 `a50fc53721f3d23325dca44eb799f0f388d65951`, Phase2 `76588845d7742703475ae1f49d5e8f5c174bb77a`, Phase3 `760f227e46a358445db3d3931b5efbe40de5f609`, Phase4 `69860277122dffe3082c5b065e4361a571317a8e` 그대로 보호. blazux → `main` PR/merge/cherry-pick/rebase/squash/sync 금지.
