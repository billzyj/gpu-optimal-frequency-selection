"""Paper-guided EnergyUCB algorithm core; not a runnable policy."""

from .core import (
    ArmState,
    deterministic_argmax,
    energy_progress_reward,
    initialize_optimistic_arm_states,
    qos_feasible_arm_ids,
    relative_performance_loss,
    standard_ucb_index,
    switching_aware_ucb_index,
    update_empirical_mean,
)

__all__ = [
    "ArmState",
    "deterministic_argmax",
    "energy_progress_reward",
    "initialize_optimistic_arm_states",
    "qos_feasible_arm_ids",
    "relative_performance_loss",
    "standard_ucb_index",
    "switching_aware_ucb_index",
    "update_empirical_mean",
]
