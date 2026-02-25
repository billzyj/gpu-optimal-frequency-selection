from __future__ import annotations

from pathlib import Path
from typing import Mapping

from src.common.experiment import ExternalMethodInterface, ExternalRunResult, ExperimentContext


class EarExternalMethod(ExternalMethodInterface):
    """External-method adapter that delegates execution to EAR runtime."""

    def run_external(
        self,
        context: ExperimentContext,
        config: Mapping[str, object],
    ) -> ExternalRunResult:
        _ = context
        _ = config
        raise NotImplementedError(
            "EAR external baseline is a placeholder. Implement launcher/parser wiring first."
        )


def build_default_ear_artifact_path(run_id: str) -> Path:
    return Path("artifacts/raw") / "ear_external" / f"{run_id}.json"
