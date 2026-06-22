# Source Tree

`src` contains executable research code that is part of this paper-specific GPU
DVFS framework.

## Subdirectories

1. `common`: algorithm-agnostic contracts and runtime building blocks.
2. `methods`: all comparable policies and method implementations.

## Current Implementation Shape

```text
src/
|-- common/
|   |-- experiment/  # implemented shared lifecycle/data/validation contract
|   |-- telemetry/   # implemented env-var provider; hardware providers pending
|   |-- control/     # implemented ClockController + shell-template backend
|   |-- power/       # placeholder for future power/energy helpers
|   |-- io/          # placeholder for future artifact IO helpers
|   `-- cli/         # placeholder for future shared CLI helpers
`-- methods/
    |-- registry.py
    |-- proposed_methods/
    `-- comparison_methods/
        |-- system_baselines/
        |-- local_reproductions/
        `-- external_integrations/
```

## Method Grouping

1. `methods/proposed_methods`: user-proposed methods under development.
2. `methods/comparison_methods/system_baselines`: fixed max/min baselines and
   future simple controls.
3. `methods/comparison_methods/local_reproductions`: locally maintained
   reproductions such as EVeREST, Ali HPEC 2022, and static-oracle.
4. `methods/comparison_methods/external_integrations`: thin adapters for
   directly usable pinned external comparison-method implementations.

## Boundary Rules

1. Shared types and validation belong under `common/experiment`.
2. Telemetry providers must return `MetricWindow` objects and should live under
   `common/telemetry`.
3. Policy heuristics, paper-specific equations, and algorithm state belong under
   `methods`.
4. Benchmark execution details belong in `external/repacss-benchmarking`, not in
   `src`.
5. Runtime entrypoints belong under `scripts/run`, not in `src`.

## Matching Tests

1. `tests/common/experiment` mirrors `src/common/experiment`.
2. `tests/common/telemetry` mirrors `src/common/telemetry`.
3. `tests/common/control` mirrors `src/common/control`.
4. `tests/methods/...` mirrors `src/methods/...`.
5. `tests/scripts/run` mirrors `scripts/run`, because runtime entrypoints are not
   part of `src`.
