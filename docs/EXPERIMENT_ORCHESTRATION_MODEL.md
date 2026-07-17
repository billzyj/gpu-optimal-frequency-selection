# Experiment Orchestration Model

## 1. Problem Statement

This project depends on an external benchmarking repository:

1. `external/repacss-benchmarking`

That repository defines benchmark adapters for cross-vendor and
cross-data-center execution. This repository must avoid duplicating those
execution responsibilities while still enabling real-time GPU DVFS control.

## 2. Design Decision

Use a two-layer adapter model with clear ownership:

1. External execution adapters in `external/repacss-benchmarking`.
2. Local orchestration, control-loop, and import helpers in this repository.

The two layers are complementary. External adapters own benchmark execution;
local code owns policy decisions and comparison artifacts.

Exception: a reviewed upstream method may be a self-contained controller that
cannot expose recommendation-only decisions without rewriting its algorithm.
Such a method uses the planned external-controller mode in Section 5.2; the
ownership exception must be explicit in the run manifest.

## 3. Responsibility Split

### 3.1 External Execution Adapters

The external repository owns:

1. Runtime environment resolution through modules, Spack, source builds, or
   containers.
2. Scheduler/site specifics and launcher details for each benchmark.
3. Benchmark-native run and parse scripts.
4. Benchmark run artifacts such as `raw` and `normalized/*`.

### 3.2 Local Orchestration and Import Helpers

This repository owns:

1. A single top-level experiment entrypoint.
2. Real-time telemetry windowing and DVFS decisions.
3. Frequency-control actuation in normal controlled mode, or exclusive
   lifecycle/observability ownership around an approved upstream controller.
4. Importing and validating external benchmark artifacts.
5. Unified comparison outputs for methods and baselines.
6. Slurm-integrated profiling/control for real-time frequency decisions.

Current status: the controlled-mode template, local policy loop, and local
`ClockController` actuation path exist. External-controller
lifecycle/observability, artifact import, and unified comparison outputs are
specified but not implemented yet.

## 4. Execution Ownership Rule

For real-time control experiments, this repository owns the job lifecycle:

1. Submit one top-level `sbatch` job from this repository.
2. Run the algorithm loop and external benchmark process in the same
   allocation.
3. Do not submit an independent nested benchmark job from the bridge layer.

Rationale:

1. The algorithm loop must observe and control the same live process.
2. Nested job submission breaks deterministic timing and control coupling.
3. A single allocation makes run provenance and failure handling easier to
   preserve.

## 5. Runtime Modes

### 5.1 Controlled Mode (Primary)

Use for `AlgorithmInterface` policies that require window-level decisions or a
whole-run frequency decision applied through the shared runner.

Implemented flow:

1. Submit `scripts/run/controlled_mode.sbatch`.
2. Start the external benchmark adapter script as a child process and capture
   its PID.
3. Launch `scripts/run/control_loop.py` once in the foreground, passing
   `BENCH_PID` through the environment.
4. The runner initializes the selected policy once.
5. The runner loops internally per window:
   - collect one `MetricWindow`;
   - call `on_window(metrics, state)`;
   - validate the `Decision`;
   - apply or dry-run the clock decision;
   - write observability artifacts.
6. Single-window failures are tolerated up to `MAX_CONSECUTIVE_FAILURES`.
7. When the benchmark process exits, a `STOP` file appears, or `MAX_WINDOWS` is
   reached, the runner calls `finalize()` and writes
   `control/final_summary.json`.
8. The orchestrator waits for the benchmark process and returns the first
   non-zero exit code from the control loop or benchmark.

### 5.2 External-Controller Mode (Planned)

Use only for a pinned upstream method, such as GEEPAFS, that combines telemetry,
policy logic, and privileged actuation in one process.

Required behavior:

1. Launch the upstream controller as a child/sidecar in the benchmark
   allocation and record its exact commit, license, arguments, and local patch
   or configuration hash.
2. Give the upstream process exclusive clock-actuation ownership; do not run the
   local `ClockController` concurrently.
3. Record the controller PID and exit code. If the controller exits before the
   benchmark, terminate the benchmark and fail the run; when the benchmark
   exits, terminate and reap the controller.
4. Parse requested decisions when the upstream log/API exposes them; otherwise
   record `requested_unknown`. Independently sample observed clocks and
   normalize both streams into comparison artifacts.
5. After the controller is stopped, the local orchestrator owns the final reset
   and verifies the restored clock state. This preserves one active actuation
   owner at a time.
6. Test startup failure, benchmark failure, signal handling, early controller
   exit, benchmark termination, and final clock reset.
7. Mark the run mode and actuation owner in the run manifest so it cannot be
   confused with an in-process `AlgorithmInterface` result.

This mode is not implemented. Do not register or execute an upstream controller
through the current controlled mode until this ownership contract is enforced.

### 5.3 Benchmark-Only Selection Mode (Secondary)

Use to select workloads, inputs, and final experiment candidates without
running a control policy.

Planned flow:

1. Execute or import benchmark runs from `external/repacss-benchmarking`.
2. Parse and validate output artifacts.
3. Include only valid runs when choosing workloads for controlled experiments.

This mode is not yet implemented in local import helpers.

