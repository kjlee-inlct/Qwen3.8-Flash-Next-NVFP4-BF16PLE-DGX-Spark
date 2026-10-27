"""Small deterministic BF16 safetensors fixtures for Track A Phase 2.

Standard library only. All weights are synthetic and live exclusively under
the caller's TemporaryDirectory; never read model snapshots or HF caches.
"""

from __future__ import annotations

import json
import math
import struct
from dataclasses import dataclass
from pathlib import Path

PREFIX = "model.language_model.layers.1.ple.ple_embedding.ngram_embedding"


@dataclass(frozen=True)
class PleFixture:
    root: Path
    rows: tuple[bytes, ...]
    width: int
    parts: int

    @property
    def vocab(self) -> int:
        return len(self.rows)

    @property
    def row_bytes(self) -> int:
        return self.width * 2


def _write_safetensors(
    destination: Path,
    tensors: list[tuple[str, str, tuple[int, ...], bytes]],
) -> None:
    """Write a valid minimal safetensors file without importing torch."""
    header: dict[str, dict[str, object]] = {
        "__metadata__": {"fixture": "blazux-phase2-synthetic"}
    }
    start = 0
    payloads: list[bytes] = []
    for name, dtype, shape, payload in tensors:
        if name in header:
            raise ValueError("duplicate fixture tensor")
        header[name] = {
            "dtype": dtype,
            "shape": list(shape),
            "data_offsets": [start, start + len(payload)],
        }
        start += len(payload)
        payloads.append(payload)
    encoded = json.dumps(header, separators=(",", ":")).encode("utf-8")
    destination.write_bytes(
        struct.pack("<Q", len(encoded)) + encoded + b"".join(payloads)
    )


def make_bf16_fixture(
    root: Path,
    *,
    omit: tuple[int, ...] = (),
    width_override: dict[int, int] | None = None,
    dtype_override: dict[int, str] | None = None,
    rows_override: dict[int, int] | None = None,
    corrupt_payload_length: tuple[int, ...] = (),
    with_index: bool = True,
    duplicate_shard_zero_in_second_file: bool = False,
) -> PleFixture:
    """Build 13 x 7 BF16 entries in four shards, including a short final shard.

    Shape/dtype corruptions are localized to the requested shard. Each file
    begins with an unrelated F32 tensor so the PLE data_offset is not zero.
    """
    root.mkdir(parents=True, exist_ok=True)
    vocab, cols, parts = 13, 7, 4
    shard_size = math.ceil(vocab / parts)
    width_override = width_override or {}
    dtype_override = dtype_override or {}
    rows_override = rows_override or {}
    rows = tuple(
        b"".join(struct.pack("<H", 0x3F80 + ((r * cols + c) % 96))
                 for c in range(cols))
        for r in range(vocab)
    )
    weight_map: dict[str, str] = {}
    for file_no in range(2):
        filename = f"synthetic-ple-{file_no}.safetensors"
        tensors: list[tuple[str, str, tuple[int, ...], bytes]] = [
            ("dummy.weight", "F32", (5,), struct.pack("<5f", 1, 2, 3, 4, 5)),
        ]
        for part in range(file_no * 2, file_no * 2 + 2):
            if part in omit:
                continue
            width = width_override.get(part, cols)
            dtype = dtype_override.get(part, "BF16")
            actual_rows = rows_override.get(
                part, max(0, min(shard_size, vocab - part * shard_size))
            )
            unit = 1 if dtype == "F8_E4M3" else 2
            payload = b"".join(
                bytes(((part * 17 + i + j) % 256 for j in range(width)))
                if unit == 1 else
                b"".join(struct.pack("<H", 0x3F80 + ((i + j) % 96))
                         for j in range(width))
                for i in range(actual_rows)
            )
            # Normal BF16 payload is independent of the header and exactly
            # reproduces the global reference rows even across shard files.
            if width == cols and dtype == "BF16" and actual_rows == max(
                0, min(shard_size, vocab - part * shard_size)
            ):
                payload = b"".join(rows[part * shard_size:part * shard_size + actual_rows])
            if part in corrupt_payload_length:
                payload = payload[:-1]
            name = f"{PREFIX}.shard_{part}.weight"
            tensors.append((name, dtype, (actual_rows, width), payload))
            weight_map[name] = filename
        if file_no == 1 and duplicate_shard_zero_in_second_file:
            # Index continues to point shard_0 to file 0; reading file 1
            # due to its valid shard_2/3 entries must still detect the
            # unexpected same shard index in another header.
            tensors.append((
                f"{PREFIX}.shard_0.weight",
                "BF16",
                (shard_size, cols),
                b"".join(rows[:shard_size]),
            ))
        _write_safetensors(root / filename, tensors)
    if with_index:
        (root / "model.safetensors.index.json").write_text(
            json.dumps({"weight_map": weight_map}, sort_keys=True),
            encoding="utf-8",
        )
    return PleFixture(root=root, rows=rows, width=cols, parts=parts)


def qsa_topk_oracle(
    scores: tuple[float, ...],
    visible: tuple[int, ...],
    k: int,
) -> tuple[int, ...]:
    """Pure CPU reference only; NOT the vLLM/QSA/torch kernel implementation.

    Highest finite score wins. Ties choose smaller column index solely to
    make fixture expectations deterministic. Kernel ties need separate ABI test.
    """
    if not isinstance(k, int) or k < 0:
        raise ValueError("invalid k")
    if len(set(visible)) != len(visible) or any(
        not isinstance(i, int) or i < 0 or i >= len(scores) for i in visible
    ):
        raise ValueError("invalid visible columns")
    if k > len(visible):
        raise ValueError("k exceeds visible columns")
    if any(not math.isfinite(scores[i]) for i in visible):
        raise ValueError("non-finite visible score")
    return tuple(sorted(visible, key=lambda i: (-scores[i], i))[:k])
