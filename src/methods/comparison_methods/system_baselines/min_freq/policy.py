from __future__ import annotations

from src.common.experiment import ExperimentContext
from src.methods.comparison_methods.system_baselines.fixed_clock import FixedClockPolicy


class MinFreqPolicy(FixedClockPolicy):
    """Baseline that pins GPU graphics clock to the platform minimum."""

    policy_name = "min_freq"

    def _select_clock_mhz(self, context: ExperimentContext) -> int:
        return context.platform.min_graphics_clock_mhz
