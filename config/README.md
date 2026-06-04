# Configuration

Shared experiment configuration for algorithms, platforms, workloads, and run
matrices.

## Layout

1. `common`: reserved for global defaults such as logging and sampling.
2. `platforms`: reserved for hardware/vendor capabilities.
3. `workloads`: reserved for benchmark input sets and launch metadata.
4. `experiments`: reserved for run matrices and sweep definitions.
5. `algorithms`: per-algorithm parameters.

## Current Status

Most config directories are placeholders. The implemented runner currently reads
configuration from environment variables plus optional policy config supplied
through:

1. `POLICY_CONFIG_PATH`
2. `POLICY_CONFIG_JSON`

Tracked algorithm config documentation:

1. `config/algorithms/README.md`
2. `config/algorithms/oracle_static/README.md`
3. `config/algorithms/ali_2022_reimpl/README.md`
4. `config/algorithms/everest/README.md`
5. `config/algorithms/my_method/README.md`

## Policy Config Ownership

1. `oracle_static` configs should contain offline sweep profiles.
2. `ali_2022_reimpl` configs should contain fitted model coefficients,
   supported frequencies, and max-frequency workload metrics.
3. `everest` configs should contain runtime hyperparameters such as phase
   window, change threshold, low-probe clock, and min ratio of max.
4. Proposed-method configs should be kept separate from reproduced baseline
   configs.

## Next Additions

1. Add platform profiles after real telemetry/control adapters are implemented.
2. Add experiment matrix files after the processed artifact schema is frozen.
3. Prefer JSON for configs passed directly to `POLICY_CONFIG_PATH` unless a
   loader for another format is added and tested.
