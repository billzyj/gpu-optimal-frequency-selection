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
        state.set("decision_emitted", False)
        state.set("total_windows", 0)
        return state

    def on_window(
        self,
        metrics: MetricWindow,
        state: AlgorithmState,
    ) -> Decision:
        state.set("total_windows", int(state.get("total_windows", 0)) + 1)
        target = int(state.get("selected_clock_mhz"))

        if not bool(state.get("decision_emitted", False)):
            state.set("decision_emitted", True)
            if _is_same_clock(metrics.graphics_clock_avg_mhz, target):
                return Decision(
                    action=DecisionAction.HOLD_CLOCK,
                    target_graphics_clock_mhz=None,
                    reason_code=f"{self.policy_name}_already_at_target",
                )
            return Decision(
                action=DecisionAction.SET_CLOCK,
                target_graphics_clock_mhz=target,
                reason_code=f"{self.policy_name}_apply",
            )

        return Decision(
            action=DecisionAction.HOLD_CLOCK,
            target_graphics_clock_mhz=None,
            reason_code=f"{self.policy_name}_hold",
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


def _is_same_clock(observed_clock_mhz: float, target_clock_mhz: int) -> bool:
    return abs(observed_clock_mhz - float(target_clock_mhz)) < 0.5
