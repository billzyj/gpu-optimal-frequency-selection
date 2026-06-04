# Methods

This directory is the canonical home for GPU DVFS policies.

## Layout

1. `registry.py`: maps stable `POLICY_NAME` strings to policy instances.
2. `proposed_methods`: the user's own method under development.
3. `comparison_methods`: all methods used for comparison against the proposed
   method.

## Comparison Method Categories

1. `comparison_methods/system_baselines`: simple controls with clear
   interpretation.
2. `comparison_methods/local_reproductions`: comparison algorithms implemented
   locally because no directly usable implementation exists, or because
   available code cannot be used unchanged through a thin adapter.
3. `comparison_methods/external_integrations`: thin adapters for directly
   usable external implementations pinned under `external/`.

External benchmarking remains under `external/repacss-benchmarking` and is
invoked through local run/import scripts. It is not itself a policy category.

## Execution Model

Policies used by the default runner implement `AlgorithmInterface`:

1. `initialize(context, config)`
2. `on_window(metrics, state) -> Decision`
3. `finalize(state) -> FinalSummary`

## Current Registry

| Policy name | Directory | Status | Purpose |
|---|---|---|---|
| `max_freq` | `comparison_methods/system_baselines/max_freq/` | Registered | Fixed maximum graphics-clock baseline. |
| `min_freq` | `comparison_methods/system_baselines/min_freq/` | Registered | Fixed minimum graphics-clock baseline. |
| `oracle_static` | `comparison_methods/local_reproductions/oracle_static/` | Registered | Offline sweep oracle baseline. |
| `everest` | `comparison_methods/local_reproductions/everest_reimpl/` | Registered | Paper-faithful EVeREST runtime policy. |
| `ali_2022_reimpl` | `comparison_methods/local_reproductions/ali_2022_reimpl/` | Registered | Ali HPEC 2022 offline model-based selector. |
| `util_policy` | `comparison_methods/system_baselines/util_policy/` | Placeholder | Not implemented or registered yet. |
| `my_method` | `proposed_methods/my_method/` | Placeholder | Reserved for the proposed paper method. |

See `src/methods/registry.py` for the runtime registry used by
`scripts/run/control_loop.py`.

## Adding a New Policy

1. Decide whether the method is proposed or comparison.
2. For comparison methods, choose exactly one category:
   `system_baselines`, `local_reproductions`, or `external_integrations`.
3. Implement the `AlgorithmInterface` lifecycle or provide an adapter that
   exposes it.
4. Emit only `Decision` objects that pass `validate_decision()`.
5. Add tests under the matching `tests/methods/...` path.
6. Add a stable name to `src/methods/registry.py`.
7. Document config keys and method scope in a local README or reproduction plan.
8. If the method is a local reproduction of a paper/system, update
   `comparison_methods/local_reproductions/README.md` before using it in
   claims.

## Method-Specific Docs

1. Local reproductions keep source caches in ignored `paper/` folders and
   reproduction notes in tracked `docs/` folders when source papers are needed.
2. Citation/source ledgers for local reproductions live in
   `comparison_methods/local_reproductions/README.md`.
3. External integrations keep third-party source under `external/` and local
   adapters under `comparison_methods/external_integrations/`.
4. Hardware clock command templates belong in `scripts/run/README.md`, not in
   method modules.
5. Proposed-method design notes should stay separate from paper-faithful
   baseline reproduction notes.
