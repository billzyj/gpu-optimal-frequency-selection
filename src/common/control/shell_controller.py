from __future__ import annotations

import subprocess
from typing import Any, Callable

from src.common.experiment.types import Decision


def _noop_logger(_message: str) -> None:
    """Default logger that drops messages."""


class ShellTemplateController:
    """Clock controller backed by shell command templates.

    This is the transitional actuation backend behind the
    :class:`~src.common.control.interfaces.ClockController` protocol. ``apply``
    formats ``apply_template`` with ``target_mhz`` / ``action`` / ``reason`` and
    runs it; when no template is configured it logs a dry-run instead. ``reset``
    runs an optional reset command. The subprocess runner and logger are
    injectable, so this backend is fully unit-testable without touching real
    hardware.
    """

    def __init__(
        self,
        *,
        apply_template: str | None,
        reset_cmd: str | None = None,
        logger: Callable[[str], None] | None = None,
        runner: Callable[..., Any] = subprocess.run,
    ) -> None:
        self._apply_template = apply_template or None
        self._reset_cmd = reset_cmd or None
        self._log = logger if logger is not None else _noop_logger
        self._runner = runner

    def apply(self, decision: Decision) -> None:
        if not decision.requires_clock_change or decision.target_graphics_clock_mhz is None:
            return

        if not self._apply_template:
            self._log(
                "dry-run control action: set_clock "
                f"target={decision.target_graphics_clock_mhz} MHz"
            )
            return

        cmd = self._apply_template.format(
            target_mhz=decision.target_graphics_clock_mhz,
            action=decision.action.value,
            reason=decision.reason_code,
        )
        self._log(f"applying control command: {cmd}")
        self._runner(cmd, shell=True, check=True)

    def reset(self) -> None:
        if not self._reset_cmd:
            return
        self._log(f"applying clock reset command: {self._reset_cmd}")
        self._runner(self._reset_cmd, shell=True, check=True)
