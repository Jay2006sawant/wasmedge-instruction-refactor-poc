#!/usr/bin/env python3
"""
POC-0 baseline memory estimator for WasmEdge instruction storage.

Input:
  - CSV file with rows: opcode,count
    opcode should be wasm text style, e.g. i32.add, local.get, i32.load

This script estimates:
  - current memory (fixed-size Instruction object per instruction)
  - estimated logical bytes actually needed
  - memory waste by category
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Tuple


HEADER_BYTES = 9  # flags + opcode + offset in proposal model
CURRENT_INSTRUCTION_BYTES = 32  # common 64-bit estimate for current Instruction


@dataclass(frozen=True)
class Category:
    name: str
    imm_bytes: int
    is_dynamic: bool = False


CATEGORIES = {
    "none": Category("No immediate", 0),
    "index1": Category("Single index immediate", 4),
    "index2": Category("Dual index immediate", 8),
    "blocktype": Category("Block/type immediate", 8),
    "memarg": Category("Memory immediate", 13),  # align+offset+(optional lane/index style)
    "const32": Category("Const immediate (4-byte)", 4),
    "const64": Category("Const immediate (8-byte)", 8),
    "const128": Category("Const immediate (16-byte)", 16),
    "lane": Category("SIMD lane immediate", 1),
    "br_table": Category("Branch table dynamic immediate", 0, True),
    "select_t": Category("Typed select list dynamic immediate", 0, True),
    "try_table": Category("Try/catch dynamic immediate", 0, True),
    "other": Category("Other / conservative fallback", 8),
}


NONE_OPS = {
    "unreachable",
    "nop",
    "return",
    "end",
    "else",
    "drop",
    "select",
    "memory.size",
    "memory.grow",
    "memory.fill",
    "ref.is_null",
    "ref.eq",
}

INDEX1_PREFIXES = (
    "local.",
    "global.",
    "ref.func",
    "call",
    "throw",
)

INDEX2_OPS = {
    "call_indirect",
    "return_call_indirect",
    "table.copy",
    "table.init",
    "memory.copy",
    "array.copy",
    "array.init_data",
    "array.init_elem",
    "struct.get",
    "struct.get_s",
    "struct.get_u",
    "struct.set",
}

JUMP_INDEX1_OPS = {
    "br",
    "br_if",
    "br_on_null",
    "br_on_non_null",
    "throw",
    "data.drop",
    "memory.init",
    "table.get",
    "table.set",
    "table.grow",
    "table.size",
    "table.fill",
    "elem.drop",
}

MEMARG_MARKERS = (
    ".load",
    ".store",
    "atomic.",
    "memory.atomic",
)


def normalize_opcode(op: str) -> str:
    op = op.strip()
    op = op.replace("__", ".")
    return op.lower()


def classify_opcode(opcode: str) -> str:
    op = normalize_opcode(opcode)

    if op in NONE_OPS:
        return "none"
    if op in ("block", "loop", "if"):
        return "blocktype"
    if op in ("br_table",):
        return "br_table"
    if op in ("select_t", "select.t"):
        return "select_t"
    if op in ("try_table", "try.table"):
        return "try_table"
    if op in JUMP_INDEX1_OPS:
        return "index1"
    if op.endswith(".const"):
        if op.startswith(("i32", "f32")):
            return "const32"
        if op.startswith(("i64", "f64")):
            return "const64"
        return "const128"
    if "shuffle" in op or op == "v128.const":
        return "const128"
    if "lane" in op:
        return "lane"
    if op in INDEX2_OPS:
        return "index2"
    if any(marker in op for marker in MEMARG_MARKERS):
        return "memarg"
    if op.startswith(INDEX1_PREFIXES) or ".get" in op or ".set" in op:
        return "index1"
    return "other"


def read_frequency_csv(path: Path) -> Iterable[Tuple[str, int]]:
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            opcode = row["opcode"].strip()
            count = int(row["count"])
            if count > 0:
                yield opcode, count


def estimate_dynamic_bytes(
    category_key: str,
    count: int,
    avg_br_table_targets: int,
    avg_select_types: int,
    avg_try_catches: int,
) -> int:
    if category_key == "br_table":
        # label count + labels (JumpDescriptor size is 16)
        return count * (4 + max(avg_br_table_targets, 1) * 16)
    if category_key == "select_t":
        # vec count + val types (ValType is 8 bytes)
        return count * (4 + max(avg_select_types, 1) * 8)
    if category_key == "try_table":
        # rough estimate: blocktype + catch vec count + catch descriptors
        # catch descriptor approximation = 24 bytes
        return count * (8 + 4 + max(avg_try_catches, 1) * 24)
    return 0


def human_bytes(num: int) -> str:
    kib = num / 1024.0
    mib = kib / 1024.0
    return f"{num:,} B ({mib:.2f} MiB)"


def main() -> None:
    parser = argparse.ArgumentParser(description="POC-0 memory estimator")
    parser.add_argument("--input", required=True, help="CSV file with opcode,count")
    parser.add_argument("--avg-br-table-targets", type=int, default=4)
    parser.add_argument("--avg-select-types", type=int, default=1)
    parser.add_argument("--avg-try-catches", type=int, default=2)
    args = parser.parse_args()

    path = Path(args.input)
    if not path.exists():
        raise SystemExit(f"Input file not found: {path}")

    by_category: Dict[str, int] = Counter()
    by_opcode: Dict[str, int] = Counter()

    for opcode, count in read_frequency_csv(path):
        key = classify_opcode(opcode)
        by_category[key] += count
        by_opcode[normalize_opcode(opcode)] += count

    total_instr = sum(by_category.values())
    old_total = total_instr * CURRENT_INSTRUCTION_BYTES

    logical_total = 0
    cat_rows = []
    for key, count in sorted(by_category.items(), key=lambda x: (-x[1], x[0])):
        cat = CATEGORIES[key]
        if cat.is_dynamic:
            imm = estimate_dynamic_bytes(
                key,
                count,
                args.avg_br_table_targets,
                args.avg_select_types,
                args.avg_try_catches,
            )
            logical = count * HEADER_BYTES + imm
        else:
            logical = count * (HEADER_BYTES + cat.imm_bytes)
        logical_total += logical
        cat_rows.append((cat.name, count, logical))

    wasted = old_total - logical_total
    reduction = (wasted / old_total * 100.0) if old_total else 0.0

    print("=== POC-0 WasmEdge Instruction Baseline Estimator ===")
    print(f"Input file: {path}")
    print(f"Total instructions: {total_instr:,}")
    print("")
    print("Category breakdown:")
    for name, count, logical in cat_rows:
        pct = (count / total_instr * 100.0) if total_instr else 0.0
        print(f"- {name:<38} {count:>10,} ({pct:5.1f}%) | logical: {human_bytes(logical)}")

    print("")
    print("Totals:")
    print(f"- Current model (fixed 32B each): {human_bytes(old_total)}")
    print(f"- Estimated logical needed      : {human_bytes(logical_total)}")
    print(f"- Estimated waste               : {human_bytes(wasted)}")
    print(f"- Estimated reducible fraction  : {reduction:.2f}%")

    print("")
    print("Top 12 opcodes by count:")
    for op, count in sorted(by_opcode.items(), key=lambda x: (-x[1], x[0]))[:12]:
        print(f"- {op:<30} {count:>10,}")

    print("")
    print("Note:")
    print("- This is a baseline estimator for planning/POC.")
    print("- Dynamic immediates use average assumptions from CLI args.")
    print("- Real final numbers will come from instrumented runtime measurement.")


if __name__ == "__main__":
    main()

