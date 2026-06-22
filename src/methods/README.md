# Methods

This directory is the canonical home for GPU DVFS policies.

## Layout

1. `registry.py`: maps stable `POLICY_NAME` strings to policy instances.
2. `proposed_methods`: the user's own method under development.
3. `comparison_methods`: all methods used for comparison against the proposed
   method.

## Comparison Method Categories

1. `comparison_methods/system_baselines`: simple controls with clear
   interpretation.
2. `comparison_methods/local_reproductions`: comparison algorithms implemented
   locally because no directly usable implementation exists, or because
   available code cannot be used unchanged through a thin adapter.
3. `comparison_methods/external_integrations`: thin adapters for directly
   usable external implementations pinned under `external/`.

External benchmarking remains under `external/repacss-benchmarking` and is
invoked through local run/import scripts. It is not itself a policy category.

## Execution Model

Policies used by the default runner implement `AlgorithmInterface`:

1. `initialize(context, config)`
2. `on_window(metrics, state) -> Decision`
3. `finalize(state) -> FinalSummary`

Fixed-clock baselines and offline/static whole-workload policies additionally
satisfy the `StaticPolicy` protocol by implementing
`initial_decision(context, state) -> Decision | None`. `control_loop.py` applies
that decision once before telemetry window 0, and `controlled_mode.sbatch`
applies it before launching the benchmark process. A `StaticPolicy`'s
`on_window` is monitor-only — it holds and never re-applies the clock.

## Hardware Frequency Probing And Actuation

Method code does not call NVIDIA or AMD tools directly. Policies compute
`Decision` objects with `target_graphics_clock_mhz`; `scripts/run/control_loop.py`
and the `ClockController` backend translate those decisions into hardware
commands. Keep vendor-specific commands in runner/config documentation rather
than inside method modules.

The tables below separate probing/telemetry from actuation. This distinction is
important for LIKWID: `NVMON`/`NVMarker` plus CUPTI belong to the
probing/profiling side. LIKWID's NVML `sysFeatures` clock setters, when built
and exposed by the local installation, belong to the actuation side.

### Frequency Probing / Telemetry

| Vendor | Path | What it can probe | Root/admin usually needed? | Notes |
|---|---|---|---|---|
| NVIDIA | `nvidia-smi` | Supported clocks via `nvidia-smi -i 0 -q -d SUPPORTED_CLOCKS`; current clocks via `nvidia-smi --query-gpu=clocks.gr,clocks.sm,clocks.mem,clocks.applications.graphics,clocks.applications.memory --format=csv` | Usually no for read/probe. | Best shell-level live probe for reportable clock grids. Always save the raw supported-clock output with experiment metadata. |
| NVIDIA | NVML / `pynvml` / `nvml-wrapper` | Current clocks, supported memory clocks, supported graphics clocks for a memory clock, power, utilization, temperature, memory, and structured error codes. | Usually no for telemetry. | Preferred future typed backend because it avoids shell parsing and can distinguish `NOT_SUPPORTED` from permission errors. |
| NVIDIA | DCGM / `dcgmi` | `dcgmi dmon` streams power, utilization, SM clock, memory clock, application clocks, pstate, and profiling fields; `dcgmi config --get -v` reports target/current configuration. | Telemetry may be non-root when hostengine is configured; some fields depend on site policy. | Useful on cluster-managed systems. DCGM sits above NVML and CUDA, so it is a management/telemetry path rather than a method implementation dependency. |
| NVIDIA | LIKWID NVMON / CUPTI | GPU topology, CUDA-kernel performance groups, NVMarker regions, and NVML-backed metrics when LIKWID is built with `NVIDIA_INTERFACE=true` and CUDA/CUPTI paths. | Usually no for ordinary metric reads if device access and libraries are available; site policy may vary. | This is a probing/profiling category, not the clock-setting category. It is useful for richer observability, not for the default clock-control loop. |
| AMD | `amd-smi` | GPU clocks and clock levels/ranges via commands such as `amd-smi static --gpu 0 --clock`. | Usually no for read/probe. | Current AMD CLI path. Output may be level/range oriented rather than a simple MHz list. |
| AMD | ROCm SMI / `rocm-smi` / ROCm SMI library | Clock levels via `rocm-smi --showclocks` / `--showclkfrq`; power, temperature, utilization, and other device telemetry. | Usually no for read/probe. | Legacy/fallback path when `amd-smi` is unavailable. Keep exact version and command output because formats vary. |
| AMD | LIKWID ROCMON | ROCm/HIP performance monitoring and topology when LIKWID is built with `ROCM_INTERFACE=true`. | Usually no for ordinary metric reads if ROCm permissions are configured. | Probing/profiling only for this repo's purposes; use AMD SMI/ROCm SMI for clock-control wrappers. |

