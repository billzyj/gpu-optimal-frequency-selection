# Ali HPEC 2022 Config

`ali_2022_reimpl` is an offline, whole-workload selector. It requires fitted
model coefficients plus one max-frequency profile for the target workload.
Pass this config through `POLICY_CONFIG_PATH` or `POLICY_CONFIG_JSON` when
running `POLICY_NAME=ali_2022_reimpl`.

## Portable Proxy Example

This example is labeled as an algorithmic proxy because the frequency space is a
local platform list, not the paper's GV100 510-1380 MHz design space.

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

## Paper-Faithful Mode

The default `reproduction_mode` is `paper_faithful_gv100`. Use it only when the
config is built from a GV100-style reproduction of the Ali HPEC 2022 workflow:

1. `frequencies_mhz` is the supported GV100 candidate set used for selection.
2. The frequency list starts at 510 MHz and ends at 1380 MHz.
3. `f_max_mhz` is 1380 MHz and equals the maximum candidate frequency.
4. `fp_activity`, `dram_activity`, and `t_fmax_s` come from max-frequency
   target-workload profiling.
5. The provenance fields identify how the max-frequency profile and fitted
   coefficients were produced.

Use `reproduction_mode: "algorithmic_proxy"` for local-platform or reduced
frequency lists that do not match the paper setup. Proxy mode is intentionally
visible in the policy state, decisions, and final summary.

## Notes

1. `objective` must be `edp` or `ed2p`; default is `edp`.
2. `frequencies_mhz` must be non-empty, unique, strictly increasing, within the
   platform graphics-clock range, and no candidate may exceed `f_max_mhz`.
3. In `paper_faithful_gv100` mode, `f_max_mhz` must equal the maximum candidate
   frequency. If a config intentionally uses a non-paper frequency space, label
   it with `reproduction_mode: "algorithmic_proxy"`.
4. `fp_activity`, `dram_activity`, and `t_fmax_s` are target-workload
   max-frequency profile values.
5. `profiling_run_count`, `sampling_interval_ms`, `profiler_source`,
   `profile_source`, and `calibration_source` are optional provenance fields.
   They should be filled when known; the paper reports three runs and 20 ms
   sampling.
6. Coefficients come from offline calibration; do not fit them inside the
   runtime policy.
7. The policy satisfies the `StaticPolicy` protocol via
   `initial_decision(context, state)` and records
   `pre_run_target_graphics_clock_mhz` in state/debug/summary fields so the
   shared runner can apply the selected whole-workload clock once before
   window 0. `on_window` is monitor-only; clock application itself remains
   runner-owned.
8. See
   `src/methods/comparison_methods/local_reproductions/ali_2022_reimpl/README.md`
   for the reproduction workflow and source notes.
