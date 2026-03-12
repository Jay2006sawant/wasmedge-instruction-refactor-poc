# POC-3: Executor Subset Validation

This POC checks runtime behavior parity for a subset executor flow.

## What it does

It executes the same program in two modes:

1. Legacy path:
   - list of instructions (`opcode + args`)
2. Split path:
   - opcode stream + immediate blob decode on execution

Then it compares final machine state:

- stack
- locals
- memory bytes

It also prints basic timing across repeated runs.

## Supported subset

- `i32.const`, `i64.const`
- `local.get`, `local.set`
- `i32.add`, `i32.sub`
- `i32.load`, `i32.store`
- `drop`, `nop`, `end`

## Run

```bash
python3 "poc/poc3/poc3_executor_subset.py" \
  --input "poc/poc3/samples/program_subset.csv" \
  --iterations 5000
```

## Why this POC matters

This is the bridge between storage parity and runtime parity:

- If behavior parity fails, split migration is unsafe.
- If behavior parity passes for covered groups, I can move to broader integration.

Timing output is an early signal only. Correctness parity is the primary goal in
this stage; performance tuning belongs to later integrated milestones.

