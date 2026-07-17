# EnergyUCB Algorithm-Core Scaffold

This directory contains an independently written, paper-guided scaffold for
the final EnergyUCB algorithm. It is intentionally limited to the mathematical
core needed to test the paper equations before any runtime integration.

## Source and provenance

The implementation target is Xiongxiao Xu, Solomon Abera Bekele, Brice
Videau, and Kai Shu, "Online GPU Energy Optimization with Switching-Aware
Bandits," The Web Conference 2026, DOI
<https://doi.org/10.1145/3774904.3793034>. The local read-only source trace is
`topics/power_management`, Zotero item key `LKDU943F`.

The public Apache-2.0
[EnergyUCB-Bandit repository](https://github.com/XiongxiaoXu/EnergyUCB-Bandit)
was audited as artifact evidence, but no source code from it was copied into
this scaffold.

## Included now

- optimistic arm state with `n_i,0 = 0` and `mu_i,0 = mu_init`;
- the reward equation `-E_t * U_C,t / U_U,t`, with explicit rejection of an
  undefined zero-uncore denominator;
- the standard UCB index and the switching-aware index from Equation 5;
- an online empirical-mean update;
- deterministic arm selection, with ties resolved by the earliest arm in the
  caller-provided order;
- the constrained feasible-set rule based on
  `s_i = 1 - p_i / p_max`.

The QoS helper accepts a **relative-performance-loss budget** in `[0, 1)`.
It does not accept a runtime-slowdown target and performs no target-semantics
conversion.

## Deliberately not included

This is not a runnable comparison method. It currently has no:

- live telemetry adapter or reward measurement path;
- GPU frequency actuation or controller ownership;
- live progress estimator or paper-specific utilization proxy;
- completion detector or control loop;
- `AlgorithmInterface` policy implementation;
- configuration schema or method-registry entry.

The scaffold was written from the final paper equations and is kept separate
from the released repository's offline replay program. A future runtime
implementation must supply and validate telemetry, reward, progress, actuation,
and lifecycle semantics before the method can be registered or used in an
experiment.
