# EVeREST Experiment Reproduction Plan and Design

## 1. Goal

Reproduce the core EVeREST claims from PPoPP 2025 in a code-independent way:

1. Runtime GPU DVFS can meet a user-defined performance degradation (PD) target.
2. Memory bandwidth utilization can predict frequency sensitivity across NVIDIA and AMD.
3. The runtime Frequency Scaling stage can outperform simple utilization-based baselines in power/energy savings under the same performance target.

This plan is based on: `10.1145/3710848.3710875` and the extracted text from `EVEREST_ppopp25.txt`.

## 2. Reproduction Scope

### 2.1 Primary claims to reproduce

1. Performance target tracking at `PD=5%` and `PD=10%`.
2. Relative power/energy improvements vs:
   - Max-frequency baseline.
   - EAR-style utilization policy baseline.
   - Ali-FP-style baseline on NVIDIA (or best-effort proxy if exact training artifacts are unavailable).
   - Static oracle (offline ideal frequency selection per workload).
3. Correlation result:
   - Memory utilization tracks performance better than GPU utilization.

### 2.2 Success criteria

1. `>=90%` of runs satisfy performance target within `±2%` tolerance.
2. EVeREST-like Frequency Scaling beats utilization baseline in average energy savings at both PD points.
3. Correlation trend is directionally identical to paper:
   - `corr(memory_util, perf_ratio)` > `corr(gpu_util, perf_ratio)` on both vendors.

### 2.3 Non-goals

1. Bit-for-bit reproduction of all figures.
2. Exact Cray EX PM-counter pipeline replication.
3. Full benchmark matrix from Table 1 in the first pass.

## 3. Constraints and Assumptions

1. Original EVeREST source code is unavailable.
2. Local environment may not match Cray EX hardware/software stack.
3. A phased reproduction is required:
   - Phase A: algorithmic and methodological reproduction.
   - Phase B: hardware-realistic replication and tighter numerical matching.

## 4. EVeREST-like Runtime Design

## 4.1 Runtime components

1. `telemetry_sampler`
   - Collect GPU utilization + memory utilization at high rate.
   - NVIDIA: DCGM fields (`GR_ENGINE_ACTIVE`, `DRAM_ACTIVE`).
   - AMD: ROCm SMI fields (`average_gfx_activity`, `average_umc_activity`).
2. `phase_identification`
   - Build phase signatures from averaged utilization windows.
   - Detect phase changes using utilization delta threshold.
3. `phase_characterization`
   - For unseen phases, sample at `f_high` and `f_low` to infer frequency sensitivity.
4. `frequency_scaling`
   - Compute ideal frequency from sensitivity and PD target.
   - Clamp and quantize to device-supported steps.
5. `actuator`
   - NVIDIA: NVML / `nvidia-smi`.
   - AMD: ROCm SMI.
6. `experiment_logger`
   - Persist decisions, utilization windows, frequencies, runtime, power, energy.

## 4.2 Key equations

Define:

- `f_high`: high clock (typically max).
- `f_low`: temporary lower clock for characterization.
- `Mem_high`, `Mem_low`: average memory utilization in same phase window at `f_high`, `f_low`.
- `PD`: allowed performance degradation target (e.g., `0.05`, `0.10`).

Frequency sensitivity (normalized form):

```text
FS = (Mem_high / Mem_low - 1) / (f_high / f_low - 1), 0 <= FS <= 1
```

Ideal frequency:

```text
f_ideal = f_high / (1 + PD / (FS * (1 - PD)))
```

Operational rules from paper:

1. Use a low frequency that is still relatively high (example: ~30% below max) to reduce characterization overhead.
2. Do not lower below ~55% of max frequency.
3. Use a phase window around `5s` (paper sensitivity shows `>1s` is generally stable).

Note: OCR around Equation (3) is ambiguous in text extraction; Equation (4) above is internally consistent with the paper’s Frequency Scaling behavior and should be treated as the implementation source of truth.

## 4.3 Control loop pseudocode

