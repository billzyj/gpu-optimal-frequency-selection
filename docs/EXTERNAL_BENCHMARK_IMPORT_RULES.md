# External Benchmark Import Rules

## 1. Scope

This repository is responsible for algorithm comparison and experiment analysis.

1. It does not build, install, or maintain benchmark software stacks.
2. Benchmark execution is delegated to an external benchmarking repository.
3. This repository only imports, normalizes, and validates benchmark results.

Current external benchmarking source:

1. `external/repacss-benchmarking` (git submodule)

## 2. Role Boundary

### 2.1 External benchmarking repository responsibilities

1. Provision benchmark runtime environments (module, spack, source, container, etc.).
2. Launch benchmark jobs on target clusters.
3. Collect raw runtime, power, and energy outputs.
4. Export machine-readable artifacts in a stable schema.

### 2.2 This repository responsibilities

1. Call external benchmark execution through a stable adapter interface.
2. Validate schema and required fields of imported artifacts.
3. Normalize imported artifacts into internal processed outputs.
4. Run policy-level comparison and generate analysis outputs.

## 3. Integration Contract

### 3.1 Invocation model

1. Integration must use `ExternalMethodInterface` from `src/common/experiment/interfaces.py`.
2. External benchmark calls are treated as job-level executions.
3. The adapter must return `ExternalRunResult` with resolved artifact paths.

### 3.2 Minimum required imported fields per run

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

### 3.3 Optional recommended fields

1. `gpu_count`
2. `node_name`
3. `driver_version`
4. `window_seconds`
5. `sampling_interval_ms`
6. `telemetry_series_path`
7. `raw_log_path`
8. `stderr_path`

## 4. Artifact Rules

1. Imported artifact files must be immutable after run completion.
2. Paths in `ExternalRunResult.artifact_paths` must be absolute.
3. Every imported run must include at least one summary artifact (JSON or CSV).
4. Timestamps must use UTC and ISO-8601 format where available.
5. Units must be explicit and stable (`seconds`, `W`, `J`, `MHz`).

## 5. Versioning Rules

1. External benchmarking repository dependency must be pinned by commit SHA or tag.
2. Contract changes require a version bump in this file (for example `v1 -> v2` section note).
3. Adapters must fail fast on incompatible schema versions.

## 6. Failure Handling Rules

1. External execution failures must preserve original return code.
2. Parser failures must report missing or malformed fields explicitly.
3. Partial artifacts may be stored but must be marked as invalid for analysis.
4. Failed runs must not silently enter final comparison statistics.

## 7. Import-Only Policy

1. New benchmark installation logic must not be added under `scripts/setup` in this repository.
2. Cluster-specific benchmark deployment logic must remain outside this repository.
3. Local scripts in this repository may orchestrate imports but must not own benchmark lifecycle management.

## 8. Compliance Checklist

For every new external benchmark integration, confirm:

1. Adapter uses `ExternalMethodInterface`.
2. Required fields in Section 3.2 are present.
3. Artifact paths are absolute and readable.
4. Units and timestamps follow Section 4.
5. External source version is pinned.
6. Failed runs are excluded from aggregate metrics by default.
