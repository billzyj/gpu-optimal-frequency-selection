# Ali HPEC 2022 Reproduction Plan

## 1. Goal

Reproduce the baseline method from Ali et al. 2022 as a paper-faithful,
model-based GPU frequency selector:

1. Collect workload utilization metrics at the maximum/default GPU core
   frequency.
2. Estimate power and execution time across the supported GPU core-frequency
   design space using the paper's analytical models.
3. Select one whole-workload GPU frequency with EDP or ED2P.
4. Keep this baseline separate from runtime/adaptive improvements proposed by
   this repository.

Repository method name: `ali_2022_reimpl`.

This plan is based on DOI `10.1109/HPEC55821.2022.9926317`, Zotero item
`D9D98WW7`, attachment `XGE3W56U`, and the co-located paper copy at
`../paper/ali_hpec2022_optimal_gpu_frequency_selection.txt`.

## 2. Source-Grounded Scope

The paper frames the method as two phases: model construction and model-based
frequency selection. The extracted text reports that model construction used 11
GPU utilization metrics across the GV100 DVFS design space, collected through
DCGMI at a 20 ms sampling interval and averaged across three runs
(`../paper/ali_hpec2022_optimal_gpu_frequency_selection.txt:176`,
`:180`, `:182`, `:185`). The selected features for the analytical models are
floating-point activity, DRAM activity, and core frequency
(`../paper/ali_hpec2022_optimal_gpu_frequency_selection.txt:196`,
`:201`, `:211`).

The reproduction should treat Ali 2022 as an offline, application-level
baseline. It is not a per-phase runtime policy like EVeREST. It predicts a
frequency for a workload from max-frequency measurements, then applies that
frequency for evaluation.

In this plan, "offline training" means calibration/fitting of analytical model
coefficients, not DNN pretraining. The later Ali ICPP 2023 DNN model is a
separate method variant and should not be merged into this baseline.

## 3. Minimal Baseline to Reproduce

1. **Source cache and traceability.**
   - Use the local PDF and text in `../paper/`.
   - Preserve Zotero trace `topics/power_management`, item `D9D98WW7`,
     attachment `XGE3W56U`.

2. **Frequency space.**
   - For strict numerical reproduction, use NVIDIA GV100 with the paper's
     evaluated range of 510 to 1380 MHz over 117 configurations
     (`../paper/ali_hpec2022_optimal_gpu_frequency_selection.txt:272`,
     `:275`).
   - For this repository's portable harness, record the platform's supported
     frequency list and label results as algorithmic reproduction unless the
     GV100/SPEC ACCEL setup is matched.

3. **Telemetry inputs.**
   - Collect at least floating-point activity and DRAM activity at max/default
     GPU frequency, plus execution time and power reference data.
   - If exact DCGMI fields differ from the current platform, document the field
     mapping explicitly rather than silently substituting broader utilization
     metrics.

4. **Power model.**
   - Implement the paper form `P_f = alpha * FP_act + beta * DRAM_act + gamma *
     f + C`.
   - Fit or load coefficients from the paper artifact/source evidence before
     claiming numerical reproduction.

5. **Performance model.**
   - Implement the paper form `T_f = T_fmax + T_f_delta`, where `T_f_delta` is a
     polynomial in `FP_act` and `delta_f`, and `delta_f = f_max - f`.
   - Use max-frequency execution time as the reference execution time, matching
     the paper's model structure
     (`../paper/ali_hpec2022_optimal_gpu_frequency_selection.txt:257`,
     `:263`, `:270`).

6. **Objective calculation.**
   - Estimate energy for each frequency as `E_f = P_f * T_f`
     (`../paper/ali_hpec2022_optimal_gpu_frequency_selection.txt:289`).
   - Select `argmin(E * T)` for EDP.
   - Select `argmin(E * T^2)` for ED2P, reflecting the paper statement that
     ED2P gives double emphasis to execution time
     (`../paper/ali_hpec2022_optimal_gpu_frequency_selection.txt:266`).

7. **Evaluation artifacts.**
   - Log model inputs, fitted coefficients, supported frequencies, estimated
     power/time/energy for every frequency, selected EDP/ED2P frequencies, and
     measured runtime/energy at the selected frequencies.
   - Compare against max-frequency baseline, not against an improved runtime
     policy.

## 4. Offline Calibration and Runtime Inputs

The HPEC 2022 method requires calibrated analytical coefficients before DVFS
selection can be run. The expected workflow is:

1. **Calibrate on representative benchmarks.**
   - Run DGEMM and STREAM, matching the paper's compute-intensive and
     memory-intensive calibration workloads.
   - Sweep the supported GPU core-frequency design space.
   - For strict paper reproduction, use the GV100 510-1380 MHz range reported in
     the paper; for this repository's harness, record the platform-specific
     frequency list and label the run as an algorithmic proxy if it differs.

2. **Collect calibration measurements.**
   - Record `fp_activity`, `dram_activity`, `sm_app_clock`, `power_usage`, and
     execution time for each calibration run.
   - Preserve the DCGMI/DCGM field mapping and sampling cadence. The paper
     reports 20 ms sampling and three runs.

