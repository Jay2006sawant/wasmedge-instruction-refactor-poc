#!/usr/bin/env python3
"""
POC-2: Dual decode parity prototype

Goal:
- take one bytecode stream
- decode it using two paths:
  1) legacy-style instruction records
  2) split-stream representation
- compare decoded logical instruction sequence
"""

from __future__ import annotations

import argparse
import csv
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


NO_IMM = {"drop", "nop", "end", "i32.add", "i32.sub"}
INDEX1 = {"local.get", "local.set", "call", "br_if"}
CONST32 = {"i32.const"}
CONST64 = {"i64.const"}
MEMARG = {"i32.load", "i32.store"}

OPCODE_TO_ID: Dict[str, int] = {
    "drop": 0x1A,
    "nop": 0x01,
    "end": 0x0B,
    "i32.add": 0x6A,
    "i32.sub": 0x6B,
    "local.get": 0x20,
    "local.set": 0x21,
    "call": 0x10,
    "br_if": 0x0D,
    "i32.const": 0x41,
    "i64.const": 0x42,
    "i32.load": 0x28,
    "i32.store": 0x36,
}
ID_TO_OPCODE = {v: k for k, v in OPCODE_TO_ID.items()}

OFFSET_NONE = 0xFFFFFFFF


@dataclass
class Instr:
    opcode: str
    args: Tuple[int, ...]
    offset: int


@dataclass
class SplitStream:
    opcodes: List[int]
    offsets: List[int]
    imm_offsets: List[int]
    imm_blob: bytearray


def parse_csv(path: Path) -> List[Tuple[str, Tuple[int, ...]]]:
    out: List[Tuple[str, Tuple[int, ...]]] = []
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            op = row["opcode"].strip().lower()
            if op not in OPCODE_TO_ID:
                raise ValueError(f"Unsupported opcode in POC-2: {op}")
            args: List[int] = []
            for key in ("arg0", "arg1", "arg2"):
                raw = (row.get(key) or "").strip()
                if raw != "":
                    args.append(int(raw))
            out.append((op, tuple(args)))
    return out


def encode_immediate(op: str, args: Tuple[int, ...]) -> bytes:
    if op in NO_IMM:
        if args:
            raise ValueError(f"{op} expects no args, got {args}")
        return b""
    if op in INDEX1:
        if len(args) != 1:
            raise ValueError(f"{op} expects 1 arg, got {args}")
        return struct.pack("<I", args[0])
    if op in CONST32:
        if len(args) != 1:
            raise ValueError(f"{op} expects 1 arg, got {args}")
        return struct.pack("<i", args[0])
    if op in CONST64:
        if len(args) != 1:
            raise ValueError(f"{op} expects 1 arg, got {args}")
        return struct.pack("<q", args[0])
    if op in MEMARG:
        if len(args) < 2 or len(args) > 3:
            raise ValueError(f"{op} expects 2 or 3 args, got {args}")
        align = args[0]
        offset = args[1]
        memidx = args[2] if len(args) == 3 else 0
        return struct.pack("<IQI", align, offset, memidx)
    raise ValueError(f"Unsupported opcode kind: {op}")


def immediate_size(op: str) -> int:
    if op in NO_IMM:
        return 0
