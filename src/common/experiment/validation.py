from __future__ import annotations

from .types import Decision, DecisionAction, PlatformSpec


class DecisionValidationError(ValueError):
    """Raised when an algorithm emits an invalid control decision."""


def validate_decision(decision: Decision, platform: PlatformSpec) -> None:
    """
    Validates one decision against platform capabilities.

    Rules:
    1. `SET_CLOCK` requires a target clock.
    2. `HOLD_CLOCK` and `NO_OP` must not include a target clock.
    3. Target clock must be within [min, max].
    4. Intermediate target clocks must align to `graphics_clock_step_mhz`.
    """
    if decision.action == DecisionAction.SET_CLOCK:
        if decision.target_graphics_clock_mhz is None:
            raise DecisionValidationError(
                "SET_CLOCK decision must include target_graphics_clock_mhz."
            )
        _validate_clock_range(
            decision.target_graphics_clock_mhz,
            platform,
        )
        return

    if decision.action == DecisionAction.RESET_TO_MAX:
        if decision.target_graphics_clock_mhz not in (None, platform.max_graphics_clock_mhz):
            raise DecisionValidationError(
                "RESET_TO_MAX may only omit target clock or set it to max_graphics_clock_mhz."
            )
        return

    if decision.action in {DecisionAction.HOLD_CLOCK, DecisionAction.NO_OP}:
        if decision.target_graphics_clock_mhz is not None:
            raise DecisionValidationError(
                f"{decision.action.value} must not include target_graphics_clock_mhz."
            )
        return

    raise DecisionValidationError(f"Unsupported decision action: {decision.action}.")


def _validate_clock_range(clock_mhz: int, platform: PlatformSpec) -> None:
    min_mhz = platform.min_graphics_clock_mhz
    max_mhz = platform.max_graphics_clock_mhz
    if not (min_mhz <= clock_mhz <= max_mhz):
        raise DecisionValidationError(
            f"Target clock {clock_mhz} MHz is out of range [{min_mhz}, {max_mhz}] MHz."
        )

    step_mhz = platform.graphics_clock_step_mhz
    if step_mhz <= 0:
        raise DecisionValidationError("graphics_clock_step_mhz must be > 0.")

    if clock_mhz in {min_mhz, max_mhz}:
        return

    if (clock_mhz - min_mhz) % step_mhz != 0:
        raise DecisionValidationError(
            f"Target clock {clock_mhz} MHz is not aligned to {step_mhz} MHz steps."
        )
