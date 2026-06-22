# EVeREST Config

`everest` can run with defaults derived from the platform and
`ExperimentContext`, but controlled experiments should record explicit
hyperparameters for reproducibility.

## Minimal Schema

```json
{
  "phase_window_seconds": 5.0,
  "change_threshold_pct": 10.0,
  "idle_gpu_threshold_pct": 5.0,
  "idle_mem_threshold_pct": 3.0,
  "characterization_low_frequency_ratio": 0.70,
  "min_ratio_of_max": 0.55,
  "min_frequency_mhz": 900
}
```

## Optional Keys

1. `high_frequency_mhz`: explicit high/default frequency; defaults to platform
   max.
2. `characterization_low_frequency_mhz`: explicit low-probe clock; overrides
   `characterization_low_frequency_ratio`.
3. `clock_match_tolerance_mhz`: observed-clock tolerance for accepting
   characterization samples; defaults to half a platform clock step, with a
   minimum of 0.5 MHz.

## Notes

1. These keys control the EVeREST reproduction baseline only.
2. `change_threshold_pct` is interpreted as absolute utilization percentage
   points, matching the paper's 10% utilization-change threshold.
3. Stable zero-memory phases remain uncharacterized at the high/default
   frequency until a valid high/low memory-utilization pair exists.
4. New adaptive heuristics, closed-loop correction, or richer phase signatures
   belong in the proposed method unless the EVeREST baseline scope is explicitly
   changed.
5. See
   `src/methods/comparison_methods/local_reproductions/everest_reimpl/README.md`
   for behavior and fidelity notes.
