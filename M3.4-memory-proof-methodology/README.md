# M3.4 — Memory proof (methodology & runbook)

I created this folder to keep the M3.4 memory-proof work concrete and repeatable. My plan here is simple: run the same fixed workloads before and after the split instruction representation, collect massif/heaptrack results with the same reporting rules, and keep the commands and outputs in one place so the final memory claim is backed by measured evidence.

## Goal

By the end of M3.4, I want this report to answer three questions clearly:

1. **Does instruction-related memory go down after the split representation is enabled?**
2. **How large is the reduction on fixed workloads?**
3. **Does the change avoid unacceptable runtime regression while improving memory usage?**

The proposal currently states an expected **20-35% instruction-storage reduction** for workloads dominated by no-immediate, index-based, and other small fixed-immediate instructions. This is the place where I will validate or revise that estimate using integrated measurements.

## Scope of the proof

I want this proof to stay focused on **instruction-related memory behavior** after the refactor, not vague whole-process impressions. The final report will include:

- per-workload instruction-related memory observations
- bytes per instruction where that number is meaningful
- peak heap measurements from **Valgrind massif**
- allocation hotspot views from **heaptrack**
- percentage reduction versus baseline
- runtime guardrail notes collected under the same workload setup

## Fixed workloads

The same workloads will be used for both baseline and split-enabled runs.

### 1. Loader-focused workload

- `wasmedgeLoaderASTTests`

This is the primary loader/AST workload because it directly exercises instruction decoding, AST construction, and the codepaths touched by the refactor.

### 2. Spec-corpus workloads

When the build enables them, selected spec corpora under WasmEdge's `test/spec/testSuites/` tree will be used as fixed inputs. The exact folders used in the final report will be listed explicitly (for example, `wasm-3.0`, `wasm-3.0-simd`, or other enabled proposal folders).

### 3. Optional additional workload

If I use any extra representative `.wasm` module beyond the two categories above, I will pin its exact source/path and keep it unchanged across baseline and after runs.

## Build matrix

I will capture the following information for every measurement set:

- git commit / branch
- whether the build is **baseline** or **split-enabled**
- compiler and target platform
- CMake flags
- build type (planned: `RelWithDebInfo`)

The key rule is that baseline and after runs must use the **same build settings** except for the intended split-representation change.

## Tools

### Valgrind massif

Massif will be used for peak heap over time. The final report will record:

- peak heap value
- command used
- workload used
- output artifact path

### heaptrack

heaptrack will be used to inspect allocation hotspots and allocation volume. The final report will record:

- command used
- workload used
- output artifact path
- any high-signal allocation observations relevant to the instruction refactor

### Optional RSS snapshot

I may also record `/usr/bin/time -v` output as a lightweight supplementary reference, but massif and heaptrack are the primary proof tools.

## Reporting rules

To avoid cherry-picked results, I will keep the reporting method fixed:

- use the same workloads before and after
- use the same build settings before and after
- repeat runs when appropriate and report a **median-style** summary
- keep the exact commands in the final report
- store before/after results side by side

The final tables will include at least:

| Workload | Baseline peak heap | Split peak heap | Reduction | Notes |
|----------|--------------------|-----------------|-----------|-------|

and, where meaningful:

| Workload | Baseline bytes/instr | Split bytes/instr | Reduction | Notes |
|----------|----------------------|-------------------|-----------|-------|

## Execution plan

### Step 1 — Baseline

Using the fixed workload list, I will collect baseline memory/runtime results with the current representation:

- build WasmEdge with the chosen fixed configuration
- run `wasmedgeLoaderASTTests`
- run selected spec workloads if included
- collect massif output
- collect heaptrack output
- store results and commands

### Step 2 — Split-enabled measurement

After the split representation is enabled for the agreed opcode families, I will repeat the same workloads with the same settings:

- rebuild with the split-enabled implementation
- rerun the same fixed workloads
- collect massif output
- collect heaptrack output
- compare against the baseline with the same metrics

### Step 3 — Final report

I will update this directory with:

- the exact commands used
- the final before/after tables
- artifact locations
- short interpretation notes
- runtime guardrail observations

## Runtime guardrail

M3.4 is not only about reducing bytes on paper. I will also record whether the measured setup shows any meaningful runtime regression on the same workloads. If runtime costs rise noticeably, I will report that explicitly instead of hiding it behind memory-only claims.

## Deliverable from this directory

By the end of M3.4, this directory will contain the detailed runbook and the final measured before/after evidence that supports the proposal's memory-proof deliverable.
