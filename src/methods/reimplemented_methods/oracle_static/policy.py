from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from src.common.experiment import (
    AlgorithmState,
    Decision,
    DecisionAction,
    ExperimentContext,
    FinalSummary,
    MetricWindow,
)


@dataclass(slots=True, frozen=True)
class SweepPoint:
    """One offline sweep point used by the static-oracle selector."""

    frequency_mhz: int
    performance_ratio: float
    power_w: float | None = None


def choose_static_oracle_clock(
    sweep_points: list[SweepPoint],
    pd_target: float,
) -> tuple[int, bool]:
    """
    Selects one fixed clock from offline sweep points.

    The static oracle chooses the lowest frequency that still satisfies:
    `performance_ratio >= (1 - pd_target)`.
    If no point satisfies the target, it falls back to the point with the best
    observed performance ratio.

    Returns:
        (selected_frequency_mhz, meets_target_in_profile)
    """
    if not sweep_points:
        raise ValueError("sweep_points must be non-empty.")

    target_ratio = 1.0 - _clamp(pd_target, 0.0, 0.99)
    valid_points = [point for point in sweep_points if point.performance_ratio >= target_ratio]

    if valid_points:
        selected = min(valid_points, key=lambda point: (point.frequency_mhz, _power_or_inf(point)))
        return selected.frequency_mhz, True

    fallback = max(sweep_points, key=lambda point: (point.performance_ratio, point.frequency_mhz))
    return fallback.frequency_mhz, False


class StaticOraclePolicy:
    """
    Static oracle baseline:
    1. Load offline profile for the current workload.
    2. Choose one fixed target clock for the configured PD.
    3. Apply once, then hold.

    Supported config schema:
    1. `workload_profiles`: mapping from workload name to point lists.
       Optional `default` entry is used as fallback.
    2. `profile`: point list for all workloads.

    Point record keys:
    - frequency: `frequency_mhz` | `freq_mhz` | `clock_mhz`
    - performance ratio: `performance_ratio` | `perf_ratio` | `relative_performance`
    - optional power: `power_w` | `avg_power_w` | `power`
    """

    policy_name = "oracle_static"

    def initialize(
        self,
        context: ExperimentContext,
        config: Mapping[str, object],
    ) -> AlgorithmState:
        sweep_points = _load_profile_for_workload(config, context.metadata.workload_name)
        selected_clock_mhz, meets_target = choose_static_oracle_clock(sweep_points, context.pd_target)
        selected_clock_mhz = _clamp_int(
            selected_clock_mhz,
            context.platform.min_graphics_clock_mhz,
            context.platform.max_graphics_clock_mhz,
        )

        state = AlgorithmState()
        state.set("run_id", context.metadata.run_id)
        state.set("pd_target", context.pd_target)
        state.set("target_ratio", 1.0 - _clamp(context.pd_target, 0.0, 0.99))
        state.set("selected_clock_mhz", selected_clock_mhz)
        state.set("selection_meets_target", meets_target)
        state.set("decision_emitted", False)
        state.set("total_windows", 0)
        state.set("pd_violation_count", 0)
        state.set("max_pd_violation", 0.0)
        return state

    def on_window(
        self,
        metrics: MetricWindow,
        state: AlgorithmState,
    ) -> Decision:
        total_windows = int(state.get("total_windows", 0)) + 1
        state.set("total_windows", total_windows)
        _update_pd_violation_if_present(metrics, state)

        selected_clock_mhz = int(state.get("selected_clock_mhz"))
        if not state.get("decision_emitted", False):
            state.set("decision_emitted", True)
            if _is_same_clock(metrics.graphics_clock_avg_mhz, selected_clock_mhz):
                return Decision(
                    action=DecisionAction.HOLD_CLOCK,
                    target_graphics_clock_mhz=None,
                    reason_code="oracle_static_already_at_target",
                    debug_fields={"selected_clock_mhz": selected_clock_mhz},
                )
            return Decision(
                action=DecisionAction.SET_CLOCK,
                target_graphics_clock_mhz=selected_clock_mhz,
                reason_code="oracle_static_apply_selected_clock",
                debug_fields={"selected_clock_mhz": selected_clock_mhz},
            )

        return Decision(
            action=DecisionAction.HOLD_CLOCK,
            target_graphics_clock_mhz=None,
            reason_code="oracle_static_hold_selected_clock",
            debug_fields={"selected_clock_mhz": selected_clock_mhz},
        )

    def finalize(self, state: AlgorithmState) -> FinalSummary:
        return FinalSummary(
            policy_name=self.policy_name,
            run_id=str(state.get("run_id")),
            total_windows=int(state.get("total_windows", 0)),
            pd_target=float(state.get("pd_target", 0.0)),
            pd_violation_count=int(state.get("pd_violation_count", 0)),
            max_pd_violation=float(state.get("max_pd_violation", 0.0)),
            custom_summary={
                "selected_clock_mhz": int(state.get("selected_clock_mhz", 0)),
                "selection_meets_target": bool(state.get("selection_meets_target", False)),
            },
        )


