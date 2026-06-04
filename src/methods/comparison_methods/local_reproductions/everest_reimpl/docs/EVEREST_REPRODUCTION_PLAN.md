# EVeREST Experiment Reproduction Plan and Design

## 1. Goal

Reproduce the core EVeREST claims from PPoPP 2025 in a code-independent way:

1. Runtime GPU DVFS can meet a user-defined performance degradation (PD) target.
2. Memory bandwidth utilization can predict frequency sensitivity across NVIDIA and AMD.
3. The runtime Frequency Scaling stage can outperform simple utilization-based baselines in power/energy savings under the same performance target.

This plan is based on: `10.1145/3710848.3710875` and the co-located
implementation copy at `../paper/EVEREST_ppopp25.txt`.

## 2. Reproduction Scope

### 2.1 Primary claims to reproduce

1. Performance target tracking at `PD=5%` and `PD=10%`.
2. Relative power/energy improvements vs:
   - Max-frequency baseline.
   - Utilization-only policy baseline.
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

## 4. Paper-Faithful EVeREST Runtime Design

## 4.0 Source-Grounded Fidelity Audit

Current status: `POLICY_NAME=everest` is treated as the paper-faithful
baseline, not as an engineering-hardened or improved EVeREST variant. The
implementation was checked against the extracted paper text in
`../paper/EVEREST_ppopp25.txt`, especially Sections 3.3, 4, and 5.

| Paper source | Paper behavior | Current implementation | Fidelity decision |
|---|---|---|---|
| `../paper/EVEREST_ppopp25.txt:63` | Analyses are limited above 900 MHz and performance is approximated as linear with frequency in that region. | `FrequencyScaler` clamps target frequency to a configurable floor, default `0.55 * f_max`, then rounds up to a supported step. | Use the paper's "about 55% of max" runtime floor as the implemented scaling floor. This is close to but not identical to the textual "above 900 MHz" across all GPUs; record platform-specific frequency bounds in runs. |
| `../paper/EVEREST_ppopp25.txt:89-103` | Measure memory utilization at max/high and one lower frequency; derive normalized frequency sensitivity `FS`. | `PhaseCharacterizer.estimate_frequency_sensitivity()` implements `(Mem_high / Mem_low - 1) / (f_high / f_low - 1)` and clamps to `[0, 1]`. | Direct implementation of Equation 2 in normalized form. |
| `../paper/EVEREST_ppopp25.txt:103` | The low characterization frequency should remain fairly high, with example around 70% of max. | `EverestPolicy` defaults to `characterization_low_frequency_ratio = 0.70`, with optional explicit `characterization_low_frequency_mhz`. | Use 70% as the default because it is the only concrete low-probe example in the paper. |
| `../paper/EVEREST_ppopp25.txt:117-122` | Compute the ideal frequency from `FS` and target `PD`. | `FrequencyScaler.compute_target_frequency()` implements Equation 4. | Direct implementation. |
| `../paper/EVEREST_ppopp25.txt:143` | A stable average GPU/memory utilization window, e.g. 5s, reveals a phase; 10% utilization change indicates a phase change. | `PhaseIdentifier` uses a rolling weighted average, default 5s through the runner, and relative 10% change vs the last stable phase. | Paper-faithful minimum; exact signature discretization is not specified by the paper and is documented below as ambiguous. |
| `../paper/EVEREST_ppopp25.txt:143` | GPU utilization is included in phase signatures to distinguish active low/zero-memory phases from initialization-like phases. | `PhaseIdentifier` includes both GPU and memory buckets plus an `idle_like` bit. | Faithful to the stated intent; exact idle thresholds are implementation choices. |
| `../paper/EVEREST_ppopp25.txt:89-103,145` | For an uncharacterized phase, use memory utilization at max/high and one lower frequency; run at the lower frequency for the same window of time and measure average memory utilization. | `EverestPolicy` first obtains a high-frequency memory-utilization window (`Mem_high`), using the current stable window only when it is already at `f_high`; otherwise it sets `f_high` and uses the next window. It then sets `f_low` and uses the next `MetricWindow` as `Mem_low`. | Paper-faithful two-point characterization at the policy level. Full paper cadence with raw 1ms/10ms samples, 1s decision averages, and 5s phase windows needs extra aggregation; see Section 4.5. |
| `../paper/EVEREST_ppopp25.txt:151` | Round up to the next supported GPU frequency step. | `FrequencyScaler` quantizes up within platform bounds. | Direct implementation. |
| `../paper/EVEREST_ppopp25.txt:153` | If phases are too short or erratic, EVeREST detects no phase and remains at max/default frequency. | Unstable/no-phase windows emit `everest_wait_for_stable_phase` and hold or set `f_high`. | Intentionally preserved. Do not add heuristics that force characterization of erratic phases in the EVeREST baseline. |

