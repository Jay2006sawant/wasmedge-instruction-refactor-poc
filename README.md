# WasmEdge Instruction Refactor POC

This repository contains proof-of-concept work for the WasmEdge instruction
refactor idea: split opcode storage from immediate storage to reduce memory
overhead and enable safer staged migration.

## What is included

- `poc/poc0`: baseline estimator for current instruction-memory pattern
- `poc/poc1`: split storage encode/decode prototype
- `poc/poc2`: dual decode parity check (legacy vs split)
- `poc/poc3`: executor subset behavior parity check
- `poc/POC_RESULTS.md`: consolidated findings and sample outputs

## Quick run commands

```bash
python3 "poc/poc0/poc0_estimator.py" --input "poc/poc0/samples/opcode_frequency_sample.csv"
python3 "poc/poc1/poc1_split_storage.py" --input "poc/poc1/samples/program_subset.csv"
python3 "poc/poc2/poc2_dual_decode_parity.py" --input "poc/poc2/samples/program_subset.csv"
python3 "poc/poc3/poc3_executor_subset.py" --input "poc/poc3/samples/program_subset.csv" --iterations 5000
```

## Expected outputs (high level)

- POC-0: memory baseline estimate by instruction category
- POC-1: split-stream roundtrip parity + size estimate
- POC-2: decode parity PASS/FAIL with mismatch details
- POC-3: executor state parity PASS/FAIL + timing signal

Each `pocX/README.md` includes a sample output block for quick verification.

## Notes

- These are prototype artifacts for design validation and migration safety.
- Final performance claims should come from integrated runtime measurement.
