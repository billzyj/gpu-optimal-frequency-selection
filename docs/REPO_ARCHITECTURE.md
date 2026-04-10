# Repository Architecture

## 1. Objectives

This repository supports three workflows in one framework:

1. Reproduce reference GPU DVFS methods (EVEREST, Ali proxy, EAR, Oracle).
2. Compare all methods under a shared protocol and schema.
3. Develop and evaluate a proposed method quickly.

## 2. Layering

1. Method layer: `src/methods`
2. Shared runtime/contracts: `src/common`
3. Experiment assets: `config`, `scripts`, `analysis`, `artifacts`
4. External benchmark sources: `external` (git submodules, e.g., `repacss-benchmarking`)

## 3. Method Taxonomy

```text
src/methods/
├── system_baselines/
│   ├── max_freq/
│   ├── min_freq/
│   └── util_policy/
├── reimplemented_methods/
│   ├── everest_reimpl/
│   ├── ali_reimpl/
│   └── oracle_static/
├── third_party/
│   └── ear_external/
└── proposed_methods/
    └── my_method/
```

### 3.1 `system_baselines`

Simple controls with low implementation cost and high interpretability.

### 3.2 `reimplemented_methods`

Reference methods from papers/systems, re-implemented in this repository.

### 3.3 `third_party`

Method wrappers for systems that run outside Python runtime (e.g., EAR in C/runtime stack).

### 3.4 `proposed_methods`

Your new method for paper contributions.

### 3.5 `external/*` submodules

External repositories own benchmark runtime and site/vendor adapter logic.
This repository must consume them through bridge interfaces instead of copying their execution internals.

## 4. Contracts

## 4.1 Online methods (`AlgorithmInterface`)

Defined in `src/common/experiment/interfaces.py`:

1. `initialize(context, config) -> AlgorithmState`
2. `on_window(metrics, state) -> Decision`
3. `finalize(state) -> FinalSummary`

Applies to:

1. `system_baselines`
2. `reimplemented_methods` methods that run online in Python
3. `proposed_methods`

## 4.2 External methods (`ExternalMethodInterface`)

Defined in `src/common/experiment/interfaces.py`:

1. `run_external(context, config) -> ExternalRunResult`

Applies to:

1. `src/methods/third_party/*` bridge modules

External methods are job-level executions and must normalize outputs into repository artifact schema.

## 5. Shared Modules (`src/common`)

1. `experiment`: common contracts, types, validation.
2. `telemetry`: vendor-specific metric adapters under a unified API.
3. `control`: clock/power actuation adapters.
4. `power`: power/energy collection adapters.
5. `io`: schema-safe artifact read/write helpers.

Rule: no method-specific heuristics in `src/common`.

## 6. Data Conventions

1. `artifacts/raw`: raw logs, vendor outputs, and trace snapshots.
2. `artifacts/processed`: normalized run/window tables.
3. `artifacts/figures`: generated plots.

All methods (online and external) must produce comparable processed outputs.

## 7. Recommended Expansion Order

1. Implement EVEREST `policy` loop.
2. Implement `oracle_static` and simple baselines.
3. Complete benchmark bridge launcher/parser/adapter for external submodules.
4. Build unified runners in `scripts/run` for controlled mode and external-only mode.
5. Freeze analysis schema and add integration tests.

## 8. Orchestration Boundary

For online control experiments:

1. Submit one top-level `sbatch` job from this repository.
2. Run algorithm control loop and benchmark process in the same allocation.
3. Use external repository adapters for benchmark execution details only.
4. Do not rely on nested independent job submission from bridge code.

Reference:

1. `docs/EXPERIMENT_ORCHESTRATION_MODEL.md`
