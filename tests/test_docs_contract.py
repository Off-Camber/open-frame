"""Docs stay aligned with the MCP tool list."""

from __future__ import annotations

from pathlib import Path

from openframe.integrations.mcp.adapter import MCP_TOOLS

ROOT = Path(__file__).resolve().parents[1]


def test_every_mcp_tool_is_named_in_the_docs() -> None:
    api = (ROOT / "docs" / "API.md").read_text(encoding="utf-8")
    server = (ROOT / "docs" / "MCP_SERVER.md").read_text(encoding="utf-8")
    missing = [
        tool["name"]
        for tool in MCP_TOOLS
        if f"`{tool['name']}`" not in api or f"`{tool['name']}`" not in server
    ]
    assert missing == []
