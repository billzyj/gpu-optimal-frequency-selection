# Comparison Methods

This directory contains every method used to compare against the user's
proposed GPU DVFS method.

## Categories

1. `system_baselines`: simple baselines implemented directly in this
   repository, such as fixed maximum and minimum clock policies.
2. `local_reproductions`: comparison algorithms implemented and maintained in
   this repository because no directly usable implementation exists, or because
   available code cannot be used unchanged through a thin adapter.
3. `external_integrations`: directly usable existing implementations brought in
   through pinned external repositories and exposed through local adapters.

## Boundary Rules

1. Comparison methods may share `AlgorithmInterface`, `Decision`, and
   `FinalSummary`, but must not depend on `proposed_methods`.
2. Local reproductions should keep source/citation ledgers and reproduction
   notes with the method.
3. External integrations should keep third-party source outside `src`, normally
   under `external/<repo>`, and expose only local adapter code here.
4. Stable policy names are registered in `src/methods/registry.py`; callers
   should not depend on category paths.
