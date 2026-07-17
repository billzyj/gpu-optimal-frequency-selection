from __future__ import annotations

import unittest

from src.methods.comparison_methods.contracts import (
    ActuationOwner,
    COMPARISON_METHOD_CONTRACTS,
    ComparisonMethodContract,
    ImplementationStatus,
    IntegrationRoute,
    RuntimeCapabilities,
    assess_admission,
    registered_contract_policy_names,
)
from src.methods.registry import supported_policy_names


class ComparisonMethodContractTests(unittest.TestCase):
    def test_registered_contracts_match_policy_registry(self) -> None:
        self.assertEqual(registered_contract_policy_names(), supported_policy_names())

    def test_incomplete_methods_are_not_registered(self) -> None:
        for method_id in ("geepafs", "energyucb_reimpl", "drlcap_reimpl", "synergy", "latest"):
            contract = COMPARISON_METHOD_CONTRACTS[method_id]
            self.assertIsNone(contract.registry_name)
            self.assertNotEqual(contract.status, ImplementationStatus.REGISTERED)

    def test_geepafs_preflight_reports_external_controller_and_artifact_gaps(self) -> None:
        report = assess_admission(
            COMPARISON_METHOD_CONTRACTS["geepafs"],
            RuntimeCapabilities(
                telemetry_fields=frozenset(
                    {
                        "gpu_util_pct",
                        "memory_bandwidth_util_pct",
                        "power_w",
                        "observed_graphics_clock_mhz",
                    }
                ),
                control_knobs=frozenset({"graphics_clock"}),
            ),
        )

        self.assertTrue(report.external_controller_mode_missing)
        self.assertEqual(
            report.missing_artifacts,
            ("pinned_upstream_checkout", "target_gpu_calibration"),
        )
        self.assertTrue(report.implementation_incomplete)
        self.assertFalse(report.ready)

    def test_registered_policy_can_pass_preflight(self) -> None:
        report = assess_admission(
            COMPARISON_METHOD_CONTRACTS["everest"],
            RuntimeCapabilities(
                telemetry_fields=frozenset(
                    {"gpu_util_pct", "mem_util_pct", "observed_graphics_clock_mhz"}
                ),
                control_knobs=frozenset({"graphics_clock"}),
            ),
        )

        self.assertTrue(report.ready)

    def test_external_controller_contract_requires_upstream_owner(self) -> None:
        with self.assertRaisesRegex(ValueError, "upstream actuation ownership"):
            ComparisonMethodContract(
                method_id="invalid",
                display_name="Invalid",
                citation_key=None,
                route=IntegrationRoute.EXTERNAL_CONTROLLER,
                status=ImplementationStatus.PLANNED,
                actuation_owner=ActuationOwner.LOCAL_CONTROLLER,
            )


if __name__ == "__main__":
    unittest.main()
