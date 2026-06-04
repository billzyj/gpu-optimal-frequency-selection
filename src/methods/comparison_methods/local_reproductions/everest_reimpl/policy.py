from __future__ import annotations

from dataclasses import asdict
from typing import Mapping

from src.common.experiment import (
    AlgorithmState,
    Decision,
    DecisionAction,
    ExperimentContext,
    FinalSummary,
    MetricWindow,
    PlatformSpec,
)
from src.methods.comparison_methods.local_reproductions.everest_reimpl.frequency_scaling import FrequencyScaler
from src.methods.comparison_methods.local_reproductions.everest_reimpl.phase_characterization import PhaseCharacterizer
from src.methods.comparison_methods.local_reproductions.everest_reimpl.phase_identification import PhaseIdentifier
from src.methods.comparison_methods.local_reproductions.everest_reimpl.types import CharacterizationRecord


class EverestPolicy:
    """Online EVeREST-like runtime policy built from the three reimplemented stages.

    Live policy state (PhaseIdentifier history and PhaseCharacterizer cache) lives
    in this object. ``state["phase_cache"]`` is a serialized observability mirror
    written on every store.
    """

    policy_name = "everest"

    def __init__(self) -> None:
        self._phase_identifier: PhaseIdentifier | None = None
        self._phase_characterizer = PhaseCharacterizer()
        self._frequency_scaler = FrequencyScaler()

    def initialize(
        self,
        context: ExperimentContext,
        config: Mapping[str, object],
    ) -> AlgorithmState:
        phase_window_seconds = _config_float(
            config,
            "phase_window_seconds",
            context.window_seconds,
        )
        change_threshold_pct = _config_float(config, "change_threshold_pct", 10.0)
        idle_gpu_threshold_pct = _config_float(config, "idle_gpu_threshold_pct", 5.0)
        idle_mem_threshold_pct = _config_float(config, "idle_mem_threshold_pct", 3.0)

        self._phase_identifier = PhaseIdentifier(
            window_seconds=phase_window_seconds,
            change_threshold_pct=change_threshold_pct,
            idle_gpu_threshold_pct=idle_gpu_threshold_pct,
            idle_mem_threshold_pct=idle_mem_threshold_pct,
        )
        self._phase_characterizer = PhaseCharacterizer()

        f_high = _config_int(
            config,
            "high_frequency_mhz",
            context.platform.max_graphics_clock_mhz,
        )
        f_high = _clamp_int(
            f_high,
            context.platform.min_graphics_clock_mhz,
            context.platform.max_graphics_clock_mhz,
        )
        if f_high not in {
            context.platform.min_graphics_clock_mhz,
            context.platform.max_graphics_clock_mhz,
        }:
            f_high = _quantize_clock_down(
                f_high,
                min_clock_mhz=context.platform.min_graphics_clock_mhz,
                max_clock_mhz=context.platform.max_graphics_clock_mhz,
                step_mhz=context.platform.graphics_clock_step_mhz,
            )

        min_ratio_of_max = _config_float(config, "min_ratio_of_max", 0.55)
        low_ratio = _config_float(config, "characterization_low_frequency_ratio", 0.70)
        low_frequency_default = int(round(float(f_high) * low_ratio))
        f_low = _config_int(config, "characterization_low_frequency_mhz", low_frequency_default)
        f_low_floor = int(round(context.platform.max_graphics_clock_mhz * min_ratio_of_max))
        f_low = _quantize_clock_up(
            max(f_low, f_low_floor),
            min_clock_mhz=context.platform.min_graphics_clock_mhz,
            max_clock_mhz=f_high,
            step_mhz=context.platform.graphics_clock_step_mhz,
        )
        if f_low >= f_high and f_high > context.platform.min_graphics_clock_mhz:
            f_low = _quantize_clock_down(
                f_high - context.platform.graphics_clock_step_mhz,
                min_clock_mhz=context.platform.min_graphics_clock_mhz,
                max_clock_mhz=f_high,
                step_mhz=context.platform.graphics_clock_step_mhz,
            )

        state = AlgorithmState()
        state.set("run_id", context.metadata.run_id)
        state.set("pd_target", context.pd_target)
        state.set("phase_window_seconds", phase_window_seconds)
        state.set("change_threshold_pct", change_threshold_pct)
        state.set("min_ratio_of_max", min_ratio_of_max)
        state.set("f_high_mhz", f_high)
        state.set("f_low_mhz", f_low)
        state.set("platform_vendor", context.platform.vendor)
        state.set("platform_gpu_model", context.platform.gpu_model)
        state.set("platform_gpu_count", context.platform.gpu_count)
        state.set("platform_min_clock_mhz", context.platform.min_graphics_clock_mhz)
        state.set("platform_max_clock_mhz", context.platform.max_graphics_clock_mhz)
        state.set("platform_clock_step_mhz", context.platform.graphics_clock_step_mhz)
        state.set("phase_cache", {})
        state.set("pending_characterization", None)
        state.set("last_target_clock_mhz", None)
        state.set("total_windows", 0)
        state.set("stable_window_count", 0)
        state.set("unstable_window_count", 0)
        state.set("phase_change_count", 0)
        state.set("characterization_count", 0)
        state.set("cache_hit_count", 0)
        state.set("cache_miss_count", 0)
        state.set("scaled_decision_count", 0)
        state.set("reset_to_high_count", 0)
        state.set("pd_violation_count", 0)
        state.set("max_pd_violation", 0.0)
        return state

    def on_window(
        self,
        metrics: MetricWindow,
        state: AlgorithmState,
    ) -> Decision:
        identifier = self._require_identifier(state)
        total_windows = int(state.get("total_windows", 0)) + 1
        state.set("total_windows", total_windows)
        _update_pd_violation_if_present(metrics, state)

        pending = state.get("pending_characterization")
        if isinstance(pending, dict):
            if pending.get("stage") == "capture_high":
                return self._capture_high_characterization(metrics, state, pending)
            # NOTE: The probe window is intentionally NOT fed to
            # self._phase_identifier.observe() here.  The probe runs at f_low
            # (a different clock frequency), so its metrics must not pollute
            # the phase-identification sliding-window average.
            return self._finish_characterization(metrics, state, pending)

        observation = identifier.observe(metrics)
        if not observation.is_stable or observation.phase_id is None:
            state.set("unstable_window_count", int(state.get("unstable_window_count", 0)) + 1)
            return self._high_frequency_decision(
                metrics,
                state,
                reason="everest_wait_for_stable_phase",
            )

        state.set("stable_window_count", int(state.get("stable_window_count", 0)) + 1)
        if observation.is_new_phase:
            state.set("phase_change_count", int(state.get("phase_change_count", 0)) + 1)

        cached = self._cached_record(observation.phase_id)
        if cached is not None:
            state.set("cache_hit_count", int(state.get("cache_hit_count", 0)) + 1)
            return self._scaled_decision(
                metrics=metrics,
                state=state,
                record=cached,
                reason="everest_apply_cached_phase",
            )

        state.set("cache_miss_count", int(state.get("cache_miss_count", 0)) + 1)
        if int(state.get("f_low_mhz")) >= int(state.get("f_high_mhz")):
            record = self._cache_default_record(
                state=state,
                phase_id=observation.phase_id,
                mem_high=max(observation.mem_util_avg_pct, 0.0),
                mem_low=max(observation.mem_util_avg_pct, 0.0),
                fs=0.0,
            )
            return self._scaled_decision(
                metrics=metrics,
                state=state,
                record=record,
                reason="everest_apply_without_low_frequency_probe",
            )

        if observation.mem_util_avg_pct <= 0:
            record = self._cache_default_record(
                state=state,
                phase_id=observation.phase_id,
                mem_high=max(observation.mem_util_avg_pct, 0.0),
                mem_low=max(observation.mem_util_avg_pct, 0.0),
                fs=0.0,
            )
            return self._scaled_decision(
                metrics=metrics,
                state=state,
                record=record,
                reason="everest_apply_zero_mem_phase",
            )

        f_high = int(state.get("f_high_mhz"))
        f_low = int(state.get("f_low_mhz"))
        if not _is_same_clock(metrics.graphics_clock_avg_mhz, f_high):
            pending_characterization = {
                "stage": "capture_high",
                "phase_id": observation.phase_id,
                "freq_high_mhz": f_high,
                "freq_low_mhz": f_low,
            }
            state.set("pending_characterization", pending_characterization)
            return self._set_clock_decision(
                metrics=metrics,
                state=state,
                target_mhz=f_high,
                reason="everest_collect_high_frequency",
                debug_fields=pending_characterization,
            )

        return self._start_low_frequency_probe(
            metrics=metrics,
            state=state,
            phase_id=observation.phase_id,
            mem_high=observation.mem_util_avg_pct,
            freq_high_mhz=f_high,
            freq_low_mhz=f_low,
            reason="everest_characterize_low_frequency",
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
                "characterized_phase_count": len(_phase_cache(state)),
                "stable_window_count": int(state.get("stable_window_count", 0)),
                "unstable_window_count": int(state.get("unstable_window_count", 0)),
                "phase_change_count": int(state.get("phase_change_count", 0)),
                "characterization_count": int(state.get("characterization_count", 0)),
                "cache_hit_count": int(state.get("cache_hit_count", 0)),
                "cache_miss_count": int(state.get("cache_miss_count", 0)),
                "scaled_decision_count": int(state.get("scaled_decision_count", 0)),
                "reset_to_high_count": int(state.get("reset_to_high_count", 0)),
                "f_high_mhz": int(state.get("f_high_mhz", 0)),
                "f_low_mhz": int(state.get("f_low_mhz", 0)),
            },
        )

    def _start_low_frequency_probe(
        self,
        *,
        metrics: MetricWindow,
        state: AlgorithmState,
        phase_id: str,
        mem_high: float,
        freq_high_mhz: int,
        freq_low_mhz: int,
        reason: str,
    ) -> Decision:
        pending_characterization = {
            "stage": "capture_low",
            "phase_id": phase_id,
            "mem_high": mem_high,
            "freq_high_mhz": freq_high_mhz,
            "freq_low_mhz": freq_low_mhz,
        }
        state.set("pending_characterization", pending_characterization)
        return self._set_clock_decision(
            metrics=metrics,
            state=state,
            target_mhz=freq_low_mhz,
            reason=reason,
            debug_fields=pending_characterization,
        )

    def _capture_high_characterization(
        self,
        metrics: MetricWindow,
        state: AlgorithmState,
        pending: dict[str, object],
    ) -> Decision:
        return self._start_low_frequency_probe(
            metrics=metrics,
            state=state,
            phase_id=str(pending["phase_id"]),
            mem_high=metrics.mem_util_avg_pct,
            freq_high_mhz=int(pending["freq_high_mhz"]),
            freq_low_mhz=int(pending["freq_low_mhz"]),
            reason="everest_characterize_low_frequency",
        )

    def _finish_characterization(
        self,
        metrics: MetricWindow,
        state: AlgorithmState,
        pending: dict[str, object],
    ) -> Decision:
        phase_id = str(pending["phase_id"])
        mem_high = float(pending["mem_high"])
        freq_high_mhz = int(pending["freq_high_mhz"])
        freq_low_mhz = int(pending["freq_low_mhz"])
        mem_low = metrics.mem_util_avg_pct
        state.set("pending_characterization", None)

        if mem_high <= 0 or mem_low <= 0:
            record = self._cache_default_record(
                state=state,
                phase_id=phase_id,
                mem_high=max(mem_high, 0.0),
                mem_low=max(mem_low, 0.0),
                fs=0.0,
            )
        else:
            fs = self._phase_characterizer.estimate_frequency_sensitivity(
                mem_high=mem_high,
                mem_low=mem_low,
                freq_high_mhz=freq_high_mhz,
                freq_low_mhz=freq_low_mhz,
            )
            record = self._store_characterization(
                state=state,
                phase_id=phase_id,
                fs=fs,
                mem_high=mem_high,
                mem_low=mem_low,
                freq_high_mhz=freq_high_mhz,
                freq_low_mhz=freq_low_mhz,
            )

        state.set("characterization_count", int(state.get("characterization_count", 0)) + 1)
        return self._scaled_decision(
            metrics=metrics,
            state=state,
            record=record,
            reason="everest_apply_new_characterization",
        )

    def _scaled_decision(
        self,
        *,
        metrics: MetricWindow,
        state: AlgorithmState,
        record: CharacterizationRecord,
        reason: str,
    ) -> Decision:
        scaled = self._frequency_scaler.compute_target_frequency(
            freq_high_mhz=int(state.get("f_high_mhz")),
            fs=record.fs,
            pd=float(state.get("pd_target", 0.0)),
            platform=_platform_from_state(metrics, state),
            min_ratio_of_max=float(state.get("min_ratio_of_max", 0.55)),
        )
        state.set("scaled_decision_count", int(state.get("scaled_decision_count", 0)) + 1)
        debug_fields = {
            "phase_id": record.phase_id,
            "fs": record.fs,
            "mem_high": record.mem_high,
            "mem_low": record.mem_low,
            "raw_frequency_mhz": scaled.raw_frequency_mhz,
            "clamped_frequency_mhz": scaled.clamped_frequency_mhz,
            "min_allowed_mhz": scaled.min_allowed_mhz,
            "max_allowed_mhz": scaled.max_allowed_mhz,
        }
        return self._set_clock_decision(
            metrics=metrics,
            state=state,
            target_mhz=scaled.target_frequency_mhz,
            reason=reason,
            debug_fields=debug_fields,
        )

    def _high_frequency_decision(
        self,
        metrics: MetricWindow,
        state: AlgorithmState,
        reason: str,
    ) -> Decision:
        target_mhz = int(state.get("f_high_mhz"))
        if _is_same_clock(metrics.graphics_clock_avg_mhz, target_mhz):
            return Decision(
                action=DecisionAction.HOLD_CLOCK,
                target_graphics_clock_mhz=None,
                reason_code=reason,
                debug_fields={"target_mhz": target_mhz},
            )
        state.set("reset_to_high_count", int(state.get("reset_to_high_count", 0)) + 1)
        state.set("last_target_clock_mhz", target_mhz)
        return Decision(
            action=DecisionAction.SET_CLOCK,
            target_graphics_clock_mhz=target_mhz,
            reason_code=reason,
            debug_fields={"target_mhz": target_mhz},
        )

    def _set_clock_decision(
        self,
        *,
        metrics: MetricWindow,
        state: AlgorithmState,
        target_mhz: int,
        reason: str,
        debug_fields: Mapping[str, object] | None = None,
    ) -> Decision:
        if _is_same_clock(metrics.graphics_clock_avg_mhz, target_mhz):
            return Decision(
                action=DecisionAction.HOLD_CLOCK,
                target_graphics_clock_mhz=None,
                reason_code=f"{reason}_already_at_target",
                debug_fields=dict(debug_fields or {}),
            )
        state.set("last_target_clock_mhz", target_mhz)
        return Decision(
            action=DecisionAction.SET_CLOCK,
            target_graphics_clock_mhz=target_mhz,
            reason_code=reason,
            debug_fields=dict(debug_fields or {}),
        )

    def _store_characterization(
        self,
        *,
        state: AlgorithmState,
        phase_id: str,
        fs: float,
        mem_high: float,
        mem_low: float,
        freq_high_mhz: int,
        freq_low_mhz: int,
    ) -> CharacterizationRecord:
        # Authoritative live cache: stored in self._phase_characterizer.
        record = self._phase_characterizer.upsert_phase_characterization(
            phase_id=phase_id,
            fs=fs,
            mem_high=max(mem_high, 1e-12),
            mem_low=max(mem_low, 1e-12),
            freq_high_mhz=freq_high_mhz,
            freq_low_mhz=freq_low_mhz,
        )
        # Observability mirror only — state["phase_cache"] is a JSON-serializable
        # snapshot for inspection and finalize counting.  Lookups always go through
        # self._phase_characterizer (see _cached_record), not this mirror.
        phase_cache = _phase_cache(state)
        phase_cache[phase_id] = asdict(record)
        state.set("phase_cache", phase_cache)
        return record

    def _cached_record(self, phase_id: str) -> CharacterizationRecord | None:
        """Return the cached characterization for *phase_id*, or None if absent.

        This is the authoritative lookup path — it reads from the live
        ``self._phase_characterizer`` cache, not from ``state["phase_cache"]``.
        """
        return self._phase_characterizer.get_phase_characterization(phase_id)

    def _cache_default_record(
        self,
        *,
        state: AlgorithmState,
        phase_id: str,
        mem_high: float,
        mem_low: float,
        fs: float,
    ) -> CharacterizationRecord:
        return self._store_characterization(
            state=state,
            phase_id=phase_id,
            fs=fs,
            mem_high=max(mem_high, 1e-12),
            mem_low=max(mem_low, 1e-12),
            freq_high_mhz=int(state.get("f_high_mhz")),
            freq_low_mhz=int(state.get("f_low_mhz")),
        )

    def _require_identifier(self, state: AlgorithmState) -> PhaseIdentifier:
        if self._phase_identifier is None:
            self._phase_identifier = PhaseIdentifier(
                window_seconds=float(state.get("phase_window_seconds", 5.0)),
                change_threshold_pct=float(state.get("change_threshold_pct", 10.0)),
            )
        return self._phase_identifier


