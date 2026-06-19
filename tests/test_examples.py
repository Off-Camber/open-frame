from __future__ import annotations

from pathlib import Path


def test_outlook_smoke_flow_file_has_expected_steps() -> None:
    flow_path = (
        Path(__file__).resolve().parent.parent / "examples" / "flows" / "outlook-new-email" / "flow.yaml"
    )
    text = flow_path.read_text(encoding="utf-8")

    assert "name: outlook-new-email-smoke" in text
    assert "kind: app" in text
    assert "kind: click" in text
    assert "kind: verify" in text
    assert "text-appeared:\"To\"" in text


def test_handoff_flow_file_has_cross_app_steps() -> None:
    flow_path = (
        Path(__file__).resolve().parent.parent
        / "examples"
        / "flows"
        / "outlook-browser-outlook"
        / "flow.yaml"
    )
    text = flow_path.read_text(encoding="utf-8")

    assert "name: outlook-browser-outlook-handoff" in text
    assert 'name: "Microsoft Outlook"' in text
    assert 'name: "{{browser_app}}"' in text
    assert "kind: navigate" in text
    assert "verify-browser-surface" in text
    assert "return-outlook" in text


def test_full_mvp_flow_file_has_end_to_end_steps() -> None:
    flow_path = (
        Path(__file__).resolve().parent.parent / "examples" / "flows" / "outlook-m365-email" / "flow.yaml"
    )
    text = flow_path.read_text(encoding="utf-8")

    assert "name: outlook-m365-email" in text
    assert "open-word-online" in text
    assert "fill-recipient" in text
    assert "attach-summary" in text
    assert "send-email" in text
    assert "verify-sent" in text


def test_mcp_pilot_example_references_compact_envelope() -> None:
    base = Path(__file__).resolve().parent.parent / "examples" / "mcp-pilot"
    readme_text = (base / "README.md").read_text(encoding="utf-8")
    pilot_text = (base / "pilot.py").read_text(encoding="utf-8")

    assert "open-frame mcp list-tools --json" in readme_text
    assert "open-frame mcp call run_flow" in readme_text
    assert "REQUIRED_KEYS" in pilot_text
    assert '"tool"' in pilot_text
    assert '"artifacts"' in pilot_text
