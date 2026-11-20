from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import openframe.integrations.mcp.adapter as adapter_mod
from openframe.integrations.mcp.adapter import call_mcp_tool, list_mcp_tools
from openframe.types import Frame, StepResult, Target

_REAL_REQUIRE_DESKTOP = adapter_mod._require_desktop


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
    assert all(item["contract_version"] == "v0.3.0" for item in tools)
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

    result = call_mcp_tool("run_flow", {"flow_path": "flow.yaml", "run_id": "r1", "dry_run": False})
    assert result["ok"] is False
    assert result["error"]["code"] == "flow_failed"
    assert result["run_id"] == "r1"
    run_dir = Path(result["artifacts"]["run_dir"])
    assert run_dir.is_absolute()
    assert run_dir.name == "r1"
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
        {
            "flow_path": "flow.yaml",
            "run_id": "r1",
            "include_step_details": True,
            "dry_run": False,
        },
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
        holder["result"] = call_mcp_tool("run_flow", {"flow_path": "flow.yaml", "dry_run": False})

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
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    result = call_mcp_tool("get_run_artifacts", {"run_id": "r1"})
    assert result["ok"] is True
    assert result["data"]["run_id"] == "r1"
    assert Path(result["data"]["run_dir"]) == (tmp_path / "runs" / "r1").resolve()
    assert Path(result["data"]["steps"][0]["step_dir"]).is_absolute()
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
    monkeypatch.setattr("openframe.integrations.mcp.adapter.focused_caret", lambda: None)
    result = call_mcp_tool(
        "click", {"query": "Save", "frame_path": str(image), "dry_run": False, "run_id": "r1"}
    )

    assert result["ok"] is True
    assert seen["origin"] == (40, 80)
    assert seen["scale_factor"] == 2.0
    assert result["data"]["point"] == {"x": 50, "y": 85}
    assert result["data"]["clicked_label"] is None


def _toolbar_words(second_word: str) -> list[dict[str, object]]:
    """OCR boxes for one button, plus a Mark Read line that misses the click."""
    return [
        {
            "text": "Mark",
            "left": 2000,
            "top": 400,
            "width": 160,
            "height": 40,
            "line": (1, 1, 1, 1),
        },
        {
            "text": second_word,
            "left": 2170,
            "top": 400,
            "width": 180,
            "height": 40,
            "line": (1, 1, 1, 1),
        },
        {"text": "Mark", "left": 10, "top": 800, "width": 80, "height": 20, "line": (2, 2, 2, 2)},
        {"text": "Read", "left": 100, "top": 800, "width": 80, "height": 20, "line": (2, 2, 2, 2)},
    ]


def _outlook_toolbar_words(second_word: str) -> list[dict[str, object]]:
    """One Outlook toolbar OCR line. The click pixel lands in the Mark button."""
    specs = (
        ("Archive", 1425, 98, 405, 38),
        ("&6", 1592, 34, 406, 32),
        ("Move", 1646, 68, 411, 21),
        ("Fe", 1790, 24, 406, 20),
        ("Flag", 1838, 52, 409, 28),
        ("VY", 1928, 24, 415, 13),
        ("©&", 2011, 38, 401, 32),
        ("Mark", 2068, 63, 410, 21),
        (second_word, 2141, 92, 410, 22),
        ("©", 2305, 30, 401, 38),
        ("Sync", 2357, 63, 411, 25),
        ("&", 2490, 34, 404, 34),
        ("Block", 2544, 70, 410, 21),
        ("®®", 2680, 35, 401, 37),
        ("send", 2737, 65, 410, 22),
        ("to", 2812, 25, 412, 19),
        ("OneNote", 2847, 115, 411, 21),
        ("O00", 3027, 26, 417, 6),
    )
    return [
        {
            "text": text,
            "left": left,
            "top": top,
            "width": width,
            "height": height,
            "line": (1, 45, 1, 1),
        }
        for text, left, width, top, height in specs
    ]


