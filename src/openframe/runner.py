"""Flow runner for executing declarative steps."""

from __future__ import annotations

import re
import webbrowser
from pathlib import Path
from time import monotonic, perf_counter, sleep
from typing import Any

from openframe.act import Actuator
from openframe.capture import list_windows, screen, window
from openframe.capture.macos import CaptureError
from openframe.flow import Flow, FlowStep
from openframe.recognize import Locator
from openframe.recognize.coords import select_target, target_logical_bounds
from openframe.recognize.defaults import build_default_locator, recognition_options_from_mapping
from openframe.recognize.match import ensure_actionable_match_count, explicit_selector
from openframe.session import Session
from openframe.types import Frame, StepResult, Target
from openframe.verify import (
    MatchBounds,
    ScreenshotDiffVerifier,
    TargetGoneVerifier,
    TextPresenceVerifier,
    VerifyResult,
    WindowStateVerifier,
    parse_match_bounds,
    write_step_artifacts,
)
from openframe.window import evaluate_window_guard, frontmost_window


# Backward-compatible private alias used by CLI/Session/tests.
def _select_target(*, targets: list[Target], selector: str, scale_factor: float = 1.0) -> Target:
    return select_target(targets=targets, selector=selector, scale_factor=scale_factor)


class FlowRunner:
    """Executes a flow and records step outcomes."""

    def __init__(self, *, dry_run: bool = False) -> None:
        self.dry_run = dry_run

    def run(self, flow: Flow, *, run_id: str) -> Session:
        session = Session(run_id=run_id)
        locator = build_default_locator()
        actuator = Actuator(dry_run=self.dry_run)
        run_dir = f"runs/{run_id}"
        substitution_base = {
            "run_id": run_id,
            "run_dir": run_dir,
            **{str(key): value for key, value in flow.variables.items()},
        }

        for step in flow.steps:
            started = perf_counter()
            before = screen()
            step_artifact_dir = f"{run_dir}/{step.id}"
            step_context = {
                **substitution_base,
                "step_id": step.id,
                "step_kind": step.kind,
                "step_artifact_dir": step_artifact_dir,
                "artifact_dir": step_artifact_dir,
            }
            resolved_params = _resolve_templates(step.params, step_context)
            resolved_step = FlowStep(id=step.id, kind=step.kind, params=resolved_params)
            error: str | None = None
            details: dict[str, Any] = {"kind": step.kind, "params": dict(resolved_step.params)}

            try:
                details.update(
                    self._execute_step(step=resolved_step, locator=locator, actuator=actuator)
                )
                success = True
            except Exception as exc:  # noqa: BLE001
                success = False
                error = str(exc)

            after = screen()
            artifact_dir = write_step_artifacts(
                run_id=run_id,
                step_id=step.id,
                before=before,
                after=after,
                verification=None,
            )
            details["artifact_dir"] = str(artifact_dir)
            duration_ms = int((perf_counter() - started) * 1000)

            session.record(
                StepResult(
                    step_id=step.id,
                    success=success,
                    duration_ms=duration_ms,
                    error=error,
                    before_frame_path=before.image_path,
                    after_frame_path=after.image_path,
                    details=details,
                )
            )

            if not success:
                break

        return session

    def _execute_step(
        self, *, step: FlowStep, locator: Locator, actuator: Actuator
    ) -> dict[str, Any]:
        kind = step.kind
        _enforce_window_guard(step=step)
        if kind == "wait":
            milliseconds = int(step.params.get("ms", 0))
            actuator.wait_ms(milliseconds)
            return {"wait_ms": milliseconds}

        if kind == "write_file":
            raw_path = str(step.params.get("path", "")).strip()
            if not raw_path:
                raise ValueError(f"Step '{step.id}' write_file requires 'path'.")
            content = step.params.get("text", step.params.get("content", ""))
            content = "" if content is None else str(content)
            target_path = Path(raw_path).expanduser()
            if not self.dry_run:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(content, encoding="utf-8")
            return {
                "path": str(target_path),
                "bytes_written": len(content.encode("utf-8")),
            }

        if kind == "scroll":
            if "clicks" not in step.params:
                raise ValueError(f"Step '{step.id}' scroll requires 'clicks'.")
            clicks = int(step.params["clicks"])
            x = int(step.params["x"]) if "x" in step.params else None
            y = int(step.params["y"]) if "y" in step.params else None
            if (x is None) ^ (y is None):
                raise ValueError(f"Step '{step.id}' scroll requires both x and y, or neither.")
            actuator.scroll(clicks, x=x, y=y)
            return {"clicks": clicks, "x": x, "y": y, "dry_run": self.dry_run}

        if kind == "drag":
            start, end, meta = _resolve_drag_endpoints(
                step=step, locator=locator, actuator=actuator
            )
            duration = float(step.params.get("duration", 0.2))
            button = str(step.params.get("button", "left")).strip().lower()
            if button not in {"left", "middle", "right"}:
                raise ValueError(f"Step '{step.id}' has invalid drag button '{button}'.")
            actuator.drag(
                start[0],
                start[1],
                end[0],
                end[1],
                duration=duration,
                button=button,  # type: ignore[arg-type]
            )
            return {
                "from": {"x": start[0], "y": start[1]},
                "to": {"x": end[0], "y": end[1]},
                "duration": duration,
                "button": button,
                "dry_run": self.dry_run,
                **meta,
            }

        if kind == "click":
            query = str(step.params.get("query", "")).strip()
            if not query:
                raise ValueError(f"Step '{step.id}' click requires 'query'.")
            expect_one = _coerce_bool(step.params.get("expect_one", False))
            selector = explicit_selector(step.params.get("selector"))
            timeout_ms = _coerce_timeout_ms(step=step, default_ms=3000)
            poll_ms = _coerce_poll_ms(step=step, default_ms=200)
            scope_to_window = _wants_window_scope(step)
            scroll_cfg = _parse_scroll_until_found(step=step)
            targets, scale_factor, scroll_meta = _find_targets_maybe_scrolling(
                locator=locator,
                actuator=actuator,
                query=query,
                strategy="all",
                timeout_ms=timeout_ms,
                poll_ms=poll_ms,
                scope_to_window=scope_to_window,
                options=recognition_options_from_mapping(step.params),
                scroll_cfg=scroll_cfg,
            )
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
                    raise ValueError(
                        f"Step '{step.id}' could not find target for query '{query}'."
                    ) from exc
                raise ValueError(f"Step '{step.id}' {message}") from exc
            selected_target = _select_target(
                targets=targets, selector=selector or "first", scale_factor=scale_factor
            )

            anchor = str(step.params.get("anchor", "center"))
            click_kind = str(step.params.get("click_kind", "click"))
            if anchor not in {"center", "top-left", "top-right", "bottom-left", "bottom-right"}:
                raise ValueError(f"Step '{step.id}' has invalid anchor '{anchor}'.")
            if click_kind not in {"click", "double", "right"}:
                raise ValueError(f"Step '{step.id}' has invalid click_kind '{click_kind}'.")
            actuator.click_target(
                selected_target, anchor=anchor, kind=click_kind, scale_factor=scale_factor
            )
            details = {
                "query": query,
                "click_kind": click_kind,
                "anchor": anchor,
                "expect_one": expect_one,
                "selector": selector or "first",
                "timeout_ms": timeout_ms,
                "poll_ms": poll_ms,
                "template": (recognition_options_from_mapping(step.params) or {}).get("template"),
            }
            if scroll_meta:
                details.update(scroll_meta)
            return details

        if kind == "click_point":
            frame = screen()
            scale_factor = frame.scale_factor
            logical_width = frame.width / scale_factor
            logical_height = frame.height / scale_factor

            if "x_ratio" in step.params and "y_ratio" in step.params:
                x = round(float(step.params["x_ratio"]) * logical_width)
                y = round(float(step.params["y_ratio"]) * logical_height)
            elif "x" in step.params and "y" in step.params:
                x = int(step.params["x"])
                y = int(step.params["y"])
            else:
                raise ValueError(f"Step '{step.id}' click_point requires x_ratio/y_ratio or x/y.")

            click_kind = str(step.params.get("click_kind", "click"))
            if click_kind not in {"click", "double", "right"}:
                raise ValueError(f"Step '{step.id}' has invalid click_kind '{click_kind}'.")
            actuator.click_point(x, y, kind=click_kind)
            return {
                "x": x,
                "y": y,
                "scale_factor": scale_factor,
                "click_kind": click_kind,
            }

        if kind == "find":
            query = str(step.params.get("query", "")).strip()
            if not query:
                raise ValueError(f"Step '{step.id}' find requires 'query'.")
            timeout_ms = _coerce_timeout_ms(step=step, default_ms=3000)
            poll_ms = _coerce_poll_ms(step=step, default_ms=200)
            scope_to_window = _wants_window_scope(step)
            scroll_cfg = _parse_scroll_until_found(step=step)
            targets, _scale_factor, scroll_meta = _find_targets_maybe_scrolling(
                locator=locator,
                actuator=actuator,
                query=query,
                strategy="all",
                timeout_ms=timeout_ms,
                poll_ms=poll_ms,
                scope_to_window=scope_to_window,
                options=recognition_options_from_mapping(step.params),
                scroll_cfg=scroll_cfg,
            )
            if not targets:
                raise ValueError(f"Step '{step.id}' did not find query '{query}'.")
            details = {
                "query": query,
                "matches": len(targets),
                "timeout_ms": timeout_ms,
                "poll_ms": poll_ms,
                "scope_to_window": scope_to_window,
                "template": (recognition_options_from_mapping(step.params) or {}).get("template"),
            }
            if scroll_meta:
                details.update(scroll_meta)
            return details

        if kind == "capture":
            out_path = step.params.get("out")
            if out_path:
                screen(out_path=str(out_path))
            else:
                screen()
            return {"out": str(out_path) if out_path else None}

        if kind == "app":
            app_name = str(step.params.get("name", "")).strip()
            if not app_name:
                raise ValueError(f"Step '{step.id}' app requires 'name'.")
            if not self.dry_run:
                _focus_app(app_name)
            return {"app": app_name}

        if kind == "type":
            text = str(step.params.get("text", ""))
            interval = float(step.params.get("interval", 0.0))
            via = str(step.params.get("via", "keystrokes")).strip().lower()
            if via in {"applescript-close", "textedit-close"}:
                if not self.dry_run:
                    _textedit_close_all_documents()
                return {"via": "applescript-close", "closed": True}
            if via in {"applescript", "textedit"}:
                size = step.params.get("size")
                font_size = int(size) if size is not None else None
                if not self.dry_run:
                    _textedit_set_front_document_text(text, font_size=font_size)
                return {
                    "text_length": len(text),
                    "via": "applescript",
                    "font_size": font_size,
                }
            actuator.type_text(text, interval=interval)
            return {"text_length": len(text), "via": "keystrokes"}

        if kind == "key":
            key = str(step.params.get("key", "")).strip()
            combo = step.params.get("combo")
            if combo is not None:
                if not isinstance(combo, list) or not combo:
                    raise ValueError(f"Step '{step.id}' key combo must be a non-empty list.")
                keys = [str(item).strip() for item in combo if str(item).strip()]
                if not keys:
                    raise ValueError(f"Step '{step.id}' key combo resolved to empty keys.")
                actuator.key_combo(*keys)
                return {"combo": keys}
            if not key:
                raise ValueError(f"Step '{step.id}' key requires 'key' or 'combo'.")
            actuator.press_key(key)
            return {"key": key}

        if kind == "fill":
            query = str(step.params.get("query", "")).strip()
            text = str(step.params.get("text", ""))
            if not query:
                raise ValueError(f"Step '{step.id}' fill requires 'query'.")
            expect_one = _coerce_bool(step.params.get("expect_one", False))
            selector = explicit_selector(step.params.get("selector"))
            timeout_ms = _coerce_timeout_ms(step=step, default_ms=3000)
            poll_ms = _coerce_poll_ms(step=step, default_ms=200)
            scope_to_window = _wants_window_scope(step)
            targets, scale_factor = _find_targets_with_retry(
                locator=locator,
                query=query,
                strategy="all",
                timeout_ms=timeout_ms,
                poll_ms=poll_ms,
                scope_to_window=scope_to_window,
                options=recognition_options_from_mapping(step.params),
            )
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
                    raise ValueError(
                        f"Step '{step.id}' could not find fill target '{query}'."
                    ) from exc
                raise ValueError(f"Step '{step.id}' {message}") from exc
            selected_target = _select_target(
                targets=targets, selector=selector or "first", scale_factor=scale_factor
            )
            actuator.click_target(
                selected_target, anchor="center", kind="click", scale_factor=scale_factor
            )
            if bool(step.params.get("clear", False)):
                actuator.key_combo("command", "a")
            actuator.type_text(text)
            return {
                "query": query,
                "text_length": len(text),
                "expect_one": expect_one,
                "selector": selector or "first",
                "timeout_ms": timeout_ms,
                "poll_ms": poll_ms,
                "template": (recognition_options_from_mapping(step.params) or {}).get("template"),
            }

        if kind == "attach":
            path = str(step.params.get("path", "")).strip()
            if not path:
                raise ValueError(f"Step '{step.id}' attach requires 'path'.")
            actuator.type_text(path)
            submit_key = str(step.params.get("submit_key", "enter")).strip()
            if submit_key:
                actuator.press_key(submit_key)
            return {"path": path, "submit_key": submit_key}

        if kind == "navigate":
            url = str(step.params.get("url", "")).strip()
            if not url:
                raise ValueError(f"Step '{step.id}' navigate requires 'url'.")
            if not self.dry_run:
                webbrowser.open(url, new=0, autoraise=True)
            return {"url": url}

        if kind == "verify":
            specs = step.params.get("specs", step.params.get("spec"))
            verify_specs: list[str]
            if isinstance(specs, str):
                verify_specs = [specs]
            elif isinstance(specs, list):
                verify_specs = [str(item) for item in specs]
            else:
                raise ValueError(f"Step '{step.id}' verify requires 'spec' or 'specs'.")

            timeout_ms = _coerce_timeout_ms(step=step, default_ms=3000)
            poll_ms = _coerce_poll_ms(step=step, default_ms=250)
            match_bounds = parse_match_bounds(step.params.get("match_bounds"))
            scope_to_window = _wants_window_scope(step)
            result = _run_verify_specs(
                verify_specs=verify_specs,
                locator=locator,
                timeout_ms=timeout_ms,
                poll_ms=poll_ms,
                match_bounds=match_bounds,
                scope_to_window=scope_to_window,
            )
            if not result.success:
                raise ValueError(result.message)
            return {
                "verification": {"verifier": result.verifier, "message": result.message},
                "timeout_ms": timeout_ms,
                "poll_ms": poll_ms,
                "match_bounds": step.params.get("match_bounds"),
            }

        raise ValueError(f"Unsupported flow step kind '{kind}' in step '{step.id}'.")


