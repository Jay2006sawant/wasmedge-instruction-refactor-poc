# POC-2: Dual Decode Parity

This POC simulates loader migration safety:

- One bytecode stream is decoded by:
  1) legacy-style path
  2) split-storage path
- Then both decoded logical instruction sequences are compared.

## Why this POC matters

When migrating instruction representation, this is the key safety check:

- If parity fails, migration is not safe.
- If parity passes on covered opcode families, we can proceed to deeper integration.

## Run

```bash
python3 "poc/poc2/poc2_dual_decode_parity.py" \
  --input "poc/poc2/samples/program_subset.csv"
```

## Expected output

- bytecode length
- decoded instruction counts
- parity PASS/FAIL
- short decoded instruction preview

## Scope

This is a subset prototype (same family scope as early migration stages).

## If parity fails

Check mismatch kind in output first (count/opcode/args/offset), then inspect the
corresponding CSV row and immediate encoding rule for that opcode family.

