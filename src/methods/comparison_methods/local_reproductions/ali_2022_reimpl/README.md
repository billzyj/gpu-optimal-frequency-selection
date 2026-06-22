# Ali HPEC 2022 Reimplementation

This folder contains the paper-faithful reimplementation of Ali et al.'s HPEC
2022 model-based GPU frequency-selection method.

- Source cache: ignored local `paper/`
- Reproduction plan: `docs/ALI_REPRODUCTION_PLAN.md`
- Zotero/topic trace: `topics/power_management`, item key `D9D98WW7`,
  attachment key `XGE3W56U`

The baseline should remain an offline, application-level selector based on the
paper's analytical power/performance models and EDP/ED2P objective selection.
Runtime adaptation, extra constraints, and cross-paper extensions belong in a
separate improved method, not in `ali_2022_reimpl`.

## What "Offline Training" Means Here

Ali HPEC 2022 does not use a pretrained DNN model. The required offline step is
analytical model calibration: fit a small set of power and performance
coefficients from benchmark profiling data, then use those coefficients for
target-workload frequency selection.

The baseline needs two kinds of inputs before it can run:

1. **Platform calibration outputs**
   - Supported GPU core frequencies, using GV100 510-1380 MHz for strict paper
     reproduction or the local platform's supported clock list for an
     algorithmic proxy.
   - DCGMI/DCGM field mapping for `fp_activity`, `dram_activity`,
     `sm_app_clock`, `power_usage`, and execution time.
   - Power coefficients for:

```text
P_f = alpha * FP_act + beta * DRAM_act + gamma * f + C
```

   - Performance coefficients for:

```text
T_f = T_fmax
    + beta1 * FP_act
    + beta2 * delta_f
    + beta3 * FP_act^2
    + beta4 * FP_act * delta_f
    + beta5 * delta_f^2
```

2. **Per-workload max-frequency profiling outputs**
   - Average `fp_activity` at max/default core frequency.
   - Average `dram_activity` at max/default core frequency.
   - Runtime at max/default core frequency, recorded as `t_fmax_s`.

## Offline Calibration Workflow

1. Run the calibration benchmarks used by the paper, at minimum DGEMM and
   STREAM, across the supported core-frequency design space.
2. For each frequency, collect DCGMI/DCGM metrics at the paper's sampling
   cadence when possible: Ali 2022 reports 20 ms sampling and three runs.
3. Fit the power equation against measured `power_usage`.
4. Fit the performance equation against measured runtime deltas from the maximum
   frequency, where `delta_f = f_max - f`.
5. Save the fitted coefficients, frequency list, `f_max_mhz`, field mapping,
   platform metadata, and benchmark provenance. These are the "offline training"
   artifacts for this baseline.
6. For each target workload, run once at max/default frequency and record
   `fp_activity`, `dram_activity`, and `t_fmax_s`.
7. Build the policy config from the platform calibration outputs plus the
   target-workload max-frequency profile.

## Runtime Config Shape

`POLICY_NAME=ali_2022_reimpl` expects the fitted coefficients and target
workload profile to be supplied through `POLICY_CONFIG_PATH` or
`POLICY_CONFIG_JSON`.

For a compact config-file schema, see
`config/algorithms/ali_2022_reimpl/README.md`.

The example below is an explicitly labeled local-platform proxy. Use
`reproduction_mode: "paper_faithful_gv100"` only with the GV100 510-1380 MHz
frequency space and max-frequency profiling provenance described above.

```json
{
  "objective": "edp",
  "reproduction_mode": "algorithmic_proxy",
  "frequencies_mhz": [900, 1200, 1500],
  "f_max_mhz": 1500,
  "fp_activity": 0.25,
  "dram_activity": 0.40,
  "t_fmax_s": 12.34,
  "profiling_run_count": 3,
  "sampling_interval_ms": 20,
  "profiler_source": "dcgmi",
  "profile_source": "max-frequency-profile-log",
  "calibration_source": "offline-calibration-fit",
  "power_coefficients": {
    "alpha": 0.0,
    "beta": 0.0,
    "gamma": 0.0,
    "constant": 0.0
  },
  "performance_coefficients": {
    "beta1": 0.0,
    "beta2": 0.0,
    "beta3": 0.0,
    "beta4": 0.0,
    "beta5": 0.0
  }
}
```

The policy predicts power, runtime, energy, EDP, and ED2P for every candidate
frequency, selects one whole-workload clock, and exposes it through the
`StaticPolicy` protocol (`initial_decision(context, state)`) for one pre-window
application. Its `on_window` is monitor-only and never re-applies or updates the
selected frequency online.
