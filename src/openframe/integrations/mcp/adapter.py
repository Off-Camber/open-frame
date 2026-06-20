"""MCP-oriented tool adapter for Open Frame."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openframe.act import ActError, Actuator
from openframe.capture import CaptureError, region, screen, window
from openframe.flow import load_flow
from openframe.recognize import Locator, MacOSA11yRecognizer, TesseractRecognizer
from openframe.runner import FlowRunner
from openframe.types import Frame
from openframe.verify import write_step_artifacts

MCP_CONTRACT_VERSION = "v0.2.0-checkpoint-1"

MCP_TOOLS: tuple[dict[str, Any], ...] = (
    {
        "name": "capture",
        "description": "Capture screen/window/region into a frame",
        "required_args": [],
        "optional_args": ["mode", "window_title", "window_id", "x", "y", "width", "height", "out_path"],
        "error_codes": ["validation_error", "capture_error", "runtime_error", "internal_error"],
    },
    {
        "name": "find",
        "description": "Find targets by query on a frame",
        "required_args": ["query"],
        "optional_args": ["strategy", "frame_path"],
        "error_codes": ["validation_error", "capture_error", "runtime_error", "internal_error"],
    },
    {
        "name": "click",
        "description": "Find and click a target by query",
        "required_args": ["query"],
        "optional_args": ["anchor", "kind", "dry_run", "run_id", "frame_path", "expect_one", "selector"],
        "error_codes": [
            "not_found",
            "ambiguous_target",
            "validation_error",
            "capture_error",
            "action_error",
            "runtime_error",
            "internal_error",
        ],
    },
    {
        "name": "type",
        "description": "Type text at current focus",
        "required_args": [],
        "optional_args": ["text", "interval", "dry_run"],
        "error_codes": ["action_error", "validation_error", "runtime_error", "internal_error"],
    },
    {
        "name": "key",
        "description": "Press a key or key combo",
        "required_args": [],
        "optional_args": ["key", "combo", "dry_run"],
        "error_codes": ["validation_error", "action_error", "runtime_error", "internal_error"],
    },
    {
        "name": "run_flow",
        "description": "Run a YAML flow file",
        "required_args": ["flow_path"],
        "optional_args": ["dry_run", "run_id"],
        "error_codes": ["flow_failed", "validation_error", "capture_error", "action_error", "runtime_error", "internal_error"],
    },
    {
        "name": "get_run_artifacts",
        "description": "List run artifact files for a run id",
        "required_args": ["run_id"],
        "optional_args": [],
        "error_codes": ["not_found", "validation_error", "runtime_error", "internal_error"],
    },
)


class MCPToolError(RuntimeError):
    """Structured error for MCP tool responses."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        data: dict[str, Any] | None = None,
        artifacts: dict[str, Any] | None = None,
        run_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data or {}
        self.artifacts = artifacts or {}
        self.run_id = run_id


def list_mcp_tools() -> list[dict[str, Any]]:
    """Return available MCP tool metadata."""
    return [{**item, "contract_version": MCP_CONTRACT_VERSION} for item in MCP_TOOLS]


