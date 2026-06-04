from __future__ import annotations

from dataclasses import asdict, dataclass
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
class PowerModelCoefficients:
    """Coefficients for Ali et al.'s analytical power model."""

    alpha: float
    beta: float
    gamma: float
    constant: float


@dataclass(slots=True, frozen=True)
class PerformanceModelCoefficients:
    """Coefficients for Ali et al.'s max-frequency-relative runtime model."""

    beta1: float
    beta2: float
    beta3: float
    beta4: float
    beta5: float


@dataclass(slots=True, frozen=True)
class AliFrequencyEstimate:
    """One estimated objective row for a candidate GPU core frequency."""

    frequency_mhz: int
    power_w: float
    runtime_s: float
    energy_j: float
    edp: float
    ed2p: float

    def to_dict(self) -> dict[str, int | float]:
        return asdict(self)


@dataclass(slots=True, frozen=True)
class AliSelectionResult:
    """Objective-selection result for one Ali whole-workload decision."""

    objective: str
    selected_frequency_mhz: int
    selected_estimate: AliFrequencyEstimate
    estimates: list[AliFrequencyEstimate]


def estimate_power_w(
    *,
    frequency_mhz: int,
    fp_activity: float,
    dram_activity: float,
    coefficients: PowerModelCoefficients,
) -> float:
    """Evaluates P_f = alpha * FP_act + beta * DRAM_act + gamma * f + C."""

    return (
        coefficients.alpha * fp_activity
        + coefficients.beta * dram_activity
        + coefficients.gamma * frequency_mhz
        + coefficients.constant
    )


def estimate_runtime_s(
    *,
    frequency_mhz: int,
    f_max_mhz: int,
    fp_activity: float,
    t_fmax_s: float,
    coefficients: PerformanceModelCoefficients,
) -> float:
    """
    Evaluates Ali et al.'s max-frequency-relative runtime model.

    delta_f is intentionally defined as f_max - f, matching the reproduction
    plan and paper model structure.
    """

    delta_f = float(f_max_mhz - frequency_mhz)
    fp = float(fp_activity)
    return (
        t_fmax_s
        + coefficients.beta1 * fp
        + coefficients.beta2 * delta_f
        + coefficients.beta3 * fp * fp
        + coefficients.beta4 * fp * delta_f
        + coefficients.beta5 * delta_f * delta_f
    )


def build_frequency_estimates(
    *,
    frequencies_mhz: list[int],
    f_max_mhz: int,
    fp_activity: float,
    dram_activity: float,
    t_fmax_s: float,
    power_coefficients: PowerModelCoefficients,
    performance_coefficients: PerformanceModelCoefficients,
) -> list[AliFrequencyEstimate]:
    """Builds power, runtime, energy, EDP, and ED2P rows for all candidates."""

    if not frequencies_mhz:
        raise ValueError("frequencies_mhz must be non-empty.")

    estimates: list[AliFrequencyEstimate] = []
    for frequency_mhz in frequencies_mhz:
        power_w = estimate_power_w(
            frequency_mhz=frequency_mhz,
            fp_activity=fp_activity,
            dram_activity=dram_activity,
            coefficients=power_coefficients,
        )
        runtime_s = estimate_runtime_s(
            frequency_mhz=frequency_mhz,
            f_max_mhz=f_max_mhz,
            fp_activity=fp_activity,
            t_fmax_s=t_fmax_s,
            coefficients=performance_coefficients,
        )
        energy_j = power_w * runtime_s
        edp = energy_j * runtime_s
        ed2p = energy_j * runtime_s * runtime_s
        estimates.append(
            AliFrequencyEstimate(
                frequency_mhz=int(frequency_mhz),
                power_w=power_w,
                runtime_s=runtime_s,
                energy_j=energy_j,
                edp=edp,
                ed2p=ed2p,
            )
        )
    return estimates


