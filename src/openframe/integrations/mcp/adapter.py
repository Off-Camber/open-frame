"""MCP-oriented tool adapter for Open Frame."""

from __future__ import annotations

import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from openframe import doctor as doctor_mod
from openframe.act import ActError, Actuator
from openframe.cancel import bind_tool_cancellation, reset_tool_cancellation
from openframe.capture import CaptureError, region, screen, window
from openframe.capture.sidecar import load_frame_sidecar
from openframe.desktop_access import (
    read_display_power,
    screen_unavailable_message,
)
from openframe.flow import load_flow
from openframe.recognize.coords import select_target
from openframe.recognize.defaults import build_default_locator, recognition_options_from_mapping
from openframe.recognize.locator import Locator
from openframe.recognize.match import ensure_actionable_match_count, explicit_selector
from openframe.runner import FlowRunner
from openframe.runs import lookup_run_directory, run_directory
from openframe.types import Frame, StepResult
from openframe.verify import write_step_artifacts

MCP_CONTRACT_VERSION = "v0.3.0"

# Wall-clock defaults (seconds). Override via env for long flows.
DEFAULT_TOOL_TIMEOUT_SEC = 60.0
DEFAULT_RUN_FLOW_TIMEOUT_SEC = 300.0
MAX_FIND_TARGETS_INLINE = 50
MAX_RUN_FLOW_DETAIL_CHARS = 32_000
_TOOLS_WITH_RUN_ID = frozenset({"click", "run_flow"})
_mcp_call_lock = threading.Lock()
_timeout_warnings_sent: set[str] = set()