### Frequency Actuation / Reset

| Vendor | Path | Set one target clock | Reset / restore | Root/admin usually needed? | Notes |
|---|---|---|---|---|---|
| NVIDIA | `nvidia-smi` locked graphics clocks | Preferred shell path: `nvidia-smi -i 0 -lgc {target_mhz},{target_mhz}` via `APPLY_CLOCK_CMD_TEMPLATE`. | `nvidia-smi -i 0 -rgc` | Yes on most clusters, commonly through `sudo` or an admin wrapper. | Best match for this repo's `target_graphics_clock_mhz` decisions. Probe supported clocks first and verify the actual clock after setting. |
| NVIDIA | `nvidia-smi` application clocks | Compatibility fallback: `nvidia-smi -i 0 -ac {memory_mhz},{target_mhz}`. | `nvidia-smi -i 0 -rac` | Yes on most clusters. | Existing reference scripts use this path, but NVIDIA now deprecates application clocks. Prefer locked graphics clocks when supported. |
| NVIDIA | NVML locked-clock APIs | `nvmlDeviceSetGpuLockedClocks(min,max)` for graphics; `nvmlDeviceSetMemoryLockedClocks(min,max)` for memory on supported GPUs. | NVML reset locked-clock APIs. | Yes / driver-policy restricted. | Preferred future typed actuation backend because errors are structured. Not implemented as the default runner backend yet. |
| NVIDIA | NVML application-clock APIs | Legacy fallback: `nvmlDeviceSetApplicationsClocks(mem,graphics)`. | `nvmlDeviceResetApplicationsClocks()`. | Yes / driver-policy restricted. | Keep only for compatibility with older systems or reference reproduction. |
| NVIDIA | DCGM / `dcgmi config` | Reference scripts use `dcgmi config --set -a {memory_mhz},{target_mhz}` for target application clocks. | Site-specific: clear/reset target config or re-apply default memory/core clocks and verify with `dcgmi config --get -v`. | Configuration management generally needs privileged DCGM access. | Useful when site policy expects DCGM-managed target/current state. Do not make it the only backend because DCGM is not universal. |
| NVIDIA | LIKWID NVML `sysFeatures` setters | If exposed by the installed LIKWID build, NVML-backed sysfeatures can set application clocks, GPU locked clocks, memory locked clocks, and power limits. | Matching LIKWID/NVML reset or restore logic, depending on exposed feature. | Yes for clock/power writes. | This is actuation through LIKWID's NVML sysfeatures layer, not through NVMON/CUPTI. Treat it as an optional advanced backend, not a current dependency. |
| AMD | `amd-smi` | Version-dependent. Frequency-limit style: `amd-smi set --gpu 0 --clk-limit sclk min {target_mhz}` plus matching `max`; some releases expose short forms such as `amd-smi set -L sclk min VALUE` or level masks such as `amd-smi set -c sclk LEVEL...`. | `amd-smi reset --gpu 0 --clocks` when supported. | Yes, generally root. | Add a MHz-to-SCLK-level adapter if the target system only accepts levels or masks. |
| AMD | ROCm SMI / `rocm-smi` | `rocm-smi --setsclk LEVEL [LEVEL ...]` or related level-mask commands. | Reset support is version/platform dependent; record the exact command used. | Yes, generally root. | Fallback when `amd-smi` is unavailable. Because it is usually level-index based, never silently treat MHz and level IDs as the same unit. |

