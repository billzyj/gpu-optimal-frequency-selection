from __future__ import annotations

import os
import unittest

from src.common.experiment.types import (
    ExperimentContext,
    ExperimentMetadata,
    PlatformSpec,
)
from src.common.telemetry import EnvTelemetryProvider, WindowTelemetryProvider


_PLATFORM = PlatformSpec(
    vendor="nvidia",
    gpu_model="TestGPU",
    gpu_count=1,
    min_graphics_clock_mhz=210,
    max_graphics_clock_mhz=1410,
    graphics_clock_step_mhz=15,
)

_METADATA = ExperimentMetadata(
    run_id="test-run-001",
    experiment_id="test-exp",
    policy_name="max_freq",
    workload_name="synthetic",
    started_at_utc="2026-01-01T00:00:00Z",
)


def _make_context(
    *,
    window_seconds: float = 5.0,
    sampling_interval_ms: int = 1000,
) -> ExperimentContext:
    return ExperimentContext(
        platform=_PLATFORM,
        metadata=_METADATA,
        pd_target=0.05,
        window_seconds=window_seconds,
        sampling_interval_ms=sampling_interval_ms,
    )


class TestEnvTelemetryProvider(unittest.TestCase):
    def test_defaults_match_current_env_window_behavior(self) -> None:
        provider: WindowTelemetryProvider = EnvTelemetryProvider(
            environ={},
            clock=lambda: 100.0,
        )

        window = provider.get_window(_make_context(), sequence_id=7)

        self.assertEqual(window.sequence_id, 7)
        self.assertEqual(window.end_unix_s, 100.0)
        self.assertEqual(window.start_unix_s, 95.0)
        self.assertEqual(window.duration_s, 5.0)
        self.assertEqual(window.sample_count, 5)
        self.assertEqual(window.gpu_util_avg_pct, 0.0)
        self.assertEqual(window.mem_util_avg_pct, 0.0)
        self.assertEqual(window.graphics_clock_avg_mhz, 1410.0)
        self.assertIsNone(window.power_avg_w)
        self.assertIsNone(window.energy_delta_j)
        self.assertEqual(window.custom_metrics, {})

    def test_reads_metric_overrides_from_mapping(self) -> None:
        provider = EnvTelemetryProvider(
            environ={
                "METRIC_GPU_UTIL_PCT": "72.5",
                "METRIC_MEM_UTIL_PCT": "33.25",
                "METRIC_GRAPHICS_CLOCK_MHZ": "900",
                "METRIC_POWER_W": "251.75",
                "METRIC_ENERGY_DELTA_J": "1258.75",
                "METRIC_PERFORMANCE_RATIO": "0.965",
            },
            clock=lambda: 25.0,
        )

        window = provider.get_window(_make_context(window_seconds=2.5), sequence_id=3)

        self.assertEqual(window.sequence_id, 3)
        self.assertEqual(window.start_unix_s, 22.5)
        self.assertEqual(window.end_unix_s, 25.0)
        self.assertEqual(window.duration_s, 2.5)
        self.assertEqual(window.sample_count, 2)
        self.assertEqual(window.gpu_util_avg_pct, 72.5)
        self.assertEqual(window.mem_util_avg_pct, 33.25)
        self.assertEqual(window.graphics_clock_avg_mhz, 900.0)
        self.assertEqual(window.power_avg_w, 251.75)
        self.assertEqual(window.energy_delta_j, 1258.75)
        self.assertEqual(window.custom_metrics, {"performance_ratio": 0.965})

    def test_empty_values_fall_back_like_current_parsers(self) -> None:
        provider = EnvTelemetryProvider(
            environ={
                "METRIC_GPU_UTIL_PCT": "",
                "METRIC_MEM_UTIL_PCT": "",
                "METRIC_GRAPHICS_CLOCK_MHZ": "",
                "METRIC_POWER_W": "",
                "METRIC_ENERGY_DELTA_J": "",
                "METRIC_PERFORMANCE_RATIO": "",
            },
            clock=lambda: 10.0,
        )

        window = provider.get_window(
            _make_context(window_seconds=0.1, sampling_interval_ms=1000),
            sequence_id=0,
        )

        self.assertEqual(window.sample_count, 1)
        self.assertEqual(window.gpu_util_avg_pct, 0.0)
        self.assertEqual(window.mem_util_avg_pct, 0.0)
        self.assertEqual(window.graphics_clock_avg_mhz, 1410.0)
        self.assertIsNone(window.power_avg_w)
        self.assertIsNone(window.energy_delta_j)
        self.assertEqual(window.custom_metrics, {})

    def test_default_provider_reads_process_environment(self) -> None:
        old_value = os.environ.get("METRIC_GPU_UTIL_PCT")
        os.environ["METRIC_GPU_UTIL_PCT"] = "88"
        try:
            provider = EnvTelemetryProvider(clock=lambda: 5.0)
            window = provider.get_window(_make_context(), sequence_id=1)
        finally:
            if old_value is None:
                os.environ.pop("METRIC_GPU_UTIL_PCT", None)
            else:
                os.environ["METRIC_GPU_UTIL_PCT"] = old_value

        self.assertEqual(window.gpu_util_avg_pct, 88.0)


if __name__ == "__main__":
    unittest.main()
