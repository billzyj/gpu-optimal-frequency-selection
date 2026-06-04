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
  "min_ratio_of_max": 0.55
}
```

## Optional Keys

1. `high_frequency_mhz`: explicit high/default frequency; defaults to platform
   max.
2. `characterization_low_frequency_mhz`: explicit low-probe clock; overrides
   `characterization_low_frequency_ratio`.

## Notes

1. These keys control the EVeREST reproduction baseline only.
2. New adaptive heuristics, closed-loop correction, or richer phase signatures
   belong in the proposed method unless the EVeREST baseline scope is explicitly
   changed.
3. See
   `src/methods/comparison_methods/local_reproductions/everest_reimpl/README.md`
   for behavior and fidelity notes.
