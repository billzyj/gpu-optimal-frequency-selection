# Scripts

Operational scripts used by experiments, controlled runs, artifact collection,
and future reproduction workflows.

## Layout

1. `run`: implemented controlled-mode entrypoints and runner helpers.
2. `setup`: reserved for lightweight environment setup only.
3. `sweep`: reserved for parameter/frequency sweeps.
4. `collect`: reserved for result aggregation and normalization.
5. `reproduce`: reserved for paper-oriented reproduction wrappers.
6. `update_submodules.sh`: updates external benchmark submodule pointers for
   reproducible dependency bumps.

## Current Status

`scripts/run` is the only implemented script area today. The other directories
are placeholders for future work and should not be treated as stable APIs.

## Boundary Rules

1. Do not add benchmark installation or site-specific deployment logic here;
   that belongs in `external/repacss-benchmarking`.
2. Do put local orchestration glue here when this repository owns the top-level
   job lifecycle.
3. Keep shared Python helper logic small and dependency-light.
4. If a script produces experiment artifacts, write them under `artifacts/` or
   the configured `RUN_DIR`, not beside the script.
