"""Built-in verifiers for screenshot and target checks."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import shutil
from typing import Any

from openframe.recognize import Locator
from openframe.types import Frame, Target
from openframe.verify.base import VerifyResult, Verifier
from openframe.window import WindowState, WindowStateProvider, frontmost_window


@dataclass(slots=True)
class MatchBounds:
    """Optional spatial filter for OCR matches within a frame."""

    min_x: int | None = None
    max_x: int | None = None
    min_y: int | None = None
    max_y: int | None = None
    min_x_ratio: float | None = None
    max_x_ratio: float | None = None
    left_of_query: str | None = None
    margin: int = 20


def parse_match_bounds(raw: dict[str, Any] | None) -> MatchBounds | None:
    """Parse optional match bounds from a verify step params mapping."""
    if not raw:
        return None
    if not isinstance(raw, dict):
        raise ValueError("match_bounds must be a mapping.")

    margin = int(raw.get("margin", 20))
    if margin < 0:
        raise ValueError("match_bounds.margin must be >= 0.")

    return MatchBounds(
        min_x=_optional_int(raw.get("min_x")),
        max_x=_optional_int(raw.get("max_x")),
        min_y=_optional_int(raw.get("min_y")),
        max_y=_optional_int(raw.get("max_y")),
        min_x_ratio=_optional_float(raw.get("min_x_ratio")),
        max_x_ratio=_optional_float(raw.get("max_x_ratio")),
        left_of_query=_optional_string(raw.get("left_of_query")),
        margin=margin,
    )


def filter_targets(
    targets: list[Target],
    *,
    frame: Frame,
    bounds: MatchBounds | None,
    locator: Locator,
) -> list[Target]:
    """Keep only targets that satisfy optional spatial bounds."""
    if bounds is None:
        return targets

    filtered = list(targets)
    if bounds.left_of_query:
        anchors = locator.find(frame, bounds.left_of_query, strategy="all")
        if not anchors:
            return []
        boundary_x = max(item.x for item in anchors)
        filtered = [
            item
            for item in filtered
            if (item.x + item.width) <= (boundary_x - bounds.margin)
        ]

    if bounds.min_x_ratio is not None:
        min_x = int(frame.width * bounds.min_x_ratio)
        filtered = [item for item in filtered if item.x >= min_x]
    if bounds.max_x_ratio is not None:
        max_x = int(frame.width * bounds.max_x_ratio)
        filtered = [item for item in filtered if item.x <= max_x]

    if bounds.min_x is not None:
        filtered = [item for item in filtered if item.x >= bounds.min_x]
    if bounds.max_x is not None:
        filtered = [item for item in filtered if (item.x + item.width) <= bounds.max_x]
    if bounds.min_y is not None:
        filtered = [item for item in filtered if item.y >= bounds.min_y]
    if bounds.max_y is not None:
        filtered = [item for item in filtered if (item.y + item.height) <= bounds.max_y]

    return filtered


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class ScreenshotDiffVerifier(Verifier):
    """Check that frame difference ratio is below threshold."""

    name = "verify:diff"

    def __init__(self, *, max_ratio: float = 0.15) -> None:
        self.max_ratio = max_ratio

    def verify(self, *, before: Frame, after: Frame) -> VerifyResult:
        ratio = _image_diff_ratio(before.image_path, after.image_path)
        success = ratio <= self.max_ratio
        message = (
            f"diff ratio {ratio:.4f} <= {self.max_ratio:.4f}"
            if success
            else f"diff ratio {ratio:.4f} > {self.max_ratio:.4f}"
        )
        return VerifyResult(
            verifier=self.name,
            success=success,
            message=message,
            details={"diff_ratio": ratio, "max_ratio": self.max_ratio},
        )


class TextPresenceVerifier(Verifier):
    """Verify text appears or disappears in the after frame."""

    name = "verify:text"

    def __init__(
        self,
        *,
        locator: Locator,
        text: str,
        should_exist: bool,
        bounds: MatchBounds | None = None,
    ) -> None:
        self.locator = locator
        self.text = text
        self.should_exist = should_exist
        self.bounds = bounds

    def verify(self, *, before: Frame, after: Frame) -> VerifyResult:
        _ = before
        matches = self.locator.find(after, self.text, strategy="all")
        bounded = filter_targets(matches, frame=after, bounds=self.bounds, locator=self.locator)
        found = len(bounded) > 0
        success = found if self.should_exist else not found
        mode = "appeared" if self.should_exist else "gone"
        message = f'text "{self.text}" {mode}' if success else f'text "{self.text}" not {mode}'
        return VerifyResult(
            verifier=self.name,
            success=success,
            message=message,
            details={
                "query": self.text,
                "found_count": len(matches),
                "bounded_count": len(bounded),
                "should_exist": self.should_exist,
                "bounds": _bounds_details(self.bounds),
            },
        )


class WindowStateVerifier(Verifier):
    """Verify the frontmost window matches a title fragment or role.

    Phase 11 verifier. Use this instead of fragile OCR tokens when the goal is
    to confirm "this app's window is frontmost" or "we are on this kind of
    window" (for example, a compose window vs. a main reading-pane window).
    """

    name = "verify:window"

    def __init__(
        self,
        *,
        kind: str,
        expected: str,
        state_provider: WindowStateProvider | None = None,
    ) -> None:
        if kind not in {"title_contains", "role", "app"}:
            raise ValueError(f"Unsupported window verify kind '{kind}'.")
        if not expected:
            raise ValueError("Window verify spec requires a non-empty expected value.")
        self.kind = kind
        self.expected = expected
        self._state_provider = state_provider or frontmost_window

    def verify(self, *, before: Frame, after: Frame) -> VerifyResult:
        _ = before, after
        state = self._state_provider()
        success, observed = _check_window_state(state=state, kind=self.kind, expected=self.expected)
        message = (
            f"window {self.kind} matched '{self.expected}'"
            if success
            else f"window {self.kind} did not match '{self.expected}' (observed: {observed})"
        )
        return VerifyResult(
            verifier=self.name,
            success=success,
            message=message,
            details={
                "kind": self.kind,
                "expected": self.expected,
                "observed": observed,
            },
        )


def _check_window_state(
    *, state: WindowState | None, kind: str, expected: str
) -> tuple[bool, str | None]:
    if state is None:
        return False, None
    if kind == "title_contains":
        return expected.lower() in state.title.lower(), state.title
    if kind == "role":
        return expected == state.role, state.role
    if kind == "app":
        return expected == state.app, state.app
    return False, None


class TargetGoneVerifier(Verifier):
    """Verify a target query is no longer found after action."""

    name = "verify:target-gone"

    def __init__(self, *, locator: Locator, query: str) -> None:
        self.locator = locator
        self.query = query

    def verify(self, *, before: Frame, after: Frame) -> VerifyResult:
        _ = before
        matches = self.locator.find(after, self.query, strategy="all")
        success = len(matches) == 0
        return VerifyResult(
            verifier=self.name,
            success=success,
            message=f'target "{self.query}" gone' if success else f'target "{self.query}" still present',
            details={"query": self.query, "found_count": len(matches)},
        )


def write_step_artifacts(
    *,
    run_id: str,
    step_id: str,
    before: Frame,
    after: Frame,
    verification: VerifyResult | None,
) -> Path:
    """Write before/after screenshots and step.json to run directory."""
    step_dir = Path("runs") / run_id / step_id
    step_dir.mkdir(parents=True, exist_ok=True)

    before_path = _copy_if_present(before.image_path, step_dir / "before.png")
    after_path = _copy_if_present(after.image_path, step_dir / "after.png")

    payload: dict[str, Any] = {
        "step_id": step_id,
        "before_frame_path": str(before_path) if before_path else None,
        "after_frame_path": str(after_path) if after_path else None,
    }
    if verification is not None:
        payload["verification"] = asdict(verification)

    import json

    (step_dir / "step.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return step_dir


def _copy_if_present(source: str | None, destination: Path) -> Path | None:
    if not source:
        return None
    src = Path(source)
    if not src.exists():
        return None
    shutil.copy2(src, destination)
    return destination


def _bounds_details(bounds: MatchBounds | None) -> dict[str, Any] | None:
    if bounds is None:
        return None
    return {
        "min_x": bounds.min_x,
        "max_x": bounds.max_x,
        "min_y": bounds.min_y,
        "max_y": bounds.max_y,
        "min_x_ratio": bounds.min_x_ratio,
        "max_x_ratio": bounds.max_x_ratio,
        "left_of_query": bounds.left_of_query,
        "margin": bounds.margin,
    }


def _image_diff_ratio(before_path: str | None, after_path: str | None) -> float:
    if not before_path or not after_path:
        raise ValueError("ScreenshotDiffVerifier requires before and after image paths.")
    try:
        from PIL import Image, ImageChops
    except ImportError:
        before_bytes = Path(before_path).read_bytes()
        after_bytes = Path(after_path).read_bytes()
        return 0.0 if before_bytes == after_bytes else 1.0

    before = Image.open(before_path).convert("RGB")
    after = Image.open(after_path).convert("RGB")
    if before.size != after.size:
        after = after.resize(before.size)

    diff = ImageChops.difference(before, after)
    histogram = diff.histogram()
    max_total = before.size[0] * before.size[1] * 3 * 255
    total = 0
    for idx, count in enumerate(histogram):
        total += (idx % 256) * count
    return float(total) / float(max_total) if max_total > 0 else 0.0