3. **Fit model coefficients.**
   - Fit `power_coefficients` for:

```text
P_f = alpha * FP_act + beta * DRAM_act + gamma * f + C
```

   - Fit `performance_coefficients` for:

```text
T_f = T_fmax
    + beta1 * FP_act
    + beta2 * delta_f
    + beta3 * FP_act^2
    + beta4 * FP_act * delta_f
    + beta5 * delta_f^2
```

   - Save `frequencies_mhz`, `f_max_mhz`, both coefficient blocks, platform
     metadata, benchmark provenance, and field mappings.

4. **Profile the target workload at max/default frequency.**
   - Run the target workload once at the maximum/default GPU core frequency.
   - Record workload-specific `fp_activity`, `dram_activity`, and `t_fmax_s`.

5. **Run DVFS selection.**
   - Supply the calibration outputs plus target-workload max-frequency profile
     through `POLICY_CONFIG_PATH` or `POLICY_CONFIG_JSON`.
   - Run with `POLICY_NAME=ali_2022_reimpl`.
   - The policy computes one fixed application-level clock and holds it for the
     run.

## 5. Ambiguities and Source-Verification Needs

1. **Model coefficients are not present in the extracted text.**
   - The paper mentions public artifacts at
     `https://github.com/nsfcac/gpupowermodel`
     (`../paper/ali_hpec2022_optimal_gpu_frequency_selection.txt:85`).
   - Before a numerical implementation is called paper-faithful, verify whether
     that artifact provides coefficients, scripts, benchmark data, or exact
     feature names.

2. **Exact DCGMI field mapping needs verification.**
   - The text names `fp active`, `sm app clock`, and `dram active` as prominent
     features, then uses FP activity, DRAM activity, and core frequency in the
     power equation.
   - A reproduction should map these to concrete DCGM/DCGMI fields and record
     any substitutions.

3. **Algorithm 1 appears to need a literal-source audit.**
   - The extracted pseudocode initializes `min` to `0`, then chooses a lower
     EDP score. For positive EDP values this would never update. Treat this as
     an OCR or paper pseudocode issue until verified against the PDF; an
     implementation should use a conventional argmin initialization and note the
     fidelity decision.

4. **Training/evaluation split is easy to blur.**
   - The text says DGEMM and STREAM represent compute- and memory-intensive
     kernels used to model SPEC ACCEL applications, while SPEC ACCEL metrics are
     test data.
   - Do not train on the evaluation workload unless the run is explicitly
     labeled as a calibration or ablation experiment.

5. **"No performance degradation" is not a hard runtime constraint.**
   - The paper selects via EDP/ED2P and reports small or no degradation, but the
     baseline is not a constraint solver with an explicit slowdown cap.
   - Do not add a performance-loss threshold to the baseline unless it is
     documented as a non-paper variant.

## 6. What Not to Add to the Baseline

These may be useful engineering ideas, but they would optimize beyond the Ali
2022 baseline and contaminate comparisons:

1. Runtime phase detection, phase caches, or per-phase clock switching.
2. Online re-fitting or adaptive correction after observing selected-frequency
   performance.
3. Extra objective constraints such as hard slowdown caps, power caps, thermal
   caps, fairness penalties, or confidence bounds.
4. DNN/model-training variants from later Ali et al. papers.
5. Cross-architecture portability features from the later journal extension
   unless clearly labeled as outside Ali HPEC 2022.
6. Additional counters beyond the paper feature set unless used only in an
   improved method or a sensitivity study.
7. Search heuristics that avoid evaluating the full supported frequency list in
   the objective calculation.

## 7. Candidate Improvement Space for This Repository's Method

Keep these ideas out of `ali_2022_reimpl` baseline behavior, but preserve them as
contrast points for the user's own method:

1. **Runtime adaptation.**
   - Add phase-aware or interval-aware frequency updates when a workload changes
     behavior during execution.

2. **Bounded-performance objectives.**
   - Select frequencies under an explicit slowdown budget rather than relying on
     EDP/ED2P to indirectly protect performance.

3. **Portable telemetry abstraction.**
   - Learn robust mappings across NVIDIA DCGM, NVML, ROCm SMI, and application
     counters while reporting confidence in substituted features.

4. **Uncertainty-aware decisions.**
   - Track prediction error and avoid aggressive down-clocking when the model is
     outside its training domain.

5. **Low-cost calibration.**
   - Replace full DGEMM/STREAM design-space fitting with a small number of
     platform calibration probes, while making that a new method rather than an
     Ali baseline change.

6. **Hybrid offline/online validation.**
   - Use the Ali model as the initial frequency predictor, then add measured
     feedback only in a separate improved policy.

## 8. First Implementation Checkpoints

1. Implement a pure objective-selection helper that takes already-estimated
   `(frequency, power, time)` rows and returns EDP and ED2P argmins.
2. Add a model container for coefficients, but leave coefficient values unset
   until source/artifact verification is complete.
3. Add a run log schema that records whether a run is `paper_faithful_gv100`,
   `algorithmic_proxy`, or `improved_method`.
4. Add tests for EDP/ED2P selection on synthetic data before any hardware
   integration.
