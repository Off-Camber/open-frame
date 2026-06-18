"""Minimal custom recognizer registration example."""

from __future__ import annotations

from openframe import Session
from openframe.recognize import Recognizer, RecognizerResult
from openframe.types import Target


class DemoRecognizer(Recognizer):
    """Simple recognizer that emits one target for demo-prefixed queries."""

    name = "demo-recognizer"

    def find(self, frame, query, options=None):
        _ = frame, options
        if not query.lower().startswith("demo"):
            return RecognizerResult(recognizer=self.name, targets=[])

        return RecognizerResult(
            recognizer=self.name,
            targets=[
                Target(
                    x=100,
                    y=80,
                    width=180,
                    height=48,
                    confidence=0.99,
                    source=self.name,
                    text=query,
                    label="Demo Target",
                )
            ],
        )


def main() -> None:
    session = Session(dry_run=True)
    session.register_recognizer(DemoRecognizer(priority=5))
    targets = session.find("demo send")
    print(f"Found {len(targets)} target(s)")
    if targets:
        print(targets[0])


if __name__ == "__main__":
    main()
