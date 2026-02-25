from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True, frozen=True)
class EarParsedResult:
    """Normalized EAR outputs before conversion to repository schema."""

    source_path: Path


class EarResultParser:
    """Parses EAR exported files (CSV/log) into normalized records."""

    def parse(self, source_path: Path) -> EarParsedResult:
        raise NotImplementedError("EAR parser integration is not implemented yet.")
