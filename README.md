# GPU Optimal Frequency Selection

A multi-method GPU DVFS research framework with three goals:

1. Reproduce published methods (EVEREST, Ali proxy, EAR, Oracle).
2. Compare methods under one unified experiment protocol.
3. Iterate quickly on a proposed method.

Agent interaction and generation rules are defined in `AGENTS.md`.

## 1. Architecture Overview

The repository uses a four-layer separation:

1. Method layer: `src/methods/*`
2. Shared runtime/contracts layer: `src/common/*`
3. Experiment assets layer: `config`, `scripts`, `analysis`, `artifacts`
4. Third-party sources layer: `third_party/*` (recommended for external code such as EAR)

### Method taxonomy

1. `system_baselines`: simple controls (`max_freq`, `min_freq`, util policy)
2. `reimplemented_methods`: paper-method re-implementations (`everest_reimpl`, `ali_reimpl`, `oracle_static`)
3. `third_party`: wrappers for out-of-process systems (`ear_external`)
4. `proposed_methods`: your new method (`my_method`)

## 2. Source Tree (Current)

```text
src/
├── common/
│   ├── experiment/      # shared interfaces/types/decision validation
│   ├── telemetry/       # hardware metric adapters (vendor-specific implementations)
│   ├── control/         # clock/power control adapters
│   ├── power/           # power/energy collection adapters
│   └── io/              # shared IO helpers for artifacts
├── methods/
│   ├── system_baselines/
│   │   ├── max_freq/
│   │   ├── min_freq/
│   │   └── util_policy/
│   ├── reimplemented_methods/
│   │   ├── everest_reimpl/      # implemented core stages
│   │   ├── ali_reimpl/          # placeholder
│   │   └── oracle_static/       # placeholder
│   ├── third_party/
│   │   └── ear_external/        # external-process wrapper skeleton
│   └── proposed_methods/
│       └── my_method/
```

## 3. Interfaces

### Online methods (window-level)

`src/common/experiment/interfaces.py` defines:

1. `AlgorithmInterface`
   - `initialize(context, config) -> AlgorithmState`
   - `on_window(metrics, state) -> Decision`
   - `finalize(state) -> FinalSummary`

This is used by:

1. `system_baselines`
2. `reimplemented_methods/everest_reimpl`
3. `reimplemented_methods/ali_reimpl`
4. `proposed_methods/my_method`

### External methods (job-level)

`src/common/experiment/interfaces.py` also defines:

1. `ExternalMethodInterface`
   - `run_external(context, config) -> ExternalRunResult`

This is used by:

1. `third_party/ear_external`

External methods run as separate processes (for example Slurm/EAR commands), then normalize outputs to repository artifacts.

## 4. EVEREST Implementation Boundary

Implemented now:

1. `Phase Identification`
2. `Phase Characterization`
3. `Frequency Scaling`
4. Unit tests for formulas and edge cases

Not implemented yet:

1. EVEREST online `policy` orchestration loop
2. Hardware telemetry/control integration (DCGM/NVML/ROCm SMI)
3. End-to-end runner integration with `scripts` and `config`

## 5. EAR Integration Recommendation

1. Keep EAR source in `third_party/ear` (git submodule, pinned commit/tag).
2. Keep Python wrappers in `src/methods/third_party/ear_external`.
3. Do not mix EAR C source into `src/`.
4. Normalize EAR outputs to the same processed schema used by online methods.

## 6. Quick Start

1. Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

2. Run unit tests:

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

## 7. Next Priorities

1. Implement EVEREST `policy` in `src/methods/reimplemented_methods/everest_reimpl/policy`.
2. Implement `oracle_static` and simple baselines (`max_freq`, `min_freq`).
3. Implement `ear_external` launcher/parser/adapter wiring.
4. Add unified run entry points in `scripts/run` for online and external methods.
5. Freeze output schema in `analysis/schema`.

## 8. Key Docs

1. `docs/REPO_ARCHITECTURE.md`: architecture and extension workflow.
2. `docs/EVEREST_REPRODUCTION_PLAN.md`: EVEREST methodology and staged implementation plan.
