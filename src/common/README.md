# Common Modules

This directory contains algorithm-agnostic contracts and runtime building
blocks. Keep this layer free of policy-specific heuristics.

## Implemented Now

### `experiment`

Shared lifecycle contract, data structures, and validation:

1. `interfaces.py`: `AlgorithmInterface`.
2. `types.py`: `ExperimentContext`, `MetricWindow`, `Decision`,
   `FinalSummary`, and related dataclasses.
3. `validation.py`: decision/platform compatibility checks.

Lifecycle contract:

1. `initialize(context, config) -> AlgorithmState`
2. `on_window(metrics, state) -> Decision`
3. `finalize(state) -> FinalSummary`

### `telemetry`

Telemetry provider protocol and current dry-run/test implementation:

1. `interfaces.py`: `WindowTelemetryProvider`.
2. `env_provider.py`: `EnvTelemetryProvider`, which builds one `MetricWindow`
   from `METRIC_*` environment variables.

`EnvTelemetryProvider` is intentionally simple. It is useful for tests, local
smoke runs, and synthetic Slurm dry-runs, but it is not hardware telemetry.

## Placeholders

These directories currently contain only `.gitkeep` files:

1. `control`: future typed clock/power actuation adapters.
2. `power`: future power and energy collection helpers.
3. `io`: future schema-safe artifact read/write helpers.
4. `cli`: future shared command-line helpers.

Do not document these as implemented modules until they have code and tests.

## Design Rules

1. `common` code may depend on shared contracts, but must not depend on a
   specific policy implementation.
2. Method-specific equations and thresholds belong in `src/methods`.
3. Hardware providers should implement protocols from `common` and be injected
   into runners; they should not import EVeREST, Ali, or oracle-specific code.
4. Shared helpers should preserve explicit units and stable field names because
   analysis artifacts will depend on them.

## Next Additions

1. A hardware-backed `WindowTelemetryProvider` for DCGM/NVML or ROCm/AMD SMI.
2. A typed clock-control interface to replace direct shell command templates in
   the runner.
3. Shared artifact IO helpers once `analysis/schema` is frozen.
