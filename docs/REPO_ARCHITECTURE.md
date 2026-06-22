# Repository Architecture

## 1. Objectives

This repository is a paper-specific GPU DVFS research codebase. It supports
three workflows in one structure:

1. Reproduce reference GPU DVFS methods and baselines.
2. Compare all methods under a shared runtime protocol and artifact schema.
3. Develop and evaluate a proposed method without contaminating reproduced
   baselines.

## 2. Current Architecture Assessment

The current architecture is sound for a research prototype and is ready for the
next hardware-integration step. The strongest choices are:

1. A single `AlgorithmInterface` shared by baselines, local reproductions, and
   proposed methods.
2. A stable policy registry used by the runner instead of ad-hoc imports in
   scripts.
3. A long-lived controlled-mode runner that preserves in-memory policy state
   and calls `finalize()` once per run.
4. Co-located reproduction plans and source ledgers for paper-faithful methods.
5. A clear boundary between local algorithm orchestration and the external
   benchmark repository.

The main architecture risks are not structural; they are unfinished integration
surfaces:

1. `src/common/telemetry` only has an environment-variable provider today, and
   `src/common/control` only has the shell-template actuation backend.
2. `src/common/power`, `src/common/io`, and `src/common/cli` are placeholders.
3. External benchmark artifact import/normalization is specified but not
   implemented.
4. `analysis/schema` is not yet frozen, so downstream result consumers should
   treat artifact layouts as provisional.

## 3. Layering

1. Method layer: `src/methods`
2. Shared runtime/contracts: `src/common`
3. Experiment assets: `config`, `scripts`, `analysis`, `artifacts`
4. External benchmark sources: `external` (git submodules, currently
   `repacss-benchmarking`)

Layering rule: policy-specific heuristics live in `src/methods`, not in
`src/common`. Site/vendor/benchmark execution details live in the external
benchmark repository, not under `src/methods`.

## 4. Method Taxonomy

```text
src/methods/
|-- registry.py
|-- proposed_methods/
|   |-- templates/
|   `-- my_method/
`-- comparison_methods/
    |-- system_baselines/
    |   |-- fixed_clock.py
    |   |-- max_freq/
    |   |-- min_freq/
    |   `-- util_policy/        # placeholder, not registered yet
    |-- local_reproductions/
    |   |-- everest_reimpl/
    |   |   |-- docs/
    |   |   |-- paper/          # ignored local source cache
    |   |   |-- phase_identification/
    |   |   |-- phase_characterization/
    |   |   |-- frequency_scaling/
    |   |   `-- policy.py
    |   |-- ali_2022_reimpl/
    |   |   |-- docs/
    |   |   |-- paper/          # ignored local source cache
    |   |   `-- policy.py
    |   `-- oracle_static/
    |       |-- docs/
    |       |-- paper/          # ignored local source cache
    |       `-- policy.py
    `-- external_integrations/
```

### 4.1 `proposed_methods`

Your new method for paper contributions. Proposed methods may improve on
EVeREST, Ali, or the baselines, but improvements should not be backported into
comparison-method baselines unless the baseline scope is explicitly changed.

### 4.2 `comparison_methods/system_baselines`

Simple controls with low implementation cost and high interpretability.
Currently registered policies:

1. `max_freq`
2. `min_freq`

`util_policy` is a placeholder and should not be reported as an implemented
baseline until it has a policy implementation, tests, and registry entry.

### 4.3 `comparison_methods/local_reproductions`

Comparison algorithms implemented and maintained locally in this repository.
Use this category when no directly usable implementation exists, or when an
available implementation cannot be used unchanged behind a thin adapter. Paper
sources and method-specific reproduction notes live inside the corresponding
method directory, not in a top-level reference cache.

Current registered policies:

1. `everest`
2. `ali_2022_reimpl`
3. `oracle_static`

### 4.4 `comparison_methods/external_integrations`

Directly usable existing implementations should be pinned under
`external/<repo>` and exposed through local adapters in this directory. The
adapter may launch, import, or parse the external implementation, but the runner
and other methods should not import third-party code directly.

### 4.5 `external/*` Submodules

External repositories own benchmark runtime, site/vendor adapter logic, or
third-party method source. This repository consumes them through top-level
orchestration, future import helpers, or local external-method adapters instead
of copying execution internals into core policy code.

## 5. Contracts

### 5.1 Online Methods (`AlgorithmInterface`)

Defined in `src/common/experiment/interfaces.py`:

1. `initialize(context, config) -> AlgorithmState`
2. `on_window(metrics, state) -> Decision`
3. `finalize(state) -> FinalSummary`

Applies to:

1. Fixed-clock baselines.
2. Local reproductions that run online or apply a whole-run decision through the
   runner.
3. Proposed methods.

### 5.2 Static Policies (`StaticPolicy`)

Also defined in `src/common/experiment/interfaces.py`. A static whole-run policy
implements `AlgorithmInterface` and additionally:

