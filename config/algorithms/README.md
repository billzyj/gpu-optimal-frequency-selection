# Algorithm Configs

This directory documents policy-specific config accepted by
`scripts/run/control_loop.py` through `POLICY_CONFIG_PATH` or
`POLICY_CONFIG_JSON`.

## Directories

1. `oracle_static/`: offline sweep profiles for the static-oracle baseline.
2. `ali_2022_reimpl/`: fitted model coefficients and target-workload
   max-frequency profiles for Ali HPEC 2022.
3. `everest/`: optional runtime hyperparameters for EVeREST.
4. `my_method/`: reserved config space for the proposed method.

## Rules

1. Keep calibration or profile-generation scripts outside this directory.
2. Store only reusable config examples, schemas, and final run configs here.
3. Keep proposed-method configs separate from comparison-method configs.
4. Prefer JSON for files passed directly to `POLICY_CONFIG_PATH` unless another
   loader is added and tested.
