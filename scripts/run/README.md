# Run Scripts

This directory contains top-level experiment entrypoints owned by this
repository.

## Files

1. `controlled_mode.sbatch`: primary Slurm orchestration template.
2. `control_loop.py`: primary long-lived policy runner.
3. `control_runtime.py`: shared helpers for manifests, decisions, state
   snapshots, telemetry windows, and clock-command application.
4. `control_hook.py`: legacy single-window hook for older flows.

New controlled-mode work should use `control_loop.py`, not `control_hook.py`.

## Controlled Mode

Purpose:

1. Submit one top-level Slurm job from this repository.
2. Launch one external benchmark adapter as a child process in the same
   allocation.
3. Run one long-lived control loop while the benchmark process is alive.
4. Preserve policy state in memory for the full run.
5. Call `finalize()` once and write `control/final_summary.json`.
6. For offline/static policies, apply any optional initial clock before the
   benchmark process starts.

This follows `docs/EXPERIMENT_ORCHESTRATION_MODEL.md`:

1. External repository owns benchmark/site execution adapters.
2. This repository owns algorithm-control orchestration.
3. The bridge layer must not submit nested independent benchmark jobs.

## Submit Example

```bash
sbatch --export=ALL,\
BENCH_ID=ior,\
BENCH_RUN_SCRIPT=benchmarks/ior/adapters/repacss/run.sh,\
POLICY_NAME=max_freq,\
PERFORMANCE_TARGET_TYPE=runtime_slowdown,\
PD_TARGET=0.10,\
CONTROL_WINDOW_SECONDS=10 \
scripts/run/controlled_mode.sbatch
```

Optional control loop override:

```bash
sbatch --export=ALL,\
BENCH_ID=hpl,\
BENCH_RUN_SCRIPT=benchmarks/hpl/adapters/repacss/run.sh,\
BENCH_ARGS="4 external/repacss-benchmarking/benchmarks/hpl/inputs/hpl/HPL-small.dat",\
CONTROL_LOOP_CMD='python3 scripts/run/my_control_loop.py' \
scripts/run/controlled_mode.sbatch
```

## Required Variables

For `controlled_mode.sbatch`:

1. `BENCH_ID`: benchmark identifier.
2. `BENCH_RUN_SCRIPT`: path relative to `external/repacss-benchmarking`.

For direct `control_loop.py` runs:

1. `RUN_DIR`: root directory for run artifacts.
2. `BENCH_ID`: workload/benchmark identifier.
3. Either `BENCH_PID` or `MAX_WINDOWS`: prevents an unbounded loop.

## Common Optional Variables

1. `POLICY_NAME`: default `max_freq`.
2. `PERFORMANCE_TARGET_TYPE`: `runtime_slowdown`,
   `relative_performance_loss`, or `none`; runner default `runtime_slowdown`.
3. `PD_TARGET`: raw target value interpreted by `PERFORMANCE_TARGET_TYPE`;
   default `0.0`. A runtime slowdown `delta` is converted to relative
   performance loss `delta / (1 + delta)` and minimum performance ratio
   `1 / (1 + delta)` before a constrained policy consumes it.
4. `CONTROL_WINDOW_SECONDS`: default `5.0`.
5. `MAX_CONSECUTIVE_FAILURES`: default `5`.
6. `POLICY_CONFIG_PATH` or `POLICY_CONFIG_JSON`: policy-specific config.
7. `CONTROL_DECISIONS_CSV`: override for decision CSV output.
8. `APPLY_CLOCK_CMD_TEMPLATE`: shell command template for applying a clock.
9. `APPLY_CLOCK_RESET_CMD`: cleanup command for restoring hardware clock state.

## Supported Policies

`control_loop.py` resolves policies through `src/methods/registry.py`:

1. `max_freq`
2. `min_freq`
3. `oracle_static`
4. `everest`
5. `ali_2022_reimpl`

`oracle_static` and `ali_2022_reimpl` require model/profile config via
`POLICY_CONFIG_PATH` or `POLICY_CONFIG_JSON`. `everest` can run with defaults
but should use an explicit config file for reportable experiments. See
`config/algorithms/README.md`.

## Current Telemetry Provider

The default runner currently uses `EnvTelemetryProvider`, which reads:

1. `METRIC_GPU_UTIL_PCT`
2. `METRIC_MEM_UTIL_PCT`
3. `METRIC_GRAPHICS_CLOCK_MHZ`
4. `METRIC_POWER_W`
5. `METRIC_ENERGY_DELTA_J`
6. `METRIC_PERFORMANCE_RATIO`

This is a dry-run and test contract. Real hardware telemetry from DCGM, NVML,
ROCm SMI, or AMD SMI is not implemented yet.

## Runner Artifacts

Default controlled-mode artifacts:

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

Notes:

1. `policy_state.json` is an observability snapshot, not the source of truth for
   a live long-lived run.
2. `run_manifest.json` records environment, policy config hash, repository
   commit, dirty status, external submodule status, and a typed
   `performance_target` object containing the raw value plus normalized runtime
   slowdown, relative performance loss, and minimum performance ratio.
