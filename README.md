# GPU Optimal Frequency Selection

Paper-specific GPU DVFS research code for one workflow:

1. Reproduce comparison methods and baselines.
2. Run them under a shared experiment protocol.
3. Keep the proposed method separate while it is still evolving.

## Research Model

This project has two coupled research layers.

1. **Frequency-selection algorithms** decide what GPU frequency, clock level, or
   frequency band an application should use at runtime. This layer includes
   paper-faithful reproductions such as EVeREST, Ali-style frequency selection,
   oracle/static baselines, and any proposed method. Its main question is:
   given workload behavior and performance-degradation targets, what frequency
   should the policy request?
2. **Hardware frequency realization** determines whether that requested
   frequency can actually be applied on the target cluster, how it is applied,
   how quickly it takes effect, which privileges it needs, how it is reset, and
   how the achieved clock is verified. This layer is vendor- and site-specific:
   REPACSS NVIDIA H100 and AMD MI210 nodes may expose different clock grids,
   command paths, permission models, latency, and telemetry fidelity.

The layers are intentionally separate but not independent. The hardware layer
defines the feasible action space for the algorithm layer: a policy cannot
reliably select arbitrary MHz values if the platform only exposes discrete
levels, range limits, privileged commands, or delayed/deferred clock changes.
Conversely, the algorithm layer defines what the hardware layer must support:
for example, a phase-aware runtime policy needs low-latency actuation and
per-window clock verification, while an offline whole-workload selector may only
need one pre-run clock setting plus a reliable reset path.

For REPACSS, a required research step is therefore to characterize the concrete
DVFS mechanisms available on the H100 and MI210 partitions before treating any
algorithmic result as hardware-realizable.

## Current Status

Implemented:

1. Shared `AlgorithmInterface`, decision types, and validation.
2. `EnvTelemetryProvider` for dry-runs and unit tests.
3. Runtime policy registry in `src/methods/registry.py`.
4. Comparison policies: `max_freq`, `min_freq`, `oracle_static`,
   `everest`, and `ali_2022_reimpl`.
5. Long-lived controlled-mode runner in `scripts/run/control_loop.py`.
6. Explicit performance-target types and conversions, with normalized values
   recorded in the run manifest and consumed by target-aware policies.
7. Machine-readable comparison-method routing/capability contracts in
   `src/methods/comparison_methods/contracts.py`.
8. A deliberately unregistered EnergyUCB algorithm-core scaffold covering the
   final paper's reward equation, initialization, UCB indices, switching
   penalty, deterministic selection, and QoS feasible set.
9. Unit tests for policies, telemetry, validation, runner behavior, contracts,
   target conversion, and the EnergyUCB equation core.

Still pending:

1. Hardware-backed telemetry and clock-control adapters.
2. Explicit irregular supported-clock grids and automatic method-capability
   preflight at policy/controller startup.
3. Required GEEPAFS comparison, preferably through a pinned sidecar if the
   target-GPU port is feasible, and completion of the EnergyUCB live telemetry,
   progress, policy, and actuation path; DRLCap remains conditional on
   licensing, artifacts, and retraining feasibility.
4. Import/normalization helpers for external benchmark artifacts.
5. Frozen processed-result schema under `analysis/schema`.
6. End-to-end hardware validation on a real benchmark.
7. REPACSS H100/MI210 DVFS capability characterization, including supported
   clock discovery, actuation/reset methods, permission requirements, latency,
   achieved-clock verification, and failure modes.

## Layout

```text
src/
|-- common/        # shared runtime contracts, types, telemetry interfaces
`-- methods/       # proposed method plus comparison methods

