# Documentation Map

This directory holds repository-level contracts. Keep the root `README.md`
short; put long-lived architecture and runtime rules here.

All paths below are relative to the repository root.

## Read This First

1. `REPO_ARCHITECTURE.md`: source layout, method taxonomy, test ownership, and
   expansion order.
2. `COMPARISON_METHOD_INTEGRATION_PLAN.md`: public artifact, license,
   direct-call versus reimplementation, and comparator-priority decisions.
3. `EXPERIMENT_ORCHESTRATION_MODEL.md`: controlled-mode job lifecycle,
   environment variables, artifacts, and failure handling.
4. `EXTERNAL_BENCHMARK_IMPORT_RULES.md`: rules for importing and normalizing
   artifacts from external benchmark repositories.

## Related Local Docs

1. `src/methods/README.md`: policy registry, method categories, and add-policy
   checklist.
2. `src/methods/comparison_methods/README.md`: comparison-method boundaries.
3. `src/methods/comparison_methods/local_reproductions/README.md`: citation
   ledger and local reproduction rules.
4. `config/README.md`: policy/platform/workload/experiment config ownership.
5. `config/algorithms/README.md`: per-policy config schemas.
6. `scripts/run/README.md`: Slurm and local controlled-mode runner usage.
7. `tests/README.md`: test layout and discovery commands.

## Boundary Summary

1. Algorithm logic lives under `src/methods`.
2. Shared runtime contracts live under `src/common`.
3. Top-level orchestration lives under `scripts/run`.
4. External benchmark execution details live under `external/`.
5. Generated results live under `artifacts/` and processed analysis under
   `analysis/`.
