# Comparison Method Artifact and Integration Plan

Status: implementation-aware audit, refreshed 2026-07-17.

This document records whether the methods added to the manuscript have a public
implementation, whether that implementation can be called from this repository,
and where any future integration or reproduction should live. It is an
artifact-provenance and integration plan. No third-party method source was
imported while producing this audit or the local scaffolds described below.

## 1. Decision Vocabulary

The following labels are used throughout this plan:

1. **Pinned external sidecar**: run an upstream executable or daemon at a fixed
   commit and keep local code limited to lifecycle, configuration, logging, and
   result parsing. The upstream process may need exclusive ownership of clock
   actuation.
2. **Thin library adapter**: import a stable upstream API and translate its
   inputs and outputs to local contracts without changing its algorithm.
3. **Paper-guided local reproduction**: implement the published algorithm in
   this repository because the public artifact is absent, incomplete, not
   licensed for the intended reuse, or incompatible with the local runtime
   boundary.
4. **Component-only adaptation**: expose a model, estimator, or partitioner for
   analysis or for use by another policy. A component is not registered as a
   runnable policy unless a paper-defined selection rule is also implemented.
5. **External characterization tool**: run a tool outside the policy registry
   to produce platform inputs such as a transition-latency matrix.
6. **Related-work only**: retain the method as a novelty or scope boundary; do
   not claim an executable comparison.

"No implementation located" means that no author- or lab-official public
artifact was found in the paper, author pages, organization repositories, or
exact-title/DOI searches performed for this audit. It is not a claim that no
private, archived, or newly released artifact exists.

### 1.1 Current local scaffold status

The following repository work is complete as of this refresh:

1. `PerformanceTargetType` distinguishes `runtime_slowdown`,
   `relative_performance_loss`, and `none`; conversions are unit-tested and the
   raw plus normalized values are written to each run manifest.
2. Oracle Static consumes the normalized minimum-performance ratio, while
   EVeREST consumes normalized relative performance loss and uses the minimum
   ratio for violation tracking.
3. `src/methods/comparison_methods/contracts.py` records integration route,
   implementation state, actuation owner, required telemetry/control knobs,
   and required artifacts. Its registered entries are tested against the
   policy registry, and its preflight helper reports capability gaps.
4. `local_reproductions/energyucb_reimpl/` contains an independently written,
   equation-tested algorithm core for the reward equation, optimistic
   initialization, empirical updates, standard and switching-aware UCB indices,
   deterministic tie handling, and the QoS feasible set.

The EnergyUCB scaffold is intentionally not a policy and is not registered.
GEEPAFS, DRLCap, SYnergy, and LATEST likewise have no runnable local package or
registry entry. Irregular clock grids, automatic startup preflight, typed
hardware telemetry, an external-controller runner mode, and hardware validation
remain open.

## 2. Repository Compatibility Gaps

The current `AlgorithmInterface` is suitable for an online Python policy that
consumes one `MetricWindow` and emits one graphics-clock `Decision`. The newly
reviewed methods expose several gaps that should be resolved before adding
registry entries.

### 2.1 Target semantics

`ExperimentContext` now pairs the legacy raw `pd_target` value with an explicit
target type:

1. `runtime_slowdown`
2. `relative_performance_loss`
3. `none`

Direct programmatic construction defaults to historical
`relative_performance_loss` semantics for compatibility. The environment-driven
runner defaults `PERFORMANCE_TARGET_TYPE` to `runtime_slowdown`, matching the
manuscript evaluation, and should set the variable explicitly in archived
experiment definitions. Every run manifest records the type, raw value, runtime
slowdown, relative performance loss, and minimum performance ratio. For
runtime-slowdown target `delta`, the latter two are `delta / (1 + delta)` and
`1 / (1 + delta)`. Reward and energy/performance trade-off parameters remain
method configuration and must not be silently mapped to a slowdown bound.

