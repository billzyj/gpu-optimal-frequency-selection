from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.common.experiment.types import Decision


@runtime_checkable
class ClockController(Protocol):
    """Typed actuation seam for applying GPU clock-control decisions.

    Implementations translate a validated :class:`Decision` into a hardware
    clock change (or a logged dry-run) and can restore default clock state. The
    control loop depends on this protocol instead of invoking a shell command
    inline, so actuation backends are swappable and unit-testable: the shell
    command-template backend today, and typed NVML / AMD-SMI backends later.

    Implementations should treat decisions that do not require a clock change
    (``HOLD_CLOCK`` / ``NO_OP``) as no-ops.
    """

    def apply(self, decision: Decision) -> None:
        """Applies a control decision, changing the clock only when required."""

    def reset(self) -> None:
        """Restores default/hardware clock state, if the backend supports it."""
