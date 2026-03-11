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
    if op in INDEX1 or op in CONST32:
        return 4
    if op in CONST64:
        return 8
    if op in MEMARG:
        return 16
    raise ValueError(f"Unsupported opcode kind: {op}")


def decode_immediate(op: str, data: bytes, pos: int) -> Tuple[Tuple[int, ...], int]:
    if op in NO_IMM:
        return tuple(), pos
    if op in INDEX1:
        end = pos + 4
        (v,) = struct.unpack("<I", data[pos:end])
        return (v,), end
    if op in CONST32:
        end = pos + 4
        (v,) = struct.unpack("<i", data[pos:end])
        return (v,), end
    if op in CONST64:
        end = pos + 8
        (v,) = struct.unpack("<q", data[pos:end])
        return (v,), end
    if op in MEMARG:
        end = pos + 16
        align, offset, memidx = struct.unpack("<IQI", data[pos:end])
        return (align, offset, memidx), end
    raise ValueError(f"Unsupported opcode kind: {op}")


def encode_program_to_bytecode(program: List[Tuple[str, Tuple[int, ...]]]) -> bytes:
    out = bytearray()
    for op, args in program:
        out.append(OPCODE_TO_ID[op])
        out.extend(encode_immediate(op, args))
    return bytes(out)


def decode_legacy(bytecode: bytes) -> List[Instr]:
    instrs: List[Instr] = []
    i = 0
    while i < len(bytecode):
        offset = i
        op_id = bytecode[i]
        i += 1
        op = ID_TO_OPCODE[op_id]
        args, i = decode_immediate(op, bytecode, i)
        instrs.append(Instr(opcode=op, args=args, offset=offset))
    return instrs


def decode_split(bytecode: bytes) -> List[Instr]:
    stream = SplitStream(opcodes=[], offsets=[], imm_offsets=[], imm_blob=bytearray())
    i = 0
    while i < len(bytecode):
        offset = i
        op_id = bytecode[i]
        i += 1
        op = ID_TO_OPCODE[op_id]
        imm_len = immediate_size(op)
        stream.opcodes.append(op_id)
        stream.offsets.append(offset)
        if imm_len == 0:
            stream.imm_offsets.append(OFFSET_NONE)
        else:
            stream.imm_offsets.append(len(stream.imm_blob))
            stream.imm_blob.extend(bytecode[i : i + imm_len])
            i += imm_len

    # decode split representation back into logical instruction list
    out: List[Instr] = []
    for idx, op_id in enumerate(stream.opcodes):
        op = ID_TO_OPCODE[op_id]
        imm_off = stream.imm_offsets[idx]
        if imm_off == OFFSET_NONE:
            args = tuple()
        else:
            args, _ = decode_immediate(op, stream.imm_blob, imm_off)
        out.append(Instr(opcode=op, args=args, offset=stream.offsets[idx]))
    return out


def parity(a: List[Instr], b: List[Instr]) -> Tuple[bool, str]:
    if len(a) != len(b):
        return False, f"count mismatch: {len(a)} vs {len(b)}"
    for idx, (x, y) in enumerate(zip(a, b)):
        if x.opcode != y.opcode:
            return False, f"opcode mismatch at #{idx}: {x.opcode} vs {y.opcode}"
        if x.args != y.args:
            return False, f"args mismatch at #{idx} ({x.opcode}): {x.args} vs {y.args}"
        if x.offset != y.offset:
            return False, f"offset mismatch at #{idx}: {x.offset} vs {y.offset}"
    return True, "parity passed"


def main() -> None:
    parser = argparse.ArgumentParser(description="POC-2 dual decode parity")
    parser.add_argument("--input", required=True, help="Program CSV")
    args = parser.parse_args()

    path = Path(args.input)
    if not path.exists():
        raise SystemExit(f"Input file not found: {path}")

    program = parse_csv(path)
    bytecode = encode_program_to_bytecode(program)
    legacy = decode_legacy(bytecode)
    split = decode_split(bytecode)
    ok, details = parity(legacy, split)

    print("=== POC-2 Dual Decode Parity ===")
    print(f"Input file              : {path}")
    print(f"Encoded bytecode length : {len(bytecode)} B")
    print(f"Legacy decoded count    : {len(legacy)}")
    print(f"Split decoded count     : {len(split)}")
    print(f"Parity                  : {'PASS' if ok else 'FAIL'}")
    print(f"Details                 : {details}")

    if legacy:
        print("")
        print("First 8 decoded instructions:")
        for ins in legacy[:8]:
            print(f"- @off={ins.offset:<3} {ins.opcode:<10} args={ins.args}")


if __name__ == "__main__":
    main()

