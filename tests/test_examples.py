from __future__ import annotations

from pathlib import Path


def test_outlook_smoke_flow_file_has_expected_steps() -> None:
    flow_path = (
        Path(__file__).resolve().parent.parent / "examples" / "flows" / "outlook-new-email" / "flow.yaml"
    )
    text = flow_path.read_text(encoding="utf-8")

    assert "name: outlook-new-email-smoke" in text
    assert "kind: app" in text
    assert "kind: key" in text
    assert "combo:" in text
    assert "- command" in text
    assert "- n" in text
    assert "kind: verify" in text
    assert "timeout_ms: 2500" in text
    assert "poll_ms: 250" in text
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
    assert "kind: navigate" in text
    assert "verify-compose-surface" in text
    assert "combo:" in text
    assert "- command" in text
    assert "- n" in text
    assert "verify-browser-surface" in text
    assert "return-outlook" in text


def test_full_mvp_flow_file_has_end_to_end_steps() -> None:
    flow_path = (
        Path(__file__).resolve().parent.parent / "examples" / "flows" / "outlook-m365-email" / "flow.yaml"
    )
    text = flow_path.read_text(encoding="utf-8")

    assert "name: outlook-m365-email" in text
    assert "open-word-online" in text
    assert "verify-compose-open" in text
    assert "click_point" in text
    assert text.count("selector: top_most") >= 3
    assert "open-blank-document" in text
    assert "type-recipient" in text
    assert "advance-to-subject" in text
    assert "attach-summary" in text
    assert "send-email" in text
    assert "open-sent-items" in text
    assert "verify-sent" in text
    assert "match_bounds:" in text
    assert 'sent_items_label: "Sent"' in text
    assert 'text-appeared:"Open Frame MVP run"' in text


def test_calibration_flow_has_unique_token_outcome_verify() -> None:
    flow_path = (
        Path(__file__).resolve().parent.parent / "examples" / "flows" / "calibration-token" / "flow.yaml"
    )
    text = flow_path.read_text(encoding="utf-8")

    assert "name: calibration-token" in text
    assert 'marker: "OFMARKZXQ"' in text
    assert 'token: "{{marker}} {{run_id}}"' in text
    assert 'name: "TextEdit"' in text
    assert "new-document" in text
    assert "- command" in text
    assert "- n" in text
    assert "type-token" in text
    assert "verify-token-visible" in text
    assert 'text-appeared:"{{marker}}"' in text


def test_word_create_only_flow_has_document_outcome_check() -> None:
    flow_path = Path(__file__).resolve().parent.parent / "examples" / "flows" / "word-create-only" / "flow.yaml"
    text = flow_path.read_text(encoding="utf-8")

    assert "name: word-create-only" in text
    assert 'doc_marker: "OFDOCZXQ"' in text
    assert "open-blank-document" in text
    assert "selector: top_most" in text
    assert "verify-document-surface" in text
    assert "focus-document-body" in text
    assert "click_point" in text
    assert "type-doc-title" in text
    assert "verify-doc-marker" in text
    assert 'text-appeared:"{{doc_marker}}"' in text


def test_outlook_send_only_flow_has_sent_outcome_check() -> None:
    flow_path = Path(__file__).resolve().parent.parent / "examples" / "flows" / "outlook-send-only" / "flow.yaml"
    text = flow_path.read_text(encoding="utf-8")

    assert "name: outlook-send-only" in text
    assert 'subject_marker: "OFSENDZXQ"' in text
    assert "verify-compose-open" in text
    assert "type-recipient" in text
    assert "advance-to-subject" in text
    assert "type-subject" in text
    assert text.count("selector: top_most") >= 2
    assert "match_bounds:" in text
    assert "left_of_query: \"From\"" in text
    assert "send-email" in text
    assert "open-sent-items" in text
    assert "verify-sent" in text
    assert 'text-appeared:"{{subject_marker}}"' in text


def test_doc_attach_email_flow_shares_one_artifact() -> None:
    flow_path = Path(__file__).resolve().parent.parent / "examples" / "flows" / "doc-attach-email" / "flow.yaml"
    text = flow_path.read_text(encoding="utf-8")

    assert "name: doc-attach-email" in text
    # The document is produced deterministically and the SAME path is attached.
    assert "kind: write_file" in text
    assert "attachment_path:" in text
    assert text.count("{{attachment_path}}") >= 2
    assert "open-attach" in text
    assert "type-attachment-path" in text
    assert "verify-attached" in text
    assert "verify-sent" in text
    assert "match_bounds:" in text
    assert 'text-appeared:"{{subject_marker}}"' in text


def test_mcp_pilot_example_references_compact_envelope() -> None:
    base = Path(__file__).resolve().parent.parent / "examples" / "mcp-pilot"
    readme_text = (base / "README.md").read_text(encoding="utf-8")
    pilot_text = (base / "pilot.py").read_text(encoding="utf-8")

    assert "open-frame mcp list-tools --json" in readme_text
    assert "open-frame mcp call run_flow" in readme_text
    assert "REQUIRED_KEYS" in pilot_text
    assert '"tool"' in pilot_text
    assert '"artifacts"' in pilot_text
