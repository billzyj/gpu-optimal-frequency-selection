from __future__ import annotations

import unittest

from src.common.control import ClockController, ShellTemplateController
from src.common.experiment.types import Decision, DecisionAction


def _set_clock(target: int = 1410) -> Decision:
    return Decision(
        action=DecisionAction.SET_CLOCK,
        target_graphics_clock_mhz=target,
        reason_code="test_apply",
    )


class _RecordingRunner:
    """Captures subprocess-style calls instead of executing them."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def __call__(self, cmd: str, **kwargs: object) -> None:
        self.calls.append((cmd, kwargs))
        return None


class ShellTemplateControllerTests(unittest.TestCase):
    def test_satisfies_clock_controller_protocol(self) -> None:
        self.assertIsInstance(ShellTemplateController(apply_template=None), ClockController)

    def test_apply_with_template_runs_formatted_command(self) -> None:
        runner = _RecordingRunner()
        logs: list[str] = []
        controller = ShellTemplateController(
            apply_template="set -g {target_mhz} a={action} r={reason}",
            logger=logs.append,
            runner=runner,
        )

        controller.apply(_set_clock(1200))

        self.assertEqual(len(runner.calls), 1)
        cmd, kwargs = runner.calls[0]
        self.assertEqual(cmd, "set -g 1200 a=set_clock r=test_apply")
        self.assertTrue(kwargs.get("shell"))
        self.assertTrue(kwargs.get("check"))
        self.assertTrue(any("applying control command" in message for message in logs))

    def test_apply_without_template_is_dry_run(self) -> None:
        runner = _RecordingRunner()
        logs: list[str] = []
        controller = ShellTemplateController(
            apply_template=None, logger=logs.append, runner=runner
        )

        controller.apply(_set_clock(900))

        self.assertEqual(runner.calls, [])
        self.assertTrue(
            any("dry-run control action" in message and "900" in message for message in logs)
        )

    def test_apply_is_noop_for_hold(self) -> None:
        runner = _RecordingRunner()
        logs: list[str] = []
        controller = ShellTemplateController(
            apply_template="set -g {target_mhz}", logger=logs.append, runner=runner
        )

        controller.apply(
            Decision(
                action=DecisionAction.HOLD_CLOCK,
                target_graphics_clock_mhz=None,
                reason_code="hold",
            )
        )

        self.assertEqual(runner.calls, [])
        self.assertEqual(logs, [])

    def test_reset_runs_reset_command(self) -> None:
        runner = _RecordingRunner()
        controller = ShellTemplateController(
            apply_template=None, reset_cmd="reset-clocks", runner=runner
        )

        controller.reset()

        self.assertEqual(len(runner.calls), 1)
        self.assertEqual(runner.calls[0][0], "reset-clocks")

    def test_reset_without_command_is_noop(self) -> None:
        runner = _RecordingRunner()
        controller = ShellTemplateController(apply_template=None, runner=runner)

        controller.reset()

        self.assertEqual(runner.calls, [])


if __name__ == "__main__":
    unittest.main()
