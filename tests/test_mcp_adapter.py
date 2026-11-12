from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from openframe.integrations.mcp.adapter import call_mcp_tool, list_mcp_tools
from openframe.types import Frame, StepResult, Target


def test_list_mcp_tools_contains_expected_names() -> None:
    tools = list_mcp_tools()
    names = {item["name"] for item in tools}
    assert {
        "capture",
        "find",
        "click",
        "type",
        "key",
        "scroll",
        "run_flow",
        "get_run_artifacts",
    }.issubset(names)
    assert all(item["contract_version"] == "v0.2.2" for item in tools)
    assert all(
        "required_args" in item and "optional_args" in item and "error_codes" in item
        for item in tools
    )


def test_call_mcp_tool_unknown_tool_returns_structured_error() -> None:
    result = call_mcp_tool("does-not-exist", {})
    assert result["ok"] is False
    assert result["error"]["code"] == "unknown_tool"
    assert result["tool"] == "does-not-exist"


def test_get_run_artifacts_reports_not_found() -> None:
    result = call_mcp_tool("get_run_artifacts", {"run_id": "run-that-does-not-exist"})
    assert result["ok"] is False
    assert result["error"]["code"] == "not_found"
    assert set(result.keys()) == {"ok", "tool", "run_id", "data", "error", "artifacts"}


