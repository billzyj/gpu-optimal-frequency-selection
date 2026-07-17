from __future__ import annotations

import math
import unittest

from src.methods.comparison_methods.local_reproductions.energyucb_reimpl import (
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


class RewardEquationTests(unittest.TestCase):
    def test_reward_matches_paper_equation(self) -> None:
        self.assertAlmostEqual(
            energy_progress_reward(
                energy_consumed_j=5.0,
                core_utilization=60.0,
                uncore_utilization=30.0,
            ),
            -10.0,
            places=12,
        )

    def test_zero_energy_or_core_produces_zero_reward(self) -> None:
        self.assertEqual(energy_progress_reward(0.0, 60.0, 30.0), 0.0)
        self.assertEqual(energy_progress_reward(5.0, 0.0, 30.0), 0.0)

    def test_invalid_energy_or_uncore_denominator_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "energy_consumed_j"):
            energy_progress_reward(-1.0, 60.0, 30.0)
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            energy_progress_reward(5.0, 60.0, 0.0)


class OptimisticStateTests(unittest.TestCase):
    def test_initializes_every_arm_with_zero_pulls_and_optimistic_mean(self) -> None:
        states = initialize_optimistic_arm_states(
            [800, 1200, 1600],
            optimistic_mean_reward=25.0,
        )

        self.assertEqual(list(states), [800, 1200, 1600])
        self.assertEqual(
            states,
            {
                800: ArmState(empirical_mean_reward=25.0, pull_count=0),
                1200: ArmState(empirical_mean_reward=25.0, pull_count=0),
                1600: ArmState(empirical_mean_reward=25.0, pull_count=0),
            },
        )

    def test_rejects_empty_or_duplicate_arm_order(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            initialize_optimistic_arm_states([], optimistic_mean_reward=1.0)
        with self.assertRaisesRegex(ValueError, "duplicates"):
            initialize_optimistic_arm_states([800, 800], optimistic_mean_reward=1.0)


class EmpiricalMeanTests(unittest.TestCase):
    def test_first_observation_replaces_optimistic_mean_then_averages(self) -> None:
        initial = ArmState(empirical_mean_reward=100.0, pull_count=0)

        after_first = update_empirical_mean(initial, observed_reward=4.0)
        after_second = update_empirical_mean(after_first, observed_reward=8.0)

        self.assertEqual(initial, ArmState(empirical_mean_reward=100.0, pull_count=0))
        self.assertEqual(after_first, ArmState(empirical_mean_reward=4.0, pull_count=1))
        self.assertEqual(after_second, ArmState(empirical_mean_reward=6.0, pull_count=2))


class UCBIndexTests(unittest.TestCase):
    def test_standard_index_matches_paper_equation(self) -> None:
        state = ArmState(empirical_mean_reward=3.0, pull_count=4)

        index = standard_ucb_index(
            state,
            time_step=16,
            exploration_coefficient=0.5,
        )

        expected = 3.0 + 0.5 * math.sqrt(math.log(16) / 4)
        self.assertAlmostEqual(index, expected, places=12)

    def test_zero_pull_count_uses_one_in_denominator(self) -> None:
        state = ArmState(empirical_mean_reward=7.0, pull_count=0)

        index = standard_ucb_index(
            state,
            time_step=9,
            exploration_coefficient=2.0,
        )

        self.assertAlmostEqual(index, 7.0 + 2.0 * math.sqrt(math.log(9)), places=12)

    def test_switching_index_penalizes_only_a_changed_arm(self) -> None:
        state = ArmState(empirical_mean_reward=3.0, pull_count=2)
        standard = standard_ucb_index(
            state,
            time_step=8,
            exploration_coefficient=1.25,
        )

        held = switching_aware_ucb_index(
            state,
            time_step=8,
            exploration_coefficient=1.25,
            switching_penalty=0.75,
            candidate_arm_id=1200,
            previous_arm_id=1200,
        )
        switched = switching_aware_ucb_index(
            state,
            time_step=8,
            exploration_coefficient=1.25,
            switching_penalty=0.75,
            candidate_arm_id=1600,
            previous_arm_id=1200,
        )

        self.assertAlmostEqual(held, standard, places=12)
        self.assertAlmostEqual(switched, standard - 0.75, places=12)

    def test_zero_switching_penalty_reduces_to_standard_ucb(self) -> None:
        state = ArmState(empirical_mean_reward=-5.0, pull_count=3)

        standard = standard_ucb_index(
            state,
            time_step=10,
            exploration_coefficient=0.8,
        )
        switching_aware = switching_aware_ucb_index(
            state,
            time_step=10,
            exploration_coefficient=0.8,
            switching_penalty=0.0,
            candidate_arm_id="new",
            previous_arm_id="old",
        )

        self.assertAlmostEqual(switching_aware, standard, places=12)


class DeterministicArgmaxTests(unittest.TestCase):
    def test_exact_tie_selects_first_arm_in_caller_order(self) -> None:
        selected = deterministic_argmax(
            [1600, 1400, 1200],
            {1200: 9.0, 1400: 9.0, 1600: 5.0},
        )

        self.assertEqual(selected, 1400)

    def test_missing_score_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing arm"):
            deterministic_argmax([800, 1200], {800: 1.0})


class QoSFeasibleSetTests(unittest.TestCase):
    def test_relative_performance_loss_matches_paper_equation(self) -> None:
        self.assertAlmostEqual(relative_performance_loss(0.8, 1.0), 0.2, places=12)

    def test_feasible_set_uses_maximum_frequency_progress_and_budget(self) -> None:
        feasible = qos_feasible_arm_ids(
            [800, 1200, 1600],
            {800: 0.7, 1200: 0.9, 1600: 1.0},
            maximum_frequency_arm_id=1600,
            relative_performance_loss_budget=0.1,
        )

        self.assertEqual(feasible, (1200, 1600))

    def test_reference_is_designated_max_frequency_arm_not_largest_estimate(self) -> None:
        feasible = qos_feasible_arm_ids(
            [800, 1200, 1600],
            {800: 1.1, 1200: 0.95, 1600: 1.0},
            maximum_frequency_arm_id=1600,
            relative_performance_loss_budget=0.06,
        )

        self.assertEqual(feasible, (800, 1200, 1600))

    def test_budget_must_already_be_relative_performance_loss(self) -> None:
        for invalid_budget in (-0.01, 1.0):
            with self.subTest(invalid_budget=invalid_budget):
                with self.assertRaisesRegex(ValueError, r"\[0, 1\)"):
                    qos_feasible_arm_ids(
                        [1600],
                        {1600: 1.0},
                        maximum_frequency_arm_id=1600,
                        relative_performance_loss_budget=invalid_budget,
                    )

    def test_zero_maximum_frequency_progress_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            qos_feasible_arm_ids(
                [800, 1600],
                {800: 0.0, 1600: 0.0},
                maximum_frequency_arm_id=1600,
                relative_performance_loss_budget=0.1,
            )


if __name__ == "__main__":
    unittest.main()