def _run_verify_specs(
    *,
    verify_specs: list[str],
    locator: Locator,
    timeout_ms: int,
    poll_ms: int,
    match_bounds: MatchBounds | None = None,
    scope_to_window: bool = False,
) -> VerifyResult:
    if not verify_specs:
        raise ValueError("At least one verify spec is required.")

    deadline = monotonic() + (timeout_ms / 1000.0)
    last: VerifyResult | None = None

    while True:
        frame, used_window_capture = _capture_scoped_frame(scope_to_window=scope_to_window)
        # Window captures are already cropped; screen-space window bounds would
        # be wrong and must not be applied on top of the window image.
        apply_window_bounds = scope_to_window and not used_window_capture
        verifiers = [
            _parse_verifier_spec(
                raw_spec=raw_spec,
                locator=locator,
                match_bounds=match_bounds,
                scope_to_window=apply_window_bounds,
            )
            for raw_spec in verify_specs
        ]

        all_success = True
        for verifier in verifiers:
            result = verifier.verify(before=frame, after=frame)
            last = result
            if not result.success:
                all_success = False
                break

        if all_success and last is not None:
            return last

        if monotonic() >= deadline:
            if last is None:
                raise ValueError("Verification produced no result.")
            return last

        sleep(poll_ms / 1000.0)


