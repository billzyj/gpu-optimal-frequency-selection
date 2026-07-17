# External Integrations

This directory is reserved for comparison methods whose primary implementation
already exists outside this repository and can be used through a thin local
adapter or a controlled external sidecar without rewriting the algorithm.

The detailed public-artifact decisions are recorded in
`docs/COMPARISON_METHOD_INTEGRATION_PLAN.md`.

## Planned Integration

GEEPAFS is the only newly reviewed method with a preferred route here, pending
target-GPU port feasibility. Its official implementation is MIT licensed, but
its programs own privileged actuation and the C version is documented as a
long-running controller rather than an importable policy. Its adapter therefore
requires an explicit external-controller mode with exclusive actuation
ownership, lifecycle and reset handling, upstream-log parsing, and target-GPU
calibration. Do not add a placeholder package or registry entry before those
runtime contracts exist. The repository now declares GEEPAFS's static
capability and actuation requirements in `../contracts.py`, but the exclusive
controller lifecycle and runner mode are still unimplemented.

SYnergy and LATEST are not normal policy integrations: SYnergy is an optional
SYCL-native workload/model harness, and LATEST is a one-time characterization
tool. Their execution and imported artifacts should remain outside the default
policy registry.

## Expected Layout

```text
external/<method_repo>/              # pinned submodule or vendor source
src/methods/comparison_methods/external_integrations/<method_name>/
|-- README.md
|-- adapter.py
|-- launcher.py
`-- parser.py
```

## Rules

1. Pin each external implementation by commit, tag, or archived release.
2. Keep third-party code out of `src` unless the project explicitly switches to
   a vendor-copy strategy.
3. Make the local adapter the only import/call boundary between this repository
   and the external implementation.
4. Add contract tests for adapter behavior and parser output so submodule
   upgrades fail visibly when interfaces drift.
5. If the external code requires substantial modification before it can be used,
   classify the method under `local_reproductions` instead.
6. If the upstream method performs its own actuation, record exclusive
   controller ownership in the run manifest and disable the local clock
   controller for that run.
7. A documented device-constant, frequency-grid, or target-parser patch may
   remain an external integration. Any algorithmic change requires
   reclassification and an explicit reproduction/deviation ledger.
