# EVeREST Implementation

This directory is reserved for reproducing the EVeREST paper logic.

Suggested module boundaries:

1. `phase_identification`: phase identification and phase-change detection.
2. `phase_characterization`: frequency sensitivity estimation.
3. `frequency_scaling`: frequency target computation and control logic.
4. `policy`: EVeREST policy orchestration.

Avoid placing generic helpers here; move shared code to `src/common`.
