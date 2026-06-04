from __future__ import annotations

from src.common.experiment import AlgorithmInterface
from src.methods.comparison_methods.local_reproductions.ali_2022_reimpl import AliFrequencySelectionPolicy
from src.methods.comparison_methods.local_reproductions.everest_reimpl import EverestPolicy
from src.methods.comparison_methods.local_reproductions.oracle_static import StaticOraclePolicy
from src.methods.comparison_methods.system_baselines.max_freq import MaxFreqPolicy
from src.methods.comparison_methods.system_baselines.min_freq import MinFreqPolicy


def supported_policy_names() -> tuple[str, ...]:
    """Returns policy names supported by the default control loop."""
    return ("max_freq", "min_freq", "oracle_static", "everest", "ali_2022_reimpl")


def resolve_policy(policy_name: str) -> AlgorithmInterface:
    """Builds a policy instance by stable CLI/config name."""
    if policy_name == "max_freq":
        return MaxFreqPolicy()
    if policy_name == "min_freq":
        return MinFreqPolicy()
    if policy_name == "oracle_static":
        return StaticOraclePolicy()
    if policy_name == "everest":
        return EverestPolicy()
    if policy_name == "ali_2022_reimpl":
        return AliFrequencySelectionPolicy()

    supported = ", ".join(supported_policy_names())
    raise ValueError(f"Unsupported POLICY_NAME. Supported values: {supported}")