def select_frequency_by_objective(
    estimates: list[AliFrequencyEstimate],
    *,
    objective: str = "edp",
) -> AliSelectionResult:
    """Selects the conventional argmin for EDP or ED2P."""

    objective = _normalize_objective(objective)
    if not estimates:
        raise ValueError("estimates must be non-empty.")

    selected = min(estimates, key=lambda estimate: getattr(estimate, objective))
    return AliSelectionResult(
        objective=objective,
        selected_frequency_mhz=selected.frequency_mhz,
        selected_estimate=selected,
        estimates=estimates,
    )


class AliFrequencySelectionPolicy:
    """
    Offline, application-level Ali HPEC 2022 frequency selector.

    The policy computes one model-based whole-workload frequency at
    initialization, applies it once if needed, then holds that clock.
    """

    policy_name = "ali_2022_reimpl"

    def initialize(
        self,
        context: ExperimentContext,
        config: Mapping[str, object],
    ) -> AlgorithmState:
        objective = _normalize_objective(_optional_string(config, "objective", "edp"))
        f_max_mhz = _optional_int(config, "f_max_mhz", context.platform.max_graphics_clock_mhz)
        frequencies_mhz = _load_frequencies(config, context)
        fp_activity = _required_float(config, "fp_activity")
        dram_activity = _required_float(config, "dram_activity")
        t_fmax_s = _required_float(config, "t_fmax_s")
        power_coefficients = _load_power_coefficients(config)
        performance_coefficients = _load_performance_coefficients(config)

        estimates = build_frequency_estimates(
            frequencies_mhz=frequencies_mhz,
            f_max_mhz=f_max_mhz,
            fp_activity=fp_activity,
            dram_activity=dram_activity,
            t_fmax_s=t_fmax_s,
            power_coefficients=power_coefficients,
            performance_coefficients=performance_coefficients,
        )
        selection = select_frequency_by_objective(estimates, objective=objective)

        state = AlgorithmState()
        state.set("run_id", context.metadata.run_id)
        state.set("pd_target", context.pd_target)
        state.set("objective", selection.objective)
        state.set("selected_clock_mhz", selection.selected_frequency_mhz)
        state.set("selected_estimate", selection.selected_estimate.to_dict())
        state.set("frequency_estimates", [estimate.to_dict() for estimate in estimates])
        state.set("f_max_mhz", f_max_mhz)
        state.set("fp_activity", fp_activity)
        state.set("dram_activity", dram_activity)
        state.set("t_fmax_s", t_fmax_s)
        state.set("power_coefficients", asdict(power_coefficients))
        state.set("performance_coefficients", asdict(performance_coefficients))
        state.set("decision_emitted", False)
        state.set("total_windows", 0)
        return state

    def on_window(
        self,
        metrics: MetricWindow,
        state: AlgorithmState,
    ) -> Decision:
        state.set("total_windows", int(state.get("total_windows", 0)) + 1)
        selected_clock_mhz = int(state.get("selected_clock_mhz"))
        debug_fields = {
            "selected_clock_mhz": selected_clock_mhz,
            "objective": str(state.get("objective")),
        }

        if not bool(state.get("decision_emitted", False)):
            state.set("decision_emitted", True)
            if _is_same_clock(metrics.graphics_clock_avg_mhz, selected_clock_mhz):
                return Decision(
                    action=DecisionAction.HOLD_CLOCK,
                    target_graphics_clock_mhz=None,
                    reason_code="ali_already_at_selected_clock",
                    debug_fields=debug_fields,
                )
            return Decision(
                action=DecisionAction.SET_CLOCK,
                target_graphics_clock_mhz=selected_clock_mhz,
                reason_code="ali_apply_selected_clock",
                debug_fields=debug_fields,
            )

        return Decision(
            action=DecisionAction.HOLD_CLOCK,
            target_graphics_clock_mhz=None,
            reason_code="ali_hold_selected_clock",
            debug_fields=debug_fields,
        )

    def finalize(self, state: AlgorithmState) -> FinalSummary:
        return FinalSummary(
            policy_name=self.policy_name,
            run_id=str(state.get("run_id")),
            total_windows=int(state.get("total_windows", 0)),
            pd_target=float(state.get("pd_target", 0.0)),
            pd_violation_count=0,
            max_pd_violation=0.0,
            custom_summary={
                "selected_clock_mhz": int(state.get("selected_clock_mhz", 0)),
                "objective": str(state.get("objective")),
                "model_scope": "offline_application_level",
                "f_max_mhz": int(state.get("f_max_mhz", 0)),
                "fp_activity": float(state.get("fp_activity", 0.0)),
                "dram_activity": float(state.get("dram_activity", 0.0)),
                "t_fmax_s": float(state.get("t_fmax_s", 0.0)),
                "selected_estimate": state.get("selected_estimate", {}),
                "frequency_estimates": state.get("frequency_estimates", []),
                "power_coefficients": state.get("power_coefficients", {}),
                "performance_coefficients": state.get("performance_coefficients", {}),
            },
        )


