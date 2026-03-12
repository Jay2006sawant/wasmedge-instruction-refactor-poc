#!/usr/bin/env python3
"""
POC-3: Executor subset validation

Runs the same subset program in two modes:
1) legacy instruction list path
2) split stream decode+execute path

Compares final machine state and prints timing for both paths.
"""

from __future__ import annotations

import argparse
import csv
import struct
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


NO_IMM = {"drop", "nop", "end", "i32.add", "i32.sub"}
INDEX1 = {"local.get", "local.set"}
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


@dataclass
class SplitStream:
    opcodes: List[int]
    imm_offsets: List[int]
    imm_blob: bytearray


@dataclass
class MachineState:
    stack: List[int]
    locals_: List[int]
    memory: bytearray

    def clone(self) -> "MachineState":
        return MachineState(
            stack=list(self.stack),
            locals_=list(self.locals_),
            memory=bytearray(self.memory),
        )


def parse_csv(path: Path) -> List[Instr]:
    out: List[Instr] = []
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            op = row["opcode"].strip().lower()
            if op not in OPCODE_TO_ID:
                raise ValueError(f"Unsupported opcode in POC-3: {op}")
            args: List[int] = []
            for key in ("arg0", "arg1", "arg2"):
                raw = (row.get(key) or "").strip()
                if raw != "":
                    args.append(int(raw))
            out.append(Instr(opcode=op, args=tuple(args)))
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
        # align(u32), offset(u64), memidx(u32 default 0)
        if len(args) < 2 or len(args) > 3:
            raise ValueError(f"{op} expects 2 or 3 args, got {args}")
        align = args[0]
        offset = args[1]
        memidx = args[2] if len(args) == 3 else 0
        return struct.pack("<IQI", align, offset, memidx)
    raise ValueError(f"Unsupported opcode kind: {op}")


def decode_immediate(op: str, blob: bytes, pos: int) -> Tuple[Tuple[int, ...], int]:
    if op in NO_IMM:
        return tuple(), pos
    if op in INDEX1:
        end = pos + 4
        (v,) = struct.unpack("<I", blob[pos:end])
        return (v,), end
    if op in CONST32:
        end = pos + 4
        (v,) = struct.unpack("<i", blob[pos:end])
        return (v,), end
    if op in CONST64:
        end = pos + 8