```text
while app_running:
  sample gpu_util, mem_util
  update rolling window aggregates

  if phase_is_stable(window=5s, change_threshold=10%):
    phase_id = signature(gpu_util_avg, mem_util_avg)

    if phase_id not characterized:
      run_at(f_low) for one window
      measure Mem_low
      restore f_high
      get Mem_high from stored window at f_high
      FS = estimate_sensitivity(Mem_high, Mem_low, f_high, f_low)
      cache phase_id -> FS

    FS = cache[phase_id]
    f_ideal = compute_f_ideal(FS, PD)
    f_ideal = clamp(f_ideal, min=0.55*f_max, max=f_max)
    f_ideal = round_up_to_supported_step(f_ideal)
    set_gpu_clock(f_ideal)
  else:
    set_gpu_clock(f_high)
```

## 4.4 Decoupled Implementation Specification

This repository uses EVeREST's three paper stages as first-class modules. Each module has a single purpose and can be tested independently.

1. `Phase Identification`
   - Input: `MetricWindow`.
   - Output: stable/not-stable phase observation with `phase_id`.
   - Core rules:
     - Rolling window average over configurable duration (`5s` default).
     - Phase change if utilization delta exceeds threshold (`10%` default).
     - Signature includes both GPU and memory utilization to separate "busy low-memory" from initialization-like behavior.
2. `Phase Characterization`
   - Input: (`phase_id`, `Mem_high`, `Mem_low`, `f_high`, `f_low`).
   - Output: frequency sensitivity `FS` and cached characterization record.
   - Core rules:
     - `FS = (Mem_high / Mem_low - 1) / (f_high / f_low - 1)`.
     - Clamp `FS` to `[0, 1]`.
     - Validate inputs (`mem_low > 0`, `f_low > 0`, `f_high > f_low`).
3. `Frequency Scaling`
   - Input: (`f_high`, `FS`, `PD`, `PlatformSpec`).
   - Output: quantized target graphics clock.
   - Core rules:
     - `f_ideal = f_high / (1 + PD / (FS * (1 - PD)))`.
     - Clamp to platform range with an EVeREST floor at `0.55 * f_max`.
     - Round up to the next supported hardware step.

Default parameters used for implementation/testing:

1. `window_seconds = 5.0`
2. `change_threshold_pct = 10.0`
3. `min_ratio_of_max = 0.55`
4. characterization low point recommendation: `f_low ~= 0.7 * f_high`

## 5. Experiment Design

## 5.1 Hardware matrix

### Tier-1 (recommended first pass)

1. 1x NVIDIA node (A100/H100 acceptable).
2. 1x AMD node (MI250X/MI300 acceptable).

### Tier-2 (closer to paper)

1. Multi-GPU nodes with 4x GPUs per node.
2. Slurm integration.
3. Node-level power telemetry.

## 5.2 Workload matrix

Prioritize representative subset first:

1. HPC memory-sensitive: LAMMPS (spce/reaxff), MILC.
2. HPC mixed behavior: PSDNS or Workflow.
3. AI/ML power-heavy: one of GPT-train, BERT, ResNet-50.
4. Vendor-specific additions:
   - NVIDIA: GROMACS.
   - AMD: WarpX.

Then expand toward full Table-1 coverage.

## 5.3 Baselines

1. `MAX_FREQ`: fixed max graphics clock.
2. `STATIC_ORACLE`:
   - Offline sweep available frequencies.
   - Pick lowest frequency meeting target performance for each workload.
3. `UTIL_POLICY` (EAR-like proxy):
   - Scale frequency/power cap from instantaneous GPU utilization.
   - No memory-util sensitivity characterization.
4. `ALI_FP_PROXY` (NVIDIA only):
   - Use FP and DRAM activity model with minimal offline calibration.
   - If full Ali model is infeasible, document approximation clearly.

## 5.4 Metrics

For each run:

1. `Perf_rel = runtime_maxfreq / runtime_policy`
2. `Power_rel = avg_power_policy / avg_power_maxfreq`
3. `Energy_rel = energy_policy / energy_maxfreq`
4. `PD_violation = max(0, (1 - PD) - Perf_rel)`

Across runs:

1. Mean, std, and 95% CI.
2. Violation rate per workload and overall.

## 5.5 Run protocol

1. Lock non-target variables:
   - Fixed application input.
   - Fixed GPU memory clock if possible.
   - CPU governor pinned (avoid host-side drift).
