"""Run-artifact location, pruning, and same-session lookup."""

from __future__ import annotations

import os
import tempfile
import time
from datetime import timedelta
from pathlib import Path

import pytest

from openframe.capture.sidecar import SIDECAR_SUFFIX
from openframe.flow import Flow, FlowStep
from openframe.integrations.mcp.adapter import call_mcp_tool
from openframe.runner import FlowRunner
from openframe.runs import prune_runs, run_directory
from openframe.types import Frame


def test_get_run_artifacts_finds_a_run_from_the_same_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    monkeypatch.setenv("OPENFRAME_RUNS_DIR", str(first))
    temps: list[Path] = []

    def fake_screen(*_args: object, **_kwargs: object) -> Frame:
        descriptor, name = tempfile.mkstemp(prefix="openframe-", suffix=".png")
        os.close(descriptor)
        path = Path(name)
        path.write_bytes(b"png")
        sidecar = Path(str(path) + SIDECAR_SUFFIX)
        sidecar.write_text("{}", encoding="utf-8")
        temps.extend((path, sidecar))
        return Frame(
            width=2,
            height=2,
            scale_factor=1.0,
            source="screen",
            image_path=str(path),
        )

    monkeypatch.setattr("openframe.runner.screen", fake_screen)
    flow = Flow(name="hello", steps=[FlowStep(id="pause", kind="wait", params={"ms": 0})])
    session = FlowRunner(dry_run=True).run(flow, run_id="session-run")

    result = session.results[0]
    before = Path(result.before_frame_path or "")
    after = Path(result.after_frame_path or "")
    assert before.is_absolute()
    assert after.is_absolute()
    assert before.is_file()
    assert after.is_file()
    assert before.parent == (first / "session-run" / "pause").resolve()
    assert after.parent == before.parent
    for temp in temps:
        assert not temp.exists()

    monkeypatch.setenv("OPENFRAME_RUNS_DIR", str(second))
    monkeypatch.chdir(tmp_path)
    found = call_mcp_tool("get_run_artifacts", {"run_id": "session-run"})

    assert found["ok"] is True
    assert Path(found["data"]["run_dir"]) == (first / "session-run").resolve()
    assert Path(found["artifacts"]["run_dir"]) == (first / "session-run").resolve()
    assert "before.png" in found["data"]["steps"][0]["files"]
    assert "after.png" in found["data"]["steps"][0]["files"]
    assert not (second / "session-run").exists()


def test_prune_deletes_by_age_then_count(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "prune-runs"
    monkeypatch.setenv("OPENFRAME_RUNS_DIR", str(root))
    old = run_directory("old")
    mid = run_directory("mid")
    new = run_directory("new")
    now = time.time()
    os.utime(old, (now - 3 * 86400, now - 3 * 86400))
    os.utime(mid, (now - 3600, now - 3600))
    os.utime(new, (now, now))

    deleted = prune_runs(older_than=timedelta(days=1), keep=1)

    assert {path.name for path in deleted} == {"old", "mid"}
    assert new.is_dir()
    assert not old.exists()
    assert not mid.exists()


def test_runs_prune_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "cli-runs"
    monkeypatch.setenv("OPENFRAME_RUNS_DIR", str(root))
    kept = run_directory("kept")
    dropped = run_directory("dropped")
    now = time.time()
    os.utime(kept, (now, now))
    os.utime(dropped, (now - 10 * 86400, now - 10 * 86400))
    monkeypatch.setattr(
        "sys.argv",
        ["open-frame", "runs", "prune", "--older-than", "7d", "--keep", "5"],
    )
    from openframe.cli import main

    assert main() == 0
    output = capsys.readouterr().out
    assert "deleted 1 run(s)" in output
    assert str(dropped.resolve()) in output
    assert kept.is_dir()
    assert not dropped.exists()


def test_runs_prune_requires_a_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["open-frame", "runs", "prune"])
    from openframe.cli import main

    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
