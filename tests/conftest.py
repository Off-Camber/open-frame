"""Shared fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

import openframe.integrations.mcp.adapter as adapter_mod
from openframe import runs as runs_mod


@pytest.fixture(autouse=True)
def isolated_runs_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Keep run artifacts out of the home directory and out of later tests."""
    root = tmp_path / "runs"
    monkeypatch.setenv("OPENFRAME_RUNS_DIR", str(root))
    runs_mod._session_runs.clear()
    monkeypatch.setattr(adapter_mod, "_require_desktop", lambda **_kwargs: None)
    yield root
    runs_mod._session_runs.clear()