def _live_click_with_after_words(
    monkeypatch,
    words: list,
    *,
    frames: list[Frame] | None = None,
    caret: dict[str, str | None] | None = None,
) -> tuple[dict, dict[str, object]]:
    sequences = words if words and isinstance(words[0], list) else [words]
    if frames is None:
        frames = [
            Frame(
                width=3440,
                height=1440,
                scale_factor=2.0,
                source="screen:1",
                image_path="/tmp/after.png" if len(sequences) == 1 else f"/tmp/after-{index}.png",
                origin_x=0,
                origin_y=0,
            )
            for index in range(len(sequences))
        ]
    before = Frame(
        width=200, height=80, scale_factor=2.0, source="window:9", image_path="/tmp/before.png"
    )
    queries: list[str] = []
    info: dict[str, object] = {"reads": [], "sleeps": [], "after": None}

    class FakeLocator:
        def find(self, frame, query, strategy="all", options=None):
            _ = frame, strategy, options
            queries.append(query)
            return [
                Target(
                    x=1580,
                    y=146,
                    width=166,
                    height=21,
                    confidence=0.5,
                    source="ocr:tesseract",
                    text="Mark Unread",
                )
            ]

    class FakeActuator:
        def __init__(self, *, dry_run: bool) -> None:
            _ = dry_run

        def click_target(self, target: Target, **kwargs: object) -> tuple[int, int]:
            _ = target, kwargs
            return (1075, 210)

    def image_words(image_path: str) -> list[dict[str, object]]:
        reads = info["reads"]
        assert isinstance(reads, list)
        reads.append(image_path)
        return sequences[min(len(reads) - 1, len(sequences) - 1)]

    def screen(**_kwargs: object) -> Frame:
        screens = info.setdefault("screens", [])
        assert isinstance(screens, list)
        frame = frames[min(len(screens), len(frames) - 1)]
        screens.append(frame.image_path)
        return frame

    def write_step_artifacts(**kwargs: object) -> Path:
        info["after"] = kwargs["after"]
        return Path("runs/r1/mcp-click")

    monkeypatch.setattr(
        "openframe.integrations.mcp.adapter._require_desktop", lambda **_kwargs: None
    )
    monkeypatch.setattr(
        "openframe.integrations.mcp.adapter._resolve_frame", lambda *_args, **_kwargs: before
    )
    monkeypatch.setattr("openframe.integrations.mcp.adapter._build_locator", lambda: FakeLocator())
    monkeypatch.setattr("openframe.integrations.mcp.adapter.Actuator", FakeActuator)
    monkeypatch.setattr("openframe.integrations.mcp.adapter.screen", screen)
    monkeypatch.setattr(
        "openframe.integrations.mcp.adapter.write_step_artifacts", write_step_artifacts
    )
    monkeypatch.setattr("openframe.recognize.ocr.tesseract.image_words", image_words)
    monkeypatch.setattr("openframe.integrations.mcp.adapter.focused_caret", lambda: caret)

    def record_sleep(seconds: float) -> None:
        sleeps = info["sleeps"]
        assert isinstance(sleeps, list)
        sleeps.append(seconds)

    monkeypatch.setattr("openframe.integrations.mcp.adapter.time.sleep", record_sleep)

    def accessibility_query() -> list[dict[str, object]]:
        raise AssertionError("clicked_label must be read from the after image")

    monkeypatch.setattr(
        "openframe.recognize.a11y.macos._list_frontmost_elements", accessibility_query
    )

    result = call_mcp_tool("click", {"query": "Mark Unread", "dry_run": False, "run_id": "r1"})
    assert queries == ["Mark Unread"]
    return result, info


def test_live_click_reads_mark_read_from_the_after_image(monkeypatch) -> None:
    result, info = _live_click_with_after_words(monkeypatch, _toolbar_words("Read"))

    assert result["ok"] is True
    assert result["data"]["target"]["text"] == "Mark Unread"
    assert result["data"]["clicked_label"] == "Mark Read"
    assert result["data"]["point"] == {"x": 1075, "y": 210}
    assert info["reads"] == ["/tmp/after.png"]
    assert info["sleeps"] == []