def _capture_scoped_frame(*, scope_to_window: bool) -> tuple[Frame, bool]:
    """Capture screen, or the frontmost window when scope_to_window is requested."""
    if scope_to_window:
        captured = _capture_frontmost_window_frame()
        if captured is not None:
            return captured, True
    return screen(), False


def _capture_frontmost_window_frame() -> Frame | None:
    """Capture the frontmost app window image (not a full-screen crop).

    Returns None when window capture is unavailable (non-macOS, permission
    gaps, or no matching window) so callers can fall back to screen capture
    plus geometric window filtering.
    """
    try:
        state = frontmost_window()
        if state is None or state.width <= 0 or state.height <= 0:
            return None

        windows = list_windows()
        candidates = [
            item
            for item in windows
            if str(item.get("owner", "")) == state.app
        ]
        if not candidates:
            return None

        selected = None
        if state.title:
            for item in candidates:
                if str(item.get("title", "")) == state.title:
                    selected = item
                    break
        if selected is None:
            selected = candidates[0]

        return window(window_id=int(selected["id"]))
    except (CaptureError, KeyError, TypeError, ValueError):
        return None


def _find_targets_with_retry(
    *,
    locator: Locator,
    query: str,
    strategy: str,
    timeout_ms: int,
    poll_ms: int,
    scope_to_window: bool = False,
    options: dict[str, Any] | None = None,
) -> tuple[list[Target], float]:
    """Find targets, returning them with the scale factor of the source frame.

    The scale factor is needed to convert recognizer pixel coordinates into
    logical click space at actuation time. When ``scope_to_window`` is true,
    only targets whose bounds lie inside the frontmost window are returned.
    """
    deadline = monotonic() + (timeout_ms / 1000.0)
    while True:
        frame, used_window_capture = _capture_scoped_frame(scope_to_window=scope_to_window)
        targets = locator.find(frame, query, strategy=strategy, options=options)
        if scope_to_window and not used_window_capture:
            targets = _filter_targets_to_window(targets=targets, scale_factor=frame.scale_factor)
        if targets:
            return targets, frame.scale_factor
        if monotonic() >= deadline:
            return [], frame.scale_factor
        sleep(poll_ms / 1000.0)


