#!/usr/bin/env python3
"""Run repeatability benchmarks against the MCP run_flow tool."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REQUIRED_ENVELOPE_KEYS = {"ok", "tool", "run_id", "data", "error", "artifacts"}


@dataclass
class RunSample:
    flow_path: str
    run_id: str
    repetition: int
    elapsed_ms: int
    exit_code: int
    ok: bool
    success: bool
    error_code: str | None
    error_message: str | None
    artifacts: dict[str, Any]


def _resolve_runner() -> list[str]:
    if _is_executable_on_path("open-frame"):
        return ["open-frame"]
    if Path(".venv311/bin/python").exists():
        return [".venv311/bin/python", "-m", "openframe.cli"]
    return [sys.executable, "-m", "openframe.cli"]


def _is_executable_on_path(name: str) -> bool:
    completed = subprocess.run(["which", name], check=False, capture_output=True, text=True)
    return completed.returncode == 0


def _call_run_flow(
    *,
    runner: list[str],
    flow_path: str,
    run_id: str,
    dry_run: bool,
) -> tuple[int, dict[str, Any], int]:
    args_payload = {"flow_path": flow_path, "dry_run": dry_run, "run_id": run_id}
    command = [
        *runner,
        "mcp",
        "call",
        "run_flow",
        "--args-json",
        json.dumps(args_payload),
    ]

    started = time.perf_counter()
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    if completed.returncode not in {0, 1}:
        raise RuntimeError(
            f"run_flow command failed with exit code {completed.returncode}\n"
            f"command: {' '.join(command)}\n"
            f"stderr: {completed.stderr.strip()}"
        )

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"run_flow output was not valid JSON.\n"
            f"command: {' '.join(command)}\n"
            f"stdout: {completed.stdout[:800]}\n"
            f"stderr: {completed.stderr[:800]}"
        ) from error

    missing = REQUIRED_ENVELOPE_KEYS - set(payload.keys())
    if missing:
        raise RuntimeError(f"Missing MCP envelope keys: {sorted(missing)}")
    return completed.returncode, payload, elapsed_ms


def _calc_median(values: list[int]) -> int:
    if not values:
        return 0
    return int(statistics.median(values))


def _calc_p95(values: list[int]) -> int:
    if not values:
        return 0
    sorted_values = sorted(values)
    # Nearest-rank percentile so small samples still surface worst-case tails.
    index = max(0, math.ceil(0.95 * len(sorted_values)) - 1)
    return int(sorted_values[index])


def _write_reports(
    *,
    out_dir: Path,
    stamp: str,
    mode: str,
    repetitions: int,
    flows: list[str],
    samples: list[RunSample],
) -> tuple[Path, Path]:
    json_path = out_dir / f"mcp-repeatability-{stamp}.json"
    md_path = out_dir / f"mcp-repeatability-{stamp}.md"

    elapsed_values = [item.elapsed_ms for item in samples]
    total = len(samples)
    pass_count = sum(1 for item in samples if item.success)
    pass_rate = (pass_count / total * 100.0) if total else 0.0

    by_flow: dict[str, dict[str, Any]] = {}
    for flow in flows:
        flow_samples = [item for item in samples if item.flow_path == flow]
        flow_total = len(flow_samples)
        flow_pass = sum(1 for item in flow_samples if item.success)
        by_flow[flow] = {
            "runs": flow_total,
            "passes": flow_pass,
            "pass_rate_percent": round((flow_pass / flow_total * 100.0) if flow_total else 0.0, 2),
            "median_elapsed_ms": _calc_median([item.elapsed_ms for item in flow_samples]),
            "p95_elapsed_ms": _calc_p95([item.elapsed_ms for item in flow_samples]),
        }

    payload = {
        "benchmark": "mcp_repeatability",
        "timestamp_utc": stamp,
        "mode": mode,
        "repetitions_per_flow": repetitions,
        "flows": flows,
        "summary": {
            "total_runs": total,
            "passes": pass_count,
            "pass_rate_percent": round(pass_rate, 2),
            "median_elapsed_ms": _calc_median(elapsed_values),
            "p95_elapsed_ms": _calc_p95(elapsed_values),
        },
        "by_flow": by_flow,
        "samples": [
            {
                "flow_path": item.flow_path,
                "run_id": item.run_id,
                "repetition": item.repetition,
                "elapsed_ms": item.elapsed_ms,
                "exit_code": item.exit_code,
                "ok": item.ok,
                "success": item.success,
                "error_code": item.error_code,
                "error_message": item.error_message,
                "artifacts": item.artifacts,
            }
            for item in samples
        ],
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        f"# MCP repeatability benchmark {stamp}",
        "",
        f"- Mode: `{mode}`",
        f"- Repetitions per flow: `{repetitions}`",
        f"- Flows: `{len(flows)}`",
        f"- Total runs: `{total}`",
        f"- Pass rate: `{round(pass_rate, 2)}%`",
        f"- Median elapsed: `{_calc_median(elapsed_values)} ms`",
        f"- P95 elapsed: `{_calc_p95(elapsed_values)} ms`",
        "",
        "## Per-flow metrics",
        "",
        "| Flow | Runs | Passes | Pass rate | Median ms | P95 ms |",
        "|------|------|--------|-----------|-----------|--------|",
    ]
    for flow in flows:
        metrics = by_flow[flow]
        lines.append(
            f"| `{flow}` | {metrics['runs']} | {metrics['passes']} | "
            f"{metrics['pass_rate_percent']}% | {metrics['median_elapsed_ms']} | {metrics['p95_elapsed_ms']} |"
        )

    lines.extend(
        [
            "",
            "## Sample results",
            "",
            "| Flow | Repetition | Run ID | Exit | OK | Success | Elapsed ms | Error code |",
            "|------|------------|--------|------|----|---------|------------|------------|",
        ]
    )
    for item in samples:
        lines.append(
            f"| `{item.flow_path}` | {item.repetition} | `{item.run_id}` | {item.exit_code} | "
            f"{str(item.ok).lower()} | {str(item.success).lower()} | {item.elapsed_ms} | `{item.error_code or ''}` |"
        )

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark MCP run_flow repeatability and runtime.")
    parser.add_argument(
        "--flow",
        dest="flows",
        action="append",
        required=True,
        help="Flow path to benchmark. Repeat this flag for multiple flows.",
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        default=5,
        help="Number of runs per flow (default: 5).",
    )
    parser.add_argument(
        "--mode",
        choices=("dry-run", "live"),
        default="dry-run",
        help="Run mode (default: dry-run).",
    )
    parser.add_argument(
        "--run-id-prefix",
        default="mcp-bench",
        help="Prefix for generated run IDs.",
    )
    parser.add_argument(
        "--out-dir",
        default="docs/benchmarks",
        help="Directory to write benchmark reports.",
    )
    args = parser.parse_args()

    if args.repetitions <= 0:
        raise ValueError("--repetitions must be greater than 0.")

    flow_paths = [str(Path(item).expanduser()) for item in args.flows]
    for flow in flow_paths:
        if not Path(flow).exists():
            raise ValueError(f"Flow path does not exist: {flow}")

    runner = _resolve_runner()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dry_run = args.mode == "dry-run"

    samples: list[RunSample] = []
    for flow in flow_paths:
        flow_slug = Path(flow).parent.name.replace("_", "-")
        for repetition in range(1, args.repetitions + 1):
            run_id = f"{args.run_id_prefix}-{flow_slug}-{stamp}-{repetition:02d}"
            exit_code, payload, elapsed_ms = _call_run_flow(
                runner=runner,
                flow_path=flow,
                run_id=run_id,
                dry_run=dry_run,
            )
            error_obj = payload.get("error") or {}
            success = bool(payload.get("ok")) and bool(payload.get("data", {}).get("success"))
            samples.append(
                RunSample(
                    flow_path=flow,
                    run_id=run_id,
                    repetition=repetition,
                    elapsed_ms=elapsed_ms,
                    exit_code=exit_code,
                    ok=bool(payload.get("ok")),
                    success=success,
                    error_code=error_obj.get("code"),
                    error_message=error_obj.get("message"),
                    artifacts=payload.get("artifacts") or {},
                )
            )

    json_path, md_path = _write_reports(
        out_dir=out_dir,
        stamp=stamp,
        mode=args.mode,
        repetitions=args.repetitions,
        flows=flow_paths,
        samples=samples,
    )

    total = len(samples)
    pass_count = sum(1 for item in samples if item.success)
    pass_rate = (pass_count / total * 100.0) if total else 0.0
    print(f"benchmark complete: {pass_count}/{total} successful ({round(pass_rate, 2)}%)")
    print(f"json report: {json_path}")
    print(f"markdown report: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
