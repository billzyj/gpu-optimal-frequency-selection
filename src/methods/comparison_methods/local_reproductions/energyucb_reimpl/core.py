from __future__ import annotations

import math
from collections.abc import Hashable, Mapping, Sequence
from dataclasses import dataclass
from typing import TypeVar


ArmId = TypeVar("ArmId", bound=Hashable)


@dataclass(slots=True, frozen=True)
class ArmState:
    """Empirical reward state for one EnergyUCB frequency arm."""

    empirical_mean_reward: float
    pull_count: int

    def __post_init__(self) -> None:
        _require_finite(self.empirical_mean_reward, "empirical_mean_reward")
        if isinstance(self.pull_count, bool) or not isinstance(self.pull_count, int):
            raise TypeError("pull_count must be an integer.")
        if self.pull_count < 0:
            raise ValueError("pull_count must be non-negative.")


def energy_progress_reward(
    energy_consumed_j: float,
    core_utilization: float,
    uncore_utilization: float,
) -> float:
    """Computes the paper's reward ``-E_t * U_C,t / U_U,t``.

    Core and uncore utilization must use the same unit (for example, both
    percentages or both fractions). A zero uncore value is rejected because
    the paper does not define a divide-by-zero fallback; a runtime adapter must
    make that missing-data behavior explicit before policy integration.
    """

    energy_consumed_j = _require_nonnegative_finite(
        energy_consumed_j,
        "energy_consumed_j",
    )
    core_utilization = _require_nonnegative_finite(
        core_utilization,
        "core_utilization",
    )
    uncore_utilization = _require_nonnegative_finite(
        uncore_utilization,
        "uncore_utilization",
    )
    if uncore_utilization == 0.0:
        raise ValueError("uncore_utilization must be greater than zero.")
    return -energy_consumed_j * core_utilization / uncore_utilization


def initialize_optimistic_arm_states(
    arm_ids: Sequence[ArmId],
    optimistic_mean_reward: float,
) -> dict[ArmId, ArmState]:
    """Creates paper-defined initial states with ``n_i,0=0`` and ``mu_i,0=mu_init``."""

    ordered_arm_ids = _validated_arm_order(arm_ids)
    optimistic_mean_reward = _require_finite(
        optimistic_mean_reward,
        "optimistic_mean_reward",
    )
    return {
        arm_id: ArmState(
            empirical_mean_reward=optimistic_mean_reward,
            pull_count=0,
        )
        for arm_id in ordered_arm_ids
    }


def update_empirical_mean(state: ArmState, observed_reward: float) -> ArmState:
    """Returns the empirical-mean state after one observed reward.

    The update follows Algorithm 1: increment ``n`` first, then compute
    ``mu <- mu + (reward - mu) / n``. Consequently, the first observation
    replaces the optimistic initial mean because its initial pull count is
    zero.
    """

    observed_reward = _require_finite(observed_reward, "observed_reward")
    updated_pull_count = state.pull_count + 1
    updated_mean = state.empirical_mean_reward + (
        observed_reward - state.empirical_mean_reward
    ) / updated_pull_count
    return ArmState(
        empirical_mean_reward=updated_mean,
        pull_count=updated_pull_count,
    )


def standard_ucb_index(
    state: ArmState,
    *,
    time_step: int,
    exploration_coefficient: float,
) -> float:
    """Computes ``mu_i,t + alpha * sqrt(ln(t) / max(1, n_i,t))``."""

    _validate_time_step(time_step)
    exploration_coefficient = _require_nonnegative_finite(
        exploration_coefficient,
        "exploration_coefficient",
    )
    exploration_bonus = exploration_coefficient * math.sqrt(
        math.log(time_step) / max(1, state.pull_count)
    )
    return state.empirical_mean_reward + exploration_bonus


def switching_aware_ucb_index(
    state: ArmState,
    *,
    time_step: int,
    exploration_coefficient: float,
    switching_penalty: float,
    candidate_arm_id: ArmId,
    previous_arm_id: ArmId,
) -> float:
    """Computes the switching-aware EnergyUCB index from Equation 5."""

    switching_penalty = _require_nonnegative_finite(
        switching_penalty,
        "switching_penalty",
    )
    index = standard_ucb_index(
        state,
        time_step=time_step,
        exploration_coefficient=exploration_coefficient,
    )
    if candidate_arm_id != previous_arm_id:
        index -= switching_penalty
    return index


