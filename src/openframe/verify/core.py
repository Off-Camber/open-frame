"""Built-in verifiers for screenshot and target checks."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import shutil
from typing import Any

from openframe.recognize import Locator
from openframe.types import Frame
from openframe.verify.base import VerifyResult, Verifier


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

    def __init__(self, *, locator: Locator, text: str, should_exist: bool) -> None:
        self.locator = locator
        self.text = text
        self.should_exist = should_exist

    def verify(self, *, before: Frame, after: Frame) -> VerifyResult:
        _ = before
        matches = self.locator.find(after, self.text, strategy="all")
        found = len(matches) > 0
        success = found if self.should_exist else not found
        mode = "appeared" if self.should_exist else "gone"
        message = f'text "{self.text}" {mode}' if success else f'text "{self.text}" not {mode}'
        return VerifyResult(
            verifier=self.name,
            success=success,
            message=message,
            details={"query": self.text, "found_count": len(matches), "should_exist": self.should_exist},
        )


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