def call_mcp_tool(tool: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    """Call one deterministic tool and return a stable response envelope."""
    payload = args or {}
    dispatch = {
        "capture": _tool_capture,
        "find": _tool_find,
        "click": _tool_click,
        "type": _tool_type,
        "key": _tool_key,
        "run_flow": _tool_run_flow,
        "get_run_artifacts": _tool_get_run_artifacts,
    }

    handler = dispatch.get(tool)
    if handler is None:
        return _response_error(tool=tool, code="unknown_tool", message=f"Unsupported tool: {tool}")

    try:
        data, run_id, artifacts = handler(payload)
        return _response_ok(tool=tool, data=data, run_id=run_id, artifacts=artifacts)
    except MCPToolError as error:
        return _response_error(
            tool=tool,
            code=error.code,
            message=error.message,
            data=error.data,
            run_id=error.run_id,
            artifacts=error.artifacts,
        )
    except CaptureError as error:
        return _response_error(tool=tool, code="capture_error", message=str(error))
    except ActError as error:
        return _response_error(tool=tool, code="action_error", message=str(error))
    except ValueError as error:
        return _response_error(tool=tool, code="validation_error", message=str(error))
    except RuntimeError as error:
        return _response_error(tool=tool, code="runtime_error", message=str(error))
    except Exception as error:  # noqa: BLE001
        return _response_error(tool=tool, code="internal_error", message=str(error))


def _tool_capture(args: dict[str, Any]) -> tuple[dict[str, Any], str | None, dict[str, Any]]:
    mode = str(args.get("mode", "screen")).strip().lower()
    out_path = args.get("out_path")

    if mode == "screen":
        frame = screen(out_path=out_path)
        return {"frame": _frame_to_dict(frame), "mode": mode}, None, {}

    if mode == "window":
        frame = window(
            title=_optional_string(args.get("window_title")),
            window_id=_optional_int(args.get("window_id")),
            out_path=out_path,
        )
        return {"frame": _frame_to_dict(frame), "mode": mode}, None, {}

    if mode == "region":
        frame = region(
            x=_required_int(args, "x"),
            y=_required_int(args, "y"),
            width=_required_int(args, "width"),
            height=_required_int(args, "height"),
            out_path=out_path,
        )
        return {"frame": _frame_to_dict(frame), "mode": mode}, None, {}

    raise ValueError(f"Unsupported capture mode: {mode}")


def _tool_find(args: dict[str, Any]) -> tuple[dict[str, Any], str | None, dict[str, Any]]:
    query = _required_string(args, "query")
    strategy = str(args.get("strategy", "first")).strip()
    if strategy not in {"first", "all"}:
        raise ValueError("find strategy must be 'first' or 'all'.")

    frame = _resolve_frame(_optional_string(args.get("frame_path")))
    locator = _build_locator()
    targets = locator.find(frame=frame, query=query, strategy=strategy)

    data: dict[str, Any] = {
        "query": query,
        "strategy": strategy,
        "source": frame.source,
        "count": len(targets),
        "targets": [asdict(item) for item in targets],
    }
    return data, None, {}


def _tool_click(args: dict[str, Any]) -> tuple[dict[str, Any], str | None, dict[str, Any]]:
    query = _required_string(args, "query")
    anchor = str(args.get("anchor", "center")).strip()
    click_kind = str(args.get("kind", "click")).strip()
    dry_run = _as_bool(args.get("dry_run", False))
    expect_one = _as_bool(args.get("expect_one", False))
    selector = str(args.get("selector", "first")).strip()
    run_id = _optional_string(args.get("run_id")) or _default_run_id()

    frame = _resolve_frame(_optional_string(args.get("frame_path")))
    locator = _build_locator()
    targets = locator.find(frame=frame, query=query, strategy="all")
    if not targets:
        raise MCPToolError(code="not_found", message=f'No target found for query "{query}".', run_id=run_id)
    if expect_one and len(targets) != 1:
        raise MCPToolError(
            code="ambiguous_target",
            message=f'Expected one target for query "{query}", found {len(targets)}.',
            run_id=run_id,
            data={"query": query, "match_count": len(targets)},
        )
    selected_target = _select_target(targets=targets, selector=selector)

    actuator = Actuator(dry_run=dry_run)
    point = actuator.click_target(
        selected_target, anchor=anchor, kind=click_kind, scale_factor=frame.scale_factor
    )
    after = frame if dry_run else screen()
    artifact_dir = write_step_artifacts(
        run_id=run_id,
        step_id="mcp-click",
        before=frame,
        after=after,
        verification=None,
    )

    data = {
        "query": query,
        "anchor": anchor,
        "kind": click_kind,
        "dry_run": dry_run,
        "expect_one": expect_one,
        "selector": selector,
        "point": {"x": point[0], "y": point[1]},
        "target": asdict(selected_target),
    }
    artifacts = {"step_dir": str(artifact_dir)}
    return data, run_id, artifacts


def _tool_type(args: dict[str, Any]) -> tuple[dict[str, Any], str | None, dict[str, Any]]:
    text = str(args.get("text", ""))
    interval = float(args.get("interval", 0.0))
    dry_run = _as_bool(args.get("dry_run", False))
    actuator = Actuator(dry_run=dry_run)
    actuator.type_text(text, interval=interval)
    return {"text_length": len(text), "interval": interval, "dry_run": dry_run}, None, {}


def _tool_key(args: dict[str, Any]) -> tuple[dict[str, Any], str | None, dict[str, Any]]:
    dry_run = _as_bool(args.get("dry_run", False))
    actuator = Actuator(dry_run=dry_run)
    combo = args.get("combo")
    if combo is not None:
        if not isinstance(combo, list) or not combo:
            raise ValueError("combo must be a non-empty list of keys.")
        keys = [str(item).strip() for item in combo if str(item).strip()]
        if not keys:
            raise ValueError("combo resolved to no usable keys.")
        actuator.key_combo(*keys)
        return {"combo": keys, "dry_run": dry_run}, None, {}

    key = _required_string(args, "key")
    actuator.press_key(key)
    return {"key": key, "dry_run": dry_run}, None, {}


def _tool_run_flow(args: dict[str, Any]) -> tuple[dict[str, Any], str | None, dict[str, Any]]:
    flow_path = _required_string(args, "flow_path")
    dry_run = _as_bool(args.get("dry_run", False))
    run_id = _optional_string(args.get("run_id")) or _default_run_id()

    flow = load_flow(flow_path)
    session = FlowRunner(dry_run=dry_run).run(flow, run_id=run_id)
    failed = any(not item.success for item in session.results)
    data = {
        "flow": flow.name,
        "run_id": run_id,
        "dry_run": dry_run,
        "success": not failed,
        "steps": [asdict(item) for item in session.results],
    }
    artifacts = {"run_dir": f"runs/{run_id}"}
    if failed:
        raise MCPToolError(
            code="flow_failed",
            message=f'Flow "{flow.name}" failed.',
            data=data,
            artifacts=artifacts,
            run_id=run_id,
        )
    return data, run_id, artifacts


def _tool_get_run_artifacts(args: dict[str, Any]) -> tuple[dict[str, Any], str | None, dict[str, Any]]:
    run_id = _required_string(args, "run_id")
    run_dir = Path("runs") / run_id
    if not run_dir.exists():
        raise MCPToolError(code="not_found", message=f"Run artifacts not found for run_id {run_id}.", run_id=run_id)

    step_payloads: list[dict[str, Any]] = []
    for step_dir in sorted([item for item in run_dir.iterdir() if item.is_dir()], key=lambda item: item.name):
        files = sorted([item.name for item in step_dir.iterdir() if item.is_file()])
        step_payloads.append(
            {
                "step_id": step_dir.name,
                "step_dir": str(step_dir),
                "files": files,
            }
        )

    data = {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "steps": step_payloads,
    }
    return data, run_id, {"run_dir": str(run_dir)}


def _build_locator() -> Locator:
    return Locator([MacOSA11yRecognizer(), TesseractRecognizer()])


def _resolve_frame(frame_path: str | None) -> Frame:
    if frame_path:
        image_path = Path(frame_path).expanduser().resolve()
        if not image_path.exists():
            raise ValueError(f"Frame path does not exist: {image_path}")
        return Frame(
            width=0,
            height=0,
            scale_factor=1.0,
            source=f"file:{image_path.name}",
            image_path=str(image_path),
            metadata={"input": "file"},
        )
    return screen()


def _frame_to_dict(frame: Frame) -> dict[str, Any]:
    payload = asdict(frame)
    payload["captured_at"] = frame.captured_at.isoformat()
    return payload


def _response_ok(
    *,
    tool: str,
    data: dict[str, Any],
    run_id: str | None,
    artifacts: dict[str, Any],
) -> dict[str, Any]:
    return {
        "ok": True,
        "tool": tool,
        "run_id": run_id,
        "data": data,
        "error": None,
        "artifacts": artifacts,
    }


def _response_error(
    *,
    tool: str,
    code: str,
    message: str,
    data: dict[str, Any] | None = None,
    run_id: str | None = None,
    artifacts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "tool": tool,
        "run_id": run_id,
        "data": data or {},
        "error": {"code": code, "message": message},
        "artifacts": artifacts or {},
    }


def _required_string(args: dict[str, Any], key: str) -> str:
    value = str(args.get(key, "")).strip()
    if not value:
        raise ValueError(f"{key} is required.")
    return value


def _required_int(args: dict[str, Any], key: str) -> int:
    if key not in args:
        raise ValueError(f"{key} is required.")
    return int(args[key])


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def _default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _select_target(*, targets: list[Any], selector: str) -> Any:
    if not targets:
        raise ValueError("No targets available for selection.")

    normalized = selector.strip().lower()
    if normalized in {"", "first"}:
        return targets[0]
    if normalized == "top_most":
        return sorted(targets, key=lambda item: (item.y, item.x))[0]
    if normalized == "left_most":
        return sorted(targets, key=lambda item: (item.x, item.y))[0]
    if normalized == "highest_confidence":
        return sorted(targets, key=lambda item: item.confidence, reverse=True)[0]
    if normalized == "right_most":
        return sorted(targets, key=lambda item: (item.x, item.y), reverse=True)[0]
    raise ValueError(f"Invalid selector '{selector}'.")

