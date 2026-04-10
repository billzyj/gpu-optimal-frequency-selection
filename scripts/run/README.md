# Run Scripts

This directory contains top-level experiment entrypoints owned by this repository.

## Controlled Mode Template

- `controlled_mode.sbatch`

Purpose:

1. Submit one top-level Slurm job from this repository.
2. Launch one external benchmark run script as a child process in the same allocation.
3. Run a periodic control-loop hook (`CONTROL_HOOK_CMD`) while benchmark is running.
4. Default hook is `scripts/run/control_hook.py`.

This follows `docs/EXPERIMENT_ORCHESTRATION_MODEL.md`:

1. External repository owns benchmark/site execution adapters.
2. This repository owns algorithm-control orchestration.
3. Bridge layer must not submit nested independent benchmark jobs.

## Usage

Example submit command:

```bash
sbatch --export=ALL,\
BENCH_ID=ior,\
BENCH_RUN_SCRIPT=benchmarks/ior/adapters/repacss/run.sh,\
POLICY_NAME=max_freq,\
PD_TARGET=0.10,\
CONTROL_WINDOW_SECONDS=10 \
scripts/run/controlled_mode.sbatch
```

Optional control hook override:

```bash
sbatch --export=ALL,\
BENCH_ID=hpl,\
BENCH_RUN_SCRIPT=benchmarks/hpl/adapters/repacss/run.sh,\
BENCH_ARGS="4 external/repacss-benchmarking/benchmarks/hpl/inputs/hpl/HPL-small.dat",\
CONTROL_HOOK_CMD='python3 scripts/run/my_control_loop.py' \
scripts/run/controlled_mode.sbatch
```

Default hook behavior (`control_hook.py`):

1. Supports `POLICY_NAME=max_freq|min_freq|oracle_static`.
2. Persists policy state under `<RUN_DIR>/control/policy_state.json`.
3. Appends decisions to `<RUN_DIR>/normalized/decisions.csv`.
4. Writes latest decision snapshot to `<RUN_DIR>/control/last_decision.json`.
5. Applies clock command only when `APPLY_CLOCK_CMD_TEMPLATE` is provided; otherwise runs in dry-run mode.
6. For `POLICY_NAME=oracle_static`, provide profile config via `POLICY_CONFIG_PATH` (JSON file) or `POLICY_CONFIG_JSON`.

## Notes

1. `BENCH_ID` and `BENCH_RUN_SCRIPT` are required.
2. `RUN_ROOT`, `EXPERIMENT_ID`, `SITE_PROFILE`, and `RUN_ID` are exported so external adapters write to deterministic run paths.
3. The default hook runs `control_hook.py`; you can replace it with your own command via `CONTROL_HOOK_CMD`.