MCP_TOOLS: tuple[dict[str, Any], ...] = (
    {
        "name": "capture",
        "description": "Capture screen/window/region into a frame",
        "required_args": [],
        "optional_args": [
            "mode",
            "window_title",
            "window_id",
            "x",
            "y",
            "width",
            "height",
            "out_path",
        ],
        "error_codes": [
            "validation_error",
            "capture_error",
            "permission_denied",
            "screen_unavailable",
            "runtime_error",
            "timeout",
            "internal_error",
            "busy",
        ],
    },
    {
        "name": "find",
        "description": "Find targets by query on a frame",
        "required_args": ["query"],
        "optional_args": ["strategy", "frame_path", "template", "template_threshold"],
        "error_codes": [
            "validation_error",
            "capture_error",
            "permission_denied",
            "screen_unavailable",
            "runtime_error",
            "timeout",
            "internal_error",
            "busy",
        ],
    },
    {
        "name": "click",
        "description": (
            "Find and click a target by query. dry_run defaults to true; "
            "pass dry_run=false to send the click."
        ),
        "required_args": ["query"],
        "optional_args": [
            "anchor",
            "kind",
            "dry_run",
            "run_id",
            "frame_path",
            "expect_one",
            "selector",
            "template",
            "template_threshold",
        ],
        "error_codes": [
            "not_found",
            "ambiguous_target",
            "validation_error",
            "capture_error",
            "action_error",
            "permission_denied",
            "screen_unavailable",
            "runtime_error",
            "timeout",
            "internal_error",
            "busy",
        ],
    },
    {
        "name": "type",
        "description": (
            "Type text at the current focus. dry_run defaults to true; "
            "pass dry_run=false to send keystrokes."
        ),
        "required_args": [],
        "optional_args": ["text", "interval", "dry_run"],
        "error_codes": [
            "action_error",
            "validation_error",
            "permission_denied",
            "screen_unavailable",
            "runtime_error",
            "timeout",
            "internal_error",
            "busy",
        ],
    },
    {
        "name": "key",
        "description": (
            "Press one key or one combo. dry_run defaults to true; "
            "pass dry_run=false to send the key."
        ),
        "required_args": [],
        "optional_args": ["key", "combo", "dry_run"],
        "error_codes": [
            "validation_error",
            "action_error",
            "permission_denied",
            "screen_unavailable",
            "runtime_error",
            "timeout",
            "internal_error",
            "busy",
        ],
    },
    {
        "name": "scroll",
        "description": (
            "Scroll the mouse wheel at an optional point. dry_run defaults to true; "
            "pass dry_run=false to scroll."
        ),
        "required_args": ["clicks"],
        "optional_args": ["x", "y", "dry_run"],
        "error_codes": [
            "validation_error",
            "action_error",
            "permission_denied",
            "screen_unavailable",
            "runtime_error",
            "timeout",
            "internal_error",
            "busy",
        ],
    },
    {
        "name": "run_flow",
        "description": (
            "Run a YAML flow file. dry_run defaults to true; pass dry_run=false to run it for real."
        ),
        "required_args": ["flow_path"],
        "optional_args": ["dry_run", "run_id", "include_step_details"],
        "error_codes": [
            "flow_failed",
            "validation_error",
            "capture_error",
            "action_error",
            "permission_denied",
            "screen_unavailable",
            "runtime_error",
            "timeout",
            "internal_error",
            "busy",
        ],
    },
    {
        "name": "get_run_artifacts",
        "description": "List run artifact files for a run id",
        "required_args": ["run_id"],
        "optional_args": [],
        "error_codes": [
            "not_found",
            "validation_error",
            "runtime_error",
            "timeout",
            "internal_error",
            "busy",
        ],
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
    """Call one deterministic tool and return a stable response envelope.

    One call runs at a time. A second call, including one that arrives while a
    timed-out worker is still finishing, returns ``busy``. On timeout the worker
    is cancelled before its next actuation or flow step.
    """
    payload = dict(args or {})
    dispatch = {
        "capture": _tool_capture,
        "find": _tool_find,
        "click": _tool_click,
        "type": _tool_type,
        "key": _tool_key,
        "scroll": _tool_scroll,
        "run_flow": _tool_run_flow,
        "get_run_artifacts": _tool_get_run_artifacts,
    }

    handler = dispatch.get(tool)
    if handler is None:
        return _response_error(tool=tool, code="unknown_tool", message=f"Unsupported tool: {tool}")
    if not _mcp_call_lock.acquire(blocking=False):
        return _response_error(
            tool=tool,
            code="busy",
            message=(
                "Another tool call is still running on this server. "
                "Wait for it to finish, including a call that already returned timeout."
            ),
        )

    try:
        data, run_id, artifacts = _invoke_with_timeout(tool=tool, handler=handler, payload=payload)
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


def _tool_timeout_sec(tool: str) -> float:
    if tool == "run_flow":
        return _parse_timeout_env(
            "OPENFRAME_MCP_RUN_FLOW_TIMEOUT_SEC", default=DEFAULT_RUN_FLOW_TIMEOUT_SEC
        )
    return _parse_timeout_env("OPENFRAME_MCP_TOOL_TIMEOUT_SEC", default=DEFAULT_TOOL_TIMEOUT_SEC)


def _parse_timeout_env(name: str, *, default: float) -> float:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return max(0.05, float(raw))
    except ValueError:
        if name not in _timeout_warnings_sent:
            _timeout_warnings_sent.add(name)
            print(
                f"Open Frame: ignoring non-numeric {name}={raw!r}; using {default:g}s.",
                file=sys.stderr,
            )
        return default


def _prepare_run_id(tool: str, payload: dict[str, Any]) -> str | None:
    """Assign the run id before the worker starts so a timeout can carry it."""
    supplied = _optional_string(payload.get("run_id"))
    if tool in _TOOLS_WITH_RUN_ID:
        run_id = supplied or _default_run_id()
        payload["run_id"] = run_id
        return run_id
    return supplied


def _invoke_with_timeout(
    *,
    tool: str,
    handler: Any,
    payload: dict[str, Any],
) -> tuple[dict[str, Any], str | None, dict[str, Any]]:
    """Run ``handler`` while the process-wide call lock is held.

    The caller acquires ``_mcp_call_lock``. This function releases it when the
    handler finishes, including when the caller has already returned a timeout.
    """
    worker_started = False
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="openframe-mcp")
    try:
        timeout_sec = _tool_timeout_sec(tool)
        run_id = _prepare_run_id(tool, payload)
        cancel = threading.Event()

        def wrapped() -> tuple[dict[str, Any], str | None, dict[str, Any]]:
            token = bind_tool_cancellation(cancel)
            try:
                return handler(payload)
            finally:
                reset_tool_cancellation(token)
                _mcp_call_lock.release()

        future = pool.submit(wrapped)
        worker_started = True
        try:
            return future.result(timeout=timeout_sec)
        except FuturesTimeoutError as exc:
            # Leave the worker running so it can observe the flag and release the lock.
            # Cancelling the future would skip that release when the thread has not started.
            cancel.set()
            message = (
                f'Tool "{tool}" exceeded wall-clock timeout of {timeout_sec:g}s. '
                "It will not actuate further. A call made before it finishes returns busy."
            )
            if run_id is not None:
                message += " get_run_artifacts can read this run_id once the call has finished."
            raise MCPToolError(code="timeout", message=message, run_id=run_id) from exc
    finally:
        if not worker_started:
            _mcp_call_lock.release()
        pool.shutdown(wait=False, cancel_futures=False)


def _require_desktop(*, capture: bool, interact: bool) -> None:
    """Reject a tool call that needs a display the process cannot use.

    A locked or sleeping display is ``screen_unavailable``. A failed Screen
    Recording or Accessibility probe, while the display is awake, is
    ``permission_denied``.
    """
    if sys.platform != "darwin" or (not capture and not interact):
        return
    state = read_display_power()
    if state.known and state.unavailable:
        raise MCPToolError(code="screen_unavailable", message=screen_unavailable_message(state))
    if capture:
        screen_check = doctor_mod._check_screen_recording()
        if screen_check.status == "fail":
            raise MCPToolError(
                code="permission_denied",
                message=screen_check.hint or screen_check.detail,
            )
    if interact:
        accessibility_check = doctor_mod._check_accessibility()
        if accessibility_check.status == "fail":
            raise MCPToolError(
                code="permission_denied",
                message=accessibility_check.hint or accessibility_check.detail,
            )


def _dry_run(args: dict[str, Any]) -> bool:
    """Live input is opt-in. Omitting dry_run previews the action."""
    return _as_bool(args.get("dry_run", True))


def _cap_step_details(steps: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Keep a prefix of full step records inside the inline character budget."""
    import json

    if len(json.dumps(steps)) <= MAX_RUN_FLOW_DETAIL_CHARS:
        return steps, 0
    kept: list[dict[str, Any]] = []
    for step in steps:
        trial = [*kept, step]
        if len(json.dumps(trial)) > MAX_RUN_FLOW_DETAIL_CHARS:
            break
        kept.append(step)
    if not kept and steps:
        step_id = steps[0].get("step_id")
        kept = [{"step_id": step_id, "truncated": True}]
        if len(json.dumps(kept)) > MAX_RUN_FLOW_DETAIL_CHARS:
            return [], len(steps)
        return kept, len(steps) - 1
    return kept, len(steps) - len(kept)


def _summarize_step_result(step: StepResult) -> dict[str, Any]:
    return {
        "step_id": step.step_id,
        "success": step.success,
        "duration_ms": step.duration_ms,
        "error": step.error,
    }


def _tool_capture(args: dict[str, Any]) -> tuple[dict[str, Any], str | None, dict[str, Any]]:
    _require_desktop(capture=True, interact=False)
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

    frame_path = _optional_string(args.get("frame_path"))
    if frame_path is None:
        _require_desktop(capture=True, interact=False)
    frame = _resolve_frame(frame_path)
    locator = _build_locator()
    options = recognition_options_from_mapping(args)
    targets = locator.find(frame=frame, query=query, strategy=strategy, options=options)
    truncated = len(targets) > MAX_FIND_TARGETS_INLINE
    inline_targets = targets[:MAX_FIND_TARGETS_INLINE]

    data: dict[str, Any] = {
        "query": query,
        "strategy": strategy,
        "source": frame.source,
        "count": len(targets),
        "targets": [asdict(item) for item in inline_targets],
    }
    if truncated:
        data["targets_truncated"] = True
        data["targets_inline_limit"] = MAX_FIND_TARGETS_INLINE
    if options and options.get("template"):
        data["template"] = options["template"]
    recognizer_errors = getattr(locator, "recognizer_errors", None)
    if recognizer_errors:
        data["recognizer_errors"] = list(recognizer_errors)
    return data, None, {}


def _tool_click(args: dict[str, Any]) -> tuple[dict[str, Any], str | None, dict[str, Any]]:
    query = _required_string(args, "query")
    anchor = str(args.get("anchor", "center")).strip()
    click_kind = str(args.get("kind", "click")).strip()
    dry_run = _dry_run(args)
    expect_one = _as_bool(args.get("expect_one", False))
    selector = explicit_selector(args.get("selector"))
    run_id = _optional_string(args.get("run_id")) or _default_run_id()

    frame_path = _optional_string(args.get("frame_path"))
    _require_desktop(capture=frame_path is None, interact=not dry_run)
    frame = _resolve_frame(frame_path, require_sidecar=bool(frame_path) and not dry_run)
    locator = _build_locator()
    options = recognition_options_from_mapping(args)
    targets = locator.find(frame=frame, query=query, strategy="all", options=options)
    try:
        ensure_actionable_match_count(
            query=query,
            match_count=len(targets),
            selector=selector,
            expect_one=expect_one,
        )
    except ValueError as exc:
        message = str(exc)
        if message.startswith("No target found"):
            raise MCPToolError(code="not_found", message=message, run_id=run_id) from exc
        raise MCPToolError(
            code="ambiguous_target",
            message=message,
            run_id=run_id,
            data={"query": query, "match_count": len(targets)},
        ) from exc
    selected_target = select_target(
        targets=targets, selector=selector or "first", scale_factor=frame.scale_factor
    )

    actuator = Actuator(dry_run=dry_run)
    point = actuator.click_target(
        selected_target,
        anchor=anchor,
        kind=click_kind,
        scale_factor=frame.scale_factor,
        origin=(frame.origin_x, frame.origin_y),
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
        "selector": selector or "first",
        "point": {"x": point[0], "y": point[1]},
        "target": asdict(selected_target),
    }
    recognizer_errors = getattr(locator, "recognizer_errors", None)
    if recognizer_errors:
        data["recognizer_errors"] = list(recognizer_errors)
    artifacts = {"step_dir": str(artifact_dir)}
    return data, run_id, artifacts


def _tool_type(args: dict[str, Any]) -> tuple[dict[str, Any], str | None, dict[str, Any]]:
    text = str(args.get("text", "")).strip()
    if not text:
        raise ValueError("text must not be empty.")
    interval = float(args.get("interval", 0.0))
    dry_run = _dry_run(args)
    _require_desktop(capture=False, interact=not dry_run)
    actuator = Actuator(dry_run=dry_run)
    actuator.type_text(text, interval=interval)
    return {"text_length": len(text), "interval": interval, "dry_run": dry_run}, None, {}


def _tool_key(args: dict[str, Any]) -> tuple[dict[str, Any], str | None, dict[str, Any]]:
    dry_run = _dry_run(args)
    key = _optional_string(args.get("key"))
    combo = args.get("combo")
    has_combo = combo is not None
    if has_combo and key is not None:
        raise ValueError("key requires exactly one of key or combo.")
    if has_combo:
        if not isinstance(combo, list) or not combo:
            raise ValueError("combo must be a non-empty list of keys.")
        keys = [str(item).strip() for item in combo if str(item).strip()]
        if not keys:
            raise ValueError("combo resolved to no usable keys.")
        _require_desktop(capture=False, interact=not dry_run)
        actuator = Actuator(dry_run=dry_run)
        actuator.key_combo(*keys)
        return {"combo": keys, "dry_run": dry_run}, None, {}
    if key is None:
        raise ValueError("key requires exactly one of key or combo.")
    _require_desktop(capture=False, interact=not dry_run)
    actuator = Actuator(dry_run=dry_run)
    actuator.press_key(key)
    return {"key": key, "dry_run": dry_run}, None, {}


def _tool_scroll(args: dict[str, Any]) -> tuple[dict[str, Any], str | None, dict[str, Any]]:
    if "clicks" not in args or args.get("clicks") is None:
        raise ValueError("clicks is required.")
    clicks = int(args["clicks"])
    dry_run = _dry_run(args)
    x = int(args["x"]) if args.get("x") is not None else None
    y = int(args["y"]) if args.get("y") is not None else None
    if (x is None) ^ (y is None):
        raise ValueError("scroll requires both x and y, or neither.")
    _require_desktop(capture=False, interact=not dry_run)
    actuator = Actuator(dry_run=dry_run)
    actuator.scroll(clicks, x=x, y=y)
    return {"clicks": clicks, "x": x, "y": y, "dry_run": dry_run}, None, {}


def _tool_run_flow(args: dict[str, Any]) -> tuple[dict[str, Any], str | None, dict[str, Any]]:
    flow_path = _required_string(args, "flow_path")
    dry_run = _dry_run(args)
    include_step_details = _as_bool(args.get("include_step_details", False))
    run_id = _optional_string(args.get("run_id")) or _default_run_id()
    _require_desktop(capture=True, interact=not dry_run)

    flow = load_flow(flow_path)
    session = FlowRunner(dry_run=dry_run).run(flow, run_id=run_id)
    failed = any(not item.success for item in session.results)
    omitted = 0
    if include_step_details:
        steps_payload = [asdict(item) for item in session.results]
        steps_payload, omitted = _cap_step_details(steps_payload)
    else:
        steps_payload = [_summarize_step_result(item) for item in session.results]
    data = {
        "flow": flow.name,
        "run_id": run_id,
        "dry_run": dry_run,
        "success": not failed,
        "steps": steps_payload,
        "step_details": "full" if include_step_details else "summary",
    }
    if omitted:
        data["step_details_truncated"] = True
        data["steps_omitted"] = omitted
    artifacts = {"run_dir": str(run_directory(run_id))}
    if failed:
        raise MCPToolError(
            code="flow_failed",
            message=f'Flow "{flow.name}" failed.',
            data=data,
            artifacts=artifacts,
            run_id=run_id,
        )
    return data, run_id, artifacts


def _tool_get_run_artifacts(
    args: dict[str, Any],
) -> tuple[dict[str, Any], str | None, dict[str, Any]]:
    run_id = _required_string(args, "run_id")
    run_dir = lookup_run_directory(run_id)
    if run_dir is None:
        raise MCPToolError(
            code="not_found", message=f"Run artifacts not found for run_id {run_id}.", run_id=run_id
        )

    step_payloads: list[dict[str, Any]] = []
    for step_dir in sorted(
        [item for item in run_dir.iterdir() if item.is_dir()], key=lambda item: item.name
    ):
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
    return build_default_locator()


def _resolve_frame(frame_path: str | None, *, require_sidecar: bool = False) -> Frame:
    if frame_path:
        image_path = Path(frame_path).expanduser().resolve()
        if not image_path.exists():
            raise ValueError(f"Frame path does not exist: {image_path}")
        loaded = load_frame_sidecar(image_path)
        if loaded is not None:
            return loaded
        if require_sidecar:
            raise ValueError(
                "frame_path has no capture metadata sidecar; "
                "refusing a live click that cannot map image coordinates."
            )
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
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
