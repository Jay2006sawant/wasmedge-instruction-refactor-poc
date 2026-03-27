# Instruction refactor: test migration and suite order

Which WasmEdge tests matter for instruction IR work, and a sensible order to run them.

---

## 1. What we are protecting

The refactor touches how **function bodies** are represented after load: today the AST uses `WasmEdge::AST::Instruction` (see `include/ast/instruction.h` and loader code under `lib/loader/ast/`). Validator and executor consume that IR; serializer tests build IR by hand.

**Goal of testing:** same semantics as today (load → validate → execute → serialize), with no silent behavior drift. Tests fall into two buckets:

| Bucket | Meaning | Typical test change |
|--------|--------|---------------------|
| **A — Direct IR** | C++ constructs `AST::Instruction`, sets `Expr.getInstrs()`, or asserts loader output shape | Often updated or wrapped in helpers when storage splits |
| **B — Pipeline / black-box** | Loads `.wasm`, runs VM, or runs JSON spec harness | Usually **no** test edits unless the public error surface or API changes |

---

## 2. CTest targets that matter for this project

These names come from `test/loader/CMakeLists.txt`, `test/validator/CMakeLists.txt`, and `test/executor/CMakeLists.txt`.

| CTest name | Executable | Sources (from CMake) |
|------------|------------|----------------------|
| `wasmedgeLoaderFileMgrTests` | `wasmedgeLoaderFileMgrTests` | `filemgrTest.cpp` |
| `wasmedgeLoaderASTTests` | `wasmedgeLoaderASTTests` | `moduleTest.cpp`, `sectionTest.cpp`, `descriptionTest.cpp`, `segmentTest.cpp`, `typeTest.cpp`, `expressionTest.cpp`, `instructionTest.cpp` |
| `wasmedgeLoaderSerializerTests` | `wasmedgeLoaderSerializerTests` | `serializeModuleTest.cpp`, `serializeSectionTest.cpp`, `serializeDescriptionTest.cpp`, `serializeSegmentTest.cpp`, `serializeTypeTest.cpp`, `serializeExpressionTest.cpp`, `serializeInstructionTest.cpp` |
| `wasmedgeValidatorRegressionTests` | `wasmedgeValidatorRegressionTests` | `ValidatorRegressionTest.cpp` |
| `wasmedgeExecutorCoreTests` | `wasmedgeExecutorCoreTests` | `ExecutorTest.cpp` |
| `wasmedgeExecutorRegressionTests` | `wasmedgeExecutorRegressionTests` | `ExecutorRegressionTest.cpp` |

**How to run one target (from build dir):**

```bash
ctest -R wasmedgeLoaderASTTests --output-on-failure
ctest -R wasmedgeLoaderSerializerTests --output-on-failure
ctest -R wasmedgeValidatorRegressionTests --output-on-failure
ctest -R wasmedgeExecutorCoreTests --output-on-failure
ctest -R wasmedgeExecutorRegressionTests --output-on-failure
```

**Full matrix** (configure first with `-DWASMEDGE_BUILD_TESTS=ON`):

```bash
cmake -S . -B build -DWASMEDGE_BUILD_TESTS=ON
cmake --build build
cd build && ctest -j"$(nproc)" --output-on-failure
```

---

## 3. Loader tests (Bucket A — highest churn)

### 3.1 `wasmedgeLoaderASTTests`

**Purpose:** Parse wasm bytes and exercise the loader AST, including expressions and instructions.

| File | Role |
|------|------|
| `test/loader/instructionTest.cpp` | Unit tests **explicitly** for loading instruction encodings (block, if, br, br_table, call, memory, SIMD, try_table, etc.). Uses `WasmEdge::Loader::Loader` and binary blobs via `prefixedVec`. |
| `test/loader/expressionTest.cpp` | Loads expression nodes (instruction sequences inside functions). |
| `test/loader/moduleTest.cpp`, `sectionTest.cpp`, `descriptionTest.cpp`, `segmentTest.cpp`, `test/loader/typeTest.cpp` | Broader module/section parsing; may pull in code sections and expressions indirectly. |

**Refactor strategy:** Prefer **stable construction helpers** in the test tree (or a small test-only helper header) so tests say “build this opcode sequence” instead of depending on raw split-blob layout. If `AST::Expression` keeps a `getInstrs()`-style view or a façade, many tests only need mechanical updates at the construction site.

---

## 4. Serializer tests (Bucket A — high churn)

**Target:** `wasmedgeLoaderSerializerTests`

| File | Role |
|------|------|
| `test/loader/serializeInstructionTest.cpp` | Builds `std::vector<WasmEdge::AST::Instruction>`, assigns `Expr.getInstrs()`, and checks serialize round-trips. Large surface of opcodes. |
| `test/loader/serializeExpressionTest.cpp` | Serialize expressions built from instructions. |
| `test/loader/serializeSectionTest.cpp`, `serializeSegmentTest.cpp`, `serializeTypeTest.cpp`, `serializeModuleTest.cpp`, `serializeDescriptionTest.cpp` | Embed `Instruction(...)` in sections/types/segments as needed for serialization tests. |

