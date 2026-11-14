"""The publish workflow rejects a tag that disagrees with pyproject.toml."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_release_tag.py"


def _write_pyproject(directory: Path, version: str) -> Path:
    path = directory / "pyproject.toml"
    path.write_text(f'[project]\nversion = "{version}"\n', encoding="utf-8")
    return path


def _run(tag: str, pyproject: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), tag, "--pyproject", str(pyproject)],
        check=False,
        capture_output=True,
        text=True,
    )


def test_mismatched_tag_fails(tmp_path: Path) -> None:
    pyproject = _write_pyproject(tmp_path, "0.2.2")
    result = _run("v9.9.9", pyproject)
    assert result.returncode == 1
    assert result.stderr.strip() == (
        "release tag v9.9.9 does not match pyproject version 0.2.2; expected v0.2.2"
    )
    assert result.stdout == ""


def test_matching_tag_passes(tmp_path: Path) -> None:
    pyproject = _write_pyproject(tmp_path, "0.2.2")
    result = _run("v0.2.2", pyproject)
    assert result.returncode == 0
    assert "matches pyproject version 0.2.2" in result.stdout
    assert result.stderr == ""


def test_tag_without_v_and_refs_prefix_match(tmp_path: Path) -> None:
    pyproject = _write_pyproject(tmp_path, "0.2.2")
    bare = _run("0.2.2", pyproject)
    prefixed = _run("refs/tags/v0.2.2", pyproject)
    assert bare.returncode == 0
    assert prefixed.returncode == 0


def test_stable_tag_matches(tmp_path: Path) -> None:
    pyproject = _write_pyproject(tmp_path, "0.3.0")
    result = _run("v0.3.0", pyproject)
    assert result.returncode == 0
    assert "matches pyproject version 0.3.0" in result.stdout


def test_release_candidate_tag_matches(tmp_path: Path) -> None:
    pyproject = _write_pyproject(tmp_path, "0.3.0rc2")
    result = _run("v0.3.0rc2", pyproject)
    assert result.returncode == 0
    assert "matches pyproject version 0.3.0rc2" in result.stdout


def test_empty_tag_fails(tmp_path: Path) -> None:
    pyproject = _write_pyproject(tmp_path, "0.2.2")
    result = _run("   ", pyproject)
    assert result.returncode == 1
    assert "empty" in result.stderr
