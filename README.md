# GPU Optimal Frequency Selection

Paper-specific GPU DVFS research code for one workflow:

1. Reproduce comparison methods and baselines.
2. Run them under a shared experiment protocol.
3. Keep the proposed method separate while it is still evolving.

## Current Status

Implemented:

1. Shared `AlgorithmInterface`, decision types, and validation.
2. `EnvTelemetryProvider` for dry-runs and unit tests.
3. Runtime policy registry in `src/methods/registry.py`.
4. Comparison policies: `max_freq`, `min_freq`, `oracle_static`,
   `everest`, and `ali_2022_reimpl`.
5. Long-lived controlled-mode runner in `scripts/run/control_loop.py`.
6. Unit tests for policies, telemetry, validation, and runner behavior.

Still pending:

1. Hardware-backed telemetry and clock-control adapters.
2. Import/normalization helpers for external benchmark artifacts.
3. Frozen processed-result schema under `analysis/schema`.
4. End-to-end hardware validation on a real benchmark.

## Layout

```text
src/
|-- common/        # shared runtime contracts, types, telemetry interfaces
`-- methods/       # proposed method plus comparison methods

scripts/run/       # controlled-mode Slurm and local runner entrypoints
config/            # policy, platform, workload, and experiment config
tests/             # mirrors src/common, src/methods, and scripts/run owners
docs/              # architecture, orchestration, and import contracts
external/          # pinned external benchmark repositories
analysis/          # future processed schema, notebooks, plots, reports
artifacts/         # generated run outputs
```

Research source caches under `src/methods/**/paper/` are local-only and ignored
by git. The package metadata in `pyproject.toml` discovers only Python packages
under `src*`; keep PDFs and extracted full text out of tracked package data.

## Method Taxonomy

1. `src/methods/proposed_methods`: the user's own contribution.
2. `src/methods/comparison_methods/system_baselines`: simple baselines
   implemented directly here, such as fixed max/min clock policies.
3. `src/methods/comparison_methods/local_reproductions`: local reproductions
   maintained in this repo because no directly usable implementation exists, or
   available code cannot be used unchanged through a thin adapter.
4. `src/methods/comparison_methods/external_integrations`: adapters for
   directly usable pinned external implementations.

Stable runtime names are registry keys, not directory paths:

```text
max_freq
min_freq
oracle_static
everest
ali_2022_reimpl
```

## Quick Start

Requires Python >= 3.10. The code uses runtime union syntax and
`dataclass(slots=True)`.

```bash
git submodule update --init --recursive
python3 -m pip install -r requirements.txt
python3 -m unittest discover -s tests -t . -p "test_*.py"
```

For a bounded local runner smoke test, see `scripts/run/README.md`.

## Policy Configs

`scripts/run/control_loop.py` loads policy config from either:

1. `POLICY_CONFIG_PATH`
2. `POLICY_CONFIG_JSON`

Config schema notes live under `config/algorithms/`. `oracle_static` and
`ali_2022_reimpl` require policy config for meaningful runs. `everest` can run
with defaults but accepts runtime hyperparameters.

## Documentation Map

Start with `docs/README.md`. The most-used docs are:

1. `docs/REPO_ARCHITECTURE.md`: structure, ownership, and extension rules.
2. `docs/EXPERIMENT_ORCHESTRATION_MODEL.md`: controlled-mode runtime model.
3. `docs/EXTERNAL_BENCHMARK_IMPORT_RULES.md`: external artifact import
   contract.
4. `src/methods/README.md`: method taxonomy, registry, and add-policy rules.
5. `config/README.md`: config directory ownership.
6. `scripts/run/README.md`: Slurm/local runner commands and clock templates.
