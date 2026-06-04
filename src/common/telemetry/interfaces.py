from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.common.experiment.types import ExperimentContext, MetricWindow


@runtime_checkable
class WindowTelemetryProvider(Protocol):
    """Produces one aggregated telemetry window for the control loop."""

    def get_window(
        self,
        context: ExperimentContext,
        sequence_id: int,
    ) -> MetricWindow:
        """Returns telemetry for ``sequence_id`` in ``context``."""