DEFAULT_MAX_SCROLL_ATTEMPTS = 5
HARD_MAX_SCROLL_ATTEMPTS = 50
DEFAULT_SCROLL_CLICKS = -3
DEFAULT_SCROLL_POLL_MS = 200


def _parse_scroll_until_found(*, step: FlowStep) -> dict[str, Any] | None:
    """Return scroll-until-found config when enabled, else None."""
    enabled = _coerce_bool(step.params.get("scroll_until_found", False))
    if not enabled:
        return None
    max_attempts = int(step.params.get("max_scroll_attempts", DEFAULT_MAX_SCROLL_ATTEMPTS))
    if max_attempts < 0:
        raise ValueError(f"Step '{step.id}' max_scroll_attempts must be >= 0.")
    if max_attempts > HARD_MAX_SCROLL_ATTEMPTS:
        raise ValueError(
            f"Step '{step.id}' max_scroll_attempts exceeds hard limit "
            f"({HARD_MAX_SCROLL_ATTEMPTS})."
        )
    scroll_clicks = int(step.params.get("scroll_clicks", DEFAULT_SCROLL_CLICKS))
    scroll_poll_ms = int(step.params.get("scroll_poll_ms", DEFAULT_SCROLL_POLL_MS))
    if scroll_poll_ms < 0:
        raise ValueError(f"Step '{step.id}' scroll_poll_ms must be >= 0.")
    x = int(step.params["scroll_x"]) if "scroll_x" in step.params else None
    y = int(step.params["scroll_y"]) if "scroll_y" in step.params else None
    if (x is None) ^ (y is None):
        raise ValueError(f"Step '{step.id}' scroll_until_found requires both scroll_x and scroll_y.")
    return {
        "max_attempts": max_attempts,
        "scroll_clicks": scroll_clicks,
        "scroll_poll_ms": scroll_poll_ms,
        "scroll_x": x,
        "scroll_y": y,
    }


