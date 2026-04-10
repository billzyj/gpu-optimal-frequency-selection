# Experiment Orchestration Model

## 1. Problem Statement

This project now depends on an external benchmarking repository:

1. `external/repacss-benchmarking`

That repository already defines benchmark adapters for cross-vendor and cross-data-center execution.
This repository must avoid duplicating those execution responsibilities while still enabling real-time DVFS control loops.

## 2. Design Decision

Use a **two-layer adapter model** with clear ownership:

1. External execution adapters (in `external/repacss-benchmarking`)
2. Local orchestration bridge (in this repository)

The two layers are complementary, not duplicates.

## 3. Responsibility Split

### 3.1 External execution adapters (external repository)

Own benchmark and site execution details:

1. Runtime environment resolution (module/spack/source/container)
2. Scheduler/site specifics and launcher details
3. Benchmark-native run and parse scripts
4. Emitting benchmark run artifacts (`raw`, `normalized/*`)

### 3.2 Local orchestration bridge (this repository)

Own algorithm control and experiment comparison logic:

1. Single top-level experiment entrypoint
2. Real-time telemetry windowing and DVFS decisions
3. Frequency control actuation
4. Importing and validating external benchmark artifacts
5. Producing unified comparison outputs

## 4. Execution Ownership Rule

For real-time control experiments, this repository owns the job lifecycle:

1. Submit one top-level `sbatch` job from this repository.
2. Run the algorithm loop and external benchmark process in the same allocation.
3. Do not submit an independent nested benchmark job from the bridge layer.

Rationale:

1. The algorithm loop must observe and control the same live process.
2. Nested job submission breaks deterministic timing and control coupling.

## 5. Runtime Modes

### 5.1 Controlled mode (primary)

Use for `AlgorithmInterface` policies that require window-level decisions.

Flow:

1. Start benchmark process from external adapter scripts as a child process.
2. Collect metrics per window.
3. Call `on_window(...)` and apply decision.
4. Finalize and import normalized benchmark artifacts.

### 5.2 External-only mode (secondary)

Use for job-level comparison baselines via `ExternalMethodInterface`.

Flow:

1. Execute external benchmark run as a job-level operation.
2. Parse/validate output artifacts.
3. Include only valid runs in aggregate statistics.

## 6. Interface Mapping in This Repository

1. `AlgorithmInterface`: online policies with real-time control loop.
2. `ExternalMethodInterface`: job-level external baselines and imports.
3. Bridge implementations stay under `src/methods/third_party/*` and must not duplicate benchmark/site logic already owned by the external repository.

## 7. Artifact Contract Alignment

The bridge must normalize imports to this repository schema and enforce:

1. Required fields in `docs/EXTERNAL_BENCHMARK_IMPORT_RULES.md`
2. Absolute artifact paths
3. Explicit units and timestamps
4. Failure visibility (failed runs excluded from aggregate metrics by default)

## 8. Implementation Priorities

1. Add a unified run entrypoint in `scripts/run` for controlled mode.
2. Implement bridge launcher/parser wiring for external benchmark artifacts.
3. Add schema validation for imported summary/power fields.
4. Add integration tests for one controlled benchmark and one external-only baseline.

Current template:

1. `scripts/run/controlled_mode.sbatch`
2. `scripts/run/control_hook.py` (default periodic policy hook used by controlled mode)