def deterministic_argmax(
    arm_order: Sequence[ArmId],
    scores: Mapping[ArmId, float],
) -> ArmId:
    """Returns the highest-scoring arm with an explicit deterministic tie rule.

    Scores are compared in ``arm_order``. If two or more arms have exactly
    equal scores, the earliest arm in that caller-provided order wins. Extra
    entries in ``scores`` are ignored; every ordered arm must have a finite
    score.
    """

    ordered_arm_ids = _validated_arm_order(arm_order)
    validated_scores: dict[ArmId, float] = {}
    for arm_id in ordered_arm_ids:
        if arm_id not in scores:
            raise ValueError(f"scores is missing arm {arm_id!r}.")
        validated_scores[arm_id] = _require_finite(
            scores[arm_id],
            f"scores[{arm_id!r}]",
        )

    selected_arm_id = ordered_arm_ids[0]
    selected_score = validated_scores[selected_arm_id]
    for arm_id in ordered_arm_ids[1:]:
        score = validated_scores[arm_id]
        if score > selected_score:
            selected_arm_id = arm_id
            selected_score = score
    return selected_arm_id


def relative_performance_loss(
    estimated_progress: float,
    maximum_frequency_progress: float,
) -> float:
    """Computes the paper's QoS quantity ``s_i = 1 - p_i / p_max``."""

    estimated_progress = _require_nonnegative_finite(
        estimated_progress,
        "estimated_progress",
    )
    maximum_frequency_progress = _require_nonnegative_finite(
        maximum_frequency_progress,
        "maximum_frequency_progress",
    )
    if maximum_frequency_progress == 0.0:
        raise ValueError("maximum_frequency_progress must be greater than zero.")
    return 1.0 - estimated_progress / maximum_frequency_progress


def qos_feasible_arm_ids(
    arm_order: Sequence[ArmId],
    estimated_progress_by_arm: Mapping[ArmId, float],
    *,
    maximum_frequency_arm_id: ArmId,
    relative_performance_loss_budget: float,
) -> tuple[ArmId, ...]:
    """Builds ``K_delta = {i | 1 - p_i/p_max <= delta}`` in caller order.

    ``maximum_frequency_arm_id`` identifies the paper's ``f_max`` arm. The
    reference ``p_max`` is read from that arm rather than inferred as the
    numerically largest progress estimate. The budget must already use
    relative-performance-loss semantics.
    """

    ordered_arm_ids = _validated_arm_order(arm_order)
    if maximum_frequency_arm_id not in ordered_arm_ids:
        raise ValueError("maximum_frequency_arm_id must appear in arm_order.")

    relative_performance_loss_budget = _require_finite(
        relative_performance_loss_budget,
        "relative_performance_loss_budget",
    )
    if not 0.0 <= relative_performance_loss_budget < 1.0:
        raise ValueError("relative_performance_loss_budget must be in [0, 1).")

    progress_by_arm: dict[ArmId, float] = {}
    for arm_id in ordered_arm_ids:
        if arm_id not in estimated_progress_by_arm:
            raise ValueError(f"estimated_progress_by_arm is missing arm {arm_id!r}.")
        progress_by_arm[arm_id] = _require_nonnegative_finite(
            estimated_progress_by_arm[arm_id],
            f"estimated_progress_by_arm[{arm_id!r}]",
        )

    maximum_frequency_progress = progress_by_arm[maximum_frequency_arm_id]
    return tuple(
        arm_id
        for arm_id in ordered_arm_ids
        if relative_performance_loss(
            progress_by_arm[arm_id],
            maximum_frequency_progress,
        )
        <= relative_performance_loss_budget
    )


def _validated_arm_order(arm_ids: Sequence[ArmId]) -> tuple[ArmId, ...]:
    ordered_arm_ids = tuple(arm_ids)
    if not ordered_arm_ids:
        raise ValueError("arm order must be non-empty.")
    if len(set(ordered_arm_ids)) != len(ordered_arm_ids):
        raise ValueError("arm order must not contain duplicates.")
    return ordered_arm_ids


def _validate_time_step(time_step: int) -> None:
    if isinstance(time_step, bool) or not isinstance(time_step, int):
        raise TypeError("time_step must be an integer.")
    if time_step < 1:
        raise ValueError("time_step must be at least 1.")


def _require_nonnegative_finite(value: float, name: str) -> float:
    value = _require_finite(value, name)
    if value < 0.0:
        raise ValueError(f"{name} must be non-negative.")
    return value


def _require_finite(value: float, name: str) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} must be a real number.") from exc
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite.")
    return value
