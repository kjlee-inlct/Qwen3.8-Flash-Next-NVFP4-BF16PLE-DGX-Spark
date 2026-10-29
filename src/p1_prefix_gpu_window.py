"""P1 exclusive-GPU maintenance window: stage pins, isolated candidate and same-ID restore.

Host-side stdlib only. All mutations require the guarded feature-branch wrapper.
Never installs a Python module, modifies the original container, or writes weights.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import tarfile
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


def verify_stage_observer_sites(path: Path = STAGE) -> None:
    """Inspect actual Stage ABI before Docker candidate creation/legacy stop.

    SHA and file permissions must already be checked by verify_stage().
    """
    import ast
    sites = {
        "mamba_hybrid.py": ("MambaHybridModelState", {
            "_ensure_align_ctx": ("self", "kv_cache_config",
                                  "mamba_group_ids", "block_tables"),
            "add_request": ("self", "req_index", "new_req_data"),
            "preprocess_state": ("self", "input_batch", "block_tables",
                                 "kv_cache_config", "num_computed_tokens"),
            "postprocess_state": ("self", "idx_mapping", "num_sampled",
                                  "num_computed_tokens"),
        }),
        "scheduler.py": ("Scheduler", {
            "_mamba_block_aligned_split": (
                "self", "request", "num_new_tokens",
                "num_new_local_computed_tokens", "num_external_computed_tokens"),
        }),
    }
    for name, (class_name, expected) in sites.items():
        try:
            tree = ast.parse((path / name).read_bytes().decode("utf-8"))
        except (OSError, UnicodeError, SyntaxError, ValueError):
            raise Blocked("STAGE_OBSERVER_SOURCE_UNPARSEABLE_" + name) from None
        classes = [node for node in tree.body if
                   isinstance(node, ast.ClassDef) and node.name == class_name]
        if len(classes) != 1:
            raise Blocked("STAGE_OBSERVER_CLASS_DRIFT_" + name)
        actual = {
            node.name: tuple(arg.arg for arg in node.args.args)
            for node in classes[0].body
            if isinstance(node, ast.FunctionDef)
        }
        for method, positional in expected.items():
            if actual.get(method) != positional:
                raise Blocked("STAGE_OBSERVER_ABI_DRIFT_" + name + "_" + method)


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
    verify_stage_observer_sites()
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
    # CPU only, as the ORIGINAL runtime user. Source stages remain host-private
    # (0700 directory, 0600 files) and are separately SHA-pinned by verify_stage.
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
        "print(json.dumps({'root':str(p),'sha256_pins_match':True}))"
    )
    command = [
        "docker", "run", "--rm", "--pull=never", "--runtime=runc",
        "--network=none", "--read-only", "--cap-drop=ALL",
        "--security-opt=no-new-privileges", "--cpus=1", "--memory=512m",
        "--memory-swap=512m", "--pids-limit=64",
        "--env", "NVIDIA_VISIBLE_DEVICES=void", "--env", "CUDA_VISIBLE_DEVICES=-1",
        "--env", "PYTHONDONTWRITEBYTECODE=1",
    ]
    if runtime_user:
        command += ["--user", runtime_user]
    command += ["--entrypoint", "python3", IMAGE, "-c", code]
    data = json.loads(checked(command, timeout=90))
    if data.get("sha256_pins_match") is not True:
        raise Blocked("PROBE_ORIGINAL_SOURCE_SHA_FAILED")
    root = data.get("root")
    if not isinstance(root, str) or not re.fullmatch(
            r"/(?:[A-Za-z0-9_.+-]+/)+vllm", root):
        raise Blocked("PROBE_VLLM_ROOT_INVALID")
    return root


def docker_cp_to_stopped_candidate(destination: str, name: str, data: bytes) -> None:
    """Copy ONLY pinned Python bytes into candidate writable overlay before stop.

    The original image and original service never change. A Docker tar stream
    with mode 0644 makes these code files readable by the preserved nonroot user,
    while the original private 0700/0600 host stage remains untouched.
    """
    if not re.fullmatch(r"[A-Za-z0-9._+-]+\.py", name):
        raise Blocked("CANDIDATE_COPY_NAME_UNSAFE")
    tar_stream = io.BytesIO()
    with tarfile.open(fileobj=tar_stream, mode="w") as archive:
        entry = tarfile.TarInfo(name=name)
        entry.size = len(data)
        entry.mode = 0o644
        entry.uid = 0
        entry.gid = 0
        entry.mtime = 0
        archive.addfile(entry, io.BytesIO(data))
    try:
        cp = subprocess.run(
            ["docker", "cp", "-", f"{NAME}:{destination}"],
            input=tar_stream.getvalue(), capture_output=True, timeout=90)
    except (OSError, subprocess.TimeoutExpired):
        raise Blocked("CANDIDATE_COPY_FAILED") from None
    if cp.returncode:
        raise Blocked("CANDIDATE_COPY_FAILED")


def verify_candidate_code(destination: str, name: str, digest: str) -> None:
    # Read back from stopped candidate (no GPU, no model, no server).
    try:
        cp = subprocess.run(["docker", "cp", f"{NAME}:{destination}/{name}", "-"],
                            capture_output=True, timeout=90)
    except (OSError, subprocess.TimeoutExpired):
        raise Blocked("CANDIDATE_READBACK_FAILED") from None
    if cp.returncode or len(cp.stdout) > 3_000_000:
        raise Blocked("CANDIDATE_READBACK_FAILED")
    try:
        with tarfile.open(fileobj=io.BytesIO(cp.stdout), mode="r:*") as archive:
            files = [member for member in archive.getmembers() if member.isfile()]
            if len(files) != 1 or Path(files[0].name).name != name:
                raise Blocked("CANDIDATE_READBACK_SHAPE")
            if stat.S_IMODE(files[0].mode) != 0o644 or files[0].size > 2_000_000:
                raise Blocked("CANDIDATE_PATCH_PERMISSIONS")
            extracted = archive.extractfile(files[0])
            if extracted is None or hashlib.sha256(extracted.read()).hexdigest() != digest:
                raise Blocked("CANDIDATE_PATCH_SHA256_MISMATCH")
    except (tarfile.TarError, OSError, ValueError):
        raise Blocked("CANDIDATE_READBACK_TAR_INVALID") from None


def create_candidate(root: str, receipt: dict, cmd: list[str], env: list[str],
                     runtime: str, runtime_user: str, runtime_workdir: str) -> None:
    # No host stage source bind mounts: its strict 0700/0600 ownership does NOT
    # give nonroot original Docker USER read access. Copy exactly two files into
    # the *isolated, stopped candidate overlay* with read-only-to-user 0644 mode.
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
                         (receipt["views"], "/recipe/recipe-views")):
        args += ["--mount", f"type=bind,src={source},dst={dest},readonly"]
    for entry in env:
        args += ["--env", entry]
    args += ["--env", "HF_HUB_OFFLINE=1", "--env", "TRANSFORMERS_OFFLINE=1",
             "--env", "PYTHONDONTWRITEBYTECODE=1",
             "--env", "P1_PREFIX_STATE_SNAPSHOT=1",
             IMAGE, *cmd]
    checked(args, timeout=60)
    actual = inspect_json("container", NAME)
    actual_conf = actual.get("Config") or {}
    if actual.get("Image") != IMAGE or (
            actual_conf.get("Labels") or {}).get(LABEL_KEY) != LABEL_VALUE:
        raise Blocked("CANDIDATE_IDENTITY_DRIFT")
    if (actual_conf.get("User") or "") != runtime_user or (
            actual_conf.get("WorkingDir") or "") != runtime_workdir:
        raise Blocked("CANDIDATE_RUNTIME_USER_OR_WORKDIR_DRIFT")
    if (actual.get("State") or {}).get("Status") != "created":
        raise Blocked("CANDIDATE_MUST_REMAIN_STOPPED_FOR_PATCH")
    target_mounts = {(receipt["cache"], "/recipe/hf-cache"),
                     (receipt["views"], "/recipe/recipe-views")}
    candidate_mounts = actual.get("Mounts") or []
    if (len(candidate_mounts) != 2 or
            any(m.get("Type") != "bind" or m.get("RW") is not False
                for m in candidate_mounts) or
            {(m.get("Source"), m.get("Destination")) for m in candidate_mounts}
                != target_mounts):
        raise Blocked("CANDIDATE_MOUNT_DRIFT")

    # The host Stage remains immutable. Instrument only the stopped candidate.
    # Observer is imported by two post-class hooks only in the candidate layer.
    observer_source = REPO / "src/p1_prefix_live_observer.py"
    observer_bytes = observer_source.read_bytes()
    if not observer_bytes or len(observer_bytes) > 200_000:
        raise Blocked("CANDIDATE_OBSERVER_SOURCE_INVALID")
    docker_cp_to_stopped_candidate(root, "_p1_prefix_live_observer.py",
                                   observer_bytes)
    verify_candidate_code(root, "_p1_prefix_live_observer.py",
                          hashlib.sha256(observer_bytes).hexdigest())
    snapshot_source = REPO / "src/p1_prefix_state_snapshot.py"
    snapshot_bytes = snapshot_source.read_bytes()
    if not snapshot_bytes or len(snapshot_bytes) > 200_000:
        raise Blocked("CANDIDATE_STATE_SNAPSHOT_SOURCE_INVALID")
    import ast
    try:
        snapshot_ast = ast.parse(snapshot_bytes.decode("utf-8"))
    except (SyntaxError, UnicodeError):
        raise Blocked("CANDIDATE_STATE_SNAPSHOT_SOURCE_UNPARSEABLE") from None
    if not any(isinstance(node, ast.FunctionDef) and node.name == "install"
               for node in snapshot_ast.body):
        raise Blocked("CANDIDATE_STATE_SNAPSHOT_INSTALL_MISSING")
    docker_cp_to_stopped_candidate(root, "_p1_prefix_state_snapshot.py",
                                   snapshot_bytes)
    verify_candidate_code(root, "_p1_prefix_state_snapshot.py",
                          hashlib.sha256(snapshot_bytes).hexdigest())
    suffixes = {
        "mamba_hybrid.py": "\n\n# P1 CANDIDATE-ONLY RUNTIME DIAGNOSTIC (not present in pinned Stage)\nfrom vllm._p1_prefix_live_observer import install as _p1_install_observer\n_p1_install_observer(MambaHybridModelState, '_ensure_align_ctx', 'align_ctx')\n_p1_install_observer(MambaHybridModelState, 'add_request', 'mamba')\n_p1_install_observer(MambaHybridModelState, 'preprocess_state', 'preprocess')\nfrom vllm._p1_prefix_state_snapshot import install as _p1_install_state_snapshot\n_p1_install_state_snapshot(MambaHybridModelState)\n",
        "scheduler.py": "\n\n# P1 CANDIDATE-ONLY RUNTIME DIAGNOSTIC (not present in pinned Stage)\nfrom vllm._p1_prefix_live_observer import install as _p1_install_observer\n_p1_install_observer(Scheduler, '_mamba_block_aligned_split', 'scheduler')\n",
    }
    for name, (relative, digest) in PATCHES.items():
        target_dir = root + "/" + relative.rsplit("/", 1)[0]
        data = (STAGE / name).read_bytes()
        if len(data) > 2_000_000 or hashlib.sha256(data).hexdigest() != digest:
            raise Blocked("CANDIDATE_STAGE_SHA256_DRIFT")
        # Reject ABI drift before original stop, never only after GPU load.
        import ast
        try:
            parsed = ast.parse(data.decode("utf-8"))
        except (SyntaxError, UnicodeError):
            raise Blocked("CANDIDATE_STAGE_PYTHON_UNPARSEABLE") from None
        expected_class, required = (
            ("MambaHybridModelState", {"_ensure_align_ctx", "add_request", "preprocess_state", "postprocess_state"})
            if name == "mamba_hybrid.py" else
            ("Scheduler", {"_mamba_block_aligned_split"}))
        classes = [node for node in parsed.body
                   if isinstance(node, ast.ClassDef)
                   and node.name == expected_class]
        methods = {node.name for node in classes[0].body
                   if isinstance(node, ast.FunctionDef)} if len(classes) == 1 else set()
        if not required.issubset(methods):
            raise Blocked("ACTIVE_OBSERVER_METHOD_NOT_IN_STAGE_" +
                          name.removesuffix(".py").upper())
        candidate_bytes = data + suffixes[name].encode("utf-8")
        try:
            ast.parse(candidate_bytes.decode("utf-8"))
        except (SyntaxError, UnicodeError):
            raise Blocked("CANDIDATE_INSTRUMENTED_SOURCE_INVALID") from None
        docker_cp_to_stopped_candidate(target_dir, name, candidate_bytes)
        verify_candidate_code(target_dir, name,
                              hashlib.sha256(candidate_bytes).hexdigest())
    print("P1_PREFIX_CANDIDATE_STOPPED_PATCH_AND_OBSERVER_SHA256_VERIFIED_NOT_GPU")


def read_candidate_observer() -> dict:
    """Collect bounded actual engine/worker events from candidate Docker logs.

    Metadata and the sampled scalar seed cannot prove full logical-to-physical
    state reuse, per-group allocation or MTP speculative acceptance.
    """
    try:
        cp = subprocess.run(["docker", "logs", "--tail", "6000", NAME],
                            capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        raise Blocked("CANDIDATE_OBSERVER_LOG_UNAVAILABLE") from None
    if cp.returncode:
        raise Blocked("CANDIDATE_OBSERVER_LOG_UNAVAILABLE")
    prefix = "P1_PREFIX_ACTIVE_ABI_JSON:"
    snapshot_prefix = "P1_PREFIX_STATE_SNAPSHOT_JSON:"
    events = []
    snapshot_events = []
    for line in (cp.stdout + "\n" + cp.stderr).splitlines():
        if snapshot_prefix in line:
            try:
                item = json.loads(line.split(snapshot_prefix, 1)[1])
            except ValueError:
                continue
            if (isinstance(item, dict) and item.get("schema") == 1
                    and item.get("phase") in
                    ("before_preprocess", "after_postprocess")):
                snapshot_events.append(item)
        if prefix not in line:
            continue
        try:
            item = json.loads(line.split(prefix, 1)[1])
        except ValueError:
            continue
        if isinstance(item, dict) and item.get("schema") == 1 and (
                item.get("kind") in ("scheduler", "mamba", "align_ctx", "preprocess")):
            events.append(item)
    mamba = [e for e in events if e["kind"] == "mamba"]
    sched = [e for e in events if e["kind"] == "scheduler"]
    align_ctx = [e for e in events if e["kind"] == "align_ctx"]
    preprocess = [e for e in events if e["kind"] == "preprocess"]
    physical = [p for e in (mamba + align_ctx + preprocess)
                for key in ("physical_map_samples",
                            "deferred_state_to_physical_samples")
                for p in e.get(key, []) if isinstance(p, dict)]
    return {
        "active_scheduler_event_count": len(sched),
        "active_mamba_align_ctx_event_count": len(align_ctx),
        "active_mamba_align_ctx_table_group_counts": [
            e.get("mamba_group_table_count") for e in align_ctx[:4]],
        "active_mamba_align_ctx_call_ordinals": [
            e.get("observer_call_ordinal") for e in align_ctx[:12]],
        "physical_table_sample_count": len(physical),
        "physical_block_entries_observed": sum(
            p.get("physical_entry_observed") is True for p in physical),
        "physical_id_within_allocation_count": sum(
            p.get("physical_id_within_state_allocation") is True
            for p in physical),
        "physical_id_outside_allocation_count": sum(
            p.get("physical_id_within_state_allocation") is False
            for p in physical),
        "physical_id_allocation_unknown_count": sum(
            p.get("physical_id_within_state_allocation") is None
            for p in physical),
        "physical_entry_out_of_bounds_count": sum(
            p.get("row_in_bounds") is False or
            p.get("column_in_bounds") is False for p in physical),
        "physical_batch_row_mapping_unknown_count": sum(
            p.get("table_row_semantics") == "BATCH_ORDER_ROW_UNRESOLVED"
            for p in physical),
        "physical_group_block_size_mismatch_count": sum(
            p.get("block_size_matches_mamba_config") is False
            for p in physical),
        "physical_group_block_size_unknown_count": sum(
            p.get("block_size_matches_mamba_config") is None
            for p in physical),
        "mamba_seed_expected_comparison_count": sum(
            "state_seed_matches_expected" in e for e in mamba),
        "mamba_seed_mismatch_count": sum(
            e.get("state_seed_matches_expected") is False
            for e in mamba if "state_seed_matches_expected" in e),
        "active_mamba_add_request_event_count": len(mamba),
        "active_preprocess_event_count": len(preprocess),
        "preprocess_observer_call_ordinals": [
            e.get("observer_call_ordinal") for e in preprocess[:12]],
        "preprocess_mapping_unavailable_reasons": {
            reason: sum(e.get("mapping_reason") == reason for e in preprocess)
            for reason in sorted({e.get("mapping_reason") for e in preprocess
                                  if isinstance(e.get("mapping_reason"), str)})},
        "batch_state_slot_mapping_observed_count": sum(
            e.get("batch_row_to_state_slot_observed") is True
            for e in preprocess),
        "batch_state_column_observed_count": sum(
            e.get("state_column_observed") is True for e in preprocess),
        "batch_mapping_observed_physical_entries_count": sum(
            p.get("request_slot_to_table_row_verified") is True and
            p.get("physical_entry_observed") is True for p in physical),
        "mamba_state_seed_observed_count":
            sum(e.get("state_seed_observed") is True for e in mamba),
        "mamba_tensor_layout_observed_count":
            sum(bool(e.get("tensor_metadata")) for e in mamba),
        "scheduler_effective_blocks": [
            e.get("self_block", {}).get("block_size") for e in sched[:4]],
        "mamba_effective_cache_blocks": [
            e.get("cache_config", {}) for e in mamba[:4]],
        "mamba_sampled_seeds": [
            e.get("state_seed_value") for e in mamba[:8]
            if e.get("state_seed_observed") is True],
        "physical_mapping_observed_partial": (
            bool(physical) and
            any(p.get("request_slot_to_table_row_verified") is True
                and p.get("physical_id_within_state_allocation") is True
                and p.get("block_size_matches_mamba_config") is True
                for p in physical)),
        "physical_mapping_and_reuse_verified": False,
        "state_content_checksum_evidence_status": (
            "CANDIDATE_SNAPSHOTS_OBSERVED_NOT_HIT_ATTRIBUTED"
            if any(e.get("samples") for e in snapshot_events)
            else "CANDIDATE_SNAPSHOT_NOT_COMPLETELY_OBSERVED"),
        "candidate_state_snapshot_event_count": len(snapshot_events),
        "candidate_state_snapshot_pre_count": sum(
            e.get("phase") == "before_preprocess" for e in snapshot_events),
        "candidate_state_snapshot_post_count": sum(
            e.get("phase") == "after_postprocess" for e in snapshot_events),
        "candidate_state_snapshot_sample_count": sum(
            len(e.get("samples", [])) for e in snapshot_events
            if isinstance(e.get("samples"), list)),
        "candidate_state_snapshot_error_count": sum(
            e.get("status") == "INCONCLUSIVE_GPU_SNAPSHOT_UNAVAILABLE"
            for e in snapshot_events),
        "candidate_state_snapshot_full_cold_hit_pair_verified": False,
        "candidate_state_snapshot_records": [
            {"phase":e.get("phase"), "ordinal":e.get("ordinal"),
             "status":e.get("status"),
             "samples": [
                 {field: sample.get(field) for field in (
                     "state_kind", "group_id", "physical_block_id",
                     "layer_sha256_prefix", "state_kind_index",
                     "shape", "dtype", "natural_byte_length",
                     "state_sha256", "block_boundary_tokens",
                     "state_column", "observed_computed_tokens",
                     "gpu_completed_before_read")}
                 for sample in e.get("samples", [])[:4]
                 if isinstance(sample, dict)
                 and isinstance(sample.get("state_sha256"), str)
                 and re.fullmatch(r"[a-f0-9]{64}",
                                  sample["state_sha256"])
             ]}
            for e in snapshot_events[:16]
            if isinstance(e.get("samples", []), list)
        ],
        "mtp_speculative_acceptance_observed": False,
        "provenance": "LIVE_CANDIDATE_WORKER_STDOUT_NOT_STATIC_AST",
    }


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
            print(json.dumps({"status": "PREFLIGHT_CPU_SOURCE_SHA_VERIFIED_NO_GPU",
                              "stage_files_sha256_match": True,
                              "original_state": ci["State"]["Status"],
                              "candidate_port": PORT,
                              "installed_vllm_root_verified": bool(root),
                              "stage_hashes_verified_on_host": True,
                              "gpu_model_loaded": False}, sort_keys=True))
            print("P1_PREFIX_GPU_PREFLIGHT_SOURCE_CPU_PROBE_PASS_NOT_GPU")
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
        # Validate the real pinned model's chat-template/logprob API *before*
        # stopping it. Do not load a second GPU model just to learn 400/empty.
        from src import p1_prefix_gpu_oracle as oracle
        try:
            proto = oracle.probe_before_stop(model, 8000)
        except oracle.OracleBlocked as exc:
            raise Blocked("ORIGINAL_CHAT_ORACLE_" + str(exc)) from None
        print(json.dumps(proto, sort_keys=True))
        print("P1_PREFIX_ORIGINAL_CHAT_ORACLE_INTERFACE_PASS_BEFORE_STOP")
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
            try:
                result = oracle.run_oracle(model, PORT, min_output_tokens=24,
                                           enable_cold_controls=True)
            except oracle.OracleBlocked as exc:
                raise Blocked("CANDIDATE_ORACLE_" + str(exc)) from None
            runtime_abi = read_candidate_observer()
            runtime_abi["mtp_speculative_acceptance_observed"] = (
                result["mtp_acceptance_observed"])
            result["active_candidate_abi"] = runtime_abi
            result["active_mamba_physical_mapping_observed"] = (
                runtime_abi["physical_mapping_and_reuse_verified"])
            print(json.dumps(result, sort_keys=True))
            print("P1_PREFIX_GPU_ORACLE_" + result["status"])
            if not result["status"].startswith("PASS_"):
                raise Blocked("ORACLE_NOT_VERIFIED_" + result["status"])
            # Strict API equality alone is not the full P1 physical+MTP gate.
            if not (runtime_abi["physical_mapping_and_reuse_verified"]
                    and runtime_abi["mtp_speculative_acceptance_observed"]):
                raise Blocked("ACTIVE_PHYSICAL_MAPPING_OR_MTP_NOT_PROVEN")
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
