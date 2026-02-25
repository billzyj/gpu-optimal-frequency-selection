# Methods

This directory is the canonical home for all comparable methods.

## Layout

1. `system_baselines`: simple controls (max/min/utilization).
2. `reimplemented_methods`: reference method re-implementations (EVEREST/Ali/Oracle).
3. `third_party`: wrappers for out-of-process systems (EAR).
4. `proposed_methods`: your method under development.

## Execution models

1. Online/window-level methods implement `AlgorithmInterface`.
2. External/job-level methods implement `ExternalMethodInterface`.
