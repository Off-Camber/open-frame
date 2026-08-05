"""MCP stdio server wrapping the Open Frame tool adapter.

The server is a thin protocol shim: every tool delegates to
``call_mcp_tool()`` and returns the existing envelope unchanged.
Requires the optional ``mcp`` extra (``pip install -e '.[mcp]'``).
"""

from __future__ import annotations

from typing import Any, Literal

from openframe.integrations.mcp.adapter import MCP_CONTRACT_VERSION, call_mcp_tool

CaptureMode = Literal["screen", "window", "region"]
FindStrategy = Literal["first", "all"]
ClickAnchor = Literal["center", "top-left", "top-right", "bottom-left", "bottom-right"]
ClickKind = Literal["click", "double", "right"]
TargetSelector = Literal["first", "top_most", "left_most", "right_most", "highest_confidence"]


def _require_fastmcp():  # type: ignore[no-untyped-def]
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - exercised via monkeypatch / missing extra
        raise RuntimeError(
            "MCP server requires the mcp extra. Install with: pip install -e '.[mcp]'"
        ) from exc
    return FastMCP


def _tool_args(**kwargs: Any) -> dict[str, Any]:
    """Drop Nones so optional MCP fields stay optional for the adapter."""
    return {key: value for key, value in kwargs.items() if value is not None}


def create_mcp_server():  # type: ignore[no-untyped-def]
    """Build a FastMCP server with the seven Open Frame tools registered."""
    FastMCP = _require_fastmcp()
    server = FastMCP(
        name="open-frame",
        instructions=(
            "Open Frame desktop recognition and action engine. "
            f"Contract {MCP_CONTRACT_VERSION}. "
            "Every tool result is an Open Frame envelope with keys "
            "ok, tool, run_id, data, error, and artifacts. "
            "Failures are in-band (ok=false + error.code), not protocol errors. "
            "Prefer dry_run=true when unsure before actuating."
        ),
    )

    @server.tool(
        name="capture",
        description="Capture screen, window, or region into a frame (envelope response).",
    )
    def capture(
        mode: CaptureMode = "screen",
        window_title: str | None = None,
        window_id: int | None = None,
        x: int | None = None,
        y: int | None = None,
        width: int | None = None,
        height: int | None = None,
        out_path: str | None = None,
    ) -> dict[str, Any]:
        return call_mcp_tool(
            "capture",
            _tool_args(
                mode=mode,
                window_title=window_title,
                window_id=window_id,
                x=x,
                y=y,
                width=width,
                height=height,
                out_path=out_path,
            ),
        )

    @server.tool(
        name="find",
        description="Find targets by query using a11y + OCR (envelope response).",
    )
    def find(
        query: str,
        strategy: FindStrategy = "first",
        frame_path: str | None = None,
    ) -> dict[str, Any]:
        return call_mcp_tool(
            "find",
            _tool_args(query=query, strategy=strategy, frame_path=frame_path),
        )

    @server.tool(
        name="click",
        description="Find and click a target by query (envelope response; supports dry_run).",
    )
    def click(
        query: str,
        anchor: ClickAnchor = "center",
        kind: ClickKind = "click",
        dry_run: bool = False,
        run_id: str | None = None,
        frame_path: str | None = None,
        expect_one: bool = False,
        selector: TargetSelector | None = None,
    ) -> dict[str, Any]:
        return call_mcp_tool(
            "click",
            _tool_args(
                query=query,
                anchor=anchor,
                kind=kind,
                dry_run=dry_run,
                run_id=run_id,
                frame_path=frame_path,
                expect_one=expect_one,
                selector=selector,
            ),
        )

    @server.tool(
        name="type",
        description="Type text at the current keyboard focus (envelope response).",
    )
    def type_text(
        text: str = "",
        interval: float = 0.0,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        return call_mcp_tool(
            "type",
            {"text": text, "interval": interval, "dry_run": dry_run},
        )

    @server.tool(
        name="key",
        description="Press a key or key combo (provide key or combo; envelope response).",
    )
    def key(
        key: str | None = None,
        combo: list[str] | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        return call_mcp_tool(
            "key",
            _tool_args(key=key, combo=combo, dry_run=dry_run),
        )

    @server.tool(
        name="run_flow",
        description="Run a YAML flow file (envelope response; supports dry_run).",
    )
    def run_flow(
        flow_path: str,
        dry_run: bool = False,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        return call_mcp_tool(
            "run_flow",
            _tool_args(flow_path=flow_path, dry_run=dry_run, run_id=run_id),
        )

    @server.tool(
        name="get_run_artifacts",
        description="List artifact files for a prior run id (envelope response).",
    )
    def get_run_artifacts(run_id: str) -> dict[str, Any]:
        return call_mcp_tool("get_run_artifacts", {"run_id": run_id})

    return server


def run_stdio_server() -> None:
    """Start the Open Frame MCP server on stdio (blocking)."""
    create_mcp_server().run(transport="stdio")