def test_live_click_keeps_mark_unread_when_the_after_image_still_shows_it(monkeypatch) -> None:
    result, info = _live_click_with_after_words(monkeypatch, _toolbar_words("Unread"))

    assert result["ok"] is True
    assert result["data"]["target"]["text"] == "Mark Unread"
    assert result["data"]["clicked_label"] == "Mark Unread"
    assert info["reads"] == ["/tmp/after.png"] * 5


def test_live_click_label_is_only_the_button_on_the_toolbar_line(monkeypatch) -> None:
    result, _info = _live_click_with_after_words(monkeypatch, _outlook_toolbar_words("Unread"))

    assert result["ok"] is True
    assert result["data"]["clicked_label"] == "Mark Unread"


def test_live_click_waits_until_the_after_image_shows_the_changed_button(monkeypatch) -> None:
    result, info = _live_click_with_after_words(
        monkeypatch,
        [_outlook_toolbar_words("Unread"), _outlook_toolbar_words("Read")],
    )

    assert result["ok"] is True
    assert result["data"]["target"]["text"] == "Mark Unread"
    assert result["data"]["clicked_label"] == "Mark Read"
    after = info["after"]
    assert isinstance(after, Frame)
    assert after.image_path == "/tmp/after-1.png"
    assert info["reads"] == ["/tmp/after-0.png", "/tmp/after-1.png"]


def test_live_click_sets_clicked_label_null_when_the_point_has_no_words(monkeypatch) -> None:
    words = [
        {"text": "Inbox", "left": 10, "top": 10, "width": 40, "height": 20, "line": (9, 9, 9, 9)}
    ]
    result, info = _live_click_with_after_words(monkeypatch, words)

    assert result["ok"] is True
    assert result["data"]["clicked_label"] is None
    assert info["reads"] == ["/tmp/after.png"]


def test_dry_run_click_does_not_report_a_new_label(monkeypatch) -> None:
    frame = Frame(
        width=100, height=100, scale_factor=1.0, source="screen:1", image_path="/tmp/f.png"
    )
    listed = {"count": 0}

    class FakeLocator:
        def find(self, frame, query, strategy="all", options=None):
            _ = frame, query, strategy, options
            return [
                Target(
                    x=10,
                    y=20,
                    width=30,
                    height=40,
                    confidence=0.9,
                    source="ocr",
                    text="Mark Unread",
                )
            ]

    class FakeActuator:
        def __init__(self, *, dry_run: bool) -> None:
            _ = dry_run

        def click_target(self, target: Target, **kwargs: object) -> tuple[int, int]:
            _ = target, kwargs
            return (25, 40)

    sleeps = {"count": 0}

    def image_words(image_path: str) -> list[dict[str, object]]:
        _ = image_path
        listed["count"] += 1
        return _toolbar_words("Read")

    monkeypatch.setattr(
        "openframe.integrations.mcp.adapter._require_desktop", lambda **_kwargs: None
    )
    monkeypatch.setattr(
        "openframe.integrations.mcp.adapter._resolve_frame", lambda *_args, **_kwargs: frame
    )
    monkeypatch.setattr("openframe.integrations.mcp.adapter._build_locator", lambda: FakeLocator())
    monkeypatch.setattr("openframe.integrations.mcp.adapter.Actuator", FakeActuator)
    monkeypatch.setattr(
        "openframe.integrations.mcp.adapter.write_step_artifacts",
        lambda **_kwargs: Path("runs/r1/mcp-click"),
    )
    monkeypatch.setattr("openframe.recognize.ocr.tesseract.image_words", image_words)
    monkeypatch.setattr(
        "openframe.integrations.mcp.adapter.focused_caret",
        lambda: listed.__setitem__("count", listed["count"] + 1),
    )
    monkeypatch.setattr(
        "openframe.integrations.mcp.adapter.time.sleep",
        lambda _seconds: sleeps.__setitem__("count", sleeps["count"] + 1),
    )

    result = call_mcp_tool("click", {"query": "Mark Unread", "dry_run": True, "run_id": "r1"})

    assert result["ok"] is True
    assert result["data"]["target"]["text"] == "Mark Unread"
    assert "clicked_label" not in result["data"]
    assert "caret" not in result["data"]
    assert listed["count"] == 0
    assert sleeps["count"] == 0


