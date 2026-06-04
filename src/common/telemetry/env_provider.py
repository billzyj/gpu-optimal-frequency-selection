from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Callable, Mapping

from src.common.experiment.types import ExperimentContext, MetricWindow


def _parse_float(raw: str | None, default: float) -> float:
    if raw is None or raw == "":
        return default
    return float(raw)


def _parse_optional_float(raw: str | None) -> float | None:
    if raw is None or raw == "":
        return None
    return float(raw)


@dataclass(frozen=True, slots=True)
class EnvTelemetryProvider:
    """Builds metric windows from the existing ``METRIC_*`` environment contract."""

    environ: Mapping[str, str] | None = None
    clock: Callable[[], float] = time.time

    def _get(self, name: str) -> str | None:
        if self.environ is None:
            return os.getenv(name)
        return self.environ.get(name)

    def get_window(
        self,
        context: ExperimentContext,
        sequence_id: int,
    ) -> MetricWindow:
        end_unix_s = self.clock()
        duration_s = context.window_seconds
        start_unix_s = end_unix_s - duration_s

        performance_ratio = _parse_optional_float(
            self._get("METRIC_PERFORMANCE_RATIO")
        )
        custom_metrics = {}
        if performance_ratio is not None:
            custom_metrics["performance_ratio"] = performance_ratio

        current_clock = _parse_float(
            self._get("METRIC_GRAPHICS_CLOCK_MHZ"),
            float(context.platform.max_graphics_clock_mhz),
        )

        return MetricWindow(
            sequence_id=sequence_id,
            start_unix_s=start_unix_s,
            end_unix_s=end_unix_s,
            duration_s=duration_s,
            sample_count=max(
                1,
                int(
                    (duration_s * 1000.0)
                    / max(1, context.sampling_interval_ms)
                ),
            ),
            gpu_util_avg_pct=_parse_float(self._get("METRIC_GPU_UTIL_PCT"), 0.0),
            mem_util_avg_pct=_parse_float(self._get("METRIC_MEM_UTIL_PCT"), 0.0),
            graphics_clock_avg_mhz=current_clock,
            power_avg_w=_parse_optional_float(self._get("METRIC_POWER_W")),
            energy_delta_j=_parse_optional_float(
                self._get("METRIC_ENERGY_DELTA_J")
            ),
            custom_metrics=custom_metrics,
        )
