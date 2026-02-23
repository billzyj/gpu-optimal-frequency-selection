# Repository Architecture

## 1. Objectives

This repository is designed to support three workflows at the same time:

1. Reproduce existing GPU DVFS methods (starting with EVeREST).
2. Benchmark multiple policies under one shared experimental protocol.
3. Rapidly develop and evaluate your own algorithm.

The architecture enforces a strict separation between:

1. Algorithm logic.
2. Shared runtime infrastructure.
3. Shared experiment operations and analysis.

## 2. Directory Design

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
│   ├── everest/
│   │   ├── phase_identification/
│   │   ├── phase_characterization/
│   │   ├── frequency_scaling/
│   │   └── policy/
│   ├── baselines/
│   │   ├── max_freq/
│   │   ├── static_oracle/
│   │   ├── util_policy/
│   │   └── ali_fp_proxy/
│   └── custom/
│       ├── my_algo/
│       └── templates/
├── config/
│   ├── common/
│   ├── platforms/
│   ├── workloads/
│   ├── experiments/
│   └── algorithms/
│       ├── everest/
│       └── my_algo/
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
├── references/
│   └── papers/
└── docs/
```

## 3. Responsibilities by Layer

## 3.1 `src/common` (shared code)

Holds modules reused by all algorithms:

1. Telemetry adapters (NVIDIA/AMD counters).
2. Frequency/power actuation wrappers.
3. Experiment runner primitives (windowing, logging, timing).
4. Common data models and I/O contracts.

Rule: no algorithm-specific heuristics here.

## 3.2 `src/everest` (paper reproduction)

Holds EVeREST-specific logic only:

1. Phase Identification: phase signature and change detection.
2. Phase Characterization: frequency sensitivity from memory utilization.
3. Frequency Scaling: target-frequency computation from FS + PD.

Rule: this directory should mirror EVeREST methodology, not become a generic utility bucket.

## 3.3 `src/baselines` (comparison policies)

Holds baseline implementations under the same runner:

1. `max_freq`
2. `static_oracle`
3. `util_policy` (EAR-like)
4. `ali_fp_proxy` (NVIDIA-oriented proxy)

Rule: each baseline is independently runnable and shares the same output schema.

## 3.4 `src/custom` (your algorithm path)

Holds your future work:

1. `my_algo`: main implementation.
2. `templates`: algorithm scaffolds and interface templates.

Rule: new ideas are implemented here first, then promoted to stable interfaces if needed.

## 3.5 `config`, `scripts`, `analysis` (shared experiment system)

1. `config`: declarative configuration for hardware, workloads, experiments, and per-algorithm parameters.
2. `scripts`: orchestration entry points for setup, run, sweep, and result collection.
3. `analysis`: shared schema, plotting, and report generation for all algorithms.

Rule: these directories are algorithm-agnostic by default.

## 4. Interface Contracts

To keep all algorithms comparable, each policy should expose the same minimal interface:

1. `initialize(context, config)`
2. `on_window(metrics, state) -> decision`
3. `finalize(state) -> summary`

Where `decision` includes:

1. `target_graphics_clock`
2. `reason_code`
3. `debug_fields` (optional)

This contract allows one runner to execute EVeREST, baselines, and custom algorithms uniformly.

## 5. Data and Artifact Conventions

1. Raw run outputs go to `artifacts/raw`.
2. Aggregated tables go to `artifacts/processed`.
3. Generated figures go to `artifacts/figures`.
4. Analysis code must read from artifacts, not from live logs directly.

## 6. Development Flow

1. Add or modify algorithm code in `src/everest`, `src/baselines`, or `src/custom`.
2. Add algorithm config in `config/algorithms/<algorithm_name>/`.
3. Run experiments via `scripts/run` and parameter sweeps via `scripts/sweep`.
4. Collect and normalize outputs via `scripts/collect`.
5. Generate plots/reports from `analysis`.

## 7. Design Principles

1. Reproducibility first: one config should fully describe one experiment.
2. Comparability first: same workload + same protocol + same schema.
3. Extensibility first: new algorithms should not require directory refactoring.
4. Vendor portability: keep NVIDIA/AMD details behind shared adapters.
