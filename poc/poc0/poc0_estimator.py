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
