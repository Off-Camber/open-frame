"""Flow runner for executing declarative steps."""

from __future__ import annotations

import re
from time import monotonic, perf_counter, sleep
from typing import Any
import webbrowser

from openframe.act import Actuator
from openframe.capture import screen
from openframe.flow import Flow, FlowStep
from openframe.recognize import Locator, MacOSA11yRecognizer, TesseractRecognizer
from openframe.session import Session
from openframe.types import StepResult, Target
from openframe.verify import (
    ScreenshotDiffVerifier,
    TargetGoneVerifier,
    TextPresenceVerifier,
    VerifyResult,
    write_step_artifacts,
)


class FlowRunner:
    """Executes a flow and records step outcomes."""

    def __init__(self, *, dry_run: bool = False) -> None:
        self.dry_run = dry_run

    def run(self, flow: Flow, *, run_id: str) -> Session:
        session = Session(run_id=run_id)
        locator = Locator([MacOSA11yRecognizer(), TesseractRecognizer()])
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
                details.update(self._execute_step(step=resolved_step, locator=locator, actuator=actuator))
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

    def _execute_step(self, *, step: FlowStep, locator: Locator, actuator: Actuator) -> dict[str, Any]:
        kind = step.kind
        if kind == "wait":
            milliseconds = int(step.params.get("ms", 0))
            actuator.wait_ms(milliseconds)
            return {"wait_ms": milliseconds}

        if kind == "click":
            query = str(step.params.get("query", "")).strip()
            if not query:
                raise ValueError(f"Step '{step.id}' click requires 'query'.")
            timeout_ms = _coerce_timeout_ms(step=step, default_ms=3000)
            poll_ms = _coerce_poll_ms(step=step, default_ms=200)
            targets = _find_targets_with_retry(
                locator=locator,
                query=query,
                strategy="first",
                timeout_ms=timeout_ms,
                poll_ms=poll_ms,
            )
            if not targets:
                raise ValueError(f"Step '{step.id}' could not find target for query '{query}'.")

            anchor = str(step.params.get("anchor", "center"))
            click_kind = str(step.params.get("click_kind", "click"))
            if anchor not in {"center", "top-left", "top-right", "bottom-left", "bottom-right"}:
                raise ValueError(f"Step '{step.id}' has invalid anchor '{anchor}'.")
            if click_kind not in {"click", "double", "right"}:
                raise ValueError(f"Step '{step.id}' has invalid click_kind '{click_kind}'.")
            actuator.click_target(targets[0], anchor=anchor, kind=click_kind)
            return {
                "query": query,
                "click_kind": click_kind,
                "anchor": anchor,
                "timeout_ms": timeout_ms,
                "poll_ms": poll_ms,
            }

        if kind == "find":
            query = str(step.params.get("query", "")).strip()
            if not query:
                raise ValueError(f"Step '{step.id}' find requires 'query'.")
            timeout_ms = _coerce_timeout_ms(step=step, default_ms=3000)
            poll_ms = _coerce_poll_ms(step=step, default_ms=200)
            targets = _find_targets_with_retry(
                locator=locator,
                query=query,
                strategy="all",
                timeout_ms=timeout_ms,
                poll_ms=poll_ms,
            )
            if not targets:
                raise ValueError(f"Step '{step.id}' did not find query '{query}'.")
            return {"query": query, "matches": len(targets), "timeout_ms": timeout_ms, "poll_ms": poll_ms}

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
            actuator.type_text(text, interval=interval)
            return {"text_length": len(text)}

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
            timeout_ms = _coerce_timeout_ms(step=step, default_ms=3000)
            poll_ms = _coerce_poll_ms(step=step, default_ms=200)
            targets = _find_targets_with_retry(
                locator=locator,
                query=query,
                strategy="first",
                timeout_ms=timeout_ms,
                poll_ms=poll_ms,
            )
            if not targets:
                raise ValueError(f"Step '{step.id}' could not find fill target '{query}'.")
            actuator.click_target(targets[0], anchor="center", kind="click")
            if bool(step.params.get("clear", False)):
                actuator.key_combo("command", "a")
            actuator.type_text(text)
            return {"query": query, "text_length": len(text), "timeout_ms": timeout_ms, "poll_ms": poll_ms}

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
            result = _run_verify_specs(
                verify_specs=verify_specs,
                locator=locator,
                timeout_ms=timeout_ms,
                poll_ms=poll_ms,
            )
            if not result.success:
                raise ValueError(result.message)
            return {
                "verification": {"verifier": result.verifier, "message": result.message},
                "timeout_ms": timeout_ms,
                "poll_ms": poll_ms,
            }

        raise ValueError(f"Unsupported flow step kind '{kind}' in step '{step.id}'.")


def _run_verify_specs(
    *,
    verify_specs: list[str],
    locator: Locator,
    timeout_ms: int,
    poll_ms: int,
) -> VerifyResult:
    verifiers = [_parse_verifier_spec(raw_spec=raw_spec, locator=locator) for raw_spec in verify_specs]
    if not verifiers:
        raise ValueError("At least one verify spec is required.")

    deadline = monotonic() + (timeout_ms / 1000.0)
    last: VerifyResult | None = None

    while True:
        frame = screen()
        all_success = True
        for verifier in verifiers:
            result = verifier.verify(before=frame, after=frame)
            last = result
            if not result.success:
                all_success = False
                break

        if all_success:
            return last

        if monotonic() >= deadline:
            return last

        sleep(poll_ms / 1000.0)


def _find_targets_with_retry(
    *,
    locator: Locator,
    query: str,
    strategy: str,
    timeout_ms: int,
    poll_ms: int,
) -> list[Target]:
    deadline = monotonic() + (timeout_ms / 1000.0)
    while True:
        targets = locator.find(screen(), query, strategy=strategy)
        if targets:
            return targets
        if monotonic() >= deadline:
            return []
        sleep(poll_ms / 1000.0)


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


def _parse_verifier_spec(*, raw_spec: str, locator: Locator):
    if ":" not in raw_spec:
        raise ValueError(f"Invalid verify spec: {raw_spec}")
    key, value = raw_spec.split(":", 1)
    value = value.strip().strip('"').strip("'")

    if key == "text-gone":
        return TextPresenceVerifier(locator=locator, text=value, should_exist=False)
    if key == "text-appeared":
        return TextPresenceVerifier(locator=locator, text=value, should_exist=True)
    if key == "target-gone":
        return TargetGoneVerifier(locator=locator, query=value)
    if key == "diff":
        return ScreenshotDiffVerifier(max_ratio=float(value))

    raise ValueError(f"Unsupported verify spec: {raw_spec}")


def _focus_app(name: str) -> None:
    import subprocess
    import sys

    if sys.platform != "darwin":
        raise RuntimeError("app step is currently supported on macOS only.")

    command = ["osascript", "-e", f'tell application "{name}" to activate']
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        stderr = completed.stderr.strip() or "unknown error"
        raise RuntimeError(f"Could not focus app '{name}': {stderr}")


_TEMPLATE_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}")


def _resolve_templates(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, str):
        def replace(match: re.Match[str]) -> str:
            key = match.group(1)
            if key not in context:
                return match.group(0)
            return str(context[key])

        return _TEMPLATE_PATTERN.sub(replace, value)

    if isinstance(value, list):
        return [_resolve_templates(item, context) for item in value]

    if isinstance(value, dict):
        return {key: _resolve_templates(item, context) for key, item in value.items()}

    return value
