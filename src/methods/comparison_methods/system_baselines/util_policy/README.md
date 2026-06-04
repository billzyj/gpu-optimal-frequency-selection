# util_policy (placeholder)

Reserved slot for a utilization-driven fixed-clock baseline. **Not implemented
and not registered** in `src/methods/registry.py`.

Intended scope when implemented: pick a graphics clock from observed GPU/memory
utilization (e.g. step down when utilization is sustained-low), as a simple
reactive control to contrast with the offline `oracle_static` and the
paper-faithful `everest` policy.

Before this becomes a reportable baseline it must, per
`src/methods/README.md` ("Adding a New Policy"):

1. Implement the `AlgorithmInterface` lifecycle.
2. Emit only decisions accepted by `validate_decision()`.
3. Add tests under
   `tests/methods/comparison_methods/system_baselines/util_policy/`.
4. Register a stable `POLICY_NAME` in `src/methods/registry.py`.
