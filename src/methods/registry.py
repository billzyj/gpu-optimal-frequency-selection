"""Default control-loop policy registry.

This module is the single stable boundary between ``POLICY_NAME`` strings and
policy instances. It is declarative on purpose:

1. ``_REGISTRY`` is the one source of truth. ``supported_policy_names()`` is
   derived from it, so there is no second list to keep in sync with the
   resolver.
2. Each entry is a lazy factory that imports its policy module only when that
   policy is resolved. Importing this registry therefore does not import every
   method (and its future heavy dependencies) just to run a lightweight policy.

Insertion order defines the order shown in CLI/help and error messages, so keep
new entries appended in a deliberate order.
"""
from __future__ import annotations

from typing import Callable

from src.common.experiment import AlgorithmInterface


def _max_freq() -> AlgorithmInterface:
    from src.methods.comparison_methods.system_baselines.max_freq import MaxFreqPolicy

    return MaxFreqPolicy()


def _min_freq() -> AlgorithmInterface:
    from src.methods.comparison_methods.system_baselines.min_freq import MinFreqPolicy

    return MinFreqPolicy()


def _oracle_static() -> AlgorithmInterface:
    from src.methods.comparison_methods.local_reproductions.oracle_static import (
        StaticOraclePolicy,
    )

    return StaticOraclePolicy()


def _everest() -> AlgorithmInterface:
    from src.methods.comparison_methods.local_reproductions.everest_reimpl import (
        EverestPolicy,
    )

    return EverestPolicy()


def _ali_2022_reimpl() -> AlgorithmInterface:
    from src.methods.comparison_methods.local_reproductions.ali_2022_reimpl import (
        AliFrequencySelectionPolicy,
    )

    return AliFrequencySelectionPolicy()


# Stable POLICY_NAME -> policy factory. Order is significant (CLI/help order).
_REGISTRY: dict[str, Callable[[], AlgorithmInterface]] = {
    "max_freq": _max_freq,
    "min_freq": _min_freq,
    "oracle_static": _oracle_static,
    "everest": _everest,
    "ali_2022_reimpl": _ali_2022_reimpl,
}


def supported_policy_names() -> tuple[str, ...]:
    """Returns policy names supported by the default control loop, in registry order."""
    return tuple(_REGISTRY)


def resolve_policy(policy_name: str) -> AlgorithmInterface:
    """Builds a policy instance by stable CLI/config name."""
    factory = _REGISTRY.get(policy_name)
    if factory is None:
        supported = ", ".join(supported_policy_names())
        raise ValueError(f"Unsupported POLICY_NAME. Supported values: {supported}")
    return factory()
