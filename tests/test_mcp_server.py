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

from openframe.integrations.mcp.adapter import MCP_CONTRACT_VERSION
from openframe.integrations.mcp.server import create_mcp_server

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


def test_stdio_server_click_dry_run_returns_adapter_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
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

    with pytest.raises(RuntimeError, match=r"pip install -e '\.\[mcp\]'"):
        server_mod._require_fastmcp()


def test_cli_mcp_serve_is_registered() -> None:
    from openframe.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["mcp", "serve"])
    assert args.command == "mcp"
    assert args.mcp_command == "serve"
