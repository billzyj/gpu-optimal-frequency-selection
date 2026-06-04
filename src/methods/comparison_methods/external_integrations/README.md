# External Integrations

This directory is reserved for comparison methods whose primary implementation
already exists outside this repository and can be used through a thin local
adapter.

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
