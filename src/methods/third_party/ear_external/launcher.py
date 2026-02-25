from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(slots=True, frozen=True)
class EarLaunchSpec:
    """Job-level launch specification for running EAR as an external method."""

    command: Sequence[str]
    workdir: Path


class EarLauncher:
    """Executes EAR commands as an external process boundary."""

    def launch(self, spec: EarLaunchSpec) -> int:
        raise NotImplementedError("EAR launcher integration is not implemented yet.")
