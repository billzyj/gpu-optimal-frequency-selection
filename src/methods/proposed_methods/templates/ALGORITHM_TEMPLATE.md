# Algorithm Template

Use this template when introducing a new policy.

## Required interface

1. `initialize(context, config)`
2. `on_window(metrics, state) -> Decision`
3. `finalize(state) -> FinalSummary`

## Decision schema

1. `action`: one of `set_clock`, `hold_clock`, `reset_to_max`, or `no_op`.
2. `target_graphics_clock_mhz`: required for `set_clock`, omitted for hold/no-op.
3. `reason_code`: stable string for logs and analysis.
4. `debug_fields`: optional JSON-compatible details.

## Validation checklist

1. Runs with shared runner.
2. Emits decisions that pass `validate_decision()`.
3. Writes useful final summary fields.
4. Supports config-based parameterization.
5. Has unit tests before being added to `src/methods/registry.py`.