def _load_profile_for_workload(config: Mapping[str, object], workload_name: str) -> list[SweepPoint]:
    profile_object: object | None = None

    raw_workload_profiles = config.get("workload_profiles")
    if isinstance(raw_workload_profiles, Mapping):
        if workload_name in raw_workload_profiles:
            profile_object = raw_workload_profiles[workload_name]
        elif "default" in raw_workload_profiles:
            profile_object = raw_workload_profiles["default"]

    if profile_object is None:
        profile_object = config.get("profile")

    if not isinstance(profile_object, list):
        raise ValueError(
            "StaticOraclePolicy requires a profile list via workload_profiles[workload]/default or profile."
        )
    return [_parse_sweep_point(entry) for entry in profile_object]


def _parse_sweep_point(entry: object) -> SweepPoint:
    if not isinstance(entry, Mapping):
        raise ValueError("Each profile entry must be a mapping.")

    frequency_mhz = _extract_required_number(entry, ("frequency_mhz", "freq_mhz", "clock_mhz"), "frequency")
    performance_ratio = _extract_required_number(
        entry,
        ("performance_ratio", "perf_ratio", "relative_performance"),
        "performance_ratio",
    )
    power_w = _extract_optional_number(entry, ("power_w", "avg_power_w", "power"))
    return SweepPoint(
        frequency_mhz=int(round(frequency_mhz)),
        performance_ratio=float(performance_ratio),
        power_w=None if power_w is None else float(power_w),
    )


def _extract_required_number(entry: Mapping[str, object], keys: tuple[str, ...], field_name: str) -> float:
    for key in keys:
        value = entry.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    raise ValueError(f"Missing numeric field for {field_name}. Checked keys: {keys}.")


def _extract_optional_number(entry: Mapping[str, object], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = entry.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _update_pd_violation_if_present(metrics: MetricWindow, state: AlgorithmState) -> None:
    custom_metrics = metrics.custom_metrics
    if not custom_metrics:
        return

    perf_ratio = _extract_optional_number(
        custom_metrics,
        ("performance_ratio", "relative_performance", "perf_ratio_to_max"),
    )
    if perf_ratio is None:
        return

    target_ratio = float(state.get("target_ratio", 1.0))
    violation = max(0.0, target_ratio - perf_ratio)
    if violation <= 0:
        return

    state.set("pd_violation_count", int(state.get("pd_violation_count", 0)) + 1)
    state.set("max_pd_violation", max(float(state.get("max_pd_violation", 0.0)), violation))


def _is_same_clock(observed_clock_mhz: float, target_clock_mhz: int) -> bool:
    return abs(observed_clock_mhz - float(target_clock_mhz)) < 0.5


def _power_or_inf(point: SweepPoint) -> float:
    return float("inf") if point.power_w is None else point.power_w


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def _clamp_int(value: int, lower: int, upper: int) -> int:
    return int(max(lower, min(value, upper)))
