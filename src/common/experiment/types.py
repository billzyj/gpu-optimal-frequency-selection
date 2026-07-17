from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


JSONPrimitive = str | int | float | bool | None
JSONValue = JSONPrimitive | list["JSONValue"] | dict[str, "JSONValue"]


class DecisionAction(str, Enum):
    """Control intent emitted by an algorithm."""

    SET_CLOCK = "set_clock"
    HOLD_CLOCK = "hold_clock"
    RESET_TO_MAX = "reset_to_max"
    NO_OP = "no_op"


class PerformanceTargetType(str, Enum):
    """Semantics attached to the raw performance-target value."""

    RUNTIME_SLOWDOWN = "runtime_slowdown"
    RELATIVE_PERFORMANCE_LOSS = "relative_performance_loss"
    NONE = "none"

    @classmethod
    def parse(cls, value: str | PerformanceTargetType) -> PerformanceTargetType:
        """Parses a target type from its stable environment/config spelling."""
        if isinstance(value, cls):
            return value
        try:
            return cls(value.strip().lower())
        except (AttributeError, ValueError) as exc:
            supported = ", ".join(member.value for member in cls)
            raise ValueError(
                f"Unsupported performance target type {value!r}. Supported values: {supported}."
            ) from exc


def runtime_slowdown_to_relative_performance_loss(runtime_slowdown: float) -> float:
    """Converts ``runtime / baseline_runtime - 1`` to relative performance loss."""
    slowdown = _validated_runtime_slowdown(runtime_slowdown)
    return slowdown / (1.0 + slowdown)


def relative_performance_loss_to_runtime_slowdown(
    relative_performance_loss: float,
) -> float:
    """Converts ``1 - relative_performance`` to relative runtime slowdown."""
    loss = _validated_relative_performance_loss(relative_performance_loss)
    return loss / (1.0 - loss)


@dataclass(slots=True, frozen=True)
class PerformanceTarget:
    """A raw performance target plus normalized, policy-facing conversions."""

    target_type: PerformanceTargetType
    raw_value: float

    def __post_init__(self) -> None:
        target_type = PerformanceTargetType.parse(self.target_type)
        raw_value = float(self.raw_value)
        object.__setattr__(self, "target_type", target_type)
        object.__setattr__(self, "raw_value", raw_value)

        if target_type is PerformanceTargetType.RUNTIME_SLOWDOWN:
            _validated_runtime_slowdown(raw_value)
        elif target_type is PerformanceTargetType.RELATIVE_PERFORMANCE_LOSS:
            _validated_relative_performance_loss(raw_value)
        elif raw_value != 0.0:
            raise ValueError("A performance target with type 'none' must have raw_value=0.0.")

    @property
    def runtime_slowdown(self) -> float | None:
        """Returns normalized runtime slowdown, or ``None`` for no constraint."""
        if self.target_type is PerformanceTargetType.NONE:
            return None
        if self.target_type is PerformanceTargetType.RUNTIME_SLOWDOWN:
            return self.raw_value
        return relative_performance_loss_to_runtime_slowdown(self.raw_value)

    @property
    def relative_performance_loss(self) -> float | None:
        """Returns normalized relative performance loss, or ``None``."""
        if self.target_type is PerformanceTargetType.NONE:
            return None
        if self.target_type is PerformanceTargetType.RELATIVE_PERFORMANCE_LOSS:
            return self.raw_value
        return runtime_slowdown_to_relative_performance_loss(self.raw_value)

    @property
    def minimum_performance_ratio(self) -> float | None:
        """Returns the minimum performance relative to the max-frequency baseline."""
        if self.target_type is PerformanceTargetType.NONE:
            return None
        if self.target_type is PerformanceTargetType.RUNTIME_SLOWDOWN:
            return 1.0 / (1.0 + self.raw_value)
        return 1.0 - self.raw_value


@dataclass(slots=True, frozen=True)
class PlatformSpec:
    """Hardware and runtime characteristics of the target platform."""

    vendor: str
    gpu_model: str
    gpu_count: int
    min_graphics_clock_mhz: int
    max_graphics_clock_mhz: int
    graphics_clock_step_mhz: int
    node_name: str | None = None
    driver_version: str | None = None
    runtime_version: str | None = None


