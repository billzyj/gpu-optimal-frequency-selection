# Common Modules

This directory contains algorithm-agnostic contracts and runtime building
blocks. Keep this layer free of policy-specific heuristics.

## Implemented Now

### `experiment`

Shared lifecycle contract, data structures, and validation:

1. `interfaces.py`: `AlgorithmInterface` and the `StaticPolicy` capability
   protocol.
2. `types.py`: `ExperimentContext`, `MetricWindow`, `Decision`,
   `FinalSummary`, and related dataclasses.
3. `validation.py`: decision/platform compatibility checks.

Lifecycle contract:

1. `initialize(context, config) -> AlgorithmState`
2. `on_window(metrics, state) -> Decision`
3. `finalize(state) -> FinalSummary`

Fixed-clock and offline/static policies additionally satisfy the `StaticPolicy`
protocol (`interfaces.py`) by exposing
`initial_decision(context, state) -> Decision | None`. The shared runner detects
this structurally with `isinstance` and applies the returned whole-run clock
once before telemetry window 0. For a `StaticPolicy`, `on_window` is
monitor-only (it returns `HOLD_CLOCK`/`NO_OP` and never changes the clock).
Online window-driven policies do not implement `StaticPolicy` and drive the
clock through `on_window`.

### `telemetry`

Telemetry provider protocol and current dry-run/test implementation:

1. `interfaces.py`: `WindowTelemetryProvider`.
2. `env_provider.py`: `EnvTelemetryProvider`, which builds one `MetricWindow`
   from `METRIC_*` environment variables.

`EnvTelemetryProvider` is intentionally simple. It is useful for tests, local
smoke runs, and synthetic Slurm dry-runs, but it is not hardware telemetry.

### `control`

Typed clock-actuation seam:

1. `interfaces.py`: `ClockController` protocol (`apply(decision)` / `reset()`).
2. `shell_controller.py`: `ShellTemplateController`, the transitional backend
   that formats `APPLY_CLOCK_CMD_TEMPLATE` / runs `APPLY_CLOCK_RESET_CMD` (or
   logs a dry-run when no template is set). Its subprocess runner and logger are
   injectable, so actuation is unit-testable without hardware.

The runner applies decisions through this protocol instead of calling a shell
command inline. Future NVML / AMD-SMI backends implement the same protocol.

## Placeholders

These directories currently contain only `.gitkeep` files:

1. `power`: future power and energy collection helpers.
2. `io`: future schema-safe artifact read/write helpers.
3. `cli`: future shared command-line helpers.

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
2. A typed `ClockController` backend (NVML / AMD-SMI) behind the existing
   protocol, replacing the shell-template path for production runs.
3. Shared artifact IO helpers once `analysis/schema` is frozen.
