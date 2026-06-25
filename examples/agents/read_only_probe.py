"""Reference agent task (Phase A.3): safe, read-only screen probe.

This script demonstrates a real AgentRunner + AnthropicProvider loop without
performing UI actions. The default task asks the model to capture the screen,
search for one phrase, and report what it found.
"""

from __future__ import annotations

import argparse
from typing import Any

from openframe import AgentRunner, AnthropicProvider

DEFAULT_TASK = (
    "Capture the current screen, check whether the phrase 'Send' appears, and "
    "summarize the result. Do not click, type, press keys, or run flows."
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a safe read-only agent probe using AnthropicProvider."
    )
    parser.add_argument(
        "--task",
        default=DEFAULT_TASK,
        help="Natural-language task for the agent (defaults to a read-only probe).",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=8,
        help="Maximum planning steps before stopping (default: 8).",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Optional model override (else OPENFRAME_AGENT_MODEL/default model).",
    )
    return parser


def _step_status(step: dict[str, Any] | None) -> str:
    if not step:
        return "no-observation"
    if step.get("ok") is True:
        return "ok"
    if step.get("error"):
        code = step["error"].get("code", "unknown")
        return f"error:{code}"
    return "unknown"


def main() -> int:
    args = _parser().parse_args()
    provider = AnthropicProvider(model=args.model)
    runner = AgentRunner(provider=provider, max_steps=args.max_steps)

    result = runner.run(args.task)
    print(f"success={result.success} stop={result.stop_reason}")
    if result.final_message:
        print(f"final: {result.final_message}")
    for idx, step in enumerate(result.steps, start=1):
        tool_call = step.action.tool_call
        if tool_call is None:
            continue
        status = _step_status(step.observation)
        print(f"{idx:02d}. {tool_call.tool}({tool_call.args}) -> {status}")
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
