"""P1 exclusive-GPU maintenance window: stage pins, isolated candidate and same-ID restore.

Host-side stdlib only. All mutations require the guarded feature-branch wrapper.
Never installs a Python module, modifies the original container, or writes weights.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import time
from urllib.error import URLError, HTTPError
from urllib.request import urlopen

from src import p1_legacy_service_window as legacy

IMAGE = "sha256:b0984c4b724b6f8c0745acb654994e1bd3a6c50b75c2c76078f1bfd6b395f39a"
STAGE = Path("/tmp/p1-prefix-stage.2dSPVPR6")
PATCHES = {
    "mamba_hybrid.py": ("v1/worker/gpu/model_states/mamba_hybrid.py",
                        "1dfb7b5566c8e683afff6640b1764c774c27daaa817437862fd465e63da9f381"),
    "scheduler.py": ("v1/core/sched/scheduler.py",
                     "0501cec135d23a21f988c67371f8f1dbf97cc63726c9c44b89e350c8887178d7"),
}
NAME = "p1-prefix-gpu-candidate"
PORT = 18080
LABEL_KEY = "ai.kjlee.p1-prefix-window"
LABEL_VALUE = "isolated-20261029"
MEMORY = "112g"
MIN_AFTER_STOP_KIB = 96 * 1024 * 1024
ENV_ALLOW = {
    "VLLM_PLE_MMAP", "VLLM_PLE_MMAP_WORKERS",
    "VLLM_PLE_MMAP_PREWARM", "HF_HUB_OFFLINE",
    "VLLM_USE_FLASHINFER_SAMPLER", "TRANSFORMERS_OFFLINE",
    "VLLM_WORKER_MULTIPROC_METHOD", "VLLM_ATTENTION_BACKEND",
    "VLLM_LOGGING_LEVEL", "VLLM_ENABLE_V1_MULTIPROCESSING",
    "OMP_NUM_THREADS", "TOKENIZERS_PARALLELISM", "PYTHONUNBUFFERED",
    "HF_HOME", "HF_HUB_CACHE", "NVIDIA_VISIBLE_DEVICES",
    "NVIDIA_DRIVER_CAPABILITIES", "CUDA_VISIBLE_DEVICES",
}
REPO = Path(__file__).resolve().parents[1]


class Blocked(Exception):
    pass


def checked(argv: list[str], *, timeout: int = 25) -> str:
    try:
        cp = subprocess.run(argv, check=True, capture_output=True, text=True,
                            timeout=timeout)
    except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired):
        raise Blocked("SUBPROCESS_FAILED_" + argv[0].upper()) from None
    return cp.stdout.strip()


def inspect_json(kind: str, name: str) -> dict:
    data = json.loads(checked(["docker", kind, "inspect", name]))
    if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
        raise Blocked("DOCKER_INSPECT_SHAPE")
    return data[0]


def verify_stage(path: Path = STAGE) -> dict:
    if path.is_symlink() or not path.is_dir():
        raise Blocked("STAGE_MISSING")
    s = path.stat()
    if s.st_uid != os.getuid() or stat.S_IMODE(s.st_mode) != 0o700:
        raise Blocked("STAGE_OWNER_OR_MODE")
    if set(p.name for p in path.iterdir()) != set(PATCHES):
        raise Blocked("STAGE_UNEXPECTED_CONTENT")
    result = {}
    for name, (_, digest) in PATCHES.items():
        f = path / name
        if f.is_symlink() or not f.is_file():
            raise Blocked("STAGE_NOT_REGULAR")
        st = f.stat()
        if st.st_uid != os.getuid() or stat.S_IMODE(st.st_mode) != 0o600:
            raise Blocked("STAGE_FILE_OWNER_OR_MODE")
        if st.st_size > 2_000_000 or hashlib.sha256(f.read_bytes()).hexdigest() != digest:
            raise Blocked("STAGE_SHA256_MISMATCH")
        result[name] = digest
    return result


def flag_value(argv: list[str], option: str) -> str:
    if argv.count(option) != 1:
        raise Blocked("CMD_FLAG_SHAPE_" + option.lstrip("-").upper())
    i = argv.index(option)
    if i + 1 >= len(argv) or argv[i + 1].startswith("--"):
        raise Blocked("CMD_FLAG_VALUE_MISSING")
    return argv[i + 1]


def candidate_cmd(cmd: list[str]) -> tuple[list[str], str]:
    if not isinstance(cmd, list) or not all(isinstance(s, str) for s in cmd):
        raise Blocked("CMD_SHAPE")
    if cmd.count("--no-enable-prefix-caching") != 1 or "--enable-prefix-caching" in cmd:
        raise Blocked("ORIGINAL_NOT_PREFIX_OFF")
    if flag_value(cmd, "--port") != "8000" or flag_value(cmd, "--host") != "0.0.0.0":
        raise Blocked("ORIGINAL_BIND_DRIFT")
    if flag_value(cmd, "--gpu-memory-utilization") != "0.8":
        raise Blocked("GPU_UTILIZATION_DRIFT")
    if flag_value(cmd, "--max-model-len") != "262144" or flag_value(cmd, "--max-num-seqs") != "8":
        raise Blocked("MODEL_LIMITS_DRIFT")
    try:
        mtp = json.loads(flag_value(cmd, "--speculative-config"))
    except ValueError:
        raise Blocked("MTP_CONFIG_UNPARSEABLE") from None
    if mtp != {"method": "mtp", "num_speculative_tokens": 2}:
        raise Blocked("MTP_CONFIG_DRIFT")
    model = flag_value(cmd, "--served-model-name")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,127}", model):
        raise Blocked("SERVED_MODEL_UNSAFE")
    new = cmd.copy()
    new[new.index("--no-enable-prefix-caching")] = "--enable-prefix-caching"
    return new, model


def environment_delta(container: dict, image: dict) -> list[str]:
    def parse(items: list[str]) -> dict:
        result = {}
        for item in items:
            if not isinstance(item, str) or "=" not in item:
                raise Blocked("ENV_MALFORMED")
            k, value = item.split("=", 1)
            if not re.fullmatch("[A-Za-z_][A-Za-z_0-9]*", k) or k in result:
                raise Blocked("ENV_DUPLICATE_OR_UNSAFE")
            result[k] = value
        return result
    original = parse(container.get("Env") or [])
    base = parse(image.get("Env") or [])
    extra = {key: value for key, value in original.items() if base.get(key) != value}
    unknown = sorted(set(extra) - ENV_ALLOW)
    if unknown:
        # Names only: no secret values, and never propagate unreviewed credentials.
        raise Blocked("UNREVIEWED_ENV_KEYS:" + ",".join(unknown))
    # PLE mmap prewarm reads the full ~95 GiB BF16 table; it is unsafe
    # to turn it on in this single-GB10 maintenance window.
    prewarm = original.get("VLLM_PLE_MMAP_PREWARM", "0")
    if prewarm not in ("0", ""):
        raise Blocked("PLE_PREWARM_MUST_BE_DISABLED")
    if extra.get("NVIDIA_VISIBLE_DEVICES", "all") not in ("all", ""):
        raise Blocked("GPU_DEVICE_SELECTION_DRIFT")
    if extra.get("CUDA_VISIBLE_DEVICES", "") in ("-1", "none"):
        raise Blocked("GPU_CUDA_DISABLED")
    return [f"{key}={value}" for key, value in sorted(extra.items())
            if key != "NVIDIA_VISIBLE_DEVICES"]


def preflight() -> tuple[dict, dict, dict, list[str], list[str], str]:
    verify_stage()
    receipt = legacy.state_receipt(Path.home())
    container = legacy.inspect("container", legacy.NAME)
    img = legacy.inspect("image", legacy.IMAGE_TAG)
    state = legacy.verify_identity(container, img, receipt)
    if state not in ("running", "exited"):
        raise Blocked("ORIGINAL_PAUSED")
    if container["Image"] != IMAGE or img["Id"] != IMAGE:
        raise Blocked("IMAGE_DRIFT")
    hc = container.get("HostConfig") or {}
    ic = img.get("Config") or {}
    cc = container.get("Config") or {}
    if cc.get("Entrypoint") != ic.get("Entrypoint"):
        raise Blocked("ENTRYPOINT_NOT_IMAGE_DEFAULT")
    # A container may legitimately override the image's USER. Preserve that
    # exact runtime user instead of demanding image-default/root identity.
    runtime_user = cc.get("User")
    image_user = ic.get("User")
    if not isinstance(runtime_user, str) or not re.fullmatch(
            r"(?:[A-Za-z0-9_.-]+(?::[A-Za-z0-9_.-]+)?)?", runtime_user):
        raise Blocked("ORIGINAL_USER_UNSUPPORTED")
    if runtime_user == "" and image_user not in ("", None, "root", "0"):
        raise Blocked("AMBIGUOUS_IMAGE_DEFAULT_USER")
    # Docker --workdir may also be an intentional runtime override.
    runtime_workdir = cc.get("WorkingDir")
    image_workdir = ic.get("WorkingDir")
    if not isinstance(runtime_workdir, str):
        raise Blocked("WORKDIR_UNSUPPORTED")
    if runtime_workdir:
        parts = runtime_workdir.split("/")
        if (not runtime_workdir.startswith("/") or
                any(part in (".", "..") for part in parts) or
                chr(0) in runtime_workdir or chr(10) in runtime_workdir):
            raise Blocked("WORKDIR_UNSAFE")
    elif image_workdir not in ("", None, "/"):
        raise Blocked("WORKDIR_IMAGE_DEFAULT_AMBIGUOUS")
    if hc.get("IpcMode") != "host":
        raise Blocked("IPC_MODE_DRIFT")
    requests = hc.get("DeviceRequests") or []
    if len(requests) != 1 or requests[0].get("Driver") not in ("", "nvidia"):
        raise Blocked("GPU_REQUEST_DRIFT")
    if requests[0].get("DeviceIDs") or requests[0].get("Count") not in (-1, None):
        raise Blocked("GPU_SELECTION_NOT_ALL")
    if not any("gpu" in group for group in requests[0].get("Capabilities", [])):
        raise Blocked("GPU_CAPABILITIES_DRIFT")
    if hc.get("Runtime") not in ("", "runc", "nvidia"):
        raise Blocked("RUNTIME_DRIFT")
    mounts = container.get("Mounts") or []
    if len(mounts) != 2 or any(m.get("Type") != "bind" or m.get("RW") is not False
                                 for m in mounts):
        raise Blocked("UNEXPECTED_OR_WRITABLE_MODEL_MOUNTS")
    expected = {(receipt["cache"], "/recipe/hf-cache"),
                (receipt["views"], "/recipe/recipe-views")}
    if {(m["Source"], m["Destination"]) for m in mounts} != expected:
        raise Blocked("MOUNT_DRIFT")
    # Do not mistake a Docker daemon/permission failure for "not found".
    if candidate_ids():
        raise Blocked("CANDIDATE_NAME_OCCUPIED")
    cmd, model = candidate_cmd(cc.get("Cmd"))
    env = environment_delta(cc, ic)
    total = next((int(line.split()[1]) for line in Path("/proc/meminfo").read_text().splitlines()
                  if line.startswith("MemTotal:")), 0)
    if total < 120 * 1024 * 1024:
        raise Blocked("HOST_TOTAL_MEMORY_TOO_LOW")
    return receipt, container, img, cmd, env, model


def probe_vllm_root(runtime_user: str) -> str:
    # CPU only. Preserve the original effective Docker user and check that
    # 0700/0600 staged sources are readable by that user BEFORE stopping.
    # No GPU, model mounts, serving network or installed-package writes.
    code = (
        "import importlib.util,json,pathlib,hashlib;"
        "s=importlib.util.find_spec('vllm');"
        "assert s is not None and len(s.submodule_search_locations)==1;"
        "p=pathlib.Path(list(s.submodule_search_locations)[0]).resolve();"
        "checks=["
        "('v1/worker/gpu/model_states/mamba_hybrid.py',"
        "'2e65f1da0a440f11a784bd36afe9206a7a2f674d522c047b838ad604e4c6acc0'),"
        "('v1/core/sched/scheduler.py',"
        "'c710f49e41e974e5b7b8f1cd2f5fb9722523f4da0165252e16351199ebd03124')"
        "];"
        "assert all((p/k).is_file() and not (p/k).is_symlink()"
        " and hashlib.sha256((p/k).read_bytes()).hexdigest()==h"
        " for k,h in checks);"
        "stage=["
        "('mamba_hybrid.py','1dfb7b5566c8e683afff6640b1764c774c27daaa817437862fd465e63da9f381'),"
        "('scheduler.py','0501cec135d23a21f988c67371f8f1dbf97cc63726c9c44b89e350c8887178d7')"
        "];"
        "assert all((pathlib.Path('/p1stage')/n).is_file()"
        " and hashlib.sha256((pathlib.Path('/p1stage')/n).read_bytes()).hexdigest()==h"
        " for n,h in stage);"
        "print(json.dumps({'root':str(p),'sha256_pins_match':True,'stage_access':True}))"
    )
    command = [
        "docker", "run", "--rm", "--pull=never", "--runtime=runc",
        "--network=none", "--read-only", "--cap-drop=ALL",
        "--security-opt=no-new-privileges", "--cpus=1", "--memory=512m",
        "--memory-swap=512m", "--pids-limit=64",
        "--env", "NVIDIA_VISIBLE_DEVICES=void", "--env", "CUDA_VISIBLE_DEVICES=-1",
        "--env", "PYTHONDONTWRITEBYTECODE=1",
        "--mount", f"type=bind,src={STAGE},dst=/p1stage,readonly",
    ]
    if runtime_user:
        command += ["--user", runtime_user]
    command += ["--entrypoint", "python3", IMAGE, "-c", code]
    data = json.loads(checked(command, timeout=90))
    if data.get("sha256_pins_match") is not True or data.get("stage_access") is not True:
        raise Blocked("PROBE_SOURCE_OR_STAGE_ACCESS_FAILED")
    root = data.get("root")
    if not isinstance(root, str) or not re.fullmatch(
            r"/(?:[A-Za-z0-9_.+-]+/)+vllm", root):
        raise Blocked("PROBE_VLLM_ROOT_INVALID")
    return root


def create_candidate(root: str, receipt: dict, cmd: list[str], env: list[str], runtime: str, runtime_user: str, runtime_workdir: str) -> None:
    args = ["docker", "create", "--name", NAME, "--pull=never",
            "--label", LABEL_KEY + "=" + LABEL_VALUE,
            "--network=bridge", "--publish", f"127.0.0.1:{PORT}:8000",
            "--gpus=all", "--ipc=host",
            "--memory=" + MEMORY, "--memory-swap=" + MEMORY, "--pids-limit=1024",
            "--restart=no", "--security-opt=no-new-privileges"]
    if runtime:
        args += ["--runtime=" + runtime]
    if runtime_user:
        args += ["--user", runtime_user]
    if runtime_workdir:
        args += ["--workdir", runtime_workdir]
    for source, dest in ((receipt["cache"], "/recipe/hf-cache"),
                         (receipt["views"], "/recipe/recipe-views"),
                         (str(STAGE / "mamba_hybrid.py"),
                          root + "/" + PATCHES["mamba_hybrid.py"][0]),
                         (str(STAGE / "scheduler.py"),
                          root + "/" + PATCHES["scheduler.py"][0])):
        args += ["--mount", f"type=bind,src={source},dst={dest},readonly"]
    for entry in env:
        args += ["--env", entry]
    args += ["--env", "HF_HUB_OFFLINE=1", "--env", "TRANSFORMERS_OFFLINE=1",
             "--env", "PYTHONDONTWRITEBYTECODE=1",
             IMAGE, *cmd]
    checked(args, timeout=60)
    actual = inspect_json("container", NAME)
    if actual.get("Image") != IMAGE or (
        (actual.get("Config") or {}).get("Labels") or {}).get(LABEL_KEY) != LABEL_VALUE:
        raise Blocked("CANDIDATE_IDENTITY_DRIFT")


def candidate_ids() -> list[str]:
    # docker ps errors MUST propagate: an unreachable daemon is not evidence
    # that the GPU-owning candidate is absent.
    out = checked(["docker", "ps", "-aq", "--no-trunc",
                   "--filter", "name=^/" + NAME + "$", "--format", "{{.ID}}"])
    ids = out.splitlines() if out else []
    if any(not re.fullmatch(r"[0-9a-f]{64}", value) for value in ids) or len(ids) > 1:
        raise Blocked("CANDIDATE_ID_LIST_AMBIGUOUS")
    return ids


def cleanup_candidate() -> None:
    ids = candidate_ids()
    if not ids:
        return
    ci = inspect_json("container", NAME)
    if (ci.get("Id") != ids[0] or ci.get("Image") != IMAGE or
            ((ci.get("Config") or {}).get("Labels") or {}).get(LABEL_KEY) != LABEL_VALUE):
        raise Blocked("REFUSE_CLEANUP_FOREIGN_CONTAINER")
    checked(["docker", "rm", "--force", ids[0]], timeout=60)
    if candidate_ids():
        raise Blocked("CANDIDATE_CLEANUP_NOT_CONFIRMED")


def restore(receipt: dict, model: str, *, timeout_s: int = 900) -> None:
    checked(["bash", str(REPO / "scripts/start.sh"), "--expected-head",
             checked(["git", "-C", str(REPO), "rev-parse", "HEAD"]),
             "--confirm-id", receipt["id"], "--execute"], timeout=90)
    ci = legacy.inspect("container", legacy.NAME)
    if ci.get("Id") != receipt["id"] or ci.get("Image") != IMAGE or (
            ci.get("State") or {}).get("Running") is not True:
        raise Blocked("RESTORE_SAME_ID_NOT_RUNNING")
    wait_ready(8000, model, timeout_s=timeout_s)
    print("P1_PREFIX_ORIGINAL_SAME_ID_HTTP_RESTORED")


def wait_ready(port: int, model: str, *, timeout_s: int) -> None:
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        try:
            with urlopen(f"http://127.0.0.1:{port}/health", timeout=4) as r:
                health = r.status == 200
            with urlopen(f"http://127.0.0.1:{port}/v1/models", timeout=4) as r:
                models = json.load(r)
            ids = [m.get("id") for m in models.get("data", [])]
            if health and model in ids:
                return
        except (OSError, ValueError, HTTPError, URLError, TimeoutError):
            pass
        time.sleep(5)
    raise Blocked("HTTP_READINESS_TIMEOUT_" + str(port))


def available_kib() -> int:
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1])
    raise Blocked("MEMAVAILABLE_UNKNOWN")


def run(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight", action="store_true")
    group.add_argument("--execute", action="store_true")
    group.add_argument("--recover", action="store_true")
    ap.add_argument("--confirm-id")
    a = ap.parse_args(argv)
    if os.geteuid() == 0:
        print("P1_PREFIX_GPU_BLOCKED_ROOT_USER")
        return 2
    try:
        receipt, ci, _, cmd, env, model = preflight() if not a.recover else (
            legacy.state_receipt(Path.home()), None, None, None, None, None)
        if a.preflight:
            if a.confirm_id:
                raise Blocked("PREFLIGHT_CONFIRM_ID_FORBIDDEN")
            root = probe_vllm_root((ci.get("Config") or {}).get("User") or "")
            print(json.dumps({"status": "PREFLIGHT_CPU_PROBE_NO_GPU",
                              "stage_files_sha256_match": True,
                              "original_state": ci["State"]["Status"],
                              "candidate_port": PORT,
                              "installed_vllm_root_verified": bool(root),
                              "stage_access_as_original_user": True,
                              "gpu_model_loaded": False}, sort_keys=True))
            print("P1_PREFIX_GPU_PREFLIGHT_SOURCE_AND_USER_CPU_PROBE_PASS_NOT_GPU")
            return 0
        if not re.fullmatch(r"[0-9a-f]{64}", a.confirm_id or "") or a.confirm_id != receipt["id"]:
            raise Blocked("EXACT_RECEIPT_ID_CONFIRMATION_REQUIRED")
        if a.recover:
            cleanup_candidate()
            if model is None:
                actual = legacy.inspect("container", legacy.NAME)
                _, model = candidate_cmd((actual.get("Config") or {}).get("Cmd"))
            restore(receipt, model)
            return 0
        if ci["State"]["Status"] != "running":
            raise Blocked("EXECUTE_REQUIRES_ORIGINAL_RUNNING")
        root = probe_vllm_root((ci.get("Config") or {}).get("User") or "")
        # Confirm pinned original sources at exact imported module paths INSIDE image
        # via CPU-only probe (stage export already compared original source SHA).
        stopped = False
        try:
            create_candidate(root, receipt, cmd, env,
                             (ci.get("HostConfig") or {}).get("Runtime") or "",
                             (ci.get("Config") or {}).get("User") or "",
                             (ci.get("Config") or {}).get("WorkingDir") or "")
            stopped = True  # Restore even if the stop subprocess reports an error AFTER stopping.
            checked(["bash", str(REPO / "scripts/stop.sh"), "--expected-head",
                     checked(["git", "-C", str(REPO), "rev-parse", "HEAD"]),
                     "--confirm-id", receipt["id"], "--execute"], timeout=90)
            if available_kib() < MIN_AFTER_STOP_KIB:
                raise Blocked("POST_STOP_MEMORY_BELOW_96GIB")
            checked(["docker", "start", NAME], timeout=90)
            wait_ready(PORT, model, timeout_s=1200)
            print("P1_PREFIX_CANDIDATE_HTTP_READY_NOT_CORRECTNESS_PASS")
            from src.p1_prefix_gpu_oracle import run_oracle
            result = run_oracle(model, PORT)
            print(json.dumps(result, sort_keys=True))
            print("P1_PREFIX_GPU_ORACLE_" + result["status"])
            if not result["status"].startswith("PASS_"):
                raise Blocked("ORACLE_NOT_VERIFIED_" + result["status"])
        finally:
            # NEVER restore the original while candidate might still own GPU memory.
            # A cleanup failure leaves original stopped and requires explicit --recover.
            cleanup_candidate()
            if stopped:
                restore(receipt, model)
        return 0
    except (Blocked, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        # Do not echo unexpected exception content (may include secret data).
        code = str(exc) if isinstance(exc, Blocked) else type(exc).__name__
        print("P1_PREFIX_GPU_BLOCKED_" + code, file=sys.stderr)
        return 2


if __name__ == "__main__":
    def _interrupted(*_):
        raise Blocked("INTERRUPTED")
    for sig in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, _interrupted)
    raise SystemExit(run())