Runner template examples live in `scripts/run/README.md`. For reportable runs,
log the chosen vendor path, supported-clock probe output, selected clock or
level mapping, whether `sudo`/root was required, and the reset command.

### NVIDIA Reference Repo Findings

The local reference workspace under `REPACSS/refactor/references` contains
several NVIDIA technology patterns that are directly relevant to this repo's
hardware backend design. Treat these as implementation evidence and design
input, not as new runtime dependencies.

| Reference input | NVIDIA technology used | What this repo should borrow |
|---|---|---|
| `Power_Profiler/idle_gpu.py` | `nvidia-smi -L` for availability plus `pynvml`/NVML for high-frequency GPU power, utilization, temperature, memory, SM clock, and memory-clock sampling. | Use NVML-style typed telemetry for fast sampling and clock verification. Frequency reads do not imply permission to set clocks. |
| `TokenPowerBench/tokenpowerbench/energy/gpu_monitor.py` | `pynvml` power sampling at 100 ms and an explicit "no root required" GPU-only monitor mode. | Keep telemetry and actuation permission models separate: GPU power reads can be user-level, while clock writes usually need admin/root. |
| `llm-power-profiler/src/llm_power_profiler/nvml.py` | Minimal NVML monitor for power, utilization, memory, and temperature; no clock control. | Good example of a low-friction telemetry adapter with clear `NVMLUnavailable` failures. |
| `curvu/src/nvidia_gpu.rs` | Rust `nvml-wrapper`: `supported_memory_clocks()`, `supported_graphics_clocks(max_mem_clock)`, power samples, `clock_info()`, `set_gpu_locked_clocks()`, fallback `set_applications_clocks()`, and restoration of original clocks. | Strongest reference for a future typed NVIDIA backend: probe supported clocks, lock graphics clocks, measure actual clocks after setting, and always restore original state. |
| `ai-inference-energy/sample-collection-scripts/control_smi.sh` | `nvidia-smi -pm 1`, `-ac MEM,GRAPHICS`, query of application clocks, and `-rac` reset. | Keep `-ac`/`-rac` as a compatibility fallback for older scripts or clusters, but prefer `-lgc`/`-rgc` when supported because NVIDIA now deprecates application clocks. |
| `ai-inference-energy/sample-collection-scripts/control.sh` and `documentation/profiling_commands.md` | DCGM/DCGMI: `dcgmi config --set -a MEM,CORE`, `dcgmi dmon`, and field alignment with `nvidia-smi` for power, utilization, SM clock, memory clock, application clocks, and pstate. | Add an optional DCGM telemetry/control path for cluster-managed NVIDIA systems; document field IDs and remember that DCGM configuration is privileged. |
| `ai-inference-energy/hardware/gpu_info.py` and `hardware/INFO_*.txt` | A100/V100/H100 frequency catalogs derived from `nvidia-smi -q -d SUPPORTED_CLOCKS`, plus helper functions for nearest supported frequency. | Cache/provenance is useful, but reportable experiments should probe the live GPU first and only use static catalogs as validation hints. |
| `likwid/src/nvmon_nvml.c`, `likwid/src/sysFeatures_nvml.c`, and LIKWID build docs | Optional `NVIDIA_INTERFACE` uses CUDA/CUPTI/NVML. `NVMON`/NVMarker are monitoring/profiling paths; `sysFeatures_nvml.c` separately exposes feature reads and privileged setters for application clocks, locked clocks, memory locked clocks, and power limits. | Keep LIKWID split into two conceptual buckets: NVMON/CUPTI for probing/profiling, optional NVML sysfeatures for actuation. Do not treat the monitoring extension itself as a clock setter. |

