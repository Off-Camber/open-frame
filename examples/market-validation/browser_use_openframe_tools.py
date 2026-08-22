"""browser-use custom tools wrapping Open Frame MCP envelopes.

Register these on a ``browser_use.Tools()`` instance so an established agent can
drive native desktop UI through Open Frame while keeping browser DOM tools for
web work.

``browser_use`` is imported lazily so Open Frame unit tests can exercise the
MCP wrappers without pulling in browser-use's display/browser session startup.
"""

from __future__ import annotations

import json
from typing import Any

from openframe.integrations.mcp.adapter import call_mcp_tool


def call_openframe(tool: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    """Call one Open Frame MCP tool and return the raw envelope."""
    return call_mcp_tool(tool, args or {})


def _envelope_to_action_result(envelope: dict[str, Any]) -> Any:
    """Map an Open Frame MCP envelope into a browser-use ActionResult."""
    try:
        from browser_use import ActionResult
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "browser-use is required for ActionResult mapping. "
            "Install with: pip install 'browser-use>=0.13'"
        ) from exc

    text = json.dumps(envelope, indent=2, default=str)
    if envelope.get("ok"):
        return ActionResult(
            extracted_content=text,
            long_term_memory=f"openframe:{envelope.get('tool')} ok",
            metadata={"openframe": envelope},
        )
    error = envelope.get("error") or {}
    code = error.get("code", "error")
    message = error.get("message", "Open Frame tool failed")
    return ActionResult(
        error=f"{code}: {message}",
        extracted_content=text,
        long_term_memory=f"openframe:{envelope.get('tool')} {code}",
        metadata={"openframe": envelope},
    )


def register_openframe_tools(tools: Any | None = None) -> Any:
    """Register desktop_* actions on a Tools registry (creates one if needed)."""
    try:
        from browser_use import Tools
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "browser-use is required for the market-validation harness. "
            "Install with: pip install 'browser-use>=0.13'"
        ) from exc

    registry = tools or Tools()

    @registry.action(
        "Capture the macOS screen (or a window) via Open Frame. "
        "Use before desktop_find when you need a fresh frame. "
        "Returns an Open Frame envelope JSON."
    )
    async def desktop_capture(
        mode: str = "screen",
        window_title: str | None = None,
        window_id: int | None = None,
    ) -> Any:
        args: dict[str, Any] = {"mode": mode}
        if window_title:
            args["window_title"] = window_title
        if window_id is not None:
            args["window_id"] = window_id
        return _envelope_to_action_result(call_openframe("capture", args))

    @registry.action(
        "Find a UI target on the desktop via Open Frame (a11y + OCR + optional template). "
        "Pass template as a filesystem path to a PNG crop for icon matching. "
        "Does not click. Returns an Open Frame envelope JSON."
    )
    async def desktop_find(
        query: str,
        strategy: str = "first",
        frame_path: str | None = None,
        template: str | None = None,
        template_threshold: float | None = None,
    ) -> Any:
        args: dict[str, Any] = {"query": query, "strategy": strategy}
        if frame_path:
            args["frame_path"] = frame_path
        if template:
            args["template"] = template
        if template_threshold is not None:
            args["template_threshold"] = template_threshold
        return _envelope_to_action_result(call_openframe("find", args))

    @registry.action(
        "Find and dry-run click a desktop target via Open Frame (never actuates). "
        "Use for safe validation. Returns an Open Frame envelope JSON."
    )
    async def desktop_click_dry_run(
        query: str,
        selector: str | None = None,
        expect_one: bool = False,
        frame_path: str | None = None,
        template: str | None = None,
    ) -> Any:
        args: dict[str, Any] = {"query": query, "dry_run": True, "expect_one": expect_one}
        if selector:
            args["selector"] = selector
        if frame_path:
            args["frame_path"] = frame_path
        if template:
            args["template"] = template
        return _envelope_to_action_result(call_openframe("click", args))

    @registry.action(
        "Scroll the mouse wheel via Open Frame. Positive clicks scroll up; "
        "negative scroll down. Returns an Open Frame envelope JSON."
    )
    async def desktop_scroll(
        clicks: int,
        x: int | None = None,
        y: int | None = None,
        dry_run: bool = False,
    ) -> Any:
        args: dict[str, Any] = {"clicks": clicks, "dry_run": dry_run}
        if x is not None:
            args["x"] = x
        if y is not None:
            args["y"] = y
        return _envelope_to_action_result(call_openframe("scroll", args))

    @registry.action(
        "Run an Open Frame YAML flow. Prefer dry_run=true for market-validation. "
        "Step details are summarized by default. Returns an Open Frame envelope JSON."
    )
    async def desktop_run_flow(
        flow_path: str,
        dry_run: bool = True,
        run_id: str | None = None,
        include_step_details: bool = False,
    ) -> Any:
        args: dict[str, Any] = {
            "flow_path": flow_path,
            "dry_run": dry_run,
            "include_step_details": include_step_details,
        }
        if run_id:
            args["run_id"] = run_id
        return _envelope_to_action_result(call_openframe("run_flow", args))

    return registry


__all__ = [
    "_envelope_to_action_result",
    "call_openframe",
    "register_openframe_tools",
]
