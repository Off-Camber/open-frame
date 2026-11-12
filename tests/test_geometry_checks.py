from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "calibration_geometry_checks",
    Path(__file__).parents[1] / "scripts" / "calibration_geometry_checks.py",
)
assert _SPEC is not None and _SPEC.loader is not None
checks = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(checks)


def test_flow_step_error_keeps_the_full_message() -> None:
    message = "Step 'click-token' could not find target for query 'CALMARK89'."
    payload = {
        "success": False,
        "steps": [
            {"step_id": "focus-textedit", "success": True, "error": None},
            {"step_id": "click-token", "success": False, "error": message},
        ],
    }

    assert checks.flow_step_error(json.dumps(payload)) == message


def test_flow_step_error_is_empty_when_stdout_is_not_json() -> None:
    assert checks.flow_step_error("usage: open-frame") == ""


def test_click_hits_marker_accepts_a_caret_inside_the_token() -> None:
    hit = {"selected": "\n", "value": "CALMARK89", "location": 4, "length": 0}
    assert checks.click_hits_marker(hit)


def test_click_hits_marker_rejects_a_caret_past_the_token() -> None:
    hit = {"selected": "\n", "value": "CALMARK89 more", "location": 12, "length": 0}
    assert not checks.click_hits_marker(hit)


def test_selection_is_marker_requires_the_whole_token() -> None:
    assert checks.selection_is_marker("CALMARK89\n")
    assert checks.selection_is_marker("  CALMARK89  ")
    assert not checks.selection_is_marker("CALMARK839")
    assert not checks.selection_is_marker("CALMARK89 extra")
    assert not checks.selection_is_marker("")
