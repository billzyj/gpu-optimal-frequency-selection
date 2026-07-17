# Comparison Methods

This directory contains every method used to compare against the user's
proposed GPU DVFS method.

## Categories

1. `system_baselines`: simple baselines implemented directly in this
   repository, such as fixed maximum and minimum clock policies.
2. `local_reproductions`: comparison algorithms implemented and maintained in
   this repository because no directly usable implementation exists, or because
   available code cannot be used unchanged through a thin adapter.
3. `external_integrations`: directly usable existing implementations brought in
   through pinned external repositories and exposed through local adapters.

## Reviewed Method Routing

The public-artifact audit was refreshed on 2026-07-17 and routes the newly
reviewed literature as follows. A route is not itself a runnable-policy claim.

| Route | Methods or artifacts |
|---|---|
| Required comparison; preferred pinned sidecar pending port feasibility | GEEPAFS |
| Paper-guided reproduction; equation-core scaffold implemented, still unregistered | EnergyUCB |
| Conditional independent paper-guided policy reproduction | DRLCap |
| Optional local estimator/partitioner component | Gupta et al. online model, Wang--Chu core/memory model, Phase-Based Frequency Scaling, DSO equation |
| External workload or characterization harness | SYnergy, Velicka et al. LATEST |
| Separate offline/domain-specific track | Predictable GPUs, SLO-aware LLM DVFS |
| Related-work only under the current hardware scope | CRISP, Harmonia |

See `docs/COMPARISON_METHOD_INTEGRATION_PLAN.md` for verified repository URLs,
licenses, artifact limitations, target paths, admission gates, and the ordered
implementation plan.

`contracts.py` is the machine-readable routing and admission surface. It records
implementation state, integration route, actuation owner, telemetry, control,
and artifact requirements. Its registered entries are tested against
`src/methods/registry.py`; incomplete methods remain absent from the registry.

## Boundary Rules

1. Comparison methods may share `AlgorithmInterface`, `Decision`, and
   `FinalSummary`, but must not depend on `proposed_methods`.
2. Local reproductions should keep source/citation ledgers and reproduction
   notes with the method.
3. External integrations should keep third-party source outside `src`, normally
   under `external/<repo>`, and expose only local adapter code here.
4. Stable policy names are registered in `src/methods/registry.py`; callers
   should not depend on category paths.
5. A performance model, measurement tool, dataset, or application-integrated
   library is not a runnable policy by itself and must not receive a registry
   name until a paper-defined selection rule satisfies the local contracts.
6. Algorithm-core scaffolds are allowed when they are equation-tested and
   explicitly unregistered; they must list every missing runtime dependency.
