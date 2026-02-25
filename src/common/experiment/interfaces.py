from __future__ import annotations

from typing import Mapping, Protocol, runtime_checkable

from .types import (
    AlgorithmState,
    Decision,
    ExternalRunResult,
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
class ExternalMethodInterface(Protocol):
    """
    Job-level contract for external comparison methods.

    External methods are executed out-of-process and return
    normalized artifact references for later analysis.
    """

    def run_external(
        self,
        context: ExperimentContext,
        config: Mapping[str, object],
    ) -> ExternalRunResult:
        """Runs one external method execution and returns normalized metadata."""