### 2.2 Clock grid and action space

`PlatformSpec` currently assumes a minimum, maximum, and uniform step. Real GPU
clock grids can be irregular. Add an explicit supported graphics-clock list and
make decision validation use membership when that list is available.

The current `Decision` cannot express memory-clock changes, power caps, active
compute-unit states, or memory-bandwidth states. Do not describe a core-only
projection as a faithful reproduction of a method that jointly controls these
knobs. Extend the action contract first, or label the result as a reduced-scope
proxy with a different policy name.

### 2.3 Capability and telemetry declarations

The initial machine-readable declarations in `contracts.py` cover:

1. required telemetry fields;
2. required offline profiles, models, checkpoints, or other artifacts;
3. required control knobs;
4. local, upstream, or no actuation ownership;
5. integration route, implementation state, and any stable registry name.

`assess_admission()` checks declared fields, knobs, artifacts, and external
controller mode against supplied runtime capabilities. It is not yet wired into
policy/controller startup, does not yet model vendor/cadence constraints, and
therefore remains a scaffold rather than an experiment-readiness gate.
`custom_metrics` may carry experimental fields during development, but
production hardware providers and contract tests must define units and
missing-data behavior.

### 2.4 External controller ownership

Some upstream artifacts combine telemetry, policy logic, and privileged
actuation in one daemon. Add an explicit external-controller run mode before
using one:

1. exactly one process owns clock changes;
2. the local `ClockController` is disabled for that run;
3. requested decisions are parsed when the upstream artifact exposes them;
   independently sampled observed clocks are always logged, and an unavailable
   request is recorded as `requested_unknown`;
4. stop, failure, signal, and reset behavior are tested;
5. the upstream commit, local patch/config, and privilege path are recorded.

This mode is different from a normal `AlgorithmInterface` policy and must be
visible in the run manifest.

### 2.5 Training and offline-cost provenance

For learned and profile-guided methods, record training applications, target
GPU, tool versions, feature mappings, hyperparameters, model/checkpoint hashes,
training time and energy, and whether evaluation workloads were excluded from
training. Report offline cost separately from online policy cost.

## 3. Public Artifact and Integration Matrix

### 3.1 Application-transparent online methods