Primary vendor references:

1. NVIDIA `nvidia-smi` guide:
   <https://docs.nvidia.com/deploy/nvidia-smi/index.html>
2. NVIDIA NVML device commands:
   <https://docs.nvidia.com/deploy/nvml-api/group__nvmlDeviceCommands.html>
3. NVIDIA DCGM getting started and feature overview:
   <https://docs.nvidia.com/datacenter/dcgm/latest/user-guide/getting-started.html>,
   <https://docs.nvidia.com/datacenter/dcgm/latest/user-guide/feature-overview.html>
4. LIKWID NVIDIA backend and build notes:
   <https://github.com/RRZE-HPC/likwid/wiki/likwid-perfctr-backends>,
   <https://github.com/RRZE-HPC/likwid/wiki/Build>
5. AMD SMI CLI guide:
   <https://rocmdocs.amd.com/projects/amdsmi/en/latest/how-to/amdsmi-cli-tool.html>
6. AMD SMI clock/power/performance control API notes:
   <https://rocmdocs.amd.com/projects/amdsmi/en/latest/doxygen/docBin/html/group__tagClkPowerPerfControl.html>
7. ROCm SMI CLI notes:
   <https://rocm.docs.amd.com/projects/rocm_smi_lib/en/docs-6.1.0/python_usage.html>

## Current Registry

| Policy name | Directory | Status | Purpose |
|---|---|---|---|
| `max_freq` | `comparison_methods/system_baselines/max_freq/` | Registered | Fixed maximum graphics-clock baseline. |
| `min_freq` | `comparison_methods/system_baselines/min_freq/` | Registered | Fixed minimum graphics-clock baseline. |
| `oracle_static` | `comparison_methods/local_reproductions/oracle_static/` | Registered | Offline sweep oracle baseline. |
| `everest` | `comparison_methods/local_reproductions/everest_reimpl/` | Registered | Paper-faithful EVeREST runtime policy. |
| `ali_2022_reimpl` | `comparison_methods/local_reproductions/ali_2022_reimpl/` | Registered | Ali HPEC 2022 offline model-based selector. |
| `util_policy` | `comparison_methods/system_baselines/util_policy/` | Placeholder | Not implemented or registered yet. |
| `my_method` | `proposed_methods/my_method/` | Placeholder | Reserved for the proposed paper method. |

See `src/methods/registry.py` for the runtime registry used by
`scripts/run/control_loop.py`.

## Adding a New Policy

1. Decide whether the method is proposed or comparison.
2. For comparison methods, choose exactly one category:
   `system_baselines`, `local_reproductions`, or `external_integrations`.
3. Implement the `AlgorithmInterface` lifecycle or provide an adapter that
   exposes it.
4. For fixed-clock or static/offline whole-workload methods, implement the
   `StaticPolicy` protocol (`initial_decision()`) so the runner applies the
   selected clock once before window 0, and keep `on_window()` monitor-only.
5. Emit only `Decision` objects that pass `validate_decision()`.
6. Add tests under the matching `tests/methods/...` path.
7. Add a stable name to `src/methods/registry.py`.
8. Document config keys and method scope in a local README or reproduction plan.
9. If the method is a local reproduction of a paper/system, update
   `comparison_methods/local_reproductions/README.md` before using it in
   claims.

## Method-Specific Docs

1. Local reproductions keep source caches in ignored `paper/` folders and
   reproduction notes in tracked `docs/` folders when source papers are needed.
2. Citation/source ledgers for local reproductions live in
   `comparison_methods/local_reproductions/README.md`.
3. External integrations keep third-party source under `external/` and local
   adapters under `comparison_methods/external_integrations/`.
4. Hardware clock command templates belong in `scripts/run/README.md`, not in
   method modules.
5. Proposed-method design notes should stay separate from paper-faithful
   baseline reproduction notes.