def _find_targets_maybe_scrolling(
    *,
    locator: Locator,
    actuator: Actuator,
    query: str,
    strategy: str,
    timeout_ms: int,
    poll_ms: int,
    scope_to_window: bool,
    options: dict[str, Any] | None,
    scroll_cfg: dict[str, Any] | None,
) -> tuple[list[Target], float, dict[str, Any]]:
    """Find targets, optionally scrolling between bounded attempts."""
    if scroll_cfg is None:
        targets, scale_factor = _find_targets_with_retry(
            locator=locator,
            query=query,
            strategy=strategy,
            timeout_ms=timeout_ms,
            poll_ms=poll_ms,
            scope_to_window=scope_to_window,
            options=options,
        )
        return targets, scale_factor, {}

    max_attempts = int(scroll_cfg["max_attempts"])
    scroll_clicks = int(scroll_cfg["scroll_clicks"])
    scroll_poll_ms = int(scroll_cfg["scroll_poll_ms"])
    scroll_x = scroll_cfg.get("scroll_x")
    scroll_y = scroll_cfg.get("scroll_y")
    # Per attempt use a short recognition window; overall bound is max_attempts.
    attempt_timeout_ms = min(timeout_ms, max(poll_ms, 300))
    scroll_attempts = 0
    scale_factor = 1.0
    for attempt in range(max_attempts + 1):
        targets, scale_factor = _find_targets_with_retry(
            locator=locator,
            query=query,
            strategy=strategy,
            timeout_ms=attempt_timeout_ms,
            poll_ms=poll_ms,
            scope_to_window=scope_to_window,
            options=options,
        )
        if targets:
            return (
                targets,
                scale_factor,
                {
                    "scroll_until_found": True,
                    "scroll_attempts": scroll_attempts,
                    "max_scroll_attempts": max_attempts,
                    "scroll_clicks": scroll_clicks,
                },
            )
        if attempt >= max_attempts:
            break
        actuator.scroll(scroll_clicks, x=scroll_x, y=scroll_y)
        scroll_attempts += 1
        if scroll_poll_ms > 0:
            sleep(scroll_poll_ms / 1000.0)

    return (
        [],
        scale_factor,
        {
            "scroll_until_found": True,
            "scroll_attempts": scroll_attempts,
            "max_scroll_attempts": max_attempts,
            "scroll_clicks": scroll_clicks,
        },
    )


