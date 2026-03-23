# WasmEdge Instruction Refactor POC

I put this repository together to support my WasmEdge GSoC proposal for
refactoring instruction storage. The idea is to split opcode storage from
immediate storage so the runtime does not pay the full `Instruction` footprint
for every decoded opcode, while still keeping migration safe through staged
parity checks.

## What this repository contains

- `poc/poc0`: baseline estimator for the current instruction-memory pattern
- `poc/poc1`: split storage encode/decode prototype
- `poc/poc2`: dual decode parity check (legacy vs split)
- `poc/poc3`: executor subset behavior parity check
- `poc/POC_RESULTS.md`: one place that summarizes the POCs and their sample outputs
- `M3.4-memory-proof-methodology/`: the detailed runbook for the final before/after memory proof promised in the proposal

## Quick run commands

```bash
python3 "poc/poc0/poc0_estimator.py" --input "poc/poc0/samples/opcode_frequency_sample.csv"
python3 "poc/poc1/poc1_split_storage.py" --input "poc/poc1/samples/program_subset.csv"
python3 "poc/poc2/poc2_dual_decode_parity.py" --input "poc/poc2/samples/program_subset.csv"
python3 "poc/poc3/poc3_executor_subset.py" --input "poc/poc3/samples/program_subset.csv" --iterations 5000
```

## What each POC is meant to show

- POC-0: a baseline estimate of where instruction-memory waste comes from
- POC-1: that a split stream can round-trip correctly on a subset and reduce storage in the model
- POC-2: that legacy decode and split decode agree on the same byte stream for covered opcodes
- POC-3: that executing from the split path preserves final machine state for the covered subset

Each `pocX/README.md` includes a short explanation, a run command, and sample output for quick verification.

## Notes

- These are prototype artifacts for design validation and migration safety.
- Final performance claims should come from integrated runtime measurement inside WasmEdge itself.
- I use this repo as supporting material for the proposal; the production-quality refactor still belongs in the WasmEdge codebase.
