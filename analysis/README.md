# Analysis

Shared post-processing and reporting space for experiment outputs.

## Layout

1. `schema`: canonical result schema and validation helpers.
2. `notebooks`: exploratory analysis.
3. `plots`: reusable plotting code.
4. `reports`: generated summaries and paper-ready tables.

## Current Status

These directories are placeholders. No processed-output schema is frozen yet, so
analysis code should treat current artifacts as provisional.

Generated files under `reports` are git-ignored by default. Keep reusable code,
schema definitions, and intentionally curated notebooks tracked.

## Expected Inputs

Future analysis should consume:

1. Controlled-mode summaries from `<RUN_DIR>/control/final_summary.json`.
2. Control decisions from `<RUN_DIR>/control/decisions.csv`.
3. Imported benchmark summaries normalized from `external/repacss-benchmarking`.
4. Raw or processed telemetry series when hardware providers are added.

## Boundary Rules

1. Do not put benchmark execution logic in `analysis`.
2. Do not put policy implementations in `analysis`.
3. Put reusable schema definitions under `schema`, plotting code under `plots`,
   exploratory work under `notebooks`, and generated tables/reports under
   `reports`.
4. Record units and schema versions in every reusable analysis output.
5. Do not commit generated report files unless they are intentionally promoted
   as paper-facing artifacts.