3. `final_summary.json` is written even when the runner aborts after repeated
   per-window failures.

## Offline Initial Decisions

Fixed-clock and static/offline whole-workload policies implement the
`StaticPolicy` protocol (`initial_decision(context, state)`). `control_loop.py`
detects support with
`isinstance`, calls the method after `initialize()` and before telemetry
window 0, validates the returned `Decision`, applies it, and records it in
`decisions.csv` with `window=-1`. A `StaticPolicy`'s `on_window()` is
monitor-only, so the clock is applied through exactly one path; online
window-driven policies do not implement the protocol and drive the clock through
`on_window()`.

The runner phase is selected by the `CONTROL_PHASE` environment variable:

1. `all` (default): apply the pre-run decision (for static policies), then run
   the windowed loop in the same process.
2. `prerun`: apply only the pre-run decision and exit. Does not require
   `BENCH_PID`/`MAX_WINDOWS`. Used to set the clock before the benchmark starts.
3. `loop`: run only the windowed loop and skip the pre-run decision because an
   earlier `prerun` phase already applied it.

`controlled_mode.sbatch` runs `CONTROL_PHASE=prerun` before launching the
benchmark, then runs the long-lived loop with `CONTROL_PHASE=loop` after
`BENCH_PID` is known. This keeps whole-workload offline methods from measuring
an initial default-frequency interval without duplicating the `window=-1`
decision.

The legacy `control_hook.py` path also applies a `StaticPolicy`'s
`initial_decision()` when `WINDOW_INDEX=0`. New controlled-mode runs should
still prefer `control_loop.py`.

## Clock Command Templates

The control loop reads platform bounds and command templates from environment
variables:

```bash
export PLATFORM_MIN_CLOCK_MHZ=210
export PLATFORM_MAX_CLOCK_MHZ=1410
export PLATFORM_CLOCK_STEP_MHZ=15
```

Actuation flows through the `ClockController` seam in `src/common/control`; the
default `ShellTemplateController` backend applies these templates and is
unit-tested without hardware. When `APPLY_CLOCK_CMD_TEMPLATE` is unset,
`control_loop.py` runs in dry-run mode and only logs decisions. When it is set,
the runner formats the template with:

1. `{target_mhz}`: selected graphics/core clock in MHz.
2. `{action}`: control action, usually `set_clock`.
3. `{reason}`: policy reason code.

Set `APPLY_CLOCK_RESET_CMD` to restore hardware clock state during Slurm
cleanup.

For a NVIDIA/AMD comparison of supported-clock probing, set-clock mechanisms,
MHz-vs-level mapping, and expected root/admin requirements, see
`src/methods/README.md`.

### NVIDIA

Discover supported clocks:

```bash
nvidia-smi -i 0 -q -d SUPPORTED_CLOCKS
```

Use fixed graphics-clock locking:

```bash
export APPLY_CLOCK_CMD_TEMPLATE='sudo nvidia-smi -i 0 -lgc {target_mhz},{target_mhz}'
export APPLY_CLOCK_RESET_CMD='sudo nvidia-smi -i 0 -rgc'
```

### AMD

Discover supported clocks:

```bash
amd-smi static --gpu 0 --clock
```

Use fixed SCLK min/max limits:

```bash
export APPLY_CLOCK_CMD_TEMPLATE='sudo amd-smi set --gpu 0 --clk-limit sclk min {target_mhz} && sudo amd-smi set --gpu 0 --clk-limit sclk max {target_mhz}'
export APPLY_CLOCK_RESET_CMD='sudo amd-smi reset --gpu 0 --clocks'
```

Legacy ROCm-SMI systems may require `rocm-smi --setsclk <level>` instead of
frequency-valued `amd-smi` limits. Record the exact command and reset path in
the run artifact for reproducibility.

## Local Smoke Run

Use `MAX_WINDOWS` for a bounded dry-run without Slurm:

```bash
RUN_DIR=/tmp/gpu-dvfs-smoke \
BENCH_ID=smoke \
MAX_WINDOWS=2 \
POLICY_NAME=max_freq \
METRIC_GPU_UTIL_PCT=50 \
METRIC_MEM_UTIL_PCT=40 \
METRIC_GRAPHICS_CLOCK_MHZ=1410 \
PLATFORM_MIN_CLOCK_MHZ=210 \
PLATFORM_MAX_CLOCK_MHZ=1410 \
PLATFORM_CLOCK_STEP_MHZ=15 \
python3 scripts/run/control_loop.py
```

Expected outputs:

1. `/tmp/gpu-dvfs-smoke/control/final_summary.json`
2. `/tmp/gpu-dvfs-smoke/control/decisions.csv`
3. `/tmp/gpu-dvfs-smoke/control/run_manifest.json`

## Safety Notes

1. Prefer dry-run mode until platform clock bounds are verified.
2. Always set `APPLY_CLOCK_RESET_CMD` for real clock-control runs.
3. Do not run nested benchmark batch submissions from `controlled_mode.sbatch`.
4. Keep per-policy configs in files when possible so manifests can record a
   stable config path and hash.
