# Algorithm Template

Use this template when introducing a new policy.

## Required interface

1. `initialize(context, config)`
2. `on_window(metrics, state) -> decision`
3. `finalize(state) -> summary`

## Decision schema

1. `target_graphics_clock`
2. `reason_code`
3. `debug_fields` (optional)

## Validation checklist

1. Runs with shared runner.
2. Produces standard metrics output.
3. Supports config-based parameterization.
