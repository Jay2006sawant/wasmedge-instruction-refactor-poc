# POC-1: Split Storage Prototype

This POC demonstrates a small working model of:

- opcode stream (`u8` per instruction),
- immediate offset table (`u32` per instruction),
- immediate blob (`bytearray` with variable-length payloads).

It supports a subset of opcodes for safe demonstration:

- no-immediate: `drop`, `nop`, `end`, `i32.add`, `i32.sub`
- index immediate: `local.get`, `local.set`, `call`
- const immediate: `i32.const`, `i64.const`
- memory immediate: `i32.load`, `i32.store`

## Run

From repo root:

```bash
python3 "poc/poc1/poc1_split_storage.py" \
  --input "poc/poc1/samples/program_subset.csv"
```

## What output means

- **Roundtrip parity PASS** means:
  - decode(encode(program)) exactly matches original instructions.
- **Estimated savings** compares:
  - old fixed-size model (32 bytes per instruction)
  - split stream estimate (`opcode bytes + offset bytes + immediate blob`)

This is a prototype for architecture validation, not the final runtime result.

## Limitation note

This subset prototype uses fixed assumptions for old-model size comparison.
Final measurements will use integrated runtime data in later milestones.

