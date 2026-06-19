"""Minimal pilot showing MCP-style Open Frame calls."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REQUIRED_KEYS = {"ok", "tool", "run_id", "data", "error", "artifacts"}


def _run(command: list[str]) -> dict:
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode not in {0, 1}:
        raise RuntimeError(f"Command failed: {' '.join(command)}\n{completed.stderr}")
    payload = json.loads(completed.stdout)
    missing = REQUIRED_KEYS - set(payload.keys())
    if missing:
        raise RuntimeError(f"Missing envelope keys: {sorted(missing)}")
    return payload


def _print_summary(title: str, payload: dict) -> None:
    status = "ok" if payload["ok"] else "error"
    print(f"{title}: {status} ({payload['tool']})")


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    flow_path = repo_root / "examples" / "flows" / "outlook-new-email" / "flow.yaml"
    run_id = "mcp-pilot-dry-run"

    tools = _run(["open-frame", "mcp", "list-tools", "--json"])
    print(f"available tools: {len(tools['tools'])}")

    capture_payload = _run(
        [
            "open-frame",
            "mcp",
            "call",
            "capture",
            "--args-json",
            json.dumps({"mode": "screen"}),
        ]
    )
    _print_summary("capture", capture_payload)

    find_payload = _run(
        [
            "open-frame",
            "mcp",
            "call",
            "find",
            "--args-json",
            json.dumps({"query": "New", "strategy": "first"}),
        ]
    )
    _print_summary("find", find_payload)

    click_payload = _run(
        [
            "open-frame",
            "mcp",
            "call",
            "click",
            "--args-json",
            json.dumps({"query": "New", "dry_run": True, "run_id": run_id}),
        ]
    )
    _print_summary("click", click_payload)

    run_payload = _run(
        [
            "open-frame",
            "mcp",
            "call",
            "run_flow",
            "--args-json",
            json.dumps({"flow_path": str(flow_path), "dry_run": True, "run_id": run_id}),
        ]
    )
    _print_summary("run_flow", run_payload)

    artifacts_payload = _run(
        [
            "open-frame",
            "mcp",
            "call",
            "get_run_artifacts",
            "--args-json",
            json.dumps({"run_id": run_id}),
        ]
    )
    _print_summary("get_run_artifacts", artifacts_payload)


if __name__ == "__main__":
    main()

