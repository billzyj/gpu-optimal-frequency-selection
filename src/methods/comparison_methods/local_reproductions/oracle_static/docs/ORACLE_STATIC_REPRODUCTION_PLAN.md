# Oracle-Static Baseline Reproduction Plan

## 1. Goal

Reproduce the minimal static-oracle GPU DVFS evaluation baseline used for
comparison with EVeREST-style runtime policies.

The oracle-static baseline chooses one fixed GPU graphics clock from an
offline frequency sweep before the run begins, applies that clock once, and
holds it for the workload. It is an evaluation upper-bound style baseline for
offline knowledge, not a runtime method proposed as a standalone publication.

## 2. Source and Citation Trace

Primary citation:

- Anna Yue, Pen-Chung Yew, and Sanyam Mehta. 2025. "EVeREST: An Effective and
  Versatile Runtime Energy Saving Tool for GPUs." PPoPP '25.
- DOI: <https://doi.org/10.1145/3710848.3710875>
- Zotero/topic trace: `topics/power_management`, item key `8AY5ISNG`,
  attachment key `7ZPWFMU3`.
- Local source cache: `../paper/EVEREST_ppopp25.pdf` and
  `../paper/EVEREST_ppopp25.txt`.

The EVeREST text describes the oracle as a static comparison that immediately
runs at the ideal frequency for a target performance degradation. It also gives
the motivating rule for low performance-loss thresholds: choose the lowest
frequency that still meets the performance target.

## 3. Why This Is a Baseline, Not a Published Method

`oracle_static` is not a separately published algorithm with its own citation.
It exists to reproduce the EVeREST evaluation role of a static oracle:

1. It assumes the workload has already been profiled across available GPU
   frequencies on the target system.
2. It uses that offline knowledge to pick a single fixed frequency before the
   measured run.
3. It avoids EVeREST's runtime phase-identification and phase-characterization
   overhead because it already knows the profile.

For manuscript claims, cite the EVeREST paper when using this baseline unless a
more specific paper or evaluation protocol is intentionally substituted.

## 4. Required Offline Inputs

A faithful run requires an offline sweep/profile for the same workload, GPU,
driver stack, benchmark input, and measurement protocol used in the comparison.

Each sweep point should include:

1. `frequency_mhz`: supported graphics clock tested in the sweep.
2. `performance_ratio`: workload performance at that clock relative to the
   max-frequency run. For example, `0.95` means 5% slower than max frequency.
3. Optional `power_w`: average power at that clock. The current implementation
   uses this only as a tie-breaker among equal-frequency candidates, so it is
   not required for basic selection.

The current `StaticOraclePolicy` accepts either:

1. `workload_profiles[workload_name]`: a per-workload profile.
2. `workload_profiles.default`: fallback profile.
3. `profile`: a single profile list applied to all workloads.

Supported profile field aliases are documented in `../policy.py`.

## 5. Selection Rule

For a configured performance-degradation target `PD`, compute:

```text
target_ratio = 1 - PD
```

Then:

1. Keep sweep points where `performance_ratio >= target_ratio`.
2. Select the lowest `frequency_mhz` among those valid points.
3. If no point satisfies the target, fall back to the point with the best
   observed `performance_ratio`.
4. Clamp the selected frequency to the platform min/max graphics-clock bounds.
5. Apply the selected clock once at initialization and hold it for the run.

This matches the current source code in `../policy.py`:
`choose_static_oracle_clock()` selects the lowest profiled frequency satisfying
the target performance ratio, and `StaticOraclePolicy` emits one set-clock
decision followed by hold decisions.

## 6. Minimal Reproduction Procedure

1. Run a max-frequency reference measurement for each workload and benchmark
   input.
2. Sweep the supported GPU graphics clocks and record performance ratio
   relative to the max-frequency run.
3. Create a policy config with the resulting profile points.
4. Run the workload with `POLICY_NAME=oracle_static` and the same `PD` target
   used for EVeREST or other runtime-policy comparisons.
5. Verify that the selected fixed clock satisfies the offline profile target.
6. In the measured run, report runtime, performance ratio, power, energy, and
   whether observed performance still satisfies the target.

## 7. Ambiguities and Limitations

1. The EVeREST paper uses the static oracle as an evaluation baseline but does
   not define a complete reusable file format for oracle profiles.
2. "Ideal frequency" is interpreted here as the lowest profiled graphics clock
   satisfying the target performance ratio. This is consistent with the
   EVeREST text and current implementation, but the paper does not publish all
   original oracle sweep records.
3. The oracle is only as valid as the offline sweep. Different inputs, GPUs,
   drivers, thermal states, process placement, or application versions can
   invalidate a profile.
4. A single static clock cannot adapt to intra-run phase changes. It is useful
   as an offline-knowledge comparison point, not as a deployable runtime
   controller.
5. The current policy falls back to best observed performance if no profiled
   point meets the target. Such runs should be reported as target-missing
   oracle profiles, not as successful oracle selections.
6. If performance is noisy, a single sweep may falsely classify a frequency as
   target-satisfying. Reproductions should prefer repeated runs or confidence
   intervals before treating a clock as oracle-valid.

## 8. Improvement Space for the Proposed Method

The following are opportunities for a new method. They should not be folded into
the `oracle_static` baseline unless the baseline scope is explicitly changed.

1. Replace full offline sweeps with sparse profiling, active sampling, or model
   transfer across workloads.
2. Adapt within a run instead of holding one static clock.
3. Track profile uncertainty and choose clocks based on confidence rather than
   a single observed ratio.
4. Incorporate power or energy directly into the objective when several clocks
   meet the same performance target.
5. Detect stale profiles caused by hardware, driver, benchmark, or input drift.
6. Combine offline prior knowledge with runtime correction while preserving a
   separate reportable comparison against the pure static oracle.
