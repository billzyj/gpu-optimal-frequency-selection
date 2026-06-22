# Oracle-Static Baseline

`oracle_static` implements the static-oracle GPU DVFS evaluation baseline used
in EVeREST-style comparisons. It is not treated as a standalone published
method; cite the evaluation paper being reproduced, currently EVeREST.

## Layout

1. `policy.py`: fixed-frequency selection from offline sweep points.
2. `paper/`: ignored local EVeREST source PDF/text cache when needed.
3. `docs/ORACLE_STATIC_REPRODUCTION_PLAN.md`: baseline scope, input
   requirements, selection rule, ambiguities, and separated improvement space.

The policy chooses the lowest in-domain profiled frequency satisfying the target
performance-degradation bound. Faithful runs require an exact
`workload_profiles[workload_name]` profile. The policy satisfies the
`StaticPolicy` protocol via `initial_decision(context, state)`, so the shared
runner applies the fixed clock once before the first measured window; `on_window`
is monitor-only and only tracks PD violations. Pass profiles through
`POLICY_CONFIG_PATH` or `POLICY_CONFIG_JSON`; see
`config/algorithms/oracle_static/README.md` for the schema.
