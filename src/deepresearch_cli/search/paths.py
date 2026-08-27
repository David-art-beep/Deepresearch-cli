"""Resolve the built-in user-configurable search registry."""

from __future__ import annotations

import sysconfig
from pathlib import Path


def builtin_search_dir() -> Path:
    project_root = Path(__file__).resolve().parents[3]
    source_search = project_root / "search"
    if (project_root / "pyproject.toml").is_file() and source_search.is_dir():
        return source_search
    return (
        Path(sysconfig.get_path("data"))
        / "share"
        / "deepresearch-cli"
        / "search"
    )
