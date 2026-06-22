# EVeREST Reimplementation

This directory contains the paper-faithful EVeREST reimplementation and the
source material used to justify it.

## Layout

1. `policy.py`: online EVeREST control policy.
2. `phase_identification/`: GPU/memory utilization phase detection.
3. `phase_characterization/`: frequency-sensitivity estimation and cache.
4. `frequency_scaling/`: Equation 4 target-clock calculation and quantization.
5. `paper/`: ignored local EVeREST PDF/text source cache.
6. `docs/EVEREST_REPRODUCTION_PLAN.md`: reproduction scope, fidelity decisions,
   known ambiguities, and improvement opportunities for proposed methods.

The top-level `references/` directory was removed intentionally. EVeREST source
evidence may live in ignored local `paper/` files next to this implementation;
the tracked source of truth is this README, the reproduction plan, and the
ledger in `../README.md`.

## Runtime Policy

`POLICY_NAME=everest` implements the online EVeREST loop:

1. Identify stable GPU/memory utilization phases using absolute utilization-point
   thresholds over the recent window.
2. For a new phase, collect `Mem_high` at `f_high` if needed, then probe
   `Mem_low` at the lower characterization frequency.
3. Cache frequency sensitivity only when the high/low windows match the observed
   clocks and still represent the same phase.
4. Cache phase characterizations and apply scaled target clocks on repeats.

The default policy intentionally stops at the behavior described in the paper.
It validates the paper-required high/low characterization measurements before
caching, but it does not add retry loops, fallback sensitivity records, or
closed-loop PD correction. Those are candidate improvements for proposed methods,
not part of this baseline.

## Supported Config Keys

Pass these through `POLICY_CONFIG_PATH` or `POLICY_CONFIG_JSON`:

1. `phase_window_seconds` (default: `ExperimentContext.window_seconds`)
2. `change_threshold_pct` (default: `10.0` percentage points)
3. `idle_gpu_threshold_pct` (default: `5.0`)
4. `idle_mem_threshold_pct` (default: `3.0`)
5. `high_frequency_mhz` (default: platform max)
6. `characterization_low_frequency_ratio` (default: `0.70`)
7. `characterization_low_frequency_mhz` (optional explicit low probe clock)
8. `min_ratio_of_max` (default: `0.55`)
9. `min_frequency_mhz` (default: `900`)
10. `clock_match_tolerance_mhz` (default: half a platform clock step, at least `0.5`)

For source-grounded ambiguity notes and known EVeREST limitations, see
`docs/EVEREST_REPRODUCTION_PLAN.md`. For a compact config-file schema, see
`config/algorithms/everest/README.md`.
