"""Tests for the MCP stdio server shim."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

pytest.importorskip("mcp")

from mcp.shared.memory import (
    create_connected_server_and_client_session as connect_session,
)

from openframe import __version__
from openframe.integrations.mcp.adapter import MCP_CONTRACT_VERSION, MCP_TOOLS
from openframe.integrations.mcp.server import create_mcp_server

SAFETY_RULES = (
    (
        "Search a window capture. Pass that capture's image_path as frame_path "
        "to find and click. A full-screen find also matches the chat that asked "
        "for the text."
    ),
    (
        "dry_run defaults to true on click, type, key, scroll, and run_flow. "
        "Pass dry_run=false to send input."
    ),
    "When click returns ambiguous_target, stop. Do not guess with a selector.",
)

EXPECTED_TOOLS = {
    "capture",
    "find",
    "click",
    "type",
    "key",
    "scroll",
    "run_flow",
    "get_run_artifacts",
}


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def _schema_enums(schema: dict[str, Any]) -> set[str]:
    values: set[str] = set(schema.get("enum", []))
    for option in schema.get("anyOf", []):
        values.update(option.get("enum", []))
    return values


def test_create_mcp_server_lists_tools_with_schemas() -> None:
    server = create_mcp_server()

    async def _check() -> None:
        async with connect_session(server) as session:
            listed = await session.list_tools()
            names = {item.name for item in listed.tools}
            assert names == EXPECTED_TOOLS
            by_name = {item.name: item for item in listed.tools}

            click_schema = by_name["click"].inputSchema
            assert click_schema["type"] == "object"
            assert "query" in click_schema["required"]
            props = click_schema["properties"]
            assert props["query"]["type"] == "string"
            assert props["dry_run"]["type"] == "boolean"
            for name in ("click", "type", "key", "scroll", "run_flow"):
                dry_run = by_name[name].inputSchema["properties"]["dry_run"]
                assert dry_run.get("default") is True
            assert {"first", "top_most", "highest_confidence"}.issubset(
                _schema_enums(props["selector"])
            )
            assert {"screen", "window", "region"}.issubset(
                _schema_enums(by_name["capture"].inputSchema["properties"]["mode"])
            )
            scroll_schema = by_name["scroll"].inputSchema
            assert "clicks" in scroll_schema["required"]
            assert scroll_schema["properties"]["clicks"]["type"] == "integer"
            assert MCP_CONTRACT_VERSION in (server.instructions or "")

    _run(_check())


def test_listed_tools_include_the_safety_rules() -> None:
    server = create_mcp_server()
    catalog = {str(tool["name"]): str(tool["description"]) for tool in MCP_TOOLS}

    async def _check() -> None:
        async with connect_session(server) as session:
            listed = await session.list_tools()
            by_name = {item.name: item.description or "" for item in listed.tools}
            received = "\n".join([server.instructions or "", *by_name.values()])
            for rule in SAFETY_RULES:
                assert rule in received
            assert by_name.keys() == catalog.keys()
            for name, description in catalog.items():
                assert by_name[name] == description
            for name in ("find", "click"):
                assert "image_path as frame_path" in by_name[name]
                assert "chat that asked for the text" in by_name[name]
            assert "clicked_label" in by_name["click"]
            assert "ambiguous_target, stop" in by_name["click"]
            assert "Do not guess with a selector" in by_name["click"]
            for name in ("click", "type", "key", "scroll", "run_flow"):
                assert "dry_run defaults to true" in by_name[name]
                assert "dry_run=false" in by_name[name]

    _run(_check())


def test_mcp_handshake_reports_package_version() -> None:
    server = create_mcp_server()
    options = server._mcp_server.create_initialization_options()
    assert options.server_version == __version__
    assert __version__ != "unknown"


def test_stdio_server_click_dry_run_returns_adapter_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = {
        "ok": True,
        "tool": "click",
        "run_id": "r1",
        "data": {"query": "Submit", "dry_run": True},
        "error": None,
        "artifacts": {"step_dir": "runs/r1/mcp-click"},
    }

    def fake_call(tool: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        assert tool == "click"
        assert args is not None
        assert args["query"] == "Submit"
        assert args["dry_run"] is True
        return expected

    monkeypatch.setattr("openframe.integrations.mcp.server.call_mcp_tool", fake_call)
    server = create_mcp_server()

    async def _check() -> None:
        async with connect_session(server) as session:
            result = await session.call_tool(
                "click",
                {"query": "Submit", "dry_run": True},
            )
            assert result.isError is False
            assert result.structuredContent == expected
            text = result.content[0].text
            assert json.loads(text) == expected

    _run(_check())


def test_stdio_server_passes_through_in_band_error(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = {
        "ok": False,
        "tool": "click",
        "run_id": "r2",
        "data": {"query": "Nope", "match_count": 0},
        "error": {"code": "not_found", "message": "No target found for 'Nope'."},
        "artifacts": {},
    }

    monkeypatch.setattr(
        "openframe.integrations.mcp.server.call_mcp_tool",
        lambda tool, args=None: expected,
    )
    server = create_mcp_server()

    async def _check() -> None:
        async with connect_session(server) as session:
            result = await session.call_tool("click", {"query": "Nope"})
            assert result.isError is False
            assert result.structuredContent == expected
            assert result.structuredContent["error"]["code"] == "not_found"

    _run(_check())


def test_require_fastmcp_missing_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        if name == "mcp.server.fastmcp" or name.startswith("mcp."):
            raise ImportError("No module named mcp")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    from openframe.integrations.mcp import server as server_mod

    with pytest.raises(RuntimeError, match=r'pip install "off-camber-open-frame\[mcp\]"'):
        server_mod._require_fastmcp()


def test_cli_mcp_serve_is_registered() -> None:
    from openframe.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["mcp", "serve"])
    assert args.command == "mcp"
    assert args.mcp_command == "serve"