def test_run_flow_failure_maps_to_flow_failed(monkeypatch) -> None:
    class FakeFlow:
        name = "demo"

    class FakeRunner:
        def __init__(self, *, dry_run: bool) -> None:
            _ = dry_run

        def run(self, flow, *, run_id: str):
            _ = flow, run_id

            class SessionObj:
                results: ClassVar[list] = [
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
    assert result["data"]["step_details"] == "summary"
    assert result["data"]["steps"][0] == {
        "step_id": "one",
        "success": False,
        "duration_ms": 1,
        "error": "boom",
    }


def test_run_flow_include_step_details(monkeypatch) -> None:
    class FakeFlow:
        name = "demo"

    class FakeRunner:
        def __init__(self, *, dry_run: bool) -> None:
            _ = dry_run

        def run(self, flow, *, run_id: str):
            _ = flow, run_id

            class SessionObj:
                results: ClassVar[list] = [
                    StepResult(
                        step_id="one",
                        success=True,
                        duration_ms=1,
                        details={"kind": "wait"},
                    )
                ]

            return SessionObj()

    monkeypatch.setattr("openframe.integrations.mcp.adapter.load_flow", lambda _path: FakeFlow())
    monkeypatch.setattr("openframe.integrations.mcp.adapter.FlowRunner", FakeRunner)

    result = call_mcp_tool(
        "run_flow",
        {"flow_path": "flow.yaml", "run_id": "r1", "include_step_details": True},
    )
    assert result["ok"] is True
    assert result["data"]["step_details"] == "full"
    assert result["data"]["steps"][0]["details"] == {"kind": "wait"}


def test_timeout_does_not_actuate_and_carries_run_id(monkeypatch) -> None:
    import threading
    import time

    from openframe.act import Actuator

    monkeypatch.setenv("OPENFRAME_MCP_TOOL_TIMEOUT_SEC", "0.05")
    monkeypatch.setenv("OPENFRAME_MCP_RUN_FLOW_TIMEOUT_SEC", "0.05")
    actuated: list[str] = []
    monkeypatch.setattr(
        "openframe.act.core._load_pyautogui",
        lambda: actuated.append("pyautogui"),
    )
    entered = threading.Event()
    finished = threading.Event()
    seen: dict[str, str | None] = {}

    def slow_handler(
        payload: dict[str, object],
    ) -> tuple[dict[str, object], str | None, dict[str, object]]:
        seen["run_id"] = payload.get("run_id") if isinstance(payload.get("run_id"), str) else None
        entered.set()
        try:
            time.sleep(0.4)
            Actuator(dry_run=False).type_text("secret")
            actuated.append("typed")
            return {}, seen["run_id"], {}
        finally:
            finished.set()

    monkeypatch.setattr("openframe.integrations.mcp.adapter._tool_run_flow", slow_handler)

    holder: dict[str, dict[str, object]] = {}

    def invoke() -> None:
        holder["result"] = call_mcp_tool("run_flow", {"flow_path": "flow.yaml"})

    worker = threading.Thread(target=invoke)
    worker.start()
    assert entered.wait(2)
    overlap = call_mcp_tool("type", {"text": "x", "dry_run": True})
    assert overlap["ok"] is False
    assert overlap["error"]["code"] == "busy"
    worker.join(2)
    assert finished.wait(2)

    result = holder["result"]
    assert result["ok"] is False
    assert result["error"]["code"] == "timeout"
    assert result["run_id"]
    assert seen["run_id"] == result["run_id"]
    assert actuated == []

    follow = call_mcp_tool("type", {"text": "x", "dry_run": True})
    assert follow["ok"] is True


def test_overlapping_mcp_call_returns_busy(monkeypatch) -> None:
    import threading

    entered = threading.Event()
    release = threading.Event()

    def blocking(_payload: dict[str, object]) -> tuple[dict[str, object], None, dict[str, object]]:
        entered.set()
        release.wait(2)
        return {"text_length": 1, "interval": 0.0, "dry_run": True}, None, {}

    monkeypatch.setattr("openframe.integrations.mcp.adapter._tool_type", blocking)
    holder: dict[str, dict[str, object]] = {}

    def invoke() -> None:
        holder["result"] = call_mcp_tool("type", {"text": "hi", "dry_run": True})

    worker = threading.Thread(target=invoke)
    worker.start()
    assert entered.wait(2)
    overlap = call_mcp_tool("click", {"query": "Submit", "dry_run": True})
    release.set()
    worker.join(2)

    assert overlap["ok"] is False
    assert overlap["error"]["code"] == "busy"
    assert holder["result"]["ok"] is True


def test_non_numeric_tool_timeout_uses_default(monkeypatch, capsys) -> None:
    from openframe.integrations.mcp import adapter as adapter_module

    adapter_module._timeout_warnings_sent.clear()
    monkeypatch.setenv("OPENFRAME_MCP_TOOL_TIMEOUT_SEC", "not-a-number")

    result = call_mcp_tool("type", {"text": "x", "dry_run": True})

    assert result["ok"] is True
    assert "OPENFRAME_MCP_TOOL_TIMEOUT_SEC" in capsys.readouterr().err


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
    assert set(result.keys()) == {"ok", "tool", "run_id", "data", "error", "artifacts"}
    assert result["error"] is None


def test_find_without_query_returns_validation_error() -> None:
    result = call_mcp_tool("find", {})
    assert result["ok"] is False
    assert result["error"]["code"] == "validation_error"
    assert result["error"]["message"] == "query is required."
    assert set(result.keys()) == {"ok", "tool", "run_id", "data", "error", "artifacts"}


def test_click_expect_one_returns_ambiguous_target(monkeypatch) -> None:
    frame = Frame(
        width=100, height=100, scale_factor=1.0, source="screen:1", image_path="/tmp/f.png"
    )

    class FakeLocator:
        def find(self, frame, query, strategy="all", options=None):
            _ = frame, query, strategy
            return [
                Target(
                    x=10, y=20, width=30, height=40, confidence=0.9, source="ocr", text="Create"
                ),
                Target(
                    x=50, y=60, width=30, height=40, confidence=0.8, source="ocr", text="Create"
                ),
            ]

    monkeypatch.setattr(
        "openframe.integrations.mcp.adapter._resolve_frame", lambda _path, **_kwargs: frame
    )
    monkeypatch.setattr("openframe.integrations.mcp.adapter._build_locator", lambda: FakeLocator())

    result = call_mcp_tool(
        "click", {"query": "Create", "expect_one": True, "dry_run": True, "run_id": "r1"}
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "ambiguous_target"
    assert result["run_id"] == "r1"


def test_click_fails_closed_without_selector(monkeypatch) -> None:
    frame = Frame(
        width=100, height=100, scale_factor=1.0, source="screen:1", image_path="/tmp/f.png"
    )
    clicked = {"count": 0}

    class FakeLocator:
        def find(self, frame, query, strategy="all", options=None):
            _ = frame, query, strategy
            return [
                Target(
                    x=10, y=20, width=30, height=40, confidence=0.9, source="ocr", text="Create"
                ),
                Target(
                    x=50, y=60, width=30, height=40, confidence=0.8, source="ocr", text="Create"
                ),
            ]

    class FakeActuator:
        def __init__(self, *, dry_run):
            _ = dry_run

        def click_target(self, *args, **kwargs):
            clicked["count"] += 1
            return (0, 0)

    monkeypatch.setattr(
        "openframe.integrations.mcp.adapter._resolve_frame", lambda _path, **_kwargs: frame
    )
    monkeypatch.setattr("openframe.integrations.mcp.adapter._build_locator", lambda: FakeLocator())
    monkeypatch.setattr("openframe.integrations.mcp.adapter.Actuator", FakeActuator)

    result = call_mcp_tool("click", {"query": "Create", "dry_run": True, "run_id": "r1"})
    assert result["ok"] is False
    assert result["error"]["code"] == "ambiguous_target"
    assert clicked["count"] == 0


def test_click_selector_top_most_picks_upper_target(monkeypatch) -> None:
    frame = Frame(
        width=100, height=100, scale_factor=1.0, source="screen:1", image_path="/tmp/f.png"
    )
    clicked = {}

    class FakeLocator:
        def find(self, frame, query, strategy="all", options=None):
            _ = frame, query, strategy
            return [
                Target(
                    x=30, y=200, width=20, height=10, confidence=0.9, source="ocr", text="Create"
                ),
                Target(
                    x=10, y=100, width=20, height=10, confidence=0.8, source="ocr", text="Create"
                ),
            ]

    class FakeActuator:
        def __init__(self, *, dry_run):
            _ = dry_run

        def click_target(self, target, *, anchor, kind, scale_factor=1.0, **kwargs: object):
            _ = anchor, kind, scale_factor
            clicked["x"] = target.x
            clicked["y"] = target.y
            return (target.x, target.y)

    monkeypatch.setattr(
        "openframe.integrations.mcp.adapter._resolve_frame", lambda _path, **_kwargs: frame
    )
    monkeypatch.setattr("openframe.integrations.mcp.adapter._build_locator", lambda: FakeLocator())
    monkeypatch.setattr("openframe.integrations.mcp.adapter.Actuator", FakeActuator)
    monkeypatch.setattr(
        "openframe.integrations.mcp.adapter.write_step_artifacts",
        lambda **_kwargs: Path("runs/r1/mcp-click"),
    )

    result = call_mcp_tool(
        "click", {"query": "Create", "selector": "top_most", "dry_run": True, "run_id": "r1"}
    )
    assert result["ok"] is True
    assert clicked == {"x": 10, "y": 100}


def test_scroll_tool_dry_run(monkeypatch) -> None:
    scrolled: list[dict[str, object]] = []

    class FakeActuator:
        def __init__(self, *, dry_run: bool) -> None:
            self.dry_run = dry_run

        def scroll(self, clicks: int, *, x=None, y=None) -> None:
            scrolled.append({"clicks": clicks, "x": x, "y": y, "dry_run": self.dry_run})

    monkeypatch.setattr("openframe.integrations.mcp.adapter.Actuator", FakeActuator)
    result = call_mcp_tool("scroll", {"clicks": -5, "x": 10, "y": 20, "dry_run": True})
    assert result["ok"] is True
    assert result["data"]["clicks"] == -5
    assert scrolled == [{"clicks": -5, "x": 10, "y": 20, "dry_run": True}]


def test_live_click_rejects_frame_path_without_sidecar(tmp_path: Path, monkeypatch) -> None:
    image = tmp_path / "region.png"
    image.write_bytes(b"not-a-real-png")
    clicked = {"count": 0}

    class FakeActuator:
        def __init__(self, *, dry_run: bool) -> None:
            _ = dry_run

        def click_target(self, target: Target, **kwargs: object) -> tuple[int, int]:
            _ = target, kwargs
            clicked["count"] += 1
            return (1, 2)

    monkeypatch.setattr("openframe.integrations.mcp.adapter.Actuator", FakeActuator)
    result = call_mcp_tool("click", {"query": "Save", "frame_path": str(image), "dry_run": False})

    assert result["ok"] is False
    assert result["error"]["code"] == "validation_error"
    assert "sidecar" in result["error"]["message"]
    assert clicked["count"] == 0


def test_find_allows_frame_path_without_sidecar(tmp_path: Path, monkeypatch) -> None:
    image = tmp_path / "region.png"
    image.write_bytes(b"not-a-real-png")

    class FakeLocator:
        def find(
            self, frame: Frame, query: str, strategy: str = "all", options=None
        ) -> list[Target]:
            _ = frame, query, strategy, options
            assert frame.scale_factor == 1.0
            return []

    monkeypatch.setattr("openframe.integrations.mcp.adapter._build_locator", lambda: FakeLocator())
    result = call_mcp_tool("find", {"query": "Save", "frame_path": str(image)})

    assert result["ok"] is True
    assert result["data"]["count"] == 0


def test_live_click_uses_sidecar_origin(tmp_path: Path, monkeypatch) -> None:
    image = tmp_path / "window.png"
    image.write_bytes(b"not-a-real-png")
    sidecar = tmp_path / "window.png.openframe.json"
    sidecar.write_text(
        '{"width": 200, "height": 80, "scale_factor": 2.0, "origin_x": 40, "origin_y": 80, '
        '"source": "window:9"}',
        encoding="utf-8",
    )
    seen: dict[str, object] = {}

    class FakeLocator:
        def find(
            self, frame: Frame, query: str, strategy: str = "all", options=None
        ) -> list[Target]:
            _ = query, strategy, options
            assert frame.scale_factor == 2.0
            assert frame.origin_x == 40
            return [Target(x=20, y=10, width=20, height=10, confidence=0.9, source="ocr")]

    class FakeActuator:
        def __init__(self, *, dry_run: bool) -> None:
            _ = dry_run

        def click_target(self, target: Target, **kwargs: object) -> tuple[int, int]:
            seen["origin"] = kwargs["origin"]
            seen["scale_factor"] = kwargs["scale_factor"]
            return (50, 85)

    monkeypatch.setattr("openframe.integrations.mcp.adapter._build_locator", lambda: FakeLocator())
    monkeypatch.setattr("openframe.integrations.mcp.adapter.Actuator", FakeActuator)
    monkeypatch.setattr(
        "openframe.integrations.mcp.adapter.screen",
        lambda out_path=None: Frame(
            width=200, height=80, scale_factor=2.0, source="screen:1", origin_x=0, origin_y=0
        ),
    )
    monkeypatch.setattr(
        "openframe.integrations.mcp.adapter.write_step_artifacts",
        lambda **_kwargs: Path("runs/r1/mcp-click"),
    )
    result = call_mcp_tool(
        "click", {"query": "Save", "frame_path": str(image), "dry_run": False, "run_id": "r1"}
    )

    assert result["ok"] is True
    assert seen["origin"] == (40, 80)
    assert seen["scale_factor"] == 2.0
    assert result["data"]["point"] == {"x": 50, "y": 85}


def test_scroll_tool_requires_clicks() -> None:
    result = call_mcp_tool("scroll", {"dry_run": True})
    assert result["ok"] is False
    assert result["error"]["code"] == "validation_error"


def test_find_reports_recognizer_failure_instead_of_not_found(monkeypatch) -> None:
    class BrokenLocator:
        recognizer_errors: ClassVar[list[str]] = ["a11y:macos: permission denied"]

        def find(self, frame, query, strategy="all", options=None):
            _ = frame, strategy, options
            raise RuntimeError(
                f'Recognizer failed and produced no targets for query "{query}": '
                "a11y:macos: permission denied"
            )

    monkeypatch.setattr(
        "openframe.integrations.mcp.adapter._resolve_frame",
        lambda *_args, **_kwargs: Frame(width=1, height=1, scale_factor=1.0, source="screen"),
    )
    monkeypatch.setattr(
        "openframe.integrations.mcp.adapter._build_locator", lambda: BrokenLocator()
    )

    result = call_mcp_tool("find", {"query": "Submit"})

    assert result["ok"] is False
    assert result["error"]["code"] == "runtime_error"
    assert "permission denied" in result["error"]["message"]


def test_find_includes_recognizer_errors_when_another_recognizer_matches(monkeypatch) -> None:
    class PartialLocator:
        recognizer_errors: ClassVar[list[str]] = ["a11y:macos: permission denied"]

        def find(self, frame, query, strategy="all", options=None):
            _ = frame, query, strategy, options
            return [
                Target(x=1, y=2, width=3, height=4, confidence=0.9, source="ocr", text="Submit")
            ]

    monkeypatch.setattr(
        "openframe.integrations.mcp.adapter._resolve_frame",
        lambda *_args, **_kwargs: Frame(width=1, height=1, scale_factor=1.0, source="screen"),
    )
    monkeypatch.setattr(
        "openframe.integrations.mcp.adapter._build_locator", lambda: PartialLocator()
    )

    result = call_mcp_tool("find", {"query": "Submit"})

    assert result["ok"] is True
    assert result["data"]["recognizer_errors"] == ["a11y:macos: permission denied"]
    assert result["data"]["count"] == 1
