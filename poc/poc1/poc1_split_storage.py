#!/usr/bin/env python3
"""
POC-1: Split instruction storage prototype

What this demonstrates:
- store opcodes in a compact opcode stream
- store immediates in a separate byte blob
- keep per-instruction immediate offsets
- decode back and compare with original sequence
"""

from __future__ import annotations

import argparse
import csv
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


NO_IMM = {"drop", "nop", "end", "i32.add", "i32.sub"}
INDEX1 = {"local.get", "local.set", "call"}
CONST32 = {"i32.const"}
CONST64 = {"i64.const"}
MEMARG = {"i32.load", "i32.store"}

CURRENT_INSTR_BYTES = 32
OFFSET_NONE = 0xFFFFFFFF


OPCODE_TO_ID: Dict[str, int] = {
    "drop": 0x1A,
    "nop": 0x01,
    "end": 0x0B,
    "i32.add": 0x6A,
    "i32.sub": 0x6B,
    "local.get": 0x20,
    "local.set": 0x21,
    "call": 0x10,
    "i32.const": 0x41,
    "i64.const": 0x42,
    "i32.load": 0x28,
    "i32.store": 0x36,
}

ID_TO_OPCODE = {v: k for k, v in OPCODE_TO_ID.items()}


@dataclass
class Instr:
    opcode: str
    args: Tuple[int, ...]


def parse_csv(path: Path) -> List[Instr]:
    out: List[Instr] = []
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            op = row["opcode"].strip().lower()
            if op not in OPCODE_TO_ID:
                raise ValueError(f"Unsupported opcode in POC-1: {op}")
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
        # arg0: align(u32), arg1: offset(u64), arg2: memidx(u32, optional default 0)
        if len(args) < 2 or len(args) > 3:
            raise ValueError(f"{op} expects 2 or 3 args, got {args}")
        align = args[0]
        offset = args[1]
        memidx = args[2] if len(args) == 3 else 0
        return struct.pack("<IQI", align, offset, memidx)
    raise ValueError(f"Unsupported opcode kind: {op}")


def decode_immediate(op: str, blob: bytes, start: int) -> Tuple[Tuple[int, ...], int]:
    if op in NO_IMM:
        return tuple(), start
    if op in INDEX1:
        end = start + 4
        (idx,) = struct.unpack("<I", blob[start:end])
        return (idx,), end
    if op in CONST32:
        end = start + 4
        (num,) = struct.unpack("<i", blob[start:end])
        return (num,), end
    if op in CONST64:
        end = start + 8
        (num,) = struct.unpack("<q", blob[start:end])
        return (num,), end
    if op in MEMARG:
        end = start + 16
        align, offset, memidx = struct.unpack("<IQI", blob[start:end])
        return (align, offset, memidx), end
    raise ValueError(f"Unsupported opcode kind: {op}")


@dataclass
class SplitStream:
    opcodes: List[int]
    imm_offsets: List[int]
    imm_blob: bytearray


def encode_split(instrs: List[Instr]) -> SplitStream:
    opcodes: List[int] = []
    imm_offsets: List[int] = []
    blob = bytearray()

    for ins in instrs:
        opcodes.append(OPCODE_TO_ID[ins.opcode])
        imm = encode_immediate(ins.opcode, ins.args)
        if len(imm) == 0:
            imm_offsets.append(OFFSET_NONE)
        else:
            imm_offsets.append(len(blob))
            blob.extend(imm)
    return SplitStream(opcodes=opcodes, imm_offsets=imm_offsets, imm_blob=blob)


def decode_split(stream: SplitStream) -> List[Instr]:
    out: List[Instr] = []
    for i, op_id in enumerate(stream.opcodes):
        op = ID_TO_OPCODE[op_id]
        off = stream.imm_offsets[i]
        if off == OFFSET_NONE:
            out.append(Instr(opcode=op, args=tuple()))
        else:
            args, _ = decode_immediate(op, stream.imm_blob, off)
            out.append(Instr(opcode=op, args=args))
    return out


def parity_check(a: List[Instr], b: List[Instr]) -> Tuple[bool, str]:
    if len(a) != len(b):
        return False, f"Instruction count mismatch: {len(a)} vs {len(b)}"
    for i, (x, y) in enumerate(zip(a, b)):
        if x.opcode != y.opcode:
            return False, f"Opcode mismatch at #{i}: {x.opcode} vs {y.opcode}"
        if x.args != y.args:
            return False, f"Args mismatch at #{i} ({x.opcode}): {x.args} vs {y.args}"
    return True, "Parity passed"


def estimate_bytes_old(n: int) -> int:
    return n * CURRENT_INSTR_BYTES


def estimate_bytes_split(stream: SplitStream) -> int:
    # opcodes as compact u8 + imm offset u32 per instruction + immediate blob bytes
    return len(stream.opcodes) + (4 * len(stream.imm_offsets)) + len(stream.imm_blob)


def main() -> None:
    parser = argparse.ArgumentParser(description="POC-1 split storage prototype")
    parser.add_argument("--input", required=True, help="CSV program file")
    args = parser.parse_args()

    path = Path(args.input)
    if not path.exists():
        raise SystemExit(f"Input file not found: {path}")

    original = parse_csv(path)
    stream = encode_split(original)
    decoded = decode_split(stream)
    ok, msg = parity_check(original, decoded)

    old_bytes = estimate_bytes_old(len(original))
    new_bytes = estimate_bytes_split(stream)
    saved = old_bytes - new_bytes
    saved_pct = (saved / old_bytes * 100.0) if old_bytes else 0.0

    print("=== POC-1 Split Storage Prototype ===")
    print(f"Input file                 : {path}")
    print(f"Instruction count          : {len(original)}")
    print(f"Opcode bytes               : {len(stream.opcodes)}")
    print(f"Immediate offset bytes     : {len(stream.imm_offsets) * 4}")
    print(f"Immediate blob bytes       : {len(stream.imm_blob)}")
    print("")
    print(f"Old model estimate         : {old_bytes} B")
    print(f"Split model estimate       : {new_bytes} B")
    print(f"Estimated savings          : {saved} B ({saved_pct:.2f}%)")
    print("")
    print(f"Roundtrip parity           : {'PASS' if ok else 'FAIL'}")
    print(f"Parity details             : {msg}")


if __name__ == "__main__":
    main()