scripts/run/       # controlled-mode Slurm and local runner entrypoints
config/            # policy, platform, workload, and experiment config
tests/             # mirrors src/common, src/methods, and scripts/run owners
docs/              # architecture, orchestration, and import contracts
external/          # pinned external benchmark repositories
analysis/          # future processed schema, notebooks, plots, reports
artifacts/         # generated run outputs
```

Research source caches under `src/methods/**/paper/` are local-only and ignored
by git. The package metadata in `pyproject.toml` discovers only Python packages
under `src*`; keep PDFs and extracted full text out of tracked package data.

## Method Taxonomy

1. `src/methods/proposed_methods`: the user's own contribution.
2. `src/methods/comparison_methods/system_baselines`: simple baselines
   implemented directly here, such as fixed max/min clock policies.
3. `src/methods/comparison_methods/local_reproductions`: local reproductions
   maintained in this repo because no directly usable implementation exists, or
   available code cannot be used unchanged through a thin adapter.
4. `src/methods/comparison_methods/external_integrations`: adapters for
   directly usable pinned external implementations.

Stable runtime names are registry keys, not directory paths:

```text
max_freq
min_freq
oracle_static
everest
ali_2022_reimpl
```

## REPACSS Hardware Characterization

Before implementing new hardware backends or reporting controlled-mode results,
REPACSS-specific DVFS support should be measured and summarized as a capability
matrix. This matrix should cover:

1. NVIDIA H100 paths such as `nvidia-smi`, NVML, DCGM, and optional LIKWID/NVML
   sysfeatures where available.
2. AMD MI210 paths such as `amd-smi`, ROCm SMI, AMD SMI library calls, and
   optional LIKWID ROCMON/sysfeatures where available.
3. For each path: whether it is telemetry-only, actuation-capable, or both.
4. Required privilege level for reads, clock changes, power-limit changes, and
   reset/restore operations.
5. Frequency representation: exact MHz, min/max ranges, supported levels, or
   vendor-specific clock domains.
6. Actuation latency, settling behavior, and whether the clock change is
   immediate, deferred, or workload-dependent.
7. Verification method for achieved clocks, power, utilization, and reset state.
8. Portability notes: what is common across NVIDIA and AMD, what is vendor-only,
   and what appears to be REPACSS-site policy rather than hardware capability.

This characterization is not merely operational documentation. It feeds back
into algorithm design by defining the legal decision set, timing assumptions,
measurement overhead, and fallback behavior for each runtime policy. Student or
operator-facing experiments should start here before changing policy code.

## Quick Start

Requires Python >= 3.10. The code uses runtime union syntax and
`dataclass(slots=True)`.

```bash
git submodule update --init --recursive
python3 -m pip install -r requirements.txt
python3 -m unittest discover -s tests -t . -p "test_*.py"
```

For a bounded local runner smoke test, see `scripts/run/README.md`.

## Policy Configs

`scripts/run/control_loop.py` loads policy config from either:

1. `POLICY_CONFIG_PATH`
2. `POLICY_CONFIG_JSON`

Config schema notes live under `config/algorithms/`. `oracle_static` and
`ali_2022_reimpl` require policy config for meaningful runs. `everest` can run
with defaults but accepts runtime hyperparameters.

## Documentation Map

Start with `docs/README.md`. The most-used docs are:

1. `docs/REPO_ARCHITECTURE.md`: structure, ownership, and extension rules.
2. `docs/COMPARISON_METHOD_INTEGRATION_PLAN.md`: verified public artifacts and
   direct-call, adapter, reproduction, component, or literature-only routing.
3. `docs/EXPERIMENT_ORCHESTRATION_MODEL.md`: controlled-mode runtime model.
4. `docs/EXTERNAL_BENCHMARK_IMPORT_RULES.md`: external artifact import
   contract.
5. `src/methods/README.md`: method taxonomy, registry, and add-policy rules.
6. `config/README.md`: config directory ownership.
7. `scripts/run/README.md`: Slurm/local runner commands and clock templates.

For hardware-control details, start with `src/methods/README.md` for the
telemetry-versus-actuation split and `scripts/run/README.md` for current runner
environment variables and shell command templates.
