"""Tests for repository scripts.

When unittest discovery starts at ``tests/`` without ``-t .``, this package can
temporarily shadow the repository-level ``scripts`` package. Extending
``__path__`` keeps imports such as ``scripts.run.control_loop`` resolvable.
"""
from __future__ import annotations

from pathlib import Path

__path__.append(str(Path(__file__).resolve().parents[2] / "scripts"))
