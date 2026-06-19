"""Command-line interface for Open Frame."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path

from openframe.act import ActError, Actuator
from openframe.capture import CaptureError, list_displays, list_windows, region, screen, window
from openframe.flow import load_flow
from openframe.integrations.mcp import call_mcp_tool, list_mcp_tools
from openframe.recognize import Locator, MacOSA11yRecognizer, TesseractRecognizer, draw_debug_overlay
from openframe.runner import FlowRunner
from openframe.types import Frame
from openframe.verify import (
    ScreenshotDiffVerifier,
    TargetGoneVerifier,
    TextPresenceVerifier,
    VerifyResult,
    Verifier,
    write_step_artifacts,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="open-frame")
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture_parser = subparsers.add_parser("capture", help="Capture display or window")
    capture_parser.add_argument("--out", type=Path, required=True, help="Output PNG path")
    capture_parser.add_argument("--window-title", type=str, help="Capture first visible matching title")
    capture_parser.add_argument("--window-id", type=int, help="Capture a visible window by id")
    capture_parser.add_argument("--x", type=int, help="Region left coordinate (screen space)")
    capture_parser.add_argument("--y", type=int, help="Region top coordinate (screen space)")
    capture_parser.add_argument("--width", type=int, help="Region width")
    capture_parser.add_argument("--height", type=int, help="Region height")

    list_parser = subparsers.add_parser("list-windows", help="List visible windows")
    list_parser.add_argument("--displays", action="store_true", help="Also show display info")
    list_parser.add_argument("--json", action="store_true", help="Output full JSON objects")

    find_parser = subparsers.add_parser("find", help="Find text on a frame using OCR")
    find_parser.add_argument("query", type=str, help="Text query to find")
    find_parser.add_argument("--frame", type=Path, help="Use an existing PNG frame path")
    find_parser.add_argument("--strategy", choices=("first", "all"), default="first")
    find_parser.add_argument("--overlay-out", type=Path, help="Write debug overlay image with matched boxes")
    find_parser.add_argument("--json", action="store_true", help="Output JSON")

    click_parser = subparsers.add_parser("click", help="Find and click a target")
    click_parser.add_argument("query", type=str, help="Text query to find before clicking")
    click_parser.add_argument("--frame", type=Path, help="Use an existing frame path for recognition")
    click_parser.add_argument(
        "--anchor",
        choices=("center", "top-left", "top-right", "bottom-left", "bottom-right"),
        default="center",
    )
    click_parser.add_argument("--kind", choices=("click", "double", "right"), default="click")
    click_parser.add_argument("--dry-run", action="store_true", help="Log click point without clicking")
    click_parser.add_argument(
        "--verify",
        action="append",
        default=[],
        help='Verification spec: text-gone:"Save", text-appeared:"Done", target-gone:"Dialog", diff:0.15',
    )
    click_parser.add_argument("--run-id", type=str, help="Run id for artifacts (defaults to timestamp)")
    click_parser.add_argument("--json", action="store_true", help="Output JSON")

    run_parser = subparsers.add_parser("run", help="Execute a YAML flow")
    run_parser.add_argument("flow_path", type=Path, help="Path to flow YAML")
    run_parser.add_argument("--run-id", type=str, help="Run id for artifacts (defaults to timestamp)")
    run_parser.add_argument("--dry-run", action="store_true", help="Run without sending input actions")
    run_parser.add_argument("--json", action="store_true", help="Output JSON")

    mcp_parser = subparsers.add_parser("mcp", help="MCP-compatible tool surface")
    mcp_subparsers = mcp_parser.add_subparsers(dest="mcp_command", required=True)
    mcp_list_parser = mcp_subparsers.add_parser("list-tools", help="List available MCP tools")
    mcp_list_parser.add_argument("--json", action="store_true", help="Output JSON")
    mcp_call_parser = mcp_subparsers.add_parser("call", help="Call one MCP tool")
    mcp_call_parser.add_argument("tool", type=str, help="Tool name")
    mcp_call_parser.add_argument(
        "--args-json",
        type=str,
        default="{}",
        help="JSON object for tool arguments",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "capture":
        region_values = (args.x, args.y, args.width, args.height)
        has_any_region = any(value is not None for value in region_values)
        has_complete_region = all(value is not None for value in region_values)

        if args.window_title and args.window_id is not None:
            parser.error("Use only one of --window-title or --window-id.")
        if has_any_region and not has_complete_region:
            parser.error("Region capture requires all of --x, --y, --width, and --height.")
        if has_any_region and (args.window_title or args.window_id is not None):
            parser.error("Choose either window capture args or region args, not both.")

        try:
            if has_complete_region:
                frame = region(
                    x=args.x,
                    y=args.y,
                    width=args.width,
                    height=args.height,
                    out_path=args.out,
                )
            elif args.window_title or args.window_id is not None:
                frame = window(
                    title=args.window_title,
                    window_id=args.window_id,
                    out_path=args.out,
                )
            else:
                frame = screen(out_path=args.out)
        except CaptureError as error:
            parser.error(str(error))
        print(frame.image_path)
        return 0

    if args.command == "list-windows":
        try:
            windows = list_windows()
            displays = list_displays() if args.displays else []
        except CaptureError as error:
            parser.error(str(error))
        if args.json:
            payload: dict[str, object]
            if args.displays:
                payload = {"windows": windows, "displays": displays}
            else:
                payload = {"windows": windows}
            print(json.dumps(payload, indent=2))
            return 0
        for item in windows:
            print(f'{item["id"]}\t{item["owner"]}\t{item["title"]}')
        if args.displays:
            print("-- displays --")
            for item in displays:
                print(f'{item["name"]}\t{item["resolution"]}\tretina={item["retina"]}\tmain={item["main"]}')
        return 0

    if args.command == "find":
        try:
            frame = _resolve_find_frame(args.frame)
            locator = Locator([MacOSA11yRecognizer(), TesseractRecognizer()])
            targets = locator.find(frame=frame, query=args.query, strategy=args.strategy)
            overlay_path = _maybe_write_overlay(frame=frame, targets=targets, out_path=args.overlay_out)
        except (CaptureError, RuntimeError, ValueError) as error:
            parser.error(str(error))
        if args.json:
            payload = {
                "query": args.query,
                "source": frame.source,
                "count": len(targets),
                "targets": [asdict(item) for item in targets],
            }
            if overlay_path is not None:
                payload["overlay_path"] = str(overlay_path)
            print(json.dumps(payload, indent=2))
            return 0
        for item in targets:
            text = item.text or ""
            print(f"{item.x},{item.y},{item.width},{item.height}\tconf={item.confidence:.2f}\t{text}")
        if overlay_path is not None:
            print(str(overlay_path))
        return 0

    if args.command == "click":
        try:
            frame = _resolve_find_frame(args.frame)
            locator = Locator([MacOSA11yRecognizer(), TesseractRecognizer()])
            targets = locator.find(frame=frame, query=args.query, strategy="first")
            if not targets:
                raise ValueError(f'No target found for query "{args.query}".')

            actuator = Actuator(dry_run=args.dry_run)
            point = actuator.click_target(targets[0], anchor=args.anchor, kind=args.kind)
            if args.dry_run and not args.verify:
                after_frame = frame
            else:
                after_frame = screen()
            verification_result = _run_verification_specs(
                verify_specs=args.verify,
                before=frame,
                after=after_frame,
                locator=locator,
            )
            run_id = args.run_id or _default_run_id()
            artifact_dir = write_step_artifacts(
                run_id=run_id,
                step_id="click",
                before=frame,
                after=after_frame,
                verification=verification_result,
            )
        except (CaptureError, RuntimeError, ValueError, ActError) as error:
            parser.error(str(error))

        if verification_result is not None and not verification_result.success:
            if args.json:
                payload = {
                    "query": args.query,
                    "dry_run": args.dry_run,
                    "kind": args.kind,
                    "anchor": args.anchor,
                    "point": {"x": point[0], "y": point[1]},
                    "target": asdict(targets[0]),
                    "verification": asdict(verification_result),
                    "artifact_dir": str(artifact_dir),
                }
                print(json.dumps(payload, indent=2))
            else:
                print(verification_result.message)
                print(str(artifact_dir))
            return 1

        if args.json:
            payload = {
                "query": args.query,
                "dry_run": args.dry_run,
                "kind": args.kind,
                "anchor": args.anchor,
                "point": {"x": point[0], "y": point[1]},
                "target": asdict(targets[0]),
                "artifact_dir": str(artifact_dir),
            }
            if verification_result is not None:
                payload["verification"] = asdict(verification_result)
            print(json.dumps(payload, indent=2))
            return 0

        action_text = "would click" if args.dry_run else "clicked"
        print(f'{action_text} "{args.query}" at {point[0]},{point[1]} ({args.kind})')
        if verification_result is not None:
            print(verification_result.message)
        print(str(artifact_dir))
        return 0

    if args.command == "run":
        try:
            flow = load_flow(args.flow_path)
            run_id = args.run_id or _default_run_id()
            runner = FlowRunner(dry_run=args.dry_run)
            session = runner.run(flow, run_id=run_id)
        except (RuntimeError, ValueError, CaptureError, ActError) as error:
            parser.error(str(error))

        failed = any(not item.success for item in session.results)
        if args.json:
            payload = {
                "flow": flow.name,
                "run_id": run_id,
                "dry_run": args.dry_run,
                "success": not failed,
                "steps": [asdict(item) for item in session.results],
            }
            print(json.dumps(payload, indent=2))
            return 1 if failed else 0

        status = "failed" if failed else "succeeded"
        print(f'flow "{flow.name}" {status} ({len(session.results)} steps)')
        return 1 if failed else 0

    if args.command == "mcp":
        if args.mcp_command == "list-tools":
            tools = list_mcp_tools()
            if args.json:
                print(json.dumps({"tools": tools}, indent=2))
                return 0
            for item in tools:
                print(f'{item["name"]}\t{item["description"]}')
            return 0

        if args.mcp_command == "call":
            try:
                payload = json.loads(args.args_json)
            except json.JSONDecodeError as error:
                parser.error(f"Invalid --args-json value: {error}")
            if not isinstance(payload, dict):
                parser.error("--args-json must parse to a JSON object.")

            result = call_mcp_tool(args.tool, payload)
            print(json.dumps(result, indent=2))
            return 0 if result.get("ok") else 1

        parser.error("Unknown mcp command")
        return 2

    parser.error("Unknown command")
    return 2


def _resolve_find_frame(frame_path: Path | None) -> Frame:
    if frame_path:
        image_path = frame_path.expanduser().resolve()
        if not image_path.exists():
            raise ValueError(f"Frame path does not exist: {image_path}")
        return Frame(
            width=0,
            height=0,
            scale_factor=1.0,
            source=f"file:{image_path.name}",
            image_path=str(image_path),
            metadata={"input": "file"},
        )
    return screen()


def _maybe_write_overlay(frame: Frame, targets: list, out_path: Path | None) -> Path | None:
    if out_path is None:
        return None
    if not frame.image_path:
        raise ValueError("Overlay output requires a frame image path.")
    return draw_debug_overlay(frame_path=frame.image_path, targets=targets, out_path=out_path)


def _run_verification_specs(
    *,
    verify_specs: list[str],
    before: Frame,
    after: Frame,
    locator: Locator,
) -> VerifyResult | None:
    if not verify_specs:
        return None

    last_result: VerifyResult | None = None
    for raw_spec in verify_specs:
        verifier = _parse_verifier_spec(raw_spec=raw_spec, locator=locator)
        result = verifier.verify(before=before, after=after)
        last_result = result
        if not result.success:
            return result
    return last_result


def _parse_verifier_spec(*, raw_spec: str, locator: Locator) -> Verifier:
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


def _default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


if __name__ == "__main__":
    raise SystemExit(main())