**Refactor strategy:** Same as loader: **centralize** “make expression from opcodes + immediates” so serializer tests do not duplicate `ImmBlob` encoding details. Serialization production code lives under `lib/loader/serialize/`; tests should follow whatever public API the serializer exposes after the split.

---

## 5. Validator tests (Bucket B — mostly pipeline)

**Target:** `wasmedgeValidatorRegressionTests`  
**Source:** `test/validator/ValidatorRegressionTest.cpp` — uses `WasmEdge::VM::VM` and generated wasm bytes; it does **not** include `AST::Instruction` in the grep sense.

**Note:** `test/validator/ValidatorSubtypeTest.cpp` exists in the tree with similar-looking subtype tests, but **`test/validator/CMakeLists.txt` only registers `ValidatorRegressionTest.cpp`**. Do not assume `ValidatorSubtypeTest.cpp` runs in CI until it is added to CMake. If you consolidate or wire it up, update this doc.

**Refactor strategy:** Expect **few or no** edits unless validation errors, opcode reporting, or module layout changes. Failures here usually mean **fix validator** against split IR, not rewrite tests.

---

## 6. Executor tests (Bucket B + spec harness)

### 6.1 `wasmedgeExecutorCoreTests` (`ExecutorTest.cpp`)

- Implements **parameterized** `CoreTest` over spec units (see `INSTANTIATE_TEST_SUITE_P` with `T.enumerate(SpecTest::TestMode::Interpreter)`).
- Uses `SpecTest` with path `../spec/testSuites` (relative to test working directory).
- Exercises full pipeline: `loadWasm`, `validate`, `instantiate`, `execute`, etc.

So “core executor tests” in practice are **large spec-driven integration tests**, not small C++ unit tests of `Instruction`.

### 6.2 `wasmedgeExecutorRegressionTests` (`ExecutorRegressionTest.cpp`)

- Linked to `wasmedgeVM` and GTest (no `wasmedgeTestSpec` in `test/executor/CMakeLists.txt` for this target).
- Regression-style tests; still pipeline-level.

**Refactor strategy:** Same as validator: **fix code first**; change tests only if timing, trap messages, or API contracts change.

---

## 7. Spec test infrastructure (not a separate CTest name per proposal)

- **Library:** `wasmedgeTestSpec` in `test/spec/CMakeLists.txt` — build from `spectest.cpp`.
- **Data:** CMake `FetchContent` pulls `https://github.com/WasmEdge/wasmedge-spectest` at tag `wasm-core-20260301` and copies each suite into `${CMAKE_CURRENT_BINARY_DIR}/testSuites/<name>` under the **spec** build dir (e.g. `build/test/spec/testSuites/wasm-1.0` when build root is `build`). Folder names are exactly `WASMEDGE_SPECTEST_FOLDERS` in `test/spec/CMakeLists.txt` (`wasm-1.0` … `component-model` as listed there).
- **Harness:** `spectest.cpp` parses JSON from `wast2json` output and drives commands (module, assert, invoke, …). Comments in `ExecutorTest.cpp` point to the official WebAssembly spec testsuite and wabt.

**Refactor strategy:** These are **semantic oracles**. If you break load/validate/exec for any instruction, failures show up here. No per-file C++ edits unless you change how the harness reports errors.

---

## 8. Other tests that mention “Instruction” but are not AST storage

| Location | What it is |
|----------|------------|
| `test/errinfo/errinfoTest.cpp` | `WasmEdge::ErrInfo::InfoInstruction` — error formatting for **invalid instruction** contexts, not `AST::Instruction` layout. |
| `test/api/APIUnitTest.cpp`, `test/thread/ThreadTest.cpp` | Statistics / “instruction counting” in the API or thread config — unrelated to AST IR storage unless you rename those APIs. |

Touch these only if your refactor changes error types or statistics behavior.

---

## 9. Order to run suites during development (practical gate)

Suggested order so failures are cheap to localize:

1. **Immediate encode/decode unit tests** (if you add them under `test/` or keep them in POC scripts first).
2. **`wasmedgeLoaderASTTests`** — loader and `instructionTest` / `expressionTest`.
3. **`wasmedgeLoaderSerializerTests`** — serializer parity with hand-built IR.
4. **`wasmedgeValidatorRegressionTests`** — validation over full modules.
5. **`wasmedgeExecutorRegressionTests`** — executor regressions without full spec sweep.
6. **`wasmedgeExecutorCoreTests`** — spec JSON harness (longest).

For bisecting, use `ctest -R '<regex>'` to narrow to one target.

---


## 10. Related code paths (for cross-checking while debugging)

- `include/ast/instruction.h` — AST `Instruction` definition.
- `lib/loader/ast/instruction.cpp`, `lib/loader/ast/expression.cpp` — load path.
- `lib/loader/serialize/` — serialize path.
- `lib/validator/formchecker.cpp`, `lib/validator/validator.cpp` — validation.
- `lib/executor/engine/engine.cpp`, `lib/executor/instantiate/function.cpp` — execution / instantiation.

---



