"""Programmatic Session API for SDK-style automation usage."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from openframe.act import Actuator, ClickAnchor, ClickKind
from openframe.capture import screen
from openframe.recognize import (
    Locator,
    LocatorStrategy,
    Recognizer,
)
from openframe.recognize.coords import select_target
from openframe.recognize.defaults import build_default_locator
from openframe.recognize.match import ensure_actionable_match_count, explicit_selector
from openframe.types import Frame, StepResult, Target


@dataclass(slots=True)
class Session:
    """Embeddable automation session with helpers for find/click/run."""

    run_id: str = field(default_factory=lambda: datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"))
    dry_run: bool = False
    results: list[StepResult] = field(default_factory=list)
    _locator: Locator | None = field(default=None, init=False, repr=False)
    _actuator: Actuator = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._actuator = Actuator(dry_run=self.dry_run)

    def record(self, result: StepResult) -> None:
        """Append a step result to this session's run history."""
        self.results.append(result)

    def register_recognizer(self, recognizer: Recognizer) -> None:
        """Register a custom recognizer plugin for subsequent find calls."""
        self._ensure_locator().register(recognizer)

    def find(
        self,
        query: str,
        *,
        frame: Frame | None = None,
        strategy: LocatorStrategy = "first",
        options: dict[str, Any] | None = None,
    ) -> list[Target]:
        """Locate targets by query using configured recognizers."""
        active_frame = frame or screen()
        return self._ensure_locator().find(
            frame=active_frame,
            query=query,
            strategy=strategy,
            options=options,
        )

    def click(
        self,
        query: str,
        *,
        frame: Frame | None = None,
        anchor: ClickAnchor = "center",
        kind: ClickKind = "click",
        selector: str | None = None,
        expect_one: bool = False,
        options: dict[str, Any] | None = None,
    ) -> tuple[int, int]:
        """Find a target by query and click it.

        Fails closed when zero targets match, or when multiple targets match
        without an explicit ``selector`` / ``expect_one`` policy.
        """
        active_frame = frame or screen()
        targets = self.find(query, frame=active_frame, strategy="all", options=options)
        resolved_selector = explicit_selector(selector)
        ensure_actionable_match_count(
            query=query,
            match_count=len(targets),
            selector=resolved_selector,
            expect_one=expect_one,
        )
        selected = select_target(
            targets=targets,
            selector=resolved_selector or "first",
            scale_factor=active_frame.scale_factor,
        )
        return self._actuator.click_target(
            selected, anchor=anchor, kind=kind, scale_factor=active_frame.scale_factor
        )

    def run(self, steps: list[dict[str, Any]]) -> list[StepResult]:
        """Execute a list of in-memory steps via the flow runner."""
        from openframe.flow import Flow, FlowStep
        from openframe.runner import FlowRunner

        flow_steps: list[FlowStep] = []
        for idx, step in enumerate(steps):
            if not isinstance(step, dict):
                raise TypeError(f"Step at index {idx} must be a mapping.")
            kind = str(step.get("kind", "")).strip()
            if not kind:
                raise ValueError(f"Step at index {idx} is missing 'kind'.")
            step_id = str(step.get("id", f"step-{idx + 1}"))
            params = {key: value for key, value in step.items() if key not in {"id", "kind"}}
            flow_steps.append(FlowStep(id=step_id, kind=kind, params=params))

        flow = Flow(name=f"session-{self.run_id}", steps=flow_steps)
        run_session = FlowRunner(dry_run=self.dry_run).run(flow, run_id=self.run_id)
        self.results.extend(run_session.results)
        return run_session.results

    def _ensure_locator(self) -> Locator:
        if self._locator is None:
            self._locator = build_default_locator()
        return self._locator
