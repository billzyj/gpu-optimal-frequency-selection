# External Benchmark Import Rules

## 1. Scope

This repository is responsible for algorithm comparison and experiment analysis.

1. It does not build, install, or maintain benchmark software stacks.
2. Benchmark execution is delegated to an external benchmarking repository.
3. This repository imports, normalizes, validates, and compares benchmark
   results.

Current external benchmarking source:

1. `external/repacss-benchmarking` (git submodule)

Current implementation status: the boundary and required schema are documented,
but local import/normalization helpers are not implemented yet.

## 2. Role Boundary

### 2.1 External Benchmarking Repository Responsibilities

1. Provision benchmark runtime environments.
2. Launch benchmark jobs or benchmark adapter scripts on target clusters.
3. Collect raw runtime, power, energy, and benchmark-native outputs.
4. Export machine-readable artifacts in a stable schema.
5. Preserve benchmark-specific parser logic.

### 2.2 This Repository Responsibilities

1. Call external benchmark execution through top-level orchestration scripts or
   import completed benchmark artifacts.
2. Validate schema and required fields of imported artifacts.
3. Normalize imported artifacts into internal processed outputs.
4. Run policy-level comparison and generate analysis outputs.
5. Own Slurm-integrated profiling/control orchestration for real-time frequency
   decisions.

## 3. Integration Contract

### 3.1 Invocation Model

1. Benchmark execution and import paths must be explicit and reproducible.
2. External benchmark calls are not method implementations under `src/methods`.
3. Import helpers must record resolved artifact paths.
4. For online control experiments, submit one top-level job from this repository
   and run benchmark/control loop in the same allocation.
5. Local orchestration code must not submit nested independent benchmark jobs.

### 3.2 Adapter Boundary

1. External repository adapters own benchmark runtime and site-specific
   execution details.
2. This repository owns orchestration and import helpers.
3. Benchmark deployment logic must remain in the external repository.
4. Real-time control glue belongs under `scripts/run` or future shared runtime
   modules, not inside `src/methods`.

### 3.3 Minimum Required Imported Fields per Run

1. `run_id`
2. `workload_name`
3. `platform.vendor`
4. `platform.gpu_model`
5. `policy_name`
6. `pd_target`
7. `runtime_seconds`
8. `avg_power_w`
9. `energy_joules`
10. `status` (`success` or `failed`)

### 3.4 Optional Recommended Fields

1. `gpu_count`
2. `node_name`
3. `driver_version`
4. `window_seconds`
5. `sampling_interval_ms`
6. `telemetry_series_path`
7. `raw_log_path`
8. `stderr_path`
9. `control_summary_path`
10. `external_repo_commit`

## 4. Artifact Rules

1. Imported artifact files must be immutable after run completion.
2. Imported artifact paths must be absolute.
3. Every imported run must include at least one summary artifact in JSON or CSV.
4. Timestamps must use UTC and ISO-8601 format where available.
5. Units must be explicit and stable: `seconds`, `W`, `J`, `MHz`.
6. Any local normalization step must preserve a link to the original raw
   artifact.

## 5. Local Output Placement

Future import helpers should write to:

1. `artifacts/raw`: copied or referenced raw external artifacts and import logs.
2. `artifacts/processed`: normalized comparison-ready tables.
3. `analysis/schema`: schema definitions and validators.

Do not write benchmark deployment scripts or benchmark-native parser logic under
these directories.

## 6. Versioning Rules

1. External benchmarking repository dependency must be pinned by commit SHA or
   tag.
2. Contract changes require a version note in this file.
3. Import helpers must fail fast on incompatible schema versions.
4. `control/run_manifest.json` should be retained with each controlled-mode run
   because it records the local repo commit, dirty status, policy config hash,
   and submodule status.

## 7. Failure Handling Rules

1. External execution failures must preserve the original return code.
2. Parser failures must report missing or malformed fields explicitly.
3. Partial artifacts may be stored but must be marked invalid for analysis.
4. Failed runs must not silently enter final comparison statistics.
5. Controlled-mode runs with `control_status=aborted` must remain visible but
   excluded from aggregate success metrics by default.

## 8. Import-Only Policy

1. New benchmark installation logic must not be added under `scripts/setup` in
   this repository.
2. Cluster-specific benchmark deployment logic must remain outside this
   repository.
3. Local scripts in this repository may orchestrate imports but must not own
   benchmark lifecycle management.
4. Local bridge scripts may launch benchmark commands inside an existing
   allocation for controlled experiments.

## 9. Compliance Checklist

For every new external benchmark integration, confirm:

1. Required fields in Section 3.3 are present.
2. Artifact paths are absolute and readable.
3. Units and timestamps follow Section 4.
4. External source version is pinned.
5. Failed or aborted runs are excluded from aggregate metrics by default.
6. Controlled-mode integrations do not submit nested independent benchmark jobs.
7. Normalized outputs preserve the original artifact path and import timestamp.
