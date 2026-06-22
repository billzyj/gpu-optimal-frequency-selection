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

PAPER_FAITHFUL_GV100_MODE = "paper_faithful_gv100"
ALGORITHMIC_PROXY_MODE = "algorithmic_proxy"
_VALID_REPRODUCTION_MODES = {PAPER_FAITHFUL_GV100_MODE, ALGORITHMIC_PROXY_MODE}
_PAPER_GV100_MIN_MHZ = 510
_PAPER_GV100_MAX_MHZ = 1380


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
        reproduction_mode = _normalize_reproduction_mode(
            _optional_string(config, "reproduction_mode", PAPER_FAITHFUL_GV100_MODE)
        )
        f_max_mhz = _optional_int(config, "f_max_mhz", context.platform.max_graphics_clock_mhz)
        _validate_f_max_mhz(f_max_mhz, context)
        frequencies_mhz = _load_frequencies(config, context)
        _validate_frequency_space(
            frequencies_mhz=frequencies_mhz,
            f_max_mhz=f_max_mhz,
            reproduction_mode=reproduction_mode,
            context=context,
        )
        fp_activity = _required_float(config, "fp_activity")
        dram_activity = _required_float(config, "dram_activity")
        t_fmax_s = _required_float(config, "t_fmax_s")
        power_coefficients = _load_power_coefficients(config)
        performance_coefficients = _load_performance_coefficients(config)
        profiling_run_count = _optional_positive_int(config, "profiling_run_count")
        sampling_interval_ms = _optional_positive_int(config, "sampling_interval_ms")
        profiler_source = _optional_nullable_string(config, "profiler_source")
        profile_source = _optional_nullable_string(config, "profile_source")
        calibration_source = _optional_nullable_string(config, "calibration_source")

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
        state.set("reproduction_mode", reproduction_mode)
        state.set("selected_clock_mhz", selection.selected_frequency_mhz)
        state.set("pre_run_target_graphics_clock_mhz", selection.selected_frequency_mhz)
        state.set("requires_pre_run_clock", True)
        state.set("selected_estimate", selection.selected_estimate.to_dict())
        state.set("frequency_estimates", [estimate.to_dict() for estimate in estimates])
        state.set("frequencies_mhz", frequencies_mhz)
        state.set("f_max_mhz", f_max_mhz)
        state.set("fp_activity", fp_activity)
        state.set("dram_activity", dram_activity)
        state.set("t_fmax_s", t_fmax_s)
        state.set("profiling_run_count", profiling_run_count)
        state.set("sampling_interval_ms", sampling_interval_ms)
        state.set("runtime_sampling_interval_ms", context.sampling_interval_ms)
        state.set("profiler_source", profiler_source)
        state.set("profile_source", profile_source)
        state.set("calibration_source", calibration_source)
        state.set("power_coefficients", asdict(power_coefficients))
        state.set("performance_coefficients", asdict(performance_coefficients))
        state.set("total_windows", 0)
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
            reason_code="ali_pre_run_apply_selected_clock",
            debug_fields=_decision_debug_fields(state),
        )

    def on_window(
        self,
        metrics: MetricWindow,  # noqa: ARG002 - monitor-only; clock owned by initial_decision.
        state: AlgorithmState,
    ) -> Decision:
        """Monitor-only window step.

        The selected whole-workload clock is owned by ``initial_decision``
        (applied once before window 0), so this method never emits a clock
        change. It only counts windows and holds.
        """
        state.set("total_windows", int(state.get("total_windows", 0)) + 1)
        return Decision(
            action=DecisionAction.HOLD_CLOCK,
            target_graphics_clock_mhz=None,
            reason_code="ali_monitor_hold",
            debug_fields=_decision_debug_fields(state),
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
                "pre_run_target_graphics_clock_mhz": int(
                    state.get("pre_run_target_graphics_clock_mhz", 0)
                ),
                "requires_pre_run_clock": bool(state.get("requires_pre_run_clock", False)),
                "objective": str(state.get("objective")),
                "reproduction_mode": str(state.get("reproduction_mode")),
                "model_scope": "offline_application_level",
                "f_max_mhz": int(state.get("f_max_mhz", 0)),
                "frequencies_mhz": state.get("frequencies_mhz", []),
                "fp_activity": float(state.get("fp_activity", 0.0)),
                "dram_activity": float(state.get("dram_activity", 0.0)),
                "t_fmax_s": float(state.get("t_fmax_s", 0.0)),
                "profiling_run_count": state.get("profiling_run_count"),
                "sampling_interval_ms": state.get("sampling_interval_ms"),
                "runtime_sampling_interval_ms": int(
                    state.get("runtime_sampling_interval_ms", 0)
                ),
                "profiler_source": state.get("profiler_source"),
                "profile_source": state.get("profile_source"),
                "calibration_source": state.get("calibration_source"),
                "selected_estimate": state.get("selected_estimate", {}),
                "frequency_estimates": state.get("frequency_estimates", []),
                "power_coefficients": state.get("power_coefficients", {}),
                "performance_coefficients": state.get("performance_coefficients", {}),
            },
        )