def _normalize_objective(objective: str) -> str:
    if objective not in {"edp", "ed2p"}:
        raise ValueError("objective must be 'edp' or 'ed2p'.")
    return objective


def _load_frequencies(config: Mapping[str, object], context: ExperimentContext) -> list[int]:
    raw_frequencies = config.get("frequencies_mhz")
    if raw_frequencies is None:
        step = context.platform.graphics_clock_step_mhz
        if step <= 0:
            raise ValueError("platform graphics_clock_step_mhz must be positive.")
        return list(
            range(
                context.platform.min_graphics_clock_mhz,
                context.platform.max_graphics_clock_mhz + 1,
                step,
            )
        )

    if not isinstance(raw_frequencies, list):
        raise ValueError("frequencies_mhz must be a list of numeric clock values.")

    frequencies: list[int] = []
    for value in raw_frequencies:
        if not _is_number(value):
            raise ValueError("frequencies_mhz must contain only numeric clock values.")
        frequencies.append(int(round(float(value))))
    if not frequencies:
        raise ValueError("frequencies_mhz must be non-empty.")
    return frequencies


def _load_power_coefficients(config: Mapping[str, object]) -> PowerModelCoefficients:
    raw_coefficients = _required_mapping(config, "power_coefficients")
    return PowerModelCoefficients(
        alpha=_required_float(raw_coefficients, "alpha"),
        beta=_required_float(raw_coefficients, "beta"),
        gamma=_required_float(raw_coefficients, "gamma"),
        constant=_required_float(raw_coefficients, "constant"),
    )


def _load_performance_coefficients(config: Mapping[str, object]) -> PerformanceModelCoefficients:
    raw_coefficients = _required_mapping(config, "performance_coefficients")
    return PerformanceModelCoefficients(
        beta1=_required_float(raw_coefficients, "beta1"),
        beta2=_required_float(raw_coefficients, "beta2"),
        beta3=_required_float(raw_coefficients, "beta3"),
        beta4=_required_float(raw_coefficients, "beta4"),
        beta5=_required_float(raw_coefficients, "beta5"),
    )


def _required_mapping(config: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = config.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"{key} must be a mapping.")
    return value


def _required_float(config: Mapping[str, object], key: str) -> float:
    value = config.get(key)
    if not _is_number(value):
        raise ValueError(f"{key} must be numeric.")
    return float(value)


def _optional_int(config: Mapping[str, object], key: str, default: int) -> int:
    value = config.get(key)
    if value is None:
        return default
    if not _is_number(value):
        raise ValueError(f"{key} must be numeric.")
    return int(round(float(value)))


def _optional_string(config: Mapping[str, object], key: str, default: str) -> str:
    value = config.get(key)
    if value is None:
        return default
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string.")
    return value


def _is_same_clock(observed_clock_mhz: float, target_clock_mhz: int) -> bool:
    return abs(observed_clock_mhz - float(target_clock_mhz)) < 0.5


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)