def _resolve_drag_endpoints(
    *,
    step: FlowStep,
    locator: Locator,
    actuator: Actuator,
) -> tuple[tuple[int, int], tuple[int, int], dict[str, Any]]:
    """Resolve drag from/to points from coordinates and/or query targets."""
    meta: dict[str, Any] = {}
    start = _resolve_point_param(
        step=step,
        locator=locator,
        actuator=actuator,
        x_key="from_x",
        y_key="from_y",
        query_key="from_query",
        selector_key="from_selector",
        label="from",
        meta=meta,
    )
    end = _resolve_point_param(
        step=step,
        locator=locator,
        actuator=actuator,
        x_key="to_x",
        y_key="to_y",
        query_key="to_query",
        selector_key="to_selector",
        label="to",
        meta=meta,
    )
    return start, end, meta


def _resolve_point_param(
    *,
    step: FlowStep,
    locator: Locator,
    actuator: Actuator,
    x_key: str,
    y_key: str,
    query_key: str,
    selector_key: str,
    label: str,
    meta: dict[str, Any],
) -> tuple[int, int]:
    if x_key in step.params and y_key in step.params:
        return int(step.params[x_key]), int(step.params[y_key])

    query = str(step.params.get(query_key, "")).strip()
    if not query:
        raise ValueError(
            f"Step '{step.id}' drag requires {x_key}/{y_key} or {query_key} for '{label}'."
        )
    timeout_ms = _coerce_timeout_ms(step=step, default_ms=3000)
    poll_ms = _coerce_poll_ms(step=step, default_ms=200)
    scope_to_window = _wants_window_scope(step)
    selector = explicit_selector(step.params.get(selector_key))
    targets, scale_factor = _find_targets_with_retry(
        locator=locator,
        query=query,
        strategy="all",
        timeout_ms=timeout_ms,
        poll_ms=poll_ms,
        scope_to_window=scope_to_window,
        options=recognition_options_from_mapping(step.params),
    )
    try:
        ensure_actionable_match_count(
            query=query,
            match_count=len(targets),
            selector=selector,
            expect_one=False,
        )
    except ValueError as exc:
        raise ValueError(f"Step '{step.id}' drag {label}: {exc}") from exc
    selected = _select_target(
        targets=targets, selector=selector or "first", scale_factor=scale_factor
    )
    point = actuator.point_for_target(selected, anchor="center", scale_factor=scale_factor)
    meta[f"{label}_query"] = query
    meta[f"{label}_selector"] = selector or "first"
    return point


def _wants_window_scope(step: FlowStep) -> bool:
    """Return True when a step opts in to window-scoped recognition."""
    raw = step.params.get("scope")
    if isinstance(raw, str) and raw.strip().lower() == "window":
        return True
    return _coerce_bool(step.params.get("scope_to_window", False))


def _filter_targets_to_window(*, targets: list[Target], scale_factor: float) -> list[Target]:
    """Keep only targets whose pixel bounds lie within the frontmost window."""
    state = frontmost_window()
    if state is None or state.width <= 0 or state.height <= 0:
        return targets
    kept: list[Target] = []
    for target in targets:
        logical_x, logical_y, logical_w, logical_h = target_logical_bounds(
            target, scale_factor=scale_factor
        )
        if state.contains(x=logical_x, y=logical_y, width=logical_w, height=logical_h):
            kept.append(target)
    return kept


def _enforce_window_guard(*, step: FlowStep) -> None:
    """Assert frontmost window matches a step's optional ``window`` guard."""
    raw_window = step.params.get("window")
    if raw_window is None:
        return
    if not isinstance(raw_window, dict):
        raise TypeError(f"Step '{step.id}' window guard must be a mapping.")
    spec = {
        key: str(value)
        for key, value in raw_window.items()
        if key in {"app", "title_contains", "role"} and value is not None
    }
    if not spec:
        return
    state = frontmost_window()
    passed, message = evaluate_window_guard(spec=spec, state=state)
    if not passed:
        raise ValueError(f"Step '{step.id}' window guard failed: {message}")


