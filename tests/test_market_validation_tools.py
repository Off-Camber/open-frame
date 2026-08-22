"""Unit tests for the market-validation harness (CI-safe + optional live)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "market-validation"
if str(EXAMPLES) not in sys.path:
    sys.path.insert(0, str(EXAMPLES))

import browser_use_openframe_tools as of_tools
import run_scenario as harness

LIVE_MACOS = sys.platform == "darwin" and os.environ.get("CI") != "true"


def test_call_openframe_delegates_to_mcp(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_call(tool: str, args: dict[str, object] | None = None) -> dict[str, object]:
        captured["tool"] = tool
        captured["args"] = args
        return {"ok": True, "tool": tool, "data": {"count": 1}, "error": None}

    monkeypatch.setattr(of_tools, "call_mcp_tool", fake_call)
    envelope = of_tools.call_openframe("find", {"query": "Notes"})
    assert envelope["ok"] is True
    assert captured["tool"] == "find"
    assert captured["args"] == {"query": "Notes"}


def test_score_envelope_ok_and_count() -> None:
    scenario = {
        "pass_checks": [
            {"type": "envelope_ok", "tool": "desktop_find"},
            {"type": "count_gte", "tool": "desktop_find", "value": 1},
        ]
    }
    envelopes = [
        {
            "step_tool": "desktop_find",
            "mcp_tool": "find",
            "envelope": {"ok": True, "data": {"count": 2, "targets": []}, "error": None},
        }
    ]
    status, notes = harness._score(scenario, envelopes=envelopes, agent_final=None)
    assert status == "pass"
    assert notes == "all checks passed"


def test_score_envelope_ok_fails_when_missing() -> None:
    scenario = {"pass_checks": [{"type": "envelope_ok", "tool": "desktop_find"}]}
    status, notes = harness._score(scenario, envelopes=[], agent_final=None)
    assert status == "fail"
    assert "envelope_ok failed" in notes


def test_score_error_code_and_openframe_unused() -> None:
    fail_closed = {
        "pass_checks": [
            {"type": "envelope_error_code", "tool": "desktop_click_dry_run", "code": "not_found"}
        ]
    }
    envelopes = [
        {
            "step_tool": "desktop_click_dry_run",
            "mcp_tool": "click",
            "envelope": {"ok": False, "error": {"code": "not_found"}, "data": None},
        }
    ]
    status, _ = harness._score(fail_closed, envelopes=envelopes, agent_final=None)
    assert status == "pass"

    unused = {"pass_checks": [{"type": "openframe_unused"}]}
    status, notes = harness._score(unused, envelopes=envelopes, agent_final="ok")
    assert status == "fail"
    assert "openframe_unused" in notes

    status, _ = harness._score(unused, envelopes=[], agent_final="Example Domain")
    assert status == "pass"


def test_score_agent_final_regex_and_target_source() -> None:
    scenario = {
        "pass_checks": [
            {"type": "agent_final_regex", "pattern": "Example Domain"},
            {"type": "target_source_contains", "tool": "find", "value": "template:ncc"},
        ]
    }
    envelopes = [
        {
            "step_tool": "desktop_find",
            "mcp_tool": "find",
            "envelope": {
                "ok": True,
                "data": {"count": 1, "targets": [{"source": "template:ncc"}]},
            },
        }
    ]
    status, _ = harness._score(scenario, envelopes=envelopes, agent_final="Heading: Example Domain")
    assert status == "pass"
    status, notes = harness._score(scenario, envelopes=envelopes, agent_final="nope")
    assert status == "fail"
    assert "agent_final_regex" in notes


def test_score_details_truthy_walks_steps() -> None:
    scenario = {"pass_checks": [{"type": "details_truthy", "tool": "run_flow", "key": "found"}]}
    envelopes = [
        {
            "step_tool": "desktop_run_flow",
            "mcp_tool": "run_flow",
            "envelope": {
                "ok": True,
                "data": {"steps": [{"details": {"found": True}}]},
            },
        }
    ]
    status, _ = harness._score(scenario, envelopes=envelopes, agent_final=None)
    assert status == "pass"


def test_apply_vars_replaces_placeholders() -> None:
    payload = {"prompt": "Open {{handoff_html}} then find {{query}}", "n": 1}
    out = harness._apply_vars(payload, {"handoff_html": "http://127.0.0.1/x", "query": "Notes"})
    assert out["prompt"] == "Open http://127.0.0.1/x then find Notes"
    assert out["n"] == 1


def test_resolve_browser_executable_honors_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    binary = tmp_path / "chrome"
    binary.write_text("", encoding="utf-8")
    monkeypatch.setenv("OPENFRAME_BROWSER_EXECUTABLE", str(binary))
    assert harness._resolve_browser_executable() == str(binary)


def test_load_scenario_yaml() -> None:
    scenario = harness._load_scenario(EXAMPLES / "scenarios" / "s6.yaml")
    assert scenario["id"] == "s6"
    assert scenario["mode"] == "openframe-only"


@pytest.mark.skipif(not LIVE_MACOS, reason="live macOS Screen Recording required")
def test_live_find_template_fixture() -> None:
    envelope = of_tools.call_openframe(
        "find",
        {
            "query": "icon",
            "strategy": "first",
            "frame_path": str(ROOT / "examples/flows/template-icon-probe/scene.png"),
            "template": str(ROOT / "examples/flows/template-icon-probe/icon-template.png"),
        },
    )
    assert envelope["ok"] is True
    assert envelope["data"]["count"] >= 1
    assert any("template:ncc" in str(t.get("source")) for t in envelope["data"]["targets"])


@pytest.mark.skipif(not LIVE_MACOS, reason="live macOS Screen Recording required")
def test_live_click_missing_is_not_found() -> None:
    envelope = of_tools.call_openframe(
        "click",
        {"query": "OF_MARKET_VALIDATION_MISSING_TARGET_ZZZ", "dry_run": True, "expect_one": True},
    )
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "not_found"