1. `initial_decision(context, state) -> Decision | None`

The runner detects support structurally with `isinstance(policy, StaticPolicy)`
and applies the returned decision exactly once before window 0. A static
policy's `on_window` is monitor-only: it returns `HOLD_CLOCK`/`NO_OP` and must
not change the clock. This gives static methods a single clock-apply path
(the pre-run decision) and avoids a duplicate window-driven apply. Current
static policies: `max_freq`, `min_freq`, `oracle_static`, `ali_2022_reimpl`.
Online window-driven policies such as `everest` do not implement this protocol.

### 5.3 Runtime Registry

`src/methods/registry.py` is the only default runner registry. Add a policy
there only after the policy:

1. Implements the `AlgorithmInterface` lifecycle.
2. Emits decisions accepted by `validate_decision()`.
3. Has at least one unit test for initialization and one decision path.
4. Has a README or reproduction note explaining config inputs and scope.

Current supported `POLICY_NAME` values:

1. `max_freq`
2. `min_freq`
3. `oracle_static`
4. `everest`
5. `ali_2022_reimpl`

## 6. Shared Modules (`src/common`)

1. `experiment`: implemented contracts, types, and decision validation.
2. `telemetry`: implemented `WindowTelemetryProvider` protocol and
   `EnvTelemetryProvider`; hardware providers are pending.
3. `control`: implemented `ClockController` protocol and `ShellTemplateController`
   shell-template backend; typed NVML/AMD-SMI backends are pending.
4. `power`: placeholder for future power/energy collection helpers.
5. `io`: placeholder for future schema-safe artifact read/write helpers.
6. `cli`: placeholder for future shared command-line helpers.

Rule: no method-specific heuristics in `src/common`.

## 7. Runtime Flow

Controlled mode is the primary runtime model:

1. `scripts/run/controlled_mode.sbatch` submits one top-level Slurm job from
   this repository.
2. The external benchmark adapter runs as a child process in the same
   allocation.
3. `scripts/run/control_loop.py` runs once, watches `BENCH_PID`, keeps policy
   state in memory, and loops until the benchmark exits or a stop condition is
   reached.
4. `scripts/run/control_runtime.py` owns shared helpers for environment parsing,
   manifests, decision logs, state snapshots, and clock-command application.
5. `scripts/run/control_hook.py` remains as a legacy single-window hook; it
   applies `StaticPolicy.initial_decision()` at `WINDOW_INDEX=0` for backward
   compatibility, but new flows should use `control_loop.py`.

The primary controlled-mode artifact directory is:

```text
<RUN_DIR>/control/
|-- run_manifest.json
|-- policy_state.json
|-- decisions.csv
|-- last_decision.json
`-- final_summary.json
```

## 8. Test Layout

Tests mirror the owner directory, not only `src`:

```text
tests/
|-- common/
|   |-- experiment/        # src/common/experiment
|   |-- telemetry/         # src/common/telemetry
|   `-- control/           # src/common/control
|-- methods/
|   |-- proposed_methods/  # src/methods/proposed_methods
|   `-- comparison_methods/
|       |-- system_baselines/
|       |-- local_reproductions/
|       `-- external_integrations/
`-- scripts/
    `-- run/               # scripts/run
```

`tests/common/*` covers shared runtime contracts and telemetry providers.
`tests/scripts/run/*` covers executable orchestration code. Method tests stay
under `tests/methods/...` and should match the method category used under
`src/methods/...`.

## 9. Data Conventions

1. `artifacts/raw`: raw logs, external benchmark outputs, Slurm logs, and trace
   snapshots.
2. `artifacts/processed`: normalized run/window tables after import and
   validation.
3. `artifacts/figures`: generated plots.

All policies and imported benchmark runs should eventually produce comparable
processed outputs. Until `analysis/schema` is frozen, treat processed schema as
provisional and record schema assumptions in each analysis script or notebook.

## 10. Recommended Expansion Order

1. Add a hardware telemetry provider behind `WindowTelemetryProvider`.
2. Add a hardware `ClockController` backend (NVML / AMD-SMI) behind the existing
   protocol; the shell-template backend already covers the transitional path.
3. Validate `POLICY_NAME=everest` with one real controlled benchmark.
4. Add import/validation helpers for `external/repacss-benchmarking` artifacts.
5. Freeze analysis schema and add integration tests for controlled and
   import-only runs.
6. Add the proposed method only after baseline artifact contracts are stable.

## 11. Orchestration Boundary

For online control experiments:

1. Submit one top-level `sbatch` job from this repository.
2. Run algorithm control loop and benchmark process in the same allocation.
3. Use external repository adapters for benchmark execution details only.
4. Do not rely on nested independent job submission from local orchestration
   code.

References:

1. `docs/EXPERIMENT_ORCHESTRATION_MODEL.md`
2. `docs/EXTERNAL_BENCHMARK_IMPORT_RULES.md`
3. `src/methods/comparison_methods/README.md`
4. `scripts/run/README.md`
