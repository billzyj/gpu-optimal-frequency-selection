from __future__ import annotations

from typing import Mapping

from src.common.experiment import (
    AlgorithmState,
    Decision,
    DecisionAction,
    ExperimentContext,
    FinalSummary,
    MetricWindow,
)


class FixedClockPolicy:
    """Base implementation for one-shot fixed-clock baselines."""

    policy_name: str

    def initialize(
        self,
        context: ExperimentContext,
        config: Mapping[str, object],
    ) -> AlgorithmState:
        _ = config
        state = AlgorithmState()
        state.set("run_id", context.metadata.run_id)
        state.set("pd_target", context.pd_target)
        state.set("selected_clock_mhz", self._select_clock_mhz(context))
        state.set("total_windows", 0)
        return state

    def initial_decision(
        self,
        context: ExperimentContext,  # noqa: ARG002 - kept for runner API symmetry.
        state: AlgorithmState,
    ) -> Decision:
        target = int(state.get("selected_clock_mhz"))
        return Decision(
            action=DecisionAction.SET_CLOCK,
            target_graphics_clock_mhz=target,
            reason_code=f"{self.policy_name}_pre_run_apply",
            debug_fields={"selected_clock_mhz": target},
        )

    def on_window(
        self,
        metrics: MetricWindow,  # noqa: ARG002 - monitor-only; clock owned by initial_decision.
        state: AlgorithmState,
    ) -> Decision:
        state.set("total_windows", int(state.get("total_windows", 0)) + 1)
        target = int(state.get("selected_clock_mhz"))

        return Decision(
            action=DecisionAction.HOLD_CLOCK,
            target_graphics_clock_mhz=None,
            reason_code=f"{self.policy_name}_monitor_hold",
            debug_fields={"selected_clock_mhz": target},
        )

    def finalize(self, state: AlgorithmState) -> FinalSummary:
        return FinalSummary(
            policy_name=self.policy_name,
            run_id=str(state.get("run_id")),
            total_windows=int(state.get("total_windows", 0)),
            pd_target=float(state.get("pd_target", 0.0)),
            pd_violation_count=0,
            max_pd_violation=0.0,
            custom_summary={"selected_clock_mhz": int(state.get("selected_clock_mhz", 0))},
        )

    def _select_clock_mhz(self, context: ExperimentContext) -> int:
        raise NotImplementedError
