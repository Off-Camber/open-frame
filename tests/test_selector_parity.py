"""Parity tests for shared scale-aware target selection."""

from __future__ import annotations

from pathlib import Path

import pytest

from openframe.flow import Flow, FlowStep
from openframe.integrations.mcp import call_mcp_tool
from openframe.recognize.coords import select_target
from openframe.runner import FlowRunner, _select_target
from openframe.types import Frame, Target


def _mixed_targets() -> list[Target]:
    """Physical OCR + logical a11y candidates that diverge without scale awareness.

    At scale_factor=2.0:
      - OCR physical (20, 600) → logical (10, 300)
      - a11y logical (20, 400) stays (20, 400)
      - OCR physical (900, 450) → logical (450, 225)
    """
    return [
        Target(
            x=20,
            y=600,
            width=100,
            height=40,
            confidence=0.9,
            source="ocr:tesseract",
            coordinate_space="physical",
            text="Create",
            label="ocr-upper",
        ),
        Target(
            x=20,
            y=400,
            width=100,
            height=40,
            confidence=0.8,
            source="a11y:macos",
            coordinate_space="logical",
            text="Create",
            label="a11y-mid",
        ),
        Target(
            x=900,
            y=450,
            width=100,
            height=40,
            confidence=0.7,
            source="ocr:tesseract",
            coordinate_space="physical",
            text="Create",
            label="ocr-right",
        ),
    ]


def _identity(target: Target) -> tuple[str | None, int, int, str]:
    return target.label, target.x, target.y, target.coordinate_space


@pytest.mark.parametrize(
    ("scale_factor", "selector", "expected_label"),
    [
        (1.0, "top_most", "a11y-mid"),
        (2.0, "top_most", "ocr-right"),  # logical y 225 beats 300 and 400
        (1.0, "left_most", "a11y-mid"),  # x=20,y=400 beats x=20,y=600
        (2.0, "left_most", "ocr-upper"),  # logical x 10 beats 20 and 450
        (1.0, "right_most", "ocr-right"),
        (2.0, "right_most", "ocr-right"),
        (1.0, "highest_confidence", "ocr-upper"),
        (2.0, "highest_confidence", "ocr-upper"),
        (1.0, "first", "ocr-upper"),
        (2.0, "first", "ocr-upper"),
    ],
)
def test_select_target_shared_helper_mixed_coords(
    scale_factor: float,
    selector: str,
    expected_label: str,
) -> None:
    selected = select_target(targets=_mixed_targets(), selector=selector, scale_factor=scale_factor)
    assert selected.label == expected_label


def _spy_actuator(store: dict[str, object]):
    class SpyActuator:
        def __init__(self, *, dry_run: bool) -> None:
            _ = dry_run

        def click_target(
            self,
            target: Target,
            *,
            anchor: str,
            kind: str,
            scale_factor: float = 1.0,
            **kwargs: object,
        ) -> tuple[int, int]:
            _ = anchor, kind, kwargs
            store["target"] = target
            store["scale_factor"] = scale_factor
            return (target.x, target.y)

    return SpyActuator


@pytest.mark.parametrize("scale_factor", [1.0, 2.0])
def test_runner_and_mcp_select_same_target_for_spatial_selectors(
    scale_factor: float, monkeypatch: pytest.MonkeyPatch
) -> None:
    targets = _mixed_targets()
    frame = Frame(
        width=1000,
        height=800,
        scale_factor=scale_factor,
        source="screen:1",
        image_path="/tmp/parity.png",
    )

    class FakeLocator:
        def __init__(self, _recognizers: list[object] | None = None) -> None:
            pass

        def find(self, frame: Frame, query: str, strategy: str = "all", options=None) -> list[Target]:
            _ = frame, query, strategy
            return list(targets)

    for selector in ("top_most", "left_most", "right_most"):
        shared = select_target(targets=targets, selector=selector, scale_factor=scale_factor)
        via_alias = _select_target(targets=targets, selector=selector, scale_factor=scale_factor)
        assert _identity(via_alias) == _identity(shared)

        clicked: dict[str, object] = {}
        flow = Flow(
            name="parity-runner",
            steps=[
                FlowStep(
                    id="click",
                    kind="click",
                    params={"query": "Create", "selector": selector},
                )
            ],
        )
        monkeypatch.setattr("openframe.runner.screen", lambda *args, **kwargs: frame)
        monkeypatch.setattr("openframe.runner.build_default_locator", lambda: FakeLocator())
        monkeypatch.setattr("openframe.runner.Actuator", _spy_actuator(clicked))
        monkeypatch.setattr(
            "openframe.runner.write_step_artifacts", lambda **kwargs: Path("runs/r1/step")
        )
        session = FlowRunner(dry_run=True).run(flow, run_id="r1")
        assert session.results[0].success is True
        runner_target = clicked["target"]
        assert isinstance(runner_target, Target)

        mcp_clicked: dict[str, object] = {}
        monkeypatch.setattr(
            "openframe.integrations.mcp.adapter._resolve_frame", lambda _path: frame
        )
        monkeypatch.setattr(
            "openframe.integrations.mcp.adapter._build_locator", lambda: FakeLocator()
        )
        monkeypatch.setattr(
            "openframe.integrations.mcp.adapter.Actuator", _spy_actuator(mcp_clicked)
        )
        monkeypatch.setattr(
            "openframe.integrations.mcp.adapter.write_step_artifacts",
            lambda **_kwargs: Path("runs/r1/mcp-click"),
        )
        result = call_mcp_tool(
            "click",
            {
                "query": "Create",
                "selector": selector,
                "dry_run": True,
                "run_id": "r1",
            },
        )
        assert result["ok"] is True
        mcp_target = mcp_clicked["target"]
        assert isinstance(mcp_target, Target)

        assert mcp_clicked["scale_factor"] == scale_factor
        assert _identity(runner_target) == _identity(shared)
        assert _identity(mcp_target) == _identity(shared)


def test_retina_top_most_prefers_scaled_physical_over_raw_logical_y() -> None:
    """Regression: raw-pixel MCP selection used to prefer a11y y=400 over OCR y=600."""
    targets = [
        Target(
            x=20,
            y=600,
            width=100,
            height=40,
            confidence=0.9,
            source="ocr:tesseract",
            coordinate_space="physical",
            text="Create",
            label="ocr",
        ),
        Target(
            x=20,
            y=400,
            width=100,
            height=40,
            confidence=0.8,
            source="a11y:macos",
            coordinate_space="logical",
            text="Create",
            label="a11y",
        ),
    ]
    selected = select_target(targets=targets, selector="top_most", scale_factor=2.0)
    assert selected.label == "ocr"
