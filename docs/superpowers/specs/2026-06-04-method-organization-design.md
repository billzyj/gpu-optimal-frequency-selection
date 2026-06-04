# Method Organization Design

## Goal

Restructure method code so the repository clearly separates the user's proposed
method from all comparison methods, while preserving stable `POLICY_NAME`
values and keeping tests aligned with source layout.

## Approved Concept

`proposed_methods` is the home for the user's own contribution. All other
methods are comparison methods and should be grouped by how they enter the
repository:

1. `system_baselines`: simple baseline policies implemented directly in this
   repository.
2. `local_reproductions`: comparison algorithms implemented and maintained in
   this repository because no directly usable implementation exists, or because
   available code cannot be used unchanged through a thin adapter.
3. `external_integrations`: directly usable existing implementations brought in
   through pinned submodules or vendor copies, with local adapters that expose
   the shared policy/runtime contract.

## Target Source Layout

```text
src/methods/
|-- registry.py
|-- proposed_methods/
|   `-- my_method/
`-- comparison_methods/
    |-- README.md
    |-- system_baselines/
    |-- local_reproductions/
    `-- external_integrations/
```

Existing methods should move as follows:

1. `src/methods/system_baselines/*` ->
   `src/methods/comparison_methods/system_baselines/*`
2. Existing local reproduction implementations ->
   `src/methods/comparison_methods/local_reproductions/*`
3. Future external integrations ->
   `src/methods/comparison_methods/external_integrations/<method_name>/`
4. `src/methods/proposed_methods/*` stays where it is.

`src/methods/registry.py` stays at the top of `src/methods` because the runner
should resolve methods by stable policy name rather than by comparison category.

## Target Test Layout

Tests should mirror owner layout:

```text
tests/methods/
|-- proposed_methods/
`-- comparison_methods/
    |-- system_baselines/
    |-- local_reproductions/
    `-- external_integrations/

tests/common/
|-- experiment/
`-- telemetry/

tests/scripts/
`-- run/
```

Existing tests should move as follows:

1. `tests/system_baselines/*` ->
   `tests/methods/comparison_methods/system_baselines/*`
2. `tests/everest/*` ->
   `tests/methods/comparison_methods/local_reproductions/everest_reimpl/*`
3. `tests/ali_2022/*` ->
   `tests/methods/comparison_methods/local_reproductions/ali_2022_reimpl/*`
4. `tests/oracle_static/*` ->
   `tests/methods/comparison_methods/local_reproductions/oracle_static/*`
5. Future proposed-method tests ->
   `tests/methods/proposed_methods/<method_name>/*`
6. Future external-method tests ->
   `tests/methods/comparison_methods/external_integrations/<method_name>/*`

Non-method tests should mirror their owners:

1. `tests/common/experiment` -> `src/common/experiment`
2. `tests/common/telemetry` -> `src/common/telemetry`
3. `tests/scripts/run` -> `scripts/run`

## External Integration Boundary

External method source should live outside `src`, normally as a pinned submodule
under `external/<method_repo>/`. Local adapter code under
`src/methods/comparison_methods/external_integrations/<method_name>/` should be the
only place that imports, launches, or parses that external implementation.

Recommended local files for an external method:

```text
src/methods/comparison_methods/external_integrations/<method_name>/
|-- README.md
|-- adapter.py
|-- launcher.py
`-- parser.py
```

Rules:

1. Pin the external repository by submodule commit.
2. Do not import external code directly from the runner or other methods.
3. Make the adapter return this repository's standard `Decision` and
   `FinalSummary` types where applicable.
4. Add contract tests that fail clearly when the external API or output format
   changes after a submodule update.

## Registry and Policy Names

The path migration must not change stable policy names. Current names remain:

1. `max_freq`
2. `min_freq`
3. `oracle_static`
4. `everest`
5. `ali_2022_reimpl`

Only import paths should change. Example:

```python
from src.methods.comparison_methods.local_reproductions.everest_reimpl import EverestPolicy
```

## Documentation Updates

The migration should update:

1. `README.md`
2. `docs/REPO_ARCHITECTURE.md`
3. `src/README.md`
4. `src/methods/README.md`
5. `src/methods/comparison_methods/README.md`
6. `src/methods/comparison_methods/local_reproductions/README.md`
7. Any method-local README files that mention old paths.

## Verification

After implementation, run:

```bash
python3 -m unittest discover -s tests -t . -p "test_*.py"
git diff --check
rg -n -g '!docs/superpowers/**' "reimplemented_methods|external_methods|src/methods/(system_baselines|local_reproductions|external_integrations)|src\\.methods\\.(system_baselines|local_reproductions|external_integrations)|tests/(system_baselines|everest|ali_2022|oracle_static|experiment|telemetry|run)(/|$)" README.md docs src tests scripts
```

The final `rg` command should report no source-code import paths that bypass the
`comparison_methods` category.