The current policy deliberately stops after the paper-required high/low
characterization measurements. It does not add clock-settle retries, retry caps,
probe-abandon logic, fallback records, closed-loop PD correction, or
re-characterization. These may be good ideas for a new method, but they are not
described in the EVeREST paper and would contaminate the baseline comparison.

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

Note: OCR around Equation (3) is ambiguous in text extraction; Equation (4)
above is internally consistent with the paper's Frequency Scaling behavior and
is treated as the implementation source of truth.

## 4.3 Control loop pseudocode

```text
while app_running:
  sample gpu_util, mem_util
  update rolling window aggregates

  if phase_is_stable(window=5s, change_threshold=10%):
    phase_id = signature(gpu_util_avg, mem_util_avg)

    if phase_id not characterized:
      if current_window_clock is not f_high:
        set_gpu_clock(f_high)
        wait/measure one characterization window
        Mem_high = average memory utilization from that high window
      else:
        Mem_high = average memory utilization from current stable window
      set_gpu_clock(f_low)
      wait/measure one characterization window
      measure Mem_low from that window
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

Default parameters used for paper-faithful runs:

1. `CONTROL_WINDOW_SECONDS = 5.0` in the long-lived runner, which becomes
   `ExperimentContext.window_seconds`.
2. `change_threshold_pct = 10.0`
3. `min_ratio_of_max = 0.55`
4. characterization low point recommendation: `f_low ~= 0.7 * f_high`
5. `METRIC_SAMPLING_INTERVAL_MS = 1000` in the current runner harness. The
   paper reports raw sampling at 1ms on A100 and 10ms on MI250X, then averaging
   every 1s for decision-making; this repository does not yet implement that
   exact hardware sampling path.

## 4.5 Reproduction Fidelity Decisions (do not "fix" these)

These are deliberate fidelity calls. They are documented here so that future contributors do not mistake faithful-to-paper behavior for a bug and "improve" it beyond the paper, which would erase contrast points for the proposed method.

1. **Required high/low characterization without engineering guards.**
   - The default EVeREST policy first obtains the paper-required high-frequency
     measurement for an uncharacterized phase: if the current stable window is
     already at `f_high`, it uses that window as `Mem_high`; otherwise it sets
     `f_high` and uses the next window as `Mem_high`. It then sets `f_low` and
     uses the next window as `Mem_low`.
   - The policy does not add clock-settle retries, repeated clock verification,
     probe-abandon logic when utilization shifts, attempt caps, or fallback to a
     conservative `FS = 1` record.
   - Reason: Sections 4.1 and 5.2 define frequency sensitivity from memory
     utilization at high/max and low frequencies, but do not define retries,
     settle tolerances, attempt caps, or corruption detection.
   - Consequence: if actuation latency or phase drift corrupts either
     characterization window, the EVeREST baseline can mispredict. This
     limitation is useful contrast for a proposed method, not a baseline bug to
     repair.

2. **Uncharacterizable / zero-memory phases keep `FS = 0` (intentionally NOT changed to "stay at max").**
   - Reason codes: `everest_apply_without_low_frequency_probe` (no room to probe, `f_low >= f_high`) and `everest_apply_zero_mem_phase` (stable, GPU-active, `mem_util <= 0`).
   - The paper is **silent** on these cases. Section 5.4's "remain at default (maximum) frequency" refers to **phase-detection failure** (no stable phase detected), not to a detected-but-uncharacterizable phase. Section 5.1 only uses GPU utilization to *distinguish* zero-memory phases in the signature; it never prescribes their frequency.
   - `FS = 0` is internally consistent with EVeREST's MBU-to-FS model taken to the zero-memory limit: memory bandwidth utilization (MBU = data / wall-clock-time) is ~0 and invariant across frequency, so the model reads it as "not frequency-sensitive" and scales down to the `0.55 * f_max` floor.
   - This preserves a real EVeREST blind spot: a compute-bound but near-zero-DRAM phase can be frequency-sensitive in reality, yet MBU labels it insensitive and the policy down-clocks it. The paper only nods at communication-bound 0%-memory phases as future work. Keep as-is for baseline contrast.

3. **`Mem_high` and `Mem_low` averaging window (literal "same window of time").**
   - Paper Section 5.2 specifies both memory-utilization measurements are taken over "the same window of time" (the phase window).
   - Current policy treats one `MetricWindow` as the characterization window.
     With the runner default `CONTROL_WINDOW_SECONDS = 5.0`, `Mem_high` and
     `Mem_low` are both 5s windows and match the paper's "same window of time"
     statement at the policy level.
   - If you configure `CONTROL_WINDOW_SECONDS = 1.0` and
     `phase_window_seconds = 5.0`, phase detection still uses a 5s rolling
     average, but explicit high/low characterization captures use one 1s
     `MetricWindow` each after the phase is identified. That is a
     higher-fidelity hardware-cadence gap, not a default EVeREST behavior.
   - A stricter implementation could keep the low clock for a full phase window
     while still recording 1s decision averages. That would be a reasonable
     future fidelity improvement, but should be documented separately from
     algorithmic changes.

4. **Phase signature discretization is intentionally simple.**
   - The paper says phases are defined by GPU and memory utilization levels but
     does not specify binning, hashing, idle thresholds, or hysteresis.
   - Current choice: floor GPU and memory averages into buckets sized by the
     change threshold (default 10%) and add an `idle_like` bit using small
     thresholds (`idle_gpu_threshold_pct = 5`, `idle_mem_threshold_pct = 3`).
   - This keeps the baseline transparent and threshold-based. It is not claimed
     to be the authors' exact implementation.

5. **State snapshots are observability artifacts, not EVeREST resume state.**
   - The paper describes one EVeREST instance running per node per job and
     caching phase characterization in that live process.
   - The long-lived `scripts/run/control_loop.py` path matches this model. JSON
     policy-state files are written for inspection, but the live
     `PhaseIdentifier` history and `PhaseCharacterizer` cache are authoritative.
   - Do not compare a restarted legacy single-window hook against the paper
     unless this limitation is explicitly documented.

## 4.6 Known Limitations of EVeREST per Stage (reference for the proposed method)

Each item is framed as: EVeREST's choice -> Limitation -> Opportunity for the proposed method. These are the most defensible angles to differentiate a new method, grounded in the paper text and the reproduced behavior.

1. **Phase Identification.**
   - Fixed global window length (~5s): high reaction latency and, per Section 5.4, phases shorter/more erratic than the window are never detected -> the GPU stays at max -> savings are lost. *Opportunity:* adaptive / multi-scale windowing, or event/kernel-boundary-driven phase detection.
   - Coarse bucketed signature (GPU + memory utilization levels, 10% change threshold): intra-bucket drift collides distinct behaviors, and equal utilization can hide different frequency sensitivities (e.g., compute-bound vs communication-bound). *Opportunity:* richer or learned phase signatures using additional low-overhead counters.
   - Reactive only: a full stable window must be observed before acting, so the first occurrence of every phase runs at max. *Opportunity:* predictive phase recurrence, or persistent cross-run phase memory.
   - Threshold-based change detection with little hysteresis/anti-flap handling. *Opportunity:* principled change-point detection.

2. **Phase Characterization.**
   - Single proxy (memory bandwidth utilization). It breaks for: compute-bound near-zero-DRAM phases (mislabeled `FS=0`, see 4.5.2), communication-bound phases (0% memory utilization despite NVLink/PCIe traffic, paper future work), and cache-bound phases. *Opportunity:* fuse a second low-overhead, vendor-portable signal (SM/FP activity, NVLink/PCIe counters) to disambiguate sensitivity.
   - Two-point linear slope: `FS` is derived from `f_high` plus one `f_low` assuming performance varies linearly with frequency (Section 3.3). Non-linear voltage-frequency response introduces error. *Opportunity:* multi-point or curvature-aware characterization; analytic V-F model.
   - Online probe cost: each new phase is deliberately run at `f_low` for one window -> exploration overhead plus a real performance-degradation (PD) hit during the probe; this is the documented gap vs the static oracle (paper Section 7.2: 1.6-2.1% less energy than oracle). *Opportunity:* cheaper or perturbation-free characterization, or hybrid offline+online cached profiles.
   - Characterize-once, cache-forever: no drift detection, re-characterization, or confidence/invalidation -> stale `FS` is reused if behavior changes within a signature bucket. *Opportunity:* confidence-tracked records with periodic re-probe.
   - `Mem_high` and `Mem_low` are one-window captures after set-clock decisions, with no settle retry or invalidation -> actuation latency or phase drift can bias `FS`. *Opportunity:* latency-aware or confidence-aware capture.
   - Current runner coupling: one `MetricWindow` is used as one characterization window. This is faithful with a 5s `MetricWindow`, but does not exactly reproduce the paper's raw 1ms/10ms sampling plus 1s decision-average cadence. *Opportunity:* separate raw telemetry sampling, 1s decision aggregates, and 5s characterization windows.

3. **Frequency Scaling.**
   - Open-loop per phase: the target is computed once from the model and held; there is no closed-loop correction against measured wall-clock performance, so if MBU mispredicts, the PD guarantee silently breaks (the policy's PD-violation tracking is observational, not corrective). *Opportunity:* feedback control that corrects toward the realized performance target.
   - Performance is enforced through the MBU model, not measured performance. *Opportunity:* combine the model with a lightweight runtime performance signal.
   - Hard floor at `0.55 * f_max`: caps achievable savings on deeply memory-bound phases that could tolerate lower clocks (Section 3.3 V-F rationale). *Opportunity:* device/phase-aware floor.
   - Single actuation knob (graphics clock only): ignores memory clock, power capping, and multi-GPU power redistribution (which EAR performs). *Opportunity:* joint core+memory-clock or power-cap control, and node-level budget allocation.
   - Round-up-only quantization biases slightly toward performance over savings (minor and intentional).

4. **Systemic / cross-cutting.**
   - Single-process, single-GPU assumption with GPU-wide metrics: cannot attribute utilization to co-located applications, so space-sharing breaks per-application PD guarantees (paper future work). *Opportunity:* per-application attribution under sharing.
   - Actuation latency ignored: decisions assume the next characterization window reflects the requested clock; transition/ramp is not modeled and the faithful baseline deliberately does not guard against it. *Opportunity:* latency-aware scheduling of clock changes.
   - Hyperparameter sensitivity: window length, change threshold, low-probe ratio, and the 55% floor are hand-tuned constants (A100 / MI250X). *Opportunity:* auto-tuning and robustness analysis.
   - A single scalar PD target: no per-phase or time-varying performance budget. *Opportunity:* allocate the PD budget across phases to spend it where it yields the most energy savings.

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
3. `UTIL_POLICY`:
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
│   │   ├── local_reproductions/
│   │   │   ├── everest_reimpl/
│   │   │   │   ├── docs/
│   │   │   │   ├── paper/
│   │   │   │   ├── phase_identification/
│   │   │   │   ├── phase_characterization/
│   │   │   │   ├── frequency_scaling/
│   │   │   │   └── policy.py
│   │   │   ├── ali_2022_reimpl/
│   │   │   └── oracle_static/
│   │   └── proposed_methods/
│   │       └── my_method/
├── config/
│   ├── common/
│   ├── platforms/
│   ├── workloads/
│   ├── experiments/
│   └── algorithms/
│       ├── everest/
│       ├── oracle_static/
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
    ├── EXPERIMENT_ORCHESTRATION_MODEL.md
    └── EXTERNAL_BENCHMARK_IMPORT_RULES.md
```

Implementation mapping for EVeREST:

1. EVeREST-specific logic is in `src/methods/comparison_methods/local_reproductions/everest_reimpl`.
2. Shared sampling/actuation/runner infrastructure stays in `src/common`.
3. Comparison baselines and reimplemented methods live in `src/methods/comparison_methods/*` and reuse the same runner contracts.
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
3. Baseline implementation uncertainty (Ali details and utilization-policy choices).
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
