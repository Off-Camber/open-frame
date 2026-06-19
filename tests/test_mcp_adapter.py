from __future__ import annotations

from pathlib import Path

from openframe.integrations.mcp.adapter import call_mcp_tool, list_mcp_tools
from openframe.types import StepResult


def test_list_mcp_tools_contains_expected_names() -> None:
    tools = list_mcp_tools()
    names = {item["name"] for item in tools}
    assert {"capture", "find", "click", "type", "key", "run_flow", "get_run_artifacts"}.issubset(names)


def test_call_mcp_tool_unknown_tool_returns_structured_error() -> None:
    result = call_mcp_tool("does-not-exist", {})
    assert result["ok"] is False
    assert result["error"]["code"] == "unknown_tool"
    assert result["tool"] == "does-not-exist"


def test_get_run_artifacts_reports_not_found() -> None:
    result = call_mcp_tool("get_run_artifacts", {"run_id": "run-that-does-not-exist"})
    assert result["ok"] is False
    assert result["error"]["code"] == "not_found"


def test_run_flow_failure_maps_to_flow_failed(monkeypatch) -> None:
    class FakeFlow:
        name = "demo"

    class FakeRunner:
        def __init__(self, *, dry_run: bool) -> None:
            _ = dry_run

        def run(self, flow, *, run_id: str):
            _ = flow, run_id

            class SessionObj:
                results = [
                    StepResult(
                        step_id="one",
                        success=False,
                        duration_ms=1,
                        error="boom",
                        details={"kind": "wait"},
                    )
                ]

            return SessionObj()

    monkeypatch.setattr("openframe.integrations.mcp.adapter.load_flow", lambda _path: FakeFlow())
    monkeypatch.setattr("openframe.integrations.mcp.adapter.FlowRunner", FakeRunner)

    result = call_mcp_tool("run_flow", {"flow_path": "flow.yaml", "run_id": "r1"})
    assert result["ok"] is False
    assert result["error"]["code"] == "flow_failed"
    assert result["run_id"] == "r1"
    assert result["artifacts"]["run_dir"].endswith("runs/r1")


def test_get_run_artifacts_lists_step_files(tmp_path: Path, monkeypatch) -> None:
    run_dir = tmp_path / "runs" / "r1" / "step-a"
    run_dir.mkdir(parents=True)
    (run_dir / "step.json").write_text("{}", encoding="utf-8")
    (run_dir / "before.png").write_text("png", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = call_mcp_tool("get_run_artifacts", {"run_id": "r1"})
    assert result["ok"] is True
    assert result["data"]["run_id"] == "r1"
    assert result["data"]["steps"][0]["step_id"] == "step-a"
    assert "step.json" in result["data"]["steps"][0]["files"]