def _decision_debug_fields(state: AlgorithmState) -> dict[str, object]:
    selected_clock_mhz = int(state.get("selected_clock_mhz", 0))
    return {
        "selected_clock_mhz": selected_clock_mhz,
        "pre_run_target_graphics_clock_mhz": int(
            state.get("pre_run_target_graphics_clock_mhz", selected_clock_mhz)
        ),
        "requires_pre_run_clock": bool(state.get("requires_pre_run_clock", False)),
        "objective": str(state.get("objective")),
        "reproduction_mode": str(state.get("reproduction_mode")),
    }


def _normalize_objective(objective: str) -> str:
    if objective not in {"edp", "ed2p"}:
        raise ValueError("objective must be 'edp' or 'ed2p'.")
    return objective


def _normalize_reproduction_mode(reproduction_mode: str) -> str:
    if reproduction_mode not in _VALID_REPRODUCTION_MODES:
        raise ValueError(
            "reproduction_mode must be 'paper_faithful_gv100' or 'algorithmic_proxy'."
        )
    return reproduction_mode


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


def _validate_f_max_mhz(f_max_mhz: int, context: ExperimentContext) -> None:
    if not (
        context.platform.min_graphics_clock_mhz
        <= f_max_mhz
        <= context.platform.max_graphics_clock_mhz
    ):
        raise ValueError(
            "f_max_mhz must fall within the platform graphics clock range."
        )


def _validate_frequency_space(
    *,
    frequencies_mhz: list[int],
    f_max_mhz: int,
    reproduction_mode: str,
    context: ExperimentContext,
) -> None:
    previous_frequency_mhz: int | None = None
    for frequency_mhz in frequencies_mhz:
        if previous_frequency_mhz is not None and frequency_mhz <= previous_frequency_mhz:
            raise ValueError(
                "frequencies_mhz must be strictly increasing with unique values."
            )
        previous_frequency_mhz = frequency_mhz

        if not (
            context.platform.min_graphics_clock_mhz
            <= frequency_mhz
            <= context.platform.max_graphics_clock_mhz
        ):
            raise ValueError(
                "frequencies_mhz values must fall within the platform graphics clock range."
            )

        if frequency_mhz > f_max_mhz:
            raise ValueError("frequencies_mhz values must not exceed f_max_mhz.")

    max_candidate_mhz = frequencies_mhz[-1]
    if reproduction_mode == PAPER_FAITHFUL_GV100_MODE:
        if f_max_mhz != max_candidate_mhz:
            raise ValueError(
                "paper_faithful_gv100 configs require f_max_mhz to equal the "
                "maximum candidate frequency."
            )
        if frequencies_mhz[0] != _PAPER_GV100_MIN_MHZ or f_max_mhz != _PAPER_GV100_MAX_MHZ:
            raise ValueError(
                "paper_faithful_gv100 configs must use the GV100 510-1380 MHz "
                "frequency range."
            )


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


def _optional_positive_int(config: Mapping[str, object], key: str) -> int | None:
    value = config.get(key)
    if value is None:
        return None
    if not _is_number(value):
        raise ValueError(f"{key} must be numeric.")
    result = int(round(float(value)))
    if result <= 0:
        raise ValueError(f"{key} must be positive.")
    return result


def _optional_string(config: Mapping[str, object], key: str, default: str) -> str:
    value = config.get(key)
    if value is None:
        return default
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string.")
    return value


def _optional_nullable_string(config: Mapping[str, object], key: str) -> str | None:
    value = config.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string.")
    return value


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)
