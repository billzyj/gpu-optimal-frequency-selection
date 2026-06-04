from __future__ import annotations

import unittest

from src.common.experiment.types import Decision, DecisionAction, PlatformSpec
from src.common.experiment.validation import DecisionValidationError, validate_decision


def _platform(*, step_mhz: int = 15) -> PlatformSpec:
    return PlatformSpec(
        vendor="nvidia",
        gpu_model="TestGPU",
        gpu_count=1,
        min_graphics_clock_mhz=210,
        max_graphics_clock_mhz=1410,
        graphics_clock_step_mhz=step_mhz,
    )


class DecisionValidationTests(unittest.TestCase):
    def test_set_clock_accepts_aligned_intermediate_clock(self) -> None:
        validate_decision(
            Decision(
                action=DecisionAction.SET_CLOCK,
                target_graphics_clock_mhz=900,
                reason_code="aligned",
            ),
            _platform(),
        )

    def test_set_clock_accepts_exact_max_clock(self) -> None:
        validate_decision(
            Decision(
                action=DecisionAction.SET_CLOCK,
                target_graphics_clock_mhz=1410,
                reason_code="max",
            ),
            _platform(step_mhz=32),
        )

    def test_set_clock_rejects_unaligned_intermediate_clock(self) -> None:
        with self.assertRaisesRegex(DecisionValidationError, "not aligned"):
            validate_decision(
                Decision(
                    action=DecisionAction.SET_CLOCK,
                    target_graphics_clock_mhz=901,
                    reason_code="unaligned",
                ),
                _platform(),
            )

    def test_set_clock_rejects_invalid_platform_step(self) -> None:
        with self.assertRaisesRegex(DecisionValidationError, "must be > 0"):
            validate_decision(
                Decision(
                    action=DecisionAction.SET_CLOCK,
                    target_graphics_clock_mhz=900,
                    reason_code="bad_step",
                ),
                _platform(step_mhz=0),
            )


if __name__ == "__main__":
    unittest.main()
