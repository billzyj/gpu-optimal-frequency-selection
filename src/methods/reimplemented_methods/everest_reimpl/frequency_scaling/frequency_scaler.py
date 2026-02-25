from __future__ import annotations

import math

from src.common.experiment.types import PlatformSpec
from src.methods.reimplemented_methods.everest_reimpl.types import ScalerOutput


class FrequencyScaler:
    """Implements EVeREST Frequency Scaling (Equation 4 + platform constraints)."""

    def compute_target_frequency(
        self,
        freq_high_mhz: int,
        fs: float,
        pd: float,
        platform: PlatformSpec,
        min_ratio_of_max: float = 0.55,
    ) -> ScalerOutput:
        if freq_high_mhz <= 0:
            raise ValueError("freq_high_mhz must be > 0.")
        if platform.graphics_clock_step_mhz <= 0:
            raise ValueError("platform.graphics_clock_step_mhz must be > 0.")

        fs_used = _clamp(fs, 0.0, 1.0)
        pd_used = _clamp(pd, 0.0, 0.99)

        max_allowed_mhz = min(platform.max_graphics_clock_mhz, freq_high_mhz)
        min_floor_mhz = int(math.ceil(min_ratio_of_max * platform.max_graphics_clock_mhz))
        min_allowed_mhz = max(platform.min_graphics_clock_mhz, min_floor_mhz)
        if min_allowed_mhz > max_allowed_mhz:
            min_allowed_mhz = max_allowed_mhz

        if fs_used <= 1e-8:
            raw_frequency_mhz = float(min_allowed_mhz)
        elif pd_used == 0.0:
            raw_frequency_mhz = float(freq_high_mhz)
        else:
            denominator = 1.0 + pd_used / (fs_used * (1.0 - pd_used))
            raw_frequency_mhz = freq_high_mhz / denominator

        clamped_frequency_mhz = _clamp(raw_frequency_mhz, float(min_allowed_mhz), float(max_allowed_mhz))
        target_frequency_mhz = _quantize_up_within_bounds(
            value_mhz=clamped_frequency_mhz,
            min_clock_mhz=platform.min_graphics_clock_mhz,
            max_clock_mhz=max_allowed_mhz,
            step_mhz=platform.graphics_clock_step_mhz,
        )

        if target_frequency_mhz < min_allowed_mhz:
            target_frequency_mhz = _quantize_up_within_bounds(
                value_mhz=float(min_allowed_mhz),
                min_clock_mhz=platform.min_graphics_clock_mhz,
                max_clock_mhz=max_allowed_mhz,
                step_mhz=platform.graphics_clock_step_mhz,
            )

        return ScalerOutput(
            target_frequency_mhz=target_frequency_mhz,
            raw_frequency_mhz=raw_frequency_mhz,
            clamped_frequency_mhz=clamped_frequency_mhz,
            fs_used=fs_used,
            pd_used=pd_used,
            min_allowed_mhz=min_allowed_mhz,
            max_allowed_mhz=max_allowed_mhz,
        )


def _quantize_up_within_bounds(
    value_mhz: float,
    min_clock_mhz: int,
    max_clock_mhz: int,
    step_mhz: int,
) -> int:
    if step_mhz <= 0:
        raise ValueError("step_mhz must be > 0.")
    if max_clock_mhz < min_clock_mhz:
        return min_clock_mhz

    up_steps = math.ceil((value_mhz - min_clock_mhz) / step_mhz)
    quantized_up = min_clock_mhz + up_steps * step_mhz
    if quantized_up <= max_clock_mhz:
        return int(quantized_up)

    down_steps = math.floor((max_clock_mhz - min_clock_mhz) / step_mhz)
    quantized_down = min_clock_mhz + down_steps * step_mhz
    return int(max(min_clock_mhz, quantized_down))


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))