_TITLE_CARET = {"role": "AXTextField", "name": "CursorSharp shares", "value": None}


def test_live_click_reports_the_focused_element_and_keeps_clicked_label(monkeypatch) -> None:
    result, _info = _live_click_with_after_words(
        monkeypatch, _toolbar_words("Read"), caret=_TITLE_CARET
    )

    assert result["ok"] is True
    assert result["data"]["clicked_label"] == "Mark Read"
    assert result["data"]["caret"] == _TITLE_CARET


def test_live_type_and_key_report_the_focused_element(monkeypatch) -> None:
    class FakeActuator:
        def __init__(self, *, dry_run: bool) -> None:
            _ = dry_run

        def type_text(self, text: str, interval: float = 0.0) -> None:
            _ = text, interval

        def press_key(self, key: str) -> None:
            _ = key

        def key_combo(self, *keys: str) -> None:
            _ = keys

    monkeypatch.setattr(
        "openframe.integrations.mcp.adapter._require_desktop", lambda **_kwargs: None
    )
    monkeypatch.setattr("openframe.integrations.mcp.adapter.Actuator", FakeActuator)
    monkeypatch.setattr("openframe.integrations.mcp.adapter.focused_caret", lambda: _TITLE_CARET)

    typed = call_mcp_tool("type", {"text": "shares", "dry_run": False})
    keyed = call_mcp_tool("key", {"key": "down", "dry_run": False})
    combo = call_mcp_tool("key", {"combo": ["down"], "dry_run": False})

    assert typed["ok"] is True
    assert typed["data"]["caret"] == _TITLE_CARET
    assert keyed["data"]["caret"] == _TITLE_CARET
    assert combo["data"]["caret"] == _TITLE_CARET


def test_dry_run_type_and_key_omit_caret(monkeypatch) -> None:
    calls = {"count": 0}

    class FakeActuator:
        def __init__(self, *, dry_run: bool) -> None:
            _ = dry_run

        def type_text(self, text: str, interval: float = 0.0) -> None:
            _ = text, interval

        def press_key(self, key: str) -> None:
            _ = key

    def focused_caret() -> dict[str, str | None]:
        calls["count"] += 1
        return _TITLE_CARET

    monkeypatch.setattr(
        "openframe.integrations.mcp.adapter._require_desktop", lambda **_kwargs: None
    )
    monkeypatch.setattr("openframe.integrations.mcp.adapter.Actuator", FakeActuator)
    monkeypatch.setattr("openframe.integrations.mcp.adapter.focused_caret", focused_caret)

    typed = call_mcp_tool("type", {"text": "shares", "dry_run": True})
    keyed = call_mcp_tool("key", {"key": "down", "dry_run": True})

    assert "caret" not in typed["data"]
    assert "caret" not in keyed["data"]
    assert calls["count"] == 0


def test_unreadable_focus_sets_caret_null(monkeypatch) -> None:
    class FakeActuator:
        def __init__(self, *, dry_run: bool) -> None:
            _ = dry_run

        def type_text(self, text: str, interval: float = 0.0) -> None:
            _ = text, interval

    monkeypatch.setattr(
        "openframe.integrations.mcp.adapter._require_desktop", lambda **_kwargs: None
    )
    monkeypatch.setattr("openframe.integrations.mcp.adapter.Actuator", FakeActuator)
    monkeypatch.setattr("openframe.integrations.mcp.adapter.focused_caret", lambda: None)

    result = call_mcp_tool("type", {"text": "shares", "dry_run": False})

    assert result["ok"] is True
    assert result["data"]["caret"] is None


