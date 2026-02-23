from __future__ import annotations

from collections import deque
from typing import Deque

from src.common.experiment.types import MetricWindow
from src.everest.types import PhaseObservation, PhaseSignature


class PhaseIdentifier:
    """Implements EVeREST Phase Identification from windowed utilization metrics."""

    def __init__(
        self,
        window_seconds: float = 5.0,
        change_threshold_pct: float = 10.0,
        idle_gpu_threshold_pct: float = 5.0,
        idle_mem_threshold_pct: float = 3.0,
    ) -> None:
        if window_seconds <= 0:
            raise ValueError("window_seconds must be > 0.")
        if change_threshold_pct <= 0:
            raise ValueError("change_threshold_pct must be > 0.")

        self.window_seconds = window_seconds
        self.change_threshold_pct = change_threshold_pct
        self.idle_gpu_threshold_pct = idle_gpu_threshold_pct
        self.idle_mem_threshold_pct = idle_mem_threshold_pct

        self._history: Deque[MetricWindow] = deque()
        self._history_duration_s = 0.0

        self._active_phase_id: str | None = None
        self._last_stable_gpu_util_pct: float | None = None
        self._last_stable_mem_util_pct: float | None = None
        self._last_stable_idle_like: bool | None = None

    def reset(self) -> None:
        self._history.clear()
        self._history_duration_s = 0.0
        self._active_phase_id = None
        self._last_stable_gpu_util_pct = None
        self._last_stable_mem_util_pct = None
        self._last_stable_idle_like = None

    def observe(self, window: MetricWindow) -> PhaseObservation:
        """Consumes one MetricWindow and emits a phase observation."""
        self._push_window(window)

        gpu_avg_pct, mem_avg_pct = self._compute_weighted_averages()
        is_idle_like = self._is_idle_like(gpu_avg_pct, mem_avg_pct)

        if self._history_duration_s < self.window_seconds:
            return PhaseObservation(
                phase_id=None,
                is_stable=False,
                is_new_phase=False,
                gpu_util_avg_pct=gpu_avg_pct,
                mem_util_avg_pct=mem_avg_pct,
                is_idle_like=is_idle_like,
            )

        signature = self._build_signature(gpu_avg_pct, mem_avg_pct, is_idle_like)
        phase_id = signature.to_phase_id()

        is_new_phase = False
        if self._active_phase_id is None:
            is_new_phase = True
        elif self._phase_changed(gpu_avg_pct, mem_avg_pct, is_idle_like):
            is_new_phase = True

        if is_new_phase:
            self._active_phase_id = phase_id
            self._last_stable_gpu_util_pct = gpu_avg_pct
            self._last_stable_mem_util_pct = mem_avg_pct
            self._last_stable_idle_like = is_idle_like

        return PhaseObservation(
            phase_id=self._active_phase_id,
            is_stable=True,
            is_new_phase=is_new_phase,
            gpu_util_avg_pct=gpu_avg_pct,
            mem_util_avg_pct=mem_avg_pct,
            is_idle_like=is_idle_like,
        )

    def _push_window(self, window: MetricWindow) -> None:
        self._history.append(window)
        self._history_duration_s += window.duration_s

        while self._history_duration_s > self.window_seconds and len(self._history) > 1:
            removed = self._history.popleft()
            self._history_duration_s -= removed.duration_s

    def _compute_weighted_averages(self) -> tuple[float, float]:
        if not self._history:
            return 0.0, 0.0

        weighted_gpu = 0.0
        weighted_mem = 0.0
        duration_sum = 0.0
        for window in self._history:
            duration = max(window.duration_s, 0.0)
            weighted_gpu += window.gpu_util_avg_pct * duration
            weighted_mem += window.mem_util_avg_pct * duration
            duration_sum += duration

        if duration_sum == 0:
            count = float(len(self._history))
            gpu_avg = sum(window.gpu_util_avg_pct for window in self._history) / count
            mem_avg = sum(window.mem_util_avg_pct for window in self._history) / count
            return gpu_avg, mem_avg

        return weighted_gpu / duration_sum, weighted_mem / duration_sum

    def _phase_changed(self, gpu_avg_pct: float, mem_avg_pct: float, is_idle_like: bool) -> bool:
        assert self._last_stable_gpu_util_pct is not None
        assert self._last_stable_mem_util_pct is not None
        assert self._last_stable_idle_like is not None

        if is_idle_like != self._last_stable_idle_like:
            return True

        gpu_delta_pct = self._relative_change_pct(gpu_avg_pct, self._last_stable_gpu_util_pct)
        mem_delta_pct = self._relative_change_pct(mem_avg_pct, self._last_stable_mem_util_pct)
        return gpu_delta_pct >= self.change_threshold_pct or mem_delta_pct >= self.change_threshold_pct

    def _build_signature(self, gpu_avg_pct: float, mem_avg_pct: float, is_idle_like: bool) -> PhaseSignature:
        bucket_size = max(self.change_threshold_pct, 1.0)
        gpu_bucket = int(gpu_avg_pct // bucket_size)
        mem_bucket = int(mem_avg_pct // bucket_size)
        return PhaseSignature(gpu_bucket=gpu_bucket, mem_bucket=mem_bucket, is_idle_like=is_idle_like)

    def _is_idle_like(self, gpu_avg_pct: float, mem_avg_pct: float) -> bool:
        return gpu_avg_pct <= self.idle_gpu_threshold_pct and mem_avg_pct <= self.idle_mem_threshold_pct

    @staticmethod
    def _relative_change_pct(current: float, baseline: float) -> float:
        denom = max(abs(baseline), 1.0)
        return abs(current - baseline) * 100.0 / denom
