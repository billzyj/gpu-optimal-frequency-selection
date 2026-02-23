# GPU Optimal Frequency Selection

This repository is organized as a **multi-algorithm GPU DVFS research framework**.

The architecture separates:

1. Algorithm-specific implementation (`src/everest`, `src/custom`, `src/baselines`).
2. Shared runtime and experiment infrastructure (`src/common`).
3. Shared experiment assets (`config`, `scripts`, `analysis`).

This lets you:

1. Reproduce EVeREST cleanly.
2. Compare against baselines with the same pipeline.
3. Add your own algorithm without restructuring the repository.

## Repository layout

```text
.
├── src/
│   ├── common/        # Shared telemetry/control/experiment modules
│   ├── everest/       # EVeREST reproduction implementation
│   ├── baselines/     # Baseline policies (max_freq, oracle, util, ali_fp_proxy)
│   └── custom/        # Your algorithms and templates
├── config/            # Shared configs for platforms/workloads/experiments/algorithms
├── scripts/           # Shared setup/run/sweep/collect/reproduce entry scripts
├── analysis/          # Shared schema, notebooks, plots, reports
├── artifacts/         # Raw/processed outputs and generated figures
├── references/        # Papers and extracted texts
└── docs/              # Design and reproduction documents
```

## Key docs

1. `docs/REPO_ARCHITECTURE.md`: full architecture and extension workflow.
2. `docs/EVEREST_REPRODUCTION_PLAN.md`: EVeREST-focused reproduction plan.
