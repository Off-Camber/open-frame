from __future__ import annotations

from pathlib import Path

import pytest

from openframe.flow import Flow, load_flow


def test_flow_from_dict_builds_steps() -> None:
    payload = {
        "name": "demo",
        "variables": {"subject": "hello"},
        "steps": [
            {"id": "s1", "kind": "wait", "ms": 10},
            {"kind": "capture", "out": "frame.png"},
        ],
    }

    flow = Flow.from_dict(payload)

    assert flow.name == "demo"
    assert flow.variables["subject"] == "hello"
    assert flow.steps[0].id == "s1"
    assert flow.steps[1].id == "step-2"
    assert flow.steps[1].params["out"] == "frame.png"


def test_load_flow_requires_existing_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        load_flow(tmp_path / "missing.yaml")
