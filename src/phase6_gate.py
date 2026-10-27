"""Phase 6 contract evaluator. No runtime imports, Docker, GPU or network."""
import argparse
import json
import pathlib
import sys

GATES = ("P6-A", "P6-B", "P6-C", "P6-D")
REQUIRED = ("source_sha", "image_digest", "scheduler_class", "cache_block_size",
            "scheduler_block_size", "hash_block_size", "groups")

def evaluate_a(snapshot):
    missing = [key for key in REQUIRED if key not in snapshot]
    if missing:
        return {"gate": "P6-A", "status": "BLOCKED", "reasons": ["missing: " + ",".join(missing)]}
    reasons = []
    for key in ("cache_block_size", "scheduler_block_size", "hash_block_size"):
        if type(snapshot[key]) is not int or snapshot[key] <= 0:
            reasons.append("invalid " + key)
    groups = snapshot["groups"]
    if not isinstance(groups, list) or not groups:
        return {"gate": "P6-A", "status": "BLOCKED", "reasons": ["group inventory unavailable"]}
    for i, group in enumerate(groups):
        required = ("block_size", "block_table", "states")
        absent = [k for k in required if k not in group]
        if absent:
            return {"gate": "P6-A", "status": "BLOCKED", "reasons": [f"group {i} missing {absent}"]}
        if type(group["block_size"]) is not int or group["block_size"] <= 0:
            reasons.append(f"group {i} invalid block size")
        table = group["block_table"]
        if not all(k in table for k in ("rows", "columns", "row_stride_elements", "physical_ids")):
            return {"gate": "P6-A", "status": "BLOCKED", "reasons": [f"group {i} incomplete table"]}
        rows, cols, stride = (table[k] for k in ("rows", "columns", "row_stride_elements"))
        if any(type(v) is not int for v in (rows, cols, stride)) or min(rows, cols) < 1 or stride < cols:
            reasons.append(f"group {i} invalid table geometry")
            continue
        ids = table["physical_ids"]
        if not isinstance(ids, list) or len(ids) != rows or any(not isinstance(row, list) or len(row) != cols for row in ids):
            return {"gate": "P6-A", "status": "BLOCKED", "reasons": [f"group {i} incomplete physical ids"]}
        states = group["states"]
        if not isinstance(states, list) or not states:
            return {"gate": "P6-A", "status": "BLOCKED", "reasons": [f"group {i} missing states"]}
        for j, state in enumerate(states):
            keys = ("allocated_bytes", "block_stride_bytes", "payload_bytes", "physical_blocks")
            if any(k not in state for k in keys):
                return {"gate": "P6-A", "status": "BLOCKED", "reasons": [f"group {i} state {j} incomplete"]}
            alloc, step, payload, count = (state[k] for k in keys)
            if any(type(v) is not int for v in (alloc, step, payload, count)) or min(alloc, step, payload, count) <= 0 or payload > step:
                reasons.append(f"group {i} state {j} invalid dimensions")
                continue
            for row in ids:
                for physical in row:
                    if type(physical) is not int or physical < 0 or physical >= count or physical * step + payload > alloc:
                        reasons.append(f"group {i} state {j} physical boundary violation")
                        break
    return {"gate": "P6-A", "status": "FAIL" if reasons else "PASS",
            "reasons": sorted(set(reasons)), "scope": "supplied snapshot contract only; not active DGX runtime"}

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--gate", choices=GATES, required=True)
    parser.add_argument("--snapshot", type=pathlib.Path)
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args(argv)
    if args.gate != "P6-A":
        result = {"gate": args.gate, "status": "BLOCKED", "reasons": ["runtime approval and implementation required"]}
    elif args.snapshot is None:
        result = {"gate": args.gate, "status": "BLOCKED", "reasons": ["read-only runtime snapshot not supplied"]}
    else:
        try:
            result = evaluate_a(json.loads(args.snapshot.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError) as exc:
            result = {"gate": args.gate, "status": "BLOCKED", "reasons": [type(exc).__name__]}
    payload = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)
    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if result["status"] == "PASS" else 2

if __name__ == "__main__":
    sys.exit(main())