2. Warmup run per workload per policy.
3. At least 5 measured repetitions per point.
4. Record ambient/system load and discard outliers only with predefined rule.

## 6. Repository Implementation Plan

Proposed structure:

```text
.
├── src/
│   ├── common/
│   │   ├── telemetry/
│   │   ├── control/
│   │   ├── power/
│   │   ├── experiment/
│   │   ├── io/
│   │   └── cli/
│   ├── methods/
│   │   ├── system_baselines/
│   │   │   ├── max_freq/
│   │   │   ├── min_freq/
│   │   │   └── util_policy/
│   │   ├── reimplemented_methods/
│   │   │   ├── everest_reimpl/
│   │   │   │   ├── phase_identification/
│   │   │   │   ├── phase_characterization/
│   │   │   │   ├── frequency_scaling/
│   │   │   │   └── policy/
│   │   │   ├── ali_reimpl/
│   │   │   └── oracle_static/
│   │   ├── third_party/
│   │   │   └── ear_external/
│   │   └── proposed_methods/
│   │       └── my_method/
├── config/
│   ├── common/
│   ├── platforms/
│   ├── workloads/
│   ├── experiments/
│   └── algorithms/
│       ├── everest/
│       └── my_method/
├── scripts/
│   ├── setup/
│   ├── run/
│   ├── sweep/
│   ├── collect/
│   └── reproduce/
├── analysis/
│   ├── schema/
│   ├── notebooks/
│   ├── plots/
│   └── reports/
├── artifacts/
│   ├── raw/
│   ├── processed/
│   └── figures/
└── docs/
    ├── REPO_ARCHITECTURE.md
    └── EVEREST_REPRODUCTION_PLAN.md
```

Implementation mapping for EVeREST:

1. EVeREST-specific logic is in `src/methods/reimplemented_methods/everest_reimpl`.
2. Shared sampling/actuation/runner infrastructure stays in `src/common`.
3. Simple baselines and references live in `src/methods/*` and reuse the same runner contracts.
4. Your future algorithm is developed in `src/methods/proposed_methods/my_method` with the same experiment pipeline.

## 7. Milestones

### M1: Foundation (Week 1)

1. Telemetry collection + clock control on one NVIDIA GPU.
2. Frequency sweep harness and raw data schema.

### M2: Three-stage alpha (Week 2)

1. Phase Identification + Phase Characterization + Frequency Scaling loop.
2. Single-workload end-to-end validation at PD 5/10.

### M3: Baseline pack (Week 3)

1. Static oracle automation.
2. UTIL_POLICY baseline.
3. Initial comparison plots.

### M4: Cross-vendor extension (Week 4)

1. AMD support path with ROCm SMI.
2. Correlation and policy comparison on AMD workloads.

### M5: Replication report (Week 5)

1. Reproduction summary with claim-by-claim status.
2. Gap analysis vs paper and reasons.

## 8. Risks and Mitigations

1. Missing exact benchmark environments.
   - Mitigation: reproduce method-level claims on accessible workloads first.
2. Power telemetry mismatch vs Cray PM counters.
   - Mitigation: use NVML/ROCm energy APIs and report measurement method explicitly.
3. Baseline implementation uncertainty (EAR/Ali details).
   - Mitigation: define faithful proxies and document all deviations.
4. Multi-tenant noise.
   - Mitigation: isolate nodes or schedule dedicated windows.

## 9. Deliverables

1. EVeREST-like runtime prototype.
2. Reproducible experiment scripts and configs.
3. Figure set:
   - Performance vs PD target.
   - Relative power/energy.
   - Utilization-performance correlation.
4. Reproduction report with:
   - Matched claims.
   - Unmatched claims with technical explanation.
   - Recommendations for your new GPU DVFS paper direction.

## 10. Immediate Next Actions

1. Confirm your available GPUs and scheduler setup.
2. Lock Tier-1 workload shortlist (3-5 workloads).
3. Implement `MAX_FREQ` and `STATIC_ORACLE` first to establish a trustworthy evaluation harness.
4. Add EVeREST-like runtime loop after baseline harness is validated.