def _coerce_timeout_ms(*, step: FlowStep, default_ms: int) -> int:
    value = int(step.params.get("timeout_ms", default_ms))
    if value < 0:
        raise ValueError(f"Step '{step.id}' timeout_ms must be >= 0.")
    return value


def _coerce_poll_ms(*, step: FlowStep, default_ms: int) -> int:
    value = int(step.params.get("poll_ms", default_ms))
    if value <= 0:
        raise ValueError(f"Step '{step.id}' poll_ms must be > 0.")
    return value


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def _parse_verifier_spec(
    *,
    raw_spec: str,
    locator: Locator,
    match_bounds: MatchBounds | None = None,
    scope_to_window: bool = False,
):
    if ":" not in raw_spec:
        raise ValueError(f"Invalid verify spec: {raw_spec}")
    key, value = raw_spec.split(":", 1)
    value = value.strip().strip('"').strip("'")

    text_bounds = match_bounds
    if scope_to_window and key in {"text-gone", "text-appeared"}:
        text_bounds = _window_bounds_as_match_bounds() or match_bounds

    if key == "text-gone":
        return TextPresenceVerifier(
            locator=locator, text=value, should_exist=False, bounds=text_bounds
        )
    if key == "text-appeared":
        return TextPresenceVerifier(
            locator=locator, text=value, should_exist=True, bounds=text_bounds
        )
    if key == "target-gone":
        return TargetGoneVerifier(locator=locator, query=value)
    if key == "diff":
        return ScreenshotDiffVerifier(max_ratio=float(value))
    if key == "window-title-contains":
        return WindowStateVerifier(
            kind="title_contains", expected=value, state_provider=frontmost_window
        )
    if key == "window-role":
        return WindowStateVerifier(kind="role", expected=value, state_provider=frontmost_window)
    if key == "window-app":
        return WindowStateVerifier(kind="app", expected=value, state_provider=frontmost_window)

    raise ValueError(f"Unsupported verify spec: {raw_spec}")


def _window_bounds_as_match_bounds() -> MatchBounds | None:
    """Return MatchBounds covering the frontmost window in pixel space."""
    state = frontmost_window()
    if state is None or state.width <= 0 or state.height <= 0:
        return None
    return MatchBounds(
        min_x=state.x,
        max_x=state.x + state.width,
        min_y=state.y,
        max_y=state.y + state.height,
    )


def _focus_app(name: str) -> None:
    import sys

    if sys.platform != "darwin":
        raise RuntimeError("app step is currently supported on macOS only.")

    # Launch via LaunchServices first so cold-start apps exist before AppleEvents
    # (Calendar and similar raise -600 when activate races a not-yet-running process).
    _launch_app_via_open(name)
    sleep(0.4)

    last_error = "unknown error"
    for attempt in range(1, 5):
        activate_error = _activate_app_via_applescript(name)
        if activate_error is not None:
            last_error = activate_error
            if _is_app_not_running_error(activate_error):
                _launch_app_via_open(name)
            sleep(0.35 * attempt)
            continue

        sleep(0.3 * attempt)
        frontmost = _frontmost_app_name()
        if _app_names_match(name, frontmost):
            return

        # Soft nudge via System Events when activate returned OK but focus stuck.
        nudge_error = _set_frontmost_via_system_events(name)
        sleep(0.25 * attempt)
        frontmost = _frontmost_app_name()
        if _app_names_match(name, frontmost):
            return

        if frontmost is None:
            if nudge_error:
                last_error = (
                    "could not read frontmost app "
                    f"(System Events query failed / nudge: {nudge_error})."
                )
            else:
                last_error = "could not read frontmost app (System Events query failed)."
        else:
            last_error = f"frontmost app is '{frontmost}'."
        sleep(0.25 * attempt)

    raise RuntimeError(f"Could not focus app '{name}': {last_error}")


def _launch_app_via_open(name: str) -> None:
    import subprocess

    subprocess.run(
        ["open", "-a", name],
        check=False,
        capture_output=True,
        text=True,
    )


def _activate_app_via_applescript(name: str) -> str | None:
    """Activate an app; return stderr on failure, else None."""
    import subprocess

    script = (
        f"with timeout of 5 seconds\n"
        f'  tell application "{name}" to activate\n'
        f"end timeout"
    )
    completed = subprocess.run(
        ["osascript", "-e", script], check=False, capture_output=True, text=True
    )
    if completed.returncode == 0:
        return None
    return completed.stderr.strip() or "unknown error"