| Method | Public artifact audit | Can it be called directly? | Repository decision |
|---|---|---|---|
| GEEPAFS | The [official GEEPAFS repository](https://github.com/zyjopensource/geepafs) contains the C/NVML and Python/DCGM implementations, launch and post-processing scripts, latency tools, and sample workloads under the MIT license. It was validated on V100/A100 and contains device-specific constants. Audited upstream commit: `e3680ba393abaa45f999d5454c99b883d4c4d5c2`. | Not as a Python policy import. Both implementations own actuation, and the C version is documented as a long-running daemon. The target GPU clock grid and constants must be calibrated. GEEPAFS `p90` is a minimum performance-ratio target of `0.90`, which corresponds to a runtime-slowdown bound of about `11.11%` under inverse-progress assumptions, not `10%`. At the audited commit, the C CLI hard-codes `p85`, `p90`, and `p95`; the Python CLI accepts a floating percentage. | **Prefer a pinned external sidecar after a port-feasibility gate.** Future paths: `external/geepafs/` plus `src/methods/comparison_methods/external_integrations/geepafs/`. Configuration/device-constant and target-parser patches may remain an external integration; any algorithmic rewrite triggers reclassification as a local reproduction. Add exclusive-controller lifecycle, parser, reset, target-GPU calibration, and contract tests. Required comparison, first new-method priority. |
| EnergyUCB | The [official EnergyUCB repository](https://github.com/XiongxiaoXu/EnergyUCB-Bandit) is Apache-2.0. Its single Python program samples Gaussian rewards from per-application pickle files that are not included. It contains the earlier exploration/UCB loop, but not the [final paper's](https://arxiv.org/abs/2410.11855) optimistic initialization, switching-aware index, QoS feasible set, live telemetry, or actuation. Audited upstream commit: `a3b24fdb45a201aa1a3d71e120e6de7f73c7d6a4`. | No. The released script is an incomplete offline replay and cannot run from the repository as published because the expected trace directories are absent. The final paper's QoS quantity `1 - p_i / p_max` is relative performance loss even when described as slowdown; map a runtime target `delta` to `delta / (1 + delta)`. | **Paper-guided local reproduction.** The independently written `energyucb_reimpl/` equation core now implements and tests the reward equation, optimistic state, empirical updates, standard/switching-aware UCB, deterministic selection, and the QoS feasible set. It remains deliberately unregistered until live reward/progress telemetry, action-space mapping, control-loop lifecycle, configuration/provenance, trace validation, and hardware tests exist. No upstream source code was copied. |
| DRLCap | The [paper](https://zwang4.github.io/publications/tsusc-2.pdf) links the author [DRLCap repository](https://github.com/yiminga/DRLCap), which contains standalone GPU-specific DDQN save/restore scripts and a one-line README. It has no declared software license, no released checkpoints, no complete training/runtime harness, hard-coded device clocks and absolute paths, and scripts that directly invoke vendor tools. Audited upstream commit: `cd2e12c1f69363d26da4c84656eb14bc45487197`. | No. No public license grant was found, so do not vendor, modify, or redistribute the source without permission. The artifact is also operationally incomplete, and the paper requires per-architecture training and online updates. | **Conditional independent paper-guided reproduction, otherwise blocked.** First request a license, checkpoints, and complete instructions from the authors. If those remain unavailable, proceed only with an independently written implementation that does not copy the unlicensed source and only if the training budget and target-architecture retraining can be reported. Keep DRLCap optional in the evaluation plan. |
| Gupta et al. online model | No author-official implementation was located for [the adaptive online GPU performance model](https://arxiv.org/abs/2003.11740). The method predicts frame time and sensitivity on integrated mobile GPUs using interval counters and online RLS-style adaptation. | No. It is a performance estimator, not a complete generic-HPC frequency-selection policy, and its original counter/kernel instrumentation does not map directly to current server GPUs. | **Component-only independent adaptation.** A future `gupta_rls_adaptation` may implement the published update rule behind a feature-provider interface. Do not register it as a policy or call it an exact reproduction without the original counter semantics and a paper-defined selector. |
| Harmonia | No public implementation was located on the [Georgia Tech CASL publication surface](https://casl.gatech.edu/publications/) or author materials. Harmonia coordinates compute frequency, active compute units, and memory bandwidth using online sensitivity predictors. | No. The current target-platform and repository control surfaces expose only graphics clock, not Harmonia's active-compute-unit and memory-bandwidth-state controls. | **Related-work only.** A graphics-clock-only controller would be Harmonia-inspired new work, not an executable Harmonia baseline. |

### 3.2 Offline, model-based, and structure-aware methods

| Method | Public artifact audit | Can it be called directly? | Repository decision |
|---|---|---|---|
| DSO | The [DSO paper](https://arxiv.org/abs/2407.13096) and author publication pages provide no code or trained model. Reproduction requires eight DCGM features, a PTX parser, full-frequency microbenchmark data, seven fitted model parameters, and a trained MLP. | No. Neither the feature/training pipeline nor the trained artifact is public. | **Defer full reproduction.** A future `dso_equation_reimplementation` may expose the published equation and a pluggable parameter provider, but it remains component-only and must not be labeled equivalent DSO until the PTX/DCGM training pipeline is reproduced and validated. |
| Phase-Based Frequency Scaling | No complete IPDPS 2025 artifact is linked from the [paper](https://biagiocosenza.com/papers/CarpentieriIPDPS25.pdf). At audited commit `21495146179da264fa5ba9c24ab43cf5de3e80f6`, the official MIT [`dev/phase-aware` prototype](https://github.com/unisa-hpc/SYnergy/tree/dev/phase-aware) has core phase selection returning an empty result and several data/overhead paths marked TODO. | No. The inspected prototype is not a runnable implementation of the published DP/greedy/clustering method. The paper also needs a profiled SYCL DAG, loop counts, per-frequency time/energy, transition overhead, and optional MPI nodes. Re-audit the branch before any future use. | **Conditional paper-guided component reproduction.** Implement and test the partitioner over a neutral trace/DAG schema only if the evaluation expands to application-integrated SYCL/MPI methods. It is not a default application-transparent comparator. |
| SYnergy | The [official SYnergy library](https://github.com/unisa-hpc/SYnergy) and [SYnergy model repository](https://github.com/unisa-hpc/SYnergy-models) are MIT licensed. Audited commits `db52f4a589f5c4c851cbbab0fac85b6a402b235a` and `1e40e24d6193aa88876f223cc634ef396746aca3` provide a SYCL queue abstraction, vendor backends, LLVM feature extraction, and model tooling. | Designed for a compatible C++ SYCL application and toolchain; current executability was not validated in this audit. It cannot be imported as a policy for arbitrary CUDA binaries or the current Python control loop, and each GPU needs model/training support. | **Optional external SYCL-native harness, not a registry policy.** Pin the licensed library/model repositories only if SYCL workloads become an evaluation axis. Invoke through a standalone workload harness and import results; do not rewrite it into a superficially equivalent Python policy. Re-audit before pinning a later revision. |
| CRISP | No official public code was located for the [CRISP paper](https://cseweb.ucsd.edu/~tullsen/micro15.pdf). Its evaluated design uses GPU-internal critical/stalled-path signals and simulator/hardware modifications that NVML/DCGM do not expose. | No, not on the target hardware. Exact reproduction is a separate GPGPU-Sim/GPUWattch or hardware-design track. | **Related-work only.** An offline CRISP-inspired model must be given a different name and cannot serve as a target-hardware runtime baseline. |
| Predictable GPUs | No official code, training data, or model was located for the [ICPP 2019 method](https://www.cosenza.eu/papers/FanICPP19.pdf). The paper requires a custom LLVM/OpenCL feature pass, generated microbenchmarks, thousands of core/memory-frequency training samples, SVR models, and Pareto extraction on Maxwell hardware. | No. A faithful result would require a high-cost, hardware-specific offline reproduction and memory-clock control. | **Separate offline reproduction track only if needed.** Exclude it from the default online comparator suite. Report any future implementation as a local reproduction with its complete training cost and hardware deviations. |
| Wang--Chu core/memory model | At audited commit `bc70c555d590be38900eff55300d61dc18e56aea`, the author/lab [NV-DVFS-Benchmark repository](https://github.com/HKBU-HPML/NV-DVFS-Benchmark) contains collection, extraction, and analytical-model scripts plus sample data. It has no declared license and targets Python 2.7, CUDA 9/10, legacy profiling tools, and hard-coded older-GPU parameters. | Current executability was not validated. No public license grant was found, so do not vendor, modify, or redistribute the source without permission. It is also a model workflow, not a runtime selection policy. | **Component-only independent paper-guided reproduction.** Reimplement the published equations in Python 3 without copying the unlicensed source and validate against public sample data. Keep it unregistered unless a separately defined selector is added. A core-only slice must be labeled as a deviation from the core-plus-memory model. |

### 3.3 Domain-specific policy and measurement support

| Method/tool | Public artifact audit | Can it be called directly? | Repository decision |
|---|---|---|---|
| SLO-Aware GPU DVFS for LLM serving | No accessible code was located for the exact [IEEE CAL 2024 method](https://ieeexplore.ieee.org/document/10540202/). A later throttLL'eM paper cited a repository that is currently unavailable; the later system must not be conflated with the four-author CAL paper. | No. The method needs iteration-level LLM-server hooks, model/workload profiling, serving SLO state, and a domain-specific latency predictor. | **Defer unless LLM serving is a core workload axis.** If enabled later, implement a domain-specific serving adapter and evaluate it only on the supported serving stack; do not present it as a generic HPC policy. |
| Velicka et al. / LATEST | The paper identifies the official [LATEST GitLab project](https://code.it4i.cz/energy-efficiency/latest). Audited main commit `27c720e7b6dd8d5f7d0389bf03364efe0013ab2b` and CUDA commit `fff3655294382fe992ef0908a3ac6d947d8f25b8` contain CUDA/NVML measurement code and CSV analysis. No public software-license grant was found, while the [published dataset](https://zenodo.org/records/17228576) is CC-BY-4.0. The inspected public code did not expose the complete indirect-switch optimization path described by the later paper. | Current executability was not validated. Treat it as a future user-supplied executable subject to installation and privilege validation; do not copy or vendor its source without permission. It is a characterization tool, not a frequency-selection baseline. | **External characterization tool.** Put a future launcher under `scripts/sweep/gpu_switching_latency/` and CSV normalization under `scripts/collect/gpu_switching_latency/`. Use the matrix as platform input; independently implement and test any indirect-transition path search. Re-audit before using a later revision. |

## 4. Planned Repository Routing

Do not create empty method packages or registry entries merely because a paper
appears in the manuscript. The intended routing is:

```text
external/
`-- geepafs/                                      # future pinned MIT submodule

src/methods/comparison_methods/
|-- external_integrations/
|   `-- geepafs/                                  # sidecar lifecycle + parser
`-- local_reproductions/
    |-- energyucb_reimpl/                         # equation core; policy pending
    |-- drlcap_reimpl/                            # conditional independent rewrite
    |-- gupta_rls_adaptation/                     # optional component, unregistered
    |-- wang_chu_model_reimpl/                    # optional component, unregistered
    |-- phase_based_reimpl/                       # optional DAG component
    `-- dso_equation_reimplementation/            # deferred component

scripts/sweep/
`-- gpu_switching_latency/                        # future LATEST CLI boundary

scripts/collect/
`-- gpu_switching_latency/                        # future CSV normalization
```

The optional SYnergy path should remain outside the normal Python policy
registry: pin its licensed repositories under `external/`, build a SYCL-native
workload harness, and import completed results through the external-artifact
contract.

## 5. Implementation Sequence and Gates

### Gate 0: Correct shared contracts

1. **Complete:** explicit target semantics, unit-tested conversions, and
   manifest normalization.
2. **Pending:** explicit supported clock grids.
3. **Partial:** method capability declarations and deterministic preflight
   reporting exist, but startup enforcement and vendor/cadence constraints do
   not.
4. **Specified, not implemented:** external-controller ownership and
   failure/reset behavior.
5. **Pending:** typed telemetry schemas for method-specific counters.
6. **Pending decision:** whether multi-knob actions are in scope; do not add
   them implicitly.

Exit condition: incompatible methods fail at initialization with an actionable
capability report, and all run manifests preserve target and action semantics.

### Gate 1: Establish hardware truth

1. Implement and validate NVIDIA/AMD telemetry and clock backends.
2. Discover and record actual supported clocks and privileges.
3. Measure request, transition, and total settling latency for the clock pairs
   policies will use, optionally through user-installed LATEST.
4. Validate existing `max_freq`, `min_freq`, `oracle_static`, `everest`, and
   `ali_2022_reimpl` paths before adding more algorithms.

Exit condition: request availability/status, independently observed clocks,
energy samples, reset state, and failure modes are demonstrated on target
hardware.

### Gate 2: Integrate required GEEPAFS

1. Pin the audited upstream commit or a later explicitly reviewed commit.
2. Complete a target-GPU feasibility check. Keep the pinned upstream checkout
   pristine and express device-constant/configuration changes as a documented
   patch with a hash, applied in a build workspace. If the port requires an
   algorithmic rewrite, reclassify it as a local reproduction.
3. Convert the manuscript runtime-slowdown target to GEEPAFS's minimum
   performance-ratio threshold and record both values. Prefer the Python CLI's
   floating target; if the C CLI is used, patch only its target parser or record
   the effective, potentially mismatched target selected from `p85`, `p90`, and
   `p95` and do not label that run as an exact target match.
4. Run the feasible upstream port in exclusive external-controller mode.
5. Parse upstream decisions when exposed; otherwise record
   `requested_unknown`. Independently sample the observed clock and align it
   with local window/run artifacts.
6. Test normal exit, early controller exit, signal handling, benchmark failure,
   benchmark termination, and final clock reset.
7. Validate the port on each target architecture before reporting results.

Exit condition: the upstream policy runs end to end, its device changes are
fully disclosed, and no local process competes for actuation.

### Gate 3: Reproduce final EnergyUCB

1. **Algorithm-core complete:** translate the final paper's reward,
   initialization, empirical update, UCB index, switching term, deterministic
   selection, and QoS feasible-set equations into pure helpers.
2. **Complete for the current core:** add switch-penalty,
   QoS-feasible-set, initialization, update, validation, and tie-breaking tests.
3. **Shared conversion complete:** map each manuscript runtime-slowdown target
   `delta` to the paper-native relative performance loss
   `delta / (1 + delta)` and test both directions. The EnergyUCB QoS helper
   accepts only the already-normalized loss budget.
4. **Pending:** define the reward measurement and live core/uncore utilization
   mapping per vendor and record any proxy.
5. **Pending:** add configuration/state orchestration, completion/progress
   estimation, a policy wrapper, capability-enforced initialization, and clock
   actuation.
6. **Pending:** validate offline on controlled traces, then in the hardware
   control loop.
7. Keep the official incomplete replay as reference evidence, not the claimed
   implementation.

Exit condition: implementation-to-equation tests, target-semantics tests, and
hardware runs support the exact label `energyucb_reimpl`.

### Gate 4: DRLCap feasibility checkpoint

Proceed only after one of the following is true:

1. the authors provide a usable license, complete training/runtime code, and
   checkpoints; or
2. an independently written, paper-guided implementation that does not copy the
   unlicensed source and a per-architecture retraining budget are approved, and
   training provenance can be reported.

Otherwise keep DRLCap as a conditional literature comparator and narrow the
experimental claim rather than presenting the public scripts as executable.

### Gate 5: Optional scope expansions

Only after the central application-transparent comparison is complete:

1. add Phase-Based/SYnergy if SYCL, DAG, or MPI-integrated evaluation is in
   scope;
2. add Predictable GPUs, DSO, or Wang--Chu as an offline modeling track;
3. add the SLO-aware method only for an explicit LLM-serving experiment;
4. keep CRISP and Harmonia as related-work boundaries unless a separate
   simulator or multi-knob hardware study is approved.

## 6. Registry Admission Checklist

A new stable `POLICY_NAME` may be added only when all of the following are true:

1. The artifact is a selection policy, not only a model, library, dataset, or
   measurement tool.
2. The exact upstream commit and license, or the local reproduction citation
   and deviations, are recorded.
3. Required telemetry, action knobs, target semantics, and offline inputs pass
   preflight validation.
4. Initialization, at least one decision path, finalization, and failure/reset
   behavior have tests.
5. Hardware validation distinguishes algorithm-interface correctness from
   paper fidelity and empirical effectiveness.
6. README, config schema, method ledger, runner docs, and manuscript status all
   use the same name and implementation label.

Until those conditions are met, the method remains a planned integration,
component, tool, or literature reference and must not appear in the registry's
supported-policy list.
