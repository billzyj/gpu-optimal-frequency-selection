# Artifacts

Generated experiment outputs live here. These files are run products, not source
code.

This directory's structure is tracked, but generated contents under `raw`,
`processed`, and `figures` are git-ignored by default.

## Layout

1. `raw`: run-level raw logs, Slurm logs, external benchmark outputs, telemetry
   snapshots, and original imported artifacts.
2. `processed`: cleaned and normalized tables ready for comparison and
   analysis.
3. `figures`: exported plots for reports and papers.

## Controlled-Mode Runs

The default Slurm template writes external run roots under:

```text
artifacts/raw/external_runs/<EXPERIMENT_ID>/<SITE_PROFILE>/<BENCH_ID>/<RUN_ID>/
```

Within each `RUN_DIR`, this repository's control loop writes:

```text
control_loop.log
control/
|-- run_manifest.json
|-- policy_state.json
|-- decisions.csv
|-- last_decision.json
`-- final_summary.json
```

## Reproducibility Rules

1. Preserve raw artifacts exactly as produced by the run.
2. Write normalized derivatives under `processed`, never by mutating raw files.
3. Keep `run_manifest.json` with every controlled-mode run.
4. Mark aborted or failed runs explicitly; do not silently remove them from raw
   storage.
5. Exclude failed/aborted runs from aggregate statistics by default unless an
   analysis explicitly studies failure modes.

## Cleanup Rules

Only clean generated artifacts after reviewing what will be removed. Preserve
any run directory that is referenced by a paper note, figure, or result table.

## Version-Control Rules

1. Keep this README and `.gitkeep` placeholders tracked.
2. Do not commit raw runs, processed tables, or generated figures by default.
3. Promote only small, final, paper-required artifacts explicitly, and document
   why they should be versioned.