## 6. Interface Mapping in This Repository

1. `AlgorithmInterface`: window-level lifecycle for all policies.
2. `StaticPolicy`: capability protocol for fixed-clock and whole-workload
   methods; the runner applies their `initial_decision()` once before window 0
   and keeps their `on_window()` monitor-only.
3. `WindowTelemetryProvider`: source of per-window `MetricWindow` objects.
4. `EnvTelemetryProvider`: current dry-run/test provider backed by `METRIC_*`
   environment variables.
5. `ClockController`: typed actuation seam. The default `ShellTemplateController`
   backend applies `APPLY_CLOCK_CMD_TEMPLATE` / `APPLY_CLOCK_RESET_CMD`, or logs
   a dry-run when no template is set.
6. External benchmarking remains a repository boundary, not a method category
   under `src/methods`.

## 7. Environment Contract

Required for controlled mode:

1. `BENCH_ID`
2. `BENCH_RUN_SCRIPT`

Required by `control_loop.py`:

1. `RUN_DIR`
2. `BENCH_ID`
3. Either `BENCH_PID` or `MAX_WINDOWS`

Common policy/runtime variables:

1. `POLICY_NAME` (default: `max_freq`)
2. `PD_TARGET` (default: `0.0`)
3. `CONTROL_WINDOW_SECONDS` (default: `5.0`)
4. `METRIC_SAMPLING_INTERVAL_MS` (default: `1000`)
5. `POLICY_CONFIG_PATH` or `POLICY_CONFIG_JSON`
6. `MAX_CONSECUTIVE_FAILURES` (default: `5`)
7. `CONTROL_PHASE` (default: `all`; `all` | `prerun` | `loop`). Selects whether
   the runner applies the static pre-run decision, runs the windowed loop, or
   both. `controlled_mode.sbatch` uses `prerun` before launching the benchmark
   and `loop` afterward.

Platform variables:

1. `PLATFORM_VENDOR`
2. `PLATFORM_GPU_MODEL`
3. `PLATFORM_GPU_COUNT`
4. `PLATFORM_MIN_CLOCK_MHZ`
5. `PLATFORM_MAX_CLOCK_MHZ`
6. `PLATFORM_CLOCK_STEP_MHZ`
7. `PLATFORM_NODE_NAME`
8. `PLATFORM_DRIVER_VERSION`
9. `PLATFORM_RUNTIME_VERSION`

Current telemetry variables read by `EnvTelemetryProvider`:

1. `METRIC_GPU_UTIL_PCT`
2. `METRIC_MEM_UTIL_PCT`
3. `METRIC_GRAPHICS_CLOCK_MHZ`
4. `METRIC_POWER_W`
5. `METRIC_ENERGY_DELTA_J`
6. `METRIC_PERFORMANCE_RATIO`

## 8. Artifact Contract Alignment

Controlled-mode runner artifacts:

```text
<RUN_DIR>/
|-- control_loop.log
`-- control/
    |-- run_manifest.json
    |-- policy_state.json
    |-- decisions.csv
    |-- last_decision.json
    `-- final_summary.json
```

The bridge must eventually normalize external benchmark artifacts to this
repository's schema and enforce:

1. Required fields in `docs/EXTERNAL_BENCHMARK_IMPORT_RULES.md`.
2. Absolute artifact paths.
3. Explicit units and timestamps.
4. Failure visibility.
5. Exclusion of failed runs from aggregate metrics by default.

## 9. Failure Handling

1. Per-window policy, telemetry, validation, or actuation exceptions are logged
   and counted.
2. The runner aborts after `MAX_CONSECUTIVE_FAILURES` consecutive window
   failures.
3. `finalize()` is still called after an abort so `final_summary.json` is
   preserved.
4. If `APPLY_CLOCK_RESET_CMD` is set, `controlled_mode.sbatch` attempts to run
   it during cleanup.
5. The run manifest records repository commit, dirty status, selected
   environment variables, policy config hash, and external submodule status.

## 10. Current Template

1. `scripts/run/controlled_mode.sbatch`: primary Slurm orchestrator.
2. `scripts/run/control_loop.py`: primary long-lived runner.
3. `scripts/run/control_runtime.py`: shared runtime helper module.
4. `scripts/run/control_hook.py`: legacy single-window hook; keep for backward
   compatibility, including `StaticPolicy` initial decisions at `WINDOW_INDEX=0`,
   but do not build new flows around it.

## 11. Implementation Priorities

1. Add supported clock grids and enforce the existing method-capability
   contracts during startup. Explicit performance-target semantics and
   manifest conversions are implemented.
2. Implement and test the external-controller ownership contract.
3. Add hardware-backed `WindowTelemetryProvider` implementations.
4. Add typed `ClockController` backends (NVML / AMD-SMI) behind the existing
   protocol, keeping `ShellTemplateController` as the fallback path.
5. Add import/validation helpers for external benchmark artifacts.
6. Freeze the processed-output schema in `analysis/schema`.
7. Add one end-to-end controlled benchmark validation run before attempting the
   preferred GEEPAFS sidecar port.

The method-specific ordering and artifact decisions are in
`docs/COMPARISON_METHOD_INTEGRATION_PLAN.md`.