@dataclass(slots=True, frozen=True)
class ExperimentMetadata:
    """Stable identity and metadata for one experiment run."""

    run_id: str
    experiment_id: str
    policy_name: str
    workload_name: str
    started_at_utc: str
    tags: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class ExperimentContext:
    """Inputs visible to all algorithms at initialization time."""

    platform: PlatformSpec
    metadata: ExperimentMetadata
    pd_target: float
    window_seconds: float
    sampling_interval_ms: int
    user_config: dict[str, JSONValue] = field(default_factory=dict)
    performance_target_type: PerformanceTargetType = (
        PerformanceTargetType.RELATIVE_PERFORMANCE_LOSS
    )

    def __post_init__(self) -> None:
        target = PerformanceTarget(self.performance_target_type, self.pd_target)
        object.__setattr__(self, "pd_target", target.raw_value)
        object.__setattr__(self, "performance_target_type", target.target_type)

    @property
    def performance_target(self) -> PerformanceTarget:
        """Returns the typed target represented by this legacy-compatible context."""
        return PerformanceTarget(self.performance_target_type, self.pd_target)

    @property
    def relative_performance_loss(self) -> float | None:
        """Returns the normalized relative performance loss for policy equations."""
        return self.performance_target.relative_performance_loss

    @property
    def minimum_performance_ratio(self) -> float | None:
        """Returns the normalized minimum relative performance constraint."""
        return self.performance_target.minimum_performance_ratio

    @property
    def performance_target_ratio(self) -> float | None:
        """Backward-compatible alias for :attr:`minimum_performance_ratio`."""
        return self.minimum_performance_ratio

    def require_relative_performance_loss(self) -> float:
        """Returns relative loss or raises when this run has no performance target."""
        value = self.relative_performance_loss
        if value is None:
            raise ValueError("This policy requires a performance target; target type is 'none'.")
        return value

    def require_minimum_performance_ratio(self) -> float:
        """Returns minimum performance or raises when the target type is ``none``."""
        value = self.minimum_performance_ratio
        if value is None:
            raise ValueError("This policy requires a performance target; target type is 'none'.")
        return value


@dataclass(slots=True, frozen=True)
class TelemetrySample:
    """Raw per-sample telemetry read from hardware APIs."""

    timestamp_unix_s: float
    gpu_util_pct: float
    mem_util_pct: float
    graphics_clock_mhz: int
    power_w: float | None = None
    energy_j: float | None = None
    temperature_c: float | None = None
    raw_counters: dict[str, JSONValue] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class MetricWindow:
    """Window-aggregated metrics passed to on_window()."""

    sequence_id: int
    start_unix_s: float
    end_unix_s: float
    duration_s: float
    sample_count: int
    gpu_util_avg_pct: float
    mem_util_avg_pct: float
    graphics_clock_avg_mhz: float
    power_avg_w: float | None = None
    energy_delta_j: float | None = None
    custom_metrics: dict[str, JSONValue] = field(default_factory=dict)


@dataclass(slots=True)
class AlgorithmState:
    """
    Mutable state bag owned by one algorithm instance.

    The shared runner should treat this object as opaque.
    """

    data: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value


@dataclass(slots=True, frozen=True)
class Decision:
    """Control decision produced for the next window."""

    action: DecisionAction
    target_graphics_clock_mhz: int | None
    reason_code: str
    debug_fields: dict[str, JSONValue] = field(default_factory=dict)

    @property
    def requires_clock_change(self) -> bool:
        return self.action in {DecisionAction.SET_CLOCK, DecisionAction.RESET_TO_MAX}


@dataclass(slots=True, frozen=True)
class FinalSummary:
    """End-of-run summary returned by finalize()."""

    policy_name: str
    run_id: str
    total_windows: int
    pd_target: float
    pd_violation_count: int
    max_pd_violation: float
    custom_summary: dict[str, JSONValue] = field(default_factory=dict)


def _validated_runtime_slowdown(value: float) -> float:
    slowdown = float(value)
    if not math.isfinite(slowdown) or slowdown < 0.0:
        raise ValueError("runtime_slowdown must be finite and >= 0.0.")
    return slowdown


def _validated_relative_performance_loss(value: float) -> float:
    loss = float(value)
    if not math.isfinite(loss) or not 0.0 <= loss < 1.0:
        raise ValueError("relative_performance_loss must be finite and in [0.0, 1.0).")
    return loss
