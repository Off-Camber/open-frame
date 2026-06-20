from __future__ import annotations

from pathlib import Path

from openframe.types import Frame, Target
from openframe.verify import ScreenshotDiffVerifier, TargetGoneVerifier, TextPresenceVerifier
from openframe.verify.core import MatchBounds, filter_targets


def _write_ppm(path: Path, rgb: tuple[int, int, int]) -> None:
    path.write_text(f"P3\n1 1\n255\n{rgb[0]} {rgb[1]} {rgb[2]}\n", encoding="utf-8")


class StubLocator:
    def __init__(self, count: int, *, targets: list[Target] | None = None) -> None:
        self.count = count
        self.targets = targets

    def find(self, frame: Frame, query: str, strategy: str = "all") -> list[Target]:
        _ = frame, query, strategy
        if self.targets is not None:
            return list(self.targets)
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


def test_text_presence_verifier_respects_left_of_query_bounds() -> None:
    frame = Frame(width=1000, height=800, scale_factor=1.0, source="screen")
    compose_marker = Target(x=900, y=100, width=40, height=10, confidence=0.9, source="stub", text="OFSENDZXQ")
    list_marker = Target(x=300, y=200, width=40, height=10, confidence=0.9, source="stub", text="OFSENDZXQ")
    from_anchor = Target(x=850, y=80, width=30, height=10, confidence=0.9, source="stub", text="From")

    locator = StubLocator(
        0,
        targets=[compose_marker, list_marker, from_anchor],
    )

    def find(frame: Frame, query: str, strategy: str = "all") -> list[Target]:
        _ = frame, strategy
        if query == "From":
            return [from_anchor]
        if query == "OFSENDZXQ":
            return [compose_marker, list_marker]
        return []

    locator.find = find  # type: ignore[method-assign]

    unbounded = TextPresenceVerifier(locator=locator, text="OFSENDZXQ", should_exist=True)
    assert unbounded.verify(before=frame, after=frame).success is True

    bounded = TextPresenceVerifier(
        locator=locator,
        text="OFSENDZXQ",
        should_exist=True,
        bounds=MatchBounds(left_of_query="From", margin=20),
    )
    result = bounded.verify(before=frame, after=frame)
    assert result.success is True
    assert result.details["bounded_count"] == 1


def test_filter_targets_excludes_matches_right_of_anchor() -> None:
    frame = Frame(width=1000, height=800, scale_factor=1.0, source="screen")
    left = Target(x=100, y=100, width=10, height=10, confidence=0.9, source="stub")
    right = Target(x=900, y=100, width=10, height=10, confidence=0.9, source="stub")
    anchor = Target(x=700, y=80, width=20, height=10, confidence=0.9, source="stub", text="From")

    locator = StubLocator(0, targets=[anchor])

    def find(frame: Frame, query: str, strategy: str = "all") -> list[Target]:
        _ = frame, strategy
        if query == "From":
            return [anchor]
        return []

    locator.find = find  # type: ignore[method-assign]

    filtered = filter_targets(
        [left, right],
        frame=frame,
        bounds=MatchBounds(left_of_query="From", margin=10),
        locator=locator,
    )
    assert filtered == [left]
