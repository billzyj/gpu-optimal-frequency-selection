from __future__ import annotations

from typing import Mapping, Protocol, runtime_checkable

from .types import (
    AlgorithmState,
    Decision,
    ExperimentContext,
    FinalSummary,
    MetricWindow,
)


@runtime_checkable
class AlgorithmInterface(Protocol):
    """
    Unified lifecycle contract for all algorithms and baselines.

    Implementations are expected to be deterministic given
    identical input windows and configuration.
    """

    def initialize(
        self,
        context: ExperimentContext,
        config: Mapping[str, object],
    ) -> AlgorithmState:
        """Creates initial algorithm state for this run."""

    def on_window(
        self,
        metrics: MetricWindow,
        state: AlgorithmState,
    ) -> Decision:
        """Returns one control decision for the current window."""

    def finalize(self, state: AlgorithmState) -> FinalSummary:
        """Builds an end-of-run summary."""


@runtime_checkable
class StaticPolicy(Protocol):
    """
    Capability contract for whole-run (offline/static) policies.

    A static policy implements the full :class:`AlgorithmInterface` and, in
    addition, exposes ``initial_decision``. It computes one whole-run control
    decision at initialization and applies it exactly once, before window 0
    (controlled mode applies it before the benchmark process even starts).

    Behavioral contract:
    1. ``initial_decision`` returns the one-shot control decision, or ``None``
       to opt out of a pre-run decision for a given run.
    2. ``on_window`` is monitor-only: it observes telemetry and must return
       ``HOLD_CLOCK`` or ``NO_OP``. It must not emit a clock change, because the
       clock is owned by the pre-run decision. This is what prevents the
       double-apply that a window-driven SET_CLOCK would cause.

    Fixed-clock baselines and offline whole-workload methods implement this
    protocol. Online window-driven policies such as EVeREST do not. The runner
    detects support structurally with ``isinstance`` and skips the pre-run step
    for policies that lack ``initial_decision``.
    """

    def initial_decision(
        self,
        context: ExperimentContext,
        state: AlgorithmState,
    ) -> Decision | None:
        """Returns a one-shot control decision applied before window 0."""
