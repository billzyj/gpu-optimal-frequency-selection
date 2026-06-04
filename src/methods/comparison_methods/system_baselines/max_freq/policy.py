from __future__ import annotations

from src.common.experiment import ExperimentContext
from src.methods.comparison_methods.system_baselines.fixed_clock import FixedClockPolicy


class MaxFreqPolicy(FixedClockPolicy):
    """Baseline that pins GPU graphics clock to the platform maximum."""

    policy_name = "max_freq"

    def _select_clock_mhz(self, context: ExperimentContext) -> int:
        return context.platform.max_graphics_clock_mhz
