"""Absolute run-artifact directories.

The directory is ``OPENFRAME_RUNS_DIR`` when that variable is set, otherwise
``~/.openframe/runs``. A run created in this process stays registered here, so
later changes to the working directory or the environment variable do not hide
it from ``get_run_artifacts``.
"""

from __future__ import annotations

import os
import shutil
import time
from datetime import timedelta
from pathlib import Path

_session_runs: dict[str, Path] = {}


def runs_root() -> Path:
    """Return the absolute runs directory, creating it when needed."""
    override = os.environ.get("OPENFRAME_RUNS_DIR", "").strip()
    if override:
        root = Path(override).expanduser()
    else:
        root = Path.home() / ".openframe" / "runs"
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def run_directory(run_id: str) -> Path:
    """Return the absolute directory for ``run_id``, stable for this process."""
    remembered = _session_runs.get(run_id)
    if remembered is not None:
        remembered.mkdir(parents=True, exist_ok=True)
        return remembered
    path = (runs_root() / run_id).resolve()
    path.mkdir(parents=True, exist_ok=True)
    _session_runs[run_id] = path
    return path


def lookup_run_directory(run_id: str) -> Path | None:
    """Find a run from this process, then from the configured directory."""
    remembered = _session_runs.get(run_id)
    if remembered is not None and remembered.is_dir():
        return remembered
    candidate = (runs_root() / run_id).resolve()
    if candidate.is_dir():
        _session_runs[run_id] = candidate
        return candidate
    return None


def prune_runs(
    *,
    older_than: timedelta | None = None,
    keep: int | None = None,
) -> list[Path]:
    """Delete run directories by age, then by count.

    Age is applied first. ``keep`` then retains the newest remaining runs.
    """
    if older_than is None and keep is None:
        raise ValueError("prune requires an age, a count, or both")
    if keep is not None and keep < 0:
        raise ValueError("keep must be zero or greater")

    root = runs_root()
    runs = [item for item in root.iterdir() if item.is_dir()]
    runs.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    doomed: list[Path] = []
    if older_than is not None:
        cutoff = time.time() - older_than.total_seconds()
        doomed = [item for item in runs if item.stat().st_mtime < cutoff]
    survivors = [item for item in runs if item not in doomed]
    if keep is not None:
        doomed.extend(survivors[keep:])

    deleted: list[Path] = []
    for path in doomed:
        shutil.rmtree(path)
        remembered = _session_runs.get(path.name)
        if remembered is not None and not remembered.exists():
            _session_runs.pop(path.name, None)
        deleted.append(path)
    return deleted
