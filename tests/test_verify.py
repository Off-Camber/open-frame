from __future__ import annotations

from pathlib import Path

from openframe.types import Frame, Target
from openframe.verify import ScreenshotDiffVerifier, TargetGoneVerifier, TextPresenceVerifier


def _write_ppm(path: Path, rgb: tuple[int, int, int]) -> None:
    path.write_text(f"P3\n1 1\n255\n{rgb[0]} {rgb[1]} {rgb[2]}\n", encoding="utf-8")


class StubLocator:
    def __init__(self, count: int) -> None:
        self.count = count

    def find(self, frame: Frame, query: str, strategy: str = "all") -> list[Target]:
        _ = frame, query, strategy
        return [
            Target(x=1, y=1, width=10, height=10, confidence=0.8, source="stub")
            for _ in range(self.count)
        ]


def test_screenshot_diff_verifier_passes_identical_images(tmp_path: Path) -> None:
    before = tmp_path / "before.ppm"
    after = tmp_path / "after.ppm"
    _write_ppm(before, (10, 10, 10))
    _write_ppm(after, (10, 10, 10))
    verifier = ScreenshotDiffVerifier(max_ratio=0.01)

    result = verifier.verify(
        before=Frame(width=1, height=1, scale_factor=1.0, source="screen", image_path=str(before)),
        after=Frame(width=1, height=1, scale_factor=1.0, source="screen", image_path=str(after)),
    )

    assert result.success is True


def test_text_presence_verifier_reports_gone() -> None:
    verifier = TextPresenceVerifier(locator=StubLocator(0), text="Save", should_exist=False)
    frame = Frame(width=1, height=1, scale_factor=1.0, source="screen")
    result = verifier.verify(before=frame, after=frame)
    assert result.success is True


def test_target_gone_verifier_fails_when_target_still_found() -> None:
    verifier = TargetGoneVerifier(locator=StubLocator(1), query="Dialog")
    frame = Frame(width=1, height=1, scale_factor=1.0, source="screen")
    result = verifier.verify(before=frame, after=frame)
    assert result.success is False
