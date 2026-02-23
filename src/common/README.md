# Common Modules

This directory contains algorithm-agnostic building blocks:

1. Telemetry collection adapters.
2. Clock/power actuation wrappers.
3. Shared experiment loop utilities.
4. Common data models and I/O contracts.

Keep this layer free of policy-specific heuristics.

## Unified algorithm contract

The unified algorithm interface and shared data structures are defined in:

1. `src/common/experiment/interfaces.py`
2. `src/common/experiment/types.py`
3. `src/common/experiment/validation.py`

Lifecycle contract:

1. `initialize(context, config) -> AlgorithmState`
2. `on_window(metrics, state) -> Decision`
3. `finalize(state) -> FinalSummary`
