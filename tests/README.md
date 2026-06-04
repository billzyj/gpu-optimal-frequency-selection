# Tests

The test tree mirrors the owner of the code under test.

## Layout

```text
tests/
|-- common/
|   |-- experiment/        # src/common/experiment
|   `-- telemetry/         # src/common/telemetry
|-- methods/
|   |-- proposed_methods/  # src/methods/proposed_methods
|   `-- comparison_methods/
|       |-- system_baselines/
|       |-- local_reproductions/
|       `-- external_integrations/
`-- scripts/
    `-- run/               # scripts/run
```

## Rules

1. Put shared contract tests under `tests/common/<module>/`.
2. Put runtime entrypoint tests under `tests/scripts/run/`.
3. Put policy tests under the matching `tests/methods/...` category.
4. Keep comparison-method tests in the same category as their implementation:
   `system_baselines`, `local_reproductions`, or `external_integrations`.

## Commands

Run all tests from the repository root with:

```bash
python3 -m unittest discover -s tests -t . -p "test_*.py"
```

The older `python3 -m unittest discover -s tests -p "test_*.py"` command is also
kept working by the `tests/scripts` package shim.