def test_caret_from_focus_keeps_role_and_name_or_value() -> None:
    from openframe.recognize.a11y.macos import caret_from_focus

    assert caret_from_focus({"role": "AXTextField", "name": "", "value": "CursorSharp shares"}) == {
        "role": "AXTextField",
        "name": None,
        "value": "CursorSharp shares",
    }
    assert caret_from_focus({"role": "AXTextArea", "name": "body", "value": None}) == {
        "role": "AXTextArea",
        "name": "body",
        "value": None,
    }
    assert caret_from_focus(None) is None
    assert caret_from_focus({"role": " ", "name": "", "value": ""}) is None


def test_click_missing_target_stays_not_found(monkeypatch) -> None:
    frame = Frame(
        width=100, height=100, scale_factor=1.0, source="screen:1", image_path="/tmp/f.png"
    )
    listed = {"count": 0}

    class FakeLocator:
        def find(self, frame, query, strategy="all", options=None):
            _ = frame, query, strategy, options
            return []

    def image_words(image_path: str) -> list[dict[str, object]]:
        _ = image_path
        listed["count"] += 1
        return _toolbar_words("Read")

    monkeypatch.setattr(
        "openframe.integrations.mcp.adapter._require_desktop", lambda **_kwargs: None
    )
    monkeypatch.setattr(
        "openframe.integrations.mcp.adapter._resolve_frame", lambda *_args, **_kwargs: frame
    )
    monkeypatch.setattr("openframe.integrations.mcp.adapter._build_locator", lambda: FakeLocator())
    monkeypatch.setattr("openframe.recognize.ocr.tesseract.image_words", image_words)

    result = call_mcp_tool("click", {"query": "Mark Unread", "dry_run": False, "run_id": "r1"})

    assert result["ok"] is False
    assert result["error"]["code"] == "not_found"
    assert listed["count"] == 0


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


def test_omitted_dry_run_does_not_send_input(monkeypatch) -> None:
    seen: list[bool] = []

    class FakeActuator:
        def __init__(self, *, dry_run: bool) -> None:
            seen.append(dry_run)

        def type_text(self, text: str, interval: float = 0.0) -> None:
            _ = text, interval

    monkeypatch.setattr("openframe.integrations.mcp.adapter.Actuator", FakeActuator)
    result = call_mcp_tool("type", {"text": "hello"})
    assert result["ok"] is True
    assert result["data"]["dry_run"] is True
    assert seen == [True]


def test_explicit_dry_run_false_is_live(monkeypatch) -> None:
    seen: list[bool] = []

    class FakeActuator:
        def __init__(self, *, dry_run: bool) -> None:
            seen.append(dry_run)

        def type_text(self, text: str, interval: float = 0.0) -> None:
            _ = text, interval

    monkeypatch.setattr("openframe.integrations.mcp.adapter.Actuator", FakeActuator)
    monkeypatch.setattr("openframe.integrations.mcp.adapter.focused_caret", lambda: None)
    result = call_mcp_tool("type", {"text": "hello", "dry_run": False})
    assert result["data"]["dry_run"] is False
    assert seen == [False]


def test_type_rejects_empty_text() -> None:
    result = call_mcp_tool("type", {"text": "   ", "dry_run": True})
    assert result["ok"] is False
    assert result["error"]["code"] == "validation_error"
    assert "empty" in result["error"]["message"]


def test_key_requires_exactly_one_of_key_or_combo() -> None:
    missing = call_mcp_tool("key", {"dry_run": True})
    assert missing["error"]["code"] == "validation_error"
    both = call_mcp_tool("key", {"key": "a", "combo": ["cmd", "c"], "dry_run": True})
    assert both["error"]["code"] == "validation_error"
    combo = call_mcp_tool("key", {"combo": ["cmd", "c"], "dry_run": True})
    assert combo["ok"] is True
    assert combo["data"]["combo"] == ["cmd", "c"]
    assert combo["data"]["dry_run"] is True


