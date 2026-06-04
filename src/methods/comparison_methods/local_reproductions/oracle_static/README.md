# Oracle-Static Baseline

`oracle_static` implements the static-oracle GPU DVFS evaluation baseline used
in EVeREST-style comparisons. It is not treated as a standalone published
method; cite the evaluation paper being reproduced, currently EVeREST.

## Layout

1. `policy.py`: fixed-frequency selection from offline sweep points.
2. `paper/`: ignored local EVeREST source PDF/text cache when needed.
3. `docs/ORACLE_STATIC_REPRODUCTION_PLAN.md`: baseline scope, input
   requirements, selection rule, ambiguities, and separated improvement space.

The current policy chooses the lowest profiled frequency satisfying the target
performance-degradation bound, applies it once, and then holds that clock.
Pass profiles through `POLICY_CONFIG_PATH` or `POLICY_CONFIG_JSON`; see
`config/algorithms/oracle_static/README.md` for an example schema.