def _phase_cache(state: AlgorithmState) -> dict[str, dict[str, object]]:
    value = state.get("phase_cache", {})
    if isinstance(value, dict):
        return dict(value)
    return {}


def _update_pd_violation_if_present(metrics: MetricWindow, state: AlgorithmState) -> None:
    perf_ratio = _extract_optional_number(
        metrics.custom_metrics,
        ("performance_ratio", "relative_performance", "perf_ratio_to_max"),
    )
    if perf_ratio is None:
        return

    target_ratio = 1.0 - _clamp(float(state.get("pd_target", 0.0)), 0.0, 0.99)
    violation = max(0.0, target_ratio - perf_ratio)
    if violation <= 0:
        return

    state.set("pd_violation_count", int(state.get("pd_violation_count", 0)) + 1)
    state.set("max_pd_violation", max(float(state.get("max_pd_violation", 0.0)), violation))


def _extract_optional_number(entry: Mapping[str, object], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = entry.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _platform_from_state(metrics: MetricWindow, state: AlgorithmState) -> PlatformSpec:
    _ = metrics
    return PlatformSpec(
        vendor=str(state.get("platform_vendor", "unknown")),
        gpu_model=str(state.get("platform_gpu_model", "unknown")),
        gpu_count=int(state.get("platform_gpu_count", 1)),
        min_graphics_clock_mhz=int(state.get("platform_min_clock_mhz", 0)),
        max_graphics_clock_mhz=int(state.get("platform_max_clock_mhz", state.get("f_high_mhz", 0))),
        graphics_clock_step_mhz=int(state.get("platform_clock_step_mhz", 1)),
    )


def _config_float(config: Mapping[str, object], key: str, default: float) -> float:
    value = config.get(key)
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _config_int(config: Mapping[str, object], key: str, default: int) -> int:
    value = config.get(key)
    if isinstance(value, (int, float)):
        return int(round(float(value)))
    return default


def _quantize_clock_up(
    value_mhz: int,
    *,
    min_clock_mhz: int,
    max_clock_mhz: int,
    step_mhz: int,
) -> int:
    if step_mhz <= 0:
        raise ValueError("step_mhz must be > 0.")
    value_mhz = _clamp_int(value_mhz, min_clock_mhz, max_clock_mhz)
    steps = -(-(value_mhz - min_clock_mhz) // step_mhz)
    return _clamp_int(min_clock_mhz + steps * step_mhz, min_clock_mhz, max_clock_mhz)


def _quantize_clock_down(
    value_mhz: int,
    *,
    min_clock_mhz: int,
    max_clock_mhz: int,
    step_mhz: int,
) -> int:
    if step_mhz <= 0:
        raise ValueError("step_mhz must be > 0.")
    value_mhz = _clamp_int(value_mhz, min_clock_mhz, max_clock_mhz)
    steps = (value_mhz - min_clock_mhz) // step_mhz
    return _clamp_int(min_clock_mhz + steps * step_mhz, min_clock_mhz, max_clock_mhz)


def _clamp_int(value: int, lower: int, upper: int) -> int:
    return int(max(lower, min(value, upper)))


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def _is_same_clock(observed_clock_mhz: float, target_clock_mhz: int) -> bool:
    return abs(observed_clock_mhz - float(target_clock_mhz)) < 0.5
