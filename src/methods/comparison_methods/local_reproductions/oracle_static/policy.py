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


@dataclass(slots=True, frozen=True)
class LoadedProfile:
    """Profile points plus provenance needed to audit oracle fidelity."""

    sweep_points: list[SweepPoint]
    mode: str
    provenance: str
    is_exact_workload: bool


PAPER_FREQUENCY_FLOOR_MHZ = 900


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
    selected, meets_target = _select_static_oracle_point(sweep_points, pd_target)
    return selected.frequency_mhz, meets_target


def _select_static_oracle_point(
    sweep_points: list[SweepPoint],
    pd_target: float,
) -> tuple[SweepPoint, bool]:
    if not sweep_points:
        raise ValueError("sweep_points must be non-empty.")

    target_ratio = 1.0 - _clamp(pd_target, 0.0, 0.99)
    valid_points = [point for point in sweep_points if point.performance_ratio >= target_ratio]

    if valid_points:
        selected = min(valid_points, key=lambda point: (point.frequency_mhz, _power_or_inf(point)))
        return selected, True

    fallback = max(sweep_points, key=lambda point: (point.performance_ratio, point.frequency_mhz))
    return fallback, False


class StaticOraclePolicy:
    """
    Static oracle baseline:
    1. Load offline profile for the current workload.
    2. Choose one fixed target clock for the configured PD.
    3. Apply once, then hold.

    Supported config schema:
    1. `workload_profiles`: mapping from workload name to point lists.
       Faithful mode requires an exact `workload_profiles[workload_name]`
       entry.
    2. `allow_proxy_profile`: optional bool. When true, the policy may use
       `workload_profiles.default` or `profile` as a non-faithful proxy and
       records that provenance in state and final summary.
    3. `enforce_paper_frequency_floor`: optional bool, default true. When true,
       points below the EVeREST-domain floor are ignored before selection.

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
        loaded_profile = _load_profile_for_workload(config, context.metadata.workload_name)
        effective_min_frequency_mhz = _effective_min_frequency_mhz(context, config)
        sweep_points, ignored_below_floor = _filter_points_by_frequency_floor(
            loaded_profile.sweep_points,
            effective_min_frequency_mhz,
            loaded_profile.provenance,
        )
        selected_point, meets_target = _select_static_oracle_point(sweep_points, context.pd_target)
        target_ratio = 1.0 - _clamp(context.pd_target, 0.0, 0.99)
        if loaded_profile.mode == "faithful" and not meets_target:
            raise ValueError(
                "StaticOraclePolicy exact workload profile does not contain any point meeting "
                f"target_ratio={target_ratio:.6g} for workload "
                f"{context.metadata.workload_name!r}."
            )

        selected_clock_mhz = selected_point.frequency_mhz
        selected_clock_mhz = _clamp_int(
            selected_clock_mhz,
            context.platform.min_graphics_clock_mhz,
            context.platform.max_graphics_clock_mhz,
        )

        state = AlgorithmState()
        state.set("run_id", context.metadata.run_id)
        state.set("pd_target", context.pd_target)
        state.set("target_ratio", target_ratio)
        state.set("selected_clock_mhz", selected_clock_mhz)
        state.set("selection_meets_target", meets_target)
        state.set("selected_profile_performance_ratio", selected_point.performance_ratio)
        state.set("selected_profile_frequency_mhz", selected_point.frequency_mhz)
        state.set("profile_mode", loaded_profile.mode)
        state.set("profile_provenance", loaded_profile.provenance)
        state.set("profile_is_exact_workload", loaded_profile.is_exact_workload)
        state.set("pre_run_target_graphics_clock_mhz", selected_clock_mhz)
        state.set("effective_min_frequency_mhz", effective_min_frequency_mhz)
        state.set("paper_frequency_floor_mhz", PAPER_FREQUENCY_FLOOR_MHZ)
        state.set(
            "enforces_paper_frequency_floor",
            _config_bool(config, "enforce_paper_frequency_floor", True),
        )
        state.set("ignored_profile_points_below_floor", ignored_below_floor)
        state.set("total_windows", 0)
        state.set("pd_violation_count", 0)
        state.set("max_pd_violation", 0.0)
        return state

    def initial_decision(
        self,
        context: ExperimentContext,  # noqa: ARG002 - kept for runner API symmetry.
        state: AlgorithmState,
    ) -> Decision:
        selected_clock_mhz = int(
            state.get("pre_run_target_graphics_clock_mhz", state.get("selected_clock_mhz"))
        )
        return Decision(
            action=DecisionAction.SET_CLOCK,
            target_graphics_clock_mhz=selected_clock_mhz,
            reason_code="oracle_static_pre_run_apply_selected_clock",
            debug_fields=_decision_debug_fields(state),
        )

    def on_window(
        self,
        metrics: MetricWindow,
        state: AlgorithmState,
    ) -> Decision:
        """Monitor-only window step.

        The fixed clock is owned by ``initial_decision`` (applied once before
        window 0), so this method never emits a clock change. It only counts
        windows, tracks PD violations, and holds.
        """
        total_windows = int(state.get("total_windows", 0)) + 1
        state.set("total_windows", total_windows)
        _update_pd_violation_if_present(metrics, state)

        return Decision(
            action=DecisionAction.HOLD_CLOCK,
            target_graphics_clock_mhz=None,
            reason_code="oracle_static_monitor_hold",
            debug_fields=_decision_debug_fields(state),
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
                "target_ratio": float(state.get("target_ratio", 1.0)),
                "selected_profile_performance_ratio": float(
                    state.get("selected_profile_performance_ratio", 0.0)
                ),
                "selected_profile_frequency_mhz": int(
                    state.get("selected_profile_frequency_mhz", 0)
                ),
                "profile_mode": str(state.get("profile_mode", "")),
                "profile_provenance": str(state.get("profile_provenance", "")),
                "profile_is_exact_workload": bool(state.get("profile_is_exact_workload", False)),
                "pre_run_target_graphics_clock_mhz": int(
                    state.get("pre_run_target_graphics_clock_mhz", 0)
                ),
                "effective_min_frequency_mhz": int(state.get("effective_min_frequency_mhz", 0)),
                "paper_frequency_floor_mhz": int(state.get("paper_frequency_floor_mhz", 0)),
                "enforces_paper_frequency_floor": bool(
                    state.get("enforces_paper_frequency_floor", False)
                ),
                "ignored_profile_points_below_floor": int(
                    state.get("ignored_profile_points_below_floor", 0)
                ),
            },
        )


def _load_profile_for_workload(config: Mapping[str, object], workload_name: str) -> LoadedProfile:
    allow_proxy_profile = _config_bool(config, "allow_proxy_profile", False)

    raw_workload_profiles = config.get("workload_profiles")
    if isinstance(raw_workload_profiles, Mapping):
        if workload_name in raw_workload_profiles:
            provenance = f"workload_profiles[{workload_name}]"
            return LoadedProfile(
                sweep_points=_parse_profile_object(
                    raw_workload_profiles[workload_name],
                    provenance,
                ),
                mode="faithful",
                provenance=provenance,
                is_exact_workload=True,
            )
        if allow_proxy_profile and "default" in raw_workload_profiles:
            provenance = "workload_profiles.default"
            return LoadedProfile(
                sweep_points=_parse_profile_object(raw_workload_profiles["default"], provenance),
                mode="proxy",
                provenance=provenance,
                is_exact_workload=False,
            )

    if allow_proxy_profile and "profile" in config:
        provenance = "profile"
        return LoadedProfile(
            sweep_points=_parse_profile_object(config.get("profile"), provenance),
            mode="proxy",
            provenance=provenance,
            is_exact_workload=False,
        )

    raise ValueError(
        "StaticOraclePolicy requires an exact workload profile at "
        f"workload_profiles[{workload_name!r}] in faithful mode. Set "
        "allow_proxy_profile=true only for explicitly labeled non-faithful "
        "proxy runs."
    )


def _parse_profile_object(profile_object: object, provenance: str) -> list[SweepPoint]:
    if not isinstance(profile_object, list):
        raise ValueError(
            f"StaticOraclePolicy profile {provenance!r} must be a list of sweep points."
        )
    return [_parse_sweep_point(entry) for entry in profile_object]


def _parse_sweep_point(entry: object) -> SweepPoint:
    if not isinstance(entry, Mapping):
        raise ValueError("Each profile entry must be a mapping.")

    frequency_mhz = _extract_required_number(
        entry,
        ("frequency_mhz", "freq_mhz", "clock_mhz"),
        "frequency",
    )
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


def _extract_required_number(
    entry: Mapping[str, object],
    keys: tuple[str, ...],
    field_name: str,
) -> float:
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


def _decision_debug_fields(state: AlgorithmState) -> dict[str, object]:
    return {
        "selected_clock_mhz": int(state.get("selected_clock_mhz", 0)),
        "pre_run_target_graphics_clock_mhz": int(
            state.get("pre_run_target_graphics_clock_mhz", 0)
        ),
        "selection_meets_target": bool(state.get("selection_meets_target", False)),
        "profile_mode": str(state.get("profile_mode", "")),
        "profile_provenance": str(state.get("profile_provenance", "")),
        "profile_is_exact_workload": bool(state.get("profile_is_exact_workload", False)),
        "effective_min_frequency_mhz": int(state.get("effective_min_frequency_mhz", 0)),
    }


def _effective_min_frequency_mhz(
    context: ExperimentContext,
    config: Mapping[str, object],
) -> int:
    if not _config_bool(config, "enforce_paper_frequency_floor", True):
        return context.platform.min_graphics_clock_mhz
    if context.platform.max_graphics_clock_mhz >= PAPER_FREQUENCY_FLOOR_MHZ:
        return max(context.platform.min_graphics_clock_mhz, PAPER_FREQUENCY_FLOOR_MHZ)
    return context.platform.min_graphics_clock_mhz


def _filter_points_by_frequency_floor(
    sweep_points: list[SweepPoint],
    effective_min_frequency_mhz: int,
    provenance: str,
) -> tuple[list[SweepPoint], int]:
    filtered_points = [
        point for point in sweep_points if point.frequency_mhz >= effective_min_frequency_mhz
    ]
    ignored_count = len(sweep_points) - len(filtered_points)
    if not filtered_points:
        raise ValueError(
            f"StaticOraclePolicy profile {provenance!r} has no sweep points at or above "
            f"effective_min_frequency_mhz={effective_min_frequency_mhz}."
        )
    return filtered_points, ignored_count


def _power_or_inf(point: SweepPoint) -> float:
    return float("inf") if point.power_w is None else point.power_w


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def _clamp_int(value: int, lower: int, upper: int) -> int:
    return int(max(lower, min(value, upper)))


def _config_bool(config: Mapping[str, object], key: str, default: bool) -> bool:
    value = config.get(key)
    if isinstance(value, bool):
        return value
    return default