def _set_frontmost_via_system_events(name: str) -> str | None:
    """Best-effort set frontmost via System Events; return stderr on failure."""
    import subprocess

    escaped = name.replace("\\", "\\\\").replace('"', '\\"')
    script = f"""
with timeout of 3 seconds
  tell application "System Events"
    if exists (process "{escaped}") then
      set frontmost of process "{escaped}" to true
    end if
  end tell
end timeout
""".strip()
    completed = subprocess.run(
        ["osascript", "-e", script], check=False, capture_output=True, text=True
    )
    if completed.returncode == 0:
        return None
    return completed.stderr.strip() or "unknown error"


def _is_app_not_running_error(message: str) -> bool:
    lowered = message.casefold()
    return "-600" in message or "isn't running" in lowered or "is not running" in lowered


def _app_names_match(expected: str, actual: str | None) -> bool:
    if actual is None:
        return False
    left = expected.strip().casefold()
    right = actual.strip().casefold()
    if left == right:
        return True
    aliases = {
        "system settings": {"system preferences"},
        "system preferences": {"system settings"},
    }
    return right in aliases.get(left, set())


def _textedit_set_front_document_text(text: str, *, font_size: int | None = None) -> None:
    """Set TextEdit front document text via AppleScript (avoids keystroke focus races)."""
    import subprocess
    import sys

    if sys.platform != "darwin":
        raise RuntimeError("applescript type via is currently supported on macOS only.")

    _textedit_close_all_documents()

    escaped = (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "")
    )
    size_block = ""
    if font_size is not None:
        if font_size <= 0:
            raise ValueError("type size must be > 0 when provided.")
        size_block = (
            f"    try\n"
            f"      set size of text of front document to {int(font_size)}\n"
            f"    end try\n"
            f"    try\n"
            f"      set size of every attribute run of text of front document "
            f"to {int(font_size)}\n"
            f"    end try\n"
        )
    script = f"""
with timeout of 8 seconds
  tell application "TextEdit"
    activate
    make new document
    set text of front document to "{escaped}"
{size_block}  end tell
end timeout
""".strip()
    completed = subprocess.run(
        ["osascript", "-e", script], check=False, capture_output=True, text=True
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip() or "unknown error"
        raise RuntimeError(f"Could not set TextEdit document text: {stderr}")
    sleep(0.45)


def _textedit_close_all_documents() -> None:
    """Close every TextEdit document without saving (dismisses save sheets)."""
    import subprocess
    import sys

    if sys.platform != "darwin":
        return

    script = """
with timeout of 8 seconds
  tell application "TextEdit"
    activate
    repeat while (count of documents) > 0
      try
        close front document saving no
      on error
        exit repeat
      end try
    end repeat
  end tell
  tell application "System Events"
    if exists (process "TextEdit") then
      tell process "TextEdit"
        repeat 10 times
          if exists (sheet 1 of window 1) then
            try
              click button "Delete" of sheet 1 of window 1
            end try
            try
              click button "Don't Save" of sheet 1 of window 1
            end try
            delay 0.15
          else
            exit repeat
          end if
        end repeat
      end tell
    end if
  end tell
end timeout
""".strip()
    subprocess.run(["osascript", "-e", script], check=False, capture_output=True, text=True)
    sleep(0.2)


def _frontmost_app_name() -> str | None:
    import subprocess

    command = [
        "osascript",
        "-e",
        (
            "with timeout of 3 seconds\n"
            '  tell application "System Events" to get name of first process '
            "whose frontmost is true\n"
            "end timeout"
        ),
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        return None
    name = completed.stdout.strip()
    return name or None


_TEMPLATE_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}")
_MAX_TEMPLATE_PASSES = 5


def _resolve_templates(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, str):

        def replace(match: re.Match[str]) -> str:
            key = match.group(1)
            if key not in context:
                return match.group(0)
            return str(context[key])

        resolved = value
        # Resolve nested placeholders such as {{token}} -> "OF-{{run_id}}" -> "OF-r123".
        for _ in range(_MAX_TEMPLATE_PASSES):
            updated = _TEMPLATE_PATTERN.sub(replace, resolved)
            if updated == resolved:
                break
            resolved = updated
        return resolved

    if isinstance(value, list):
        return [_resolve_templates(item, context) for item in value]

    if isinstance(value, dict):
        return {key: _resolve_templates(item, context) for key, item in value.items()}

    return value