def test_run_flow_caps_full_step_details(monkeypatch) -> None:
    class FakeFlow:
        name = "big"

    class FakeRunner:
        def __init__(self, *, dry_run: bool) -> None:
            _ = dry_run

        def run(self, flow, *, run_id: str):
            _ = flow, run_id

            class SessionObj:
                results: ClassVar[list] = [
                    StepResult(
                        step_id=f"s{index}",
                        success=True,
                        duration_ms=1,
                        details={"blob": "x" * 10_000},
                    )
                    for index in range(6)
                ]

            return SessionObj()

    monkeypatch.setattr("openframe.integrations.mcp.adapter.load_flow", lambda _path: FakeFlow())
    monkeypatch.setattr("openframe.integrations.mcp.adapter.FlowRunner", FakeRunner)
    result = call_mcp_tool(
        "run_flow",
        {"flow_path": "flow.yaml", "include_step_details": True, "dry_run": True},
    )
    assert result["ok"] is True
    assert result["data"]["step_details_truncated"] is True
    assert result["data"]["steps_omitted"] >= 1
    assert len(result["data"]["steps"]) < 6


def test_locked_screen_is_not_permission_denied(monkeypatch) -> None:
    from openframe.desktop_access import DisplayPower

    monkeypatch.setattr(adapter_mod.sys, "platform", "darwin")
    monkeypatch.setattr(adapter_mod, "_require_desktop", _REAL_REQUIRE_DESKTOP)
    monkeypatch.setattr(
        adapter_mod,
        "read_display_power",
        lambda: DisplayPower(locked=True, asleep=False, known=True),
    )
    result = call_mcp_tool("capture", {})
    assert result["ok"] is False
    assert result["error"]["code"] == "screen_unavailable"
    assert "not a missing Screen Recording or Accessibility grant" in result["error"]["message"]


def test_awake_permission_failure_names_the_host_process(monkeypatch) -> None:
    from openframe.desktop_access import DisplayPower, host_process_label
    from openframe.doctor import CheckResult

    monkeypatch.setattr(adapter_mod.sys, "platform", "darwin")
    monkeypatch.setattr(adapter_mod, "_require_desktop", _REAL_REQUIRE_DESKTOP)
    monkeypatch.setattr(
        adapter_mod,
        "read_display_power",
        lambda: DisplayPower(locked=False, asleep=False, known=True),
    )
    monkeypatch.setattr(
        "openframe.doctor._check_screen_recording",
        lambda: CheckResult(
            id="screen_recording",
            status="fail",
            detail="capture failed",
            hint=f"Screen Recording is not available to {host_process_label()}.",
            required=True,
        ),
    )
    result = call_mcp_tool("capture", {})
    assert result["error"]["code"] == "permission_denied"
    assert host_process_label().split()[0] in result["error"]["message"]


def test_awake_accessibility_failure_is_permission_denied(monkeypatch) -> None:
    from openframe.desktop_access import DisplayPower
    from openframe.doctor import CheckResult

    class FakeActuator:
        def __init__(self, *, dry_run: bool) -> None:
            _ = dry_run

        def type_text(self, text: str, interval: float = 0.0) -> None:
            raise AssertionError(text)

    monkeypatch.setattr(adapter_mod, "Actuator", FakeActuator)
    monkeypatch.setattr(adapter_mod.sys, "platform", "darwin")
    monkeypatch.setattr(adapter_mod, "_require_desktop", _REAL_REQUIRE_DESKTOP)
    monkeypatch.setattr(
        adapter_mod,
        "read_display_power",
        lambda: DisplayPower(locked=False, asleep=False, known=True),
    )
    monkeypatch.setattr(
        "openframe.doctor._check_accessibility",
        lambda: CheckResult(
            id="accessibility",
            status="fail",
            detail="not allowed",
            hint="Accessibility is not available to python.",
            required=True,
        ),
    )
    result = call_mcp_tool("type", {"text": "hello", "dry_run": False})
    assert result["error"]["code"] == "permission_denied"
    assert "Accessibility" in result["error"]["message"]
