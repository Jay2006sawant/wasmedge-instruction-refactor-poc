# POC-0: Instruction Baseline Memory Estimator

This is the first implementation POC for the WasmEdge instruction refactor proposal.

## What this POC does

It gives a **baseline estimate** of instruction memory usage by:

1. Reading opcode frequency input (`opcode,count`).
2. Classifying instructions by immediate shape.
3. Estimating:
   - current memory (`32 bytes * instruction count`)
   - logical bytes needed (header + immediate bytes by category)
   - estimated waste/reducible fraction.

## Why this POC is useful

- It provides measurable baseline numbers before refactor.
- It helps discuss priority opcode families with mentors.
- It is quick to verify and iterate.

## Files

- `poc0_estimator.py` - estimator script
- `samples/opcode_frequency_sample.csv` - sample dataset for quick verification

Input CSV format:
- header: `opcode,count`
- each row: opcode text and positive integer count

## Run

From repo root:

```bash
python3 "poc/poc0/poc0_estimator.py" \
  --input "poc/poc0/samples/opcode_frequency_sample.csv"
```

Optional tuning for dynamic immediates:

```bash
python3 "poc/poc0/poc0_estimator.py" \
  --input "poc/poc0/samples/opcode_frequency_sample.csv" \
  --avg-br-table-targets 6 \
  --avg-select-types 1 \
  --avg-try-catches 3
```

## Expected output

The script prints:

- category distribution
- current model bytes
- estimated logical bytes
- estimated waste + reducible fraction
- top opcodes by count

## Important note

This is a planning baseline estimator, not final performance proof.

Final proof in later milestones will use:
- instrumented runtime data,
- full test-backed parity,
- before/after on real workloads.

