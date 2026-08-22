"""Run one or more market-validation scenarios and write a scorecard.

Supports:
- ``browser-only`` / ``hybrid`` — browser-use Agent + Open Frame custom tools
- ``openframe-only`` — deterministic Open Frame tool sequence (no LLM required)

Examples:
  python examples/market-validation/run_scenario.py --scenario s2
  python examples/market-validation/run_scenario.py --all --deterministic-only
  python examples/market-validation/run_scenario.py --ab ab1 --ab ab2 --repeats 3
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS_DIR = Path(__file__).resolve().parent / "scenarios"
AB_DIR = SCENARIOS_DIR / "ab"
RUNS_DIR = ROOT / "docs" / "market-validation-runs"
PASS_RATE_THRESHOLD = 2 / 3

if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from browser_use_openframe_tools import call_openframe, register_openframe_tools

_http_servers: list[Any] = []


def _start_static_http_server(directory: Path) -> str:
    """Serve ``directory`` on an ephemeral localhost port; return base URL."""
    import threading
    from functools import partial
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    _http_servers.append(server)
    host, port = server.server_address[:2]
    return f"http://{host}:{port}"


def _stop_http_servers() -> None:
    while _http_servers:
        server = _http_servers.pop()
        try:
            server.shutdown()
        except Exception as exc:  # noqa: BLE001
            print(f"warning: http server shutdown failed: {exc}", file=sys.stderr)
        try:
            server.server_close()
        except Exception as exc:  # noqa: BLE001
            print(f"warning: http server close failed: {exc}", file=sys.stderr)


def _load_scenario(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or "id" not in payload:
        raise ValueError(f"Invalid scenario file: {path}")
    return payload


def _list_scenarios() -> list[Path]:
    return sorted(SCENARIOS_DIR.glob("s*.yaml"))


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _focus_app(name: str) -> None:
    from openframe.runner import _focus_app as focus

    focus(name)


def _prepare_scenario(scenario: dict[str, Any], *, work_dir: Path) -> dict[str, str]:
    """Run setup.prepare hooks; return template vars for prompts/steps."""
    vars_: dict[str, str] = {}
    prepare = (scenario.get("setup") or {}).get("prepare")
    work_dir.mkdir(parents=True, exist_ok=True)

    if prepare == "handoff_html":
        fixtures = ROOT / "examples" / "market-validation" / "fixtures"
        # browser-use blocks file:// (no hostname); serve over localhost HTTP.
        base = _start_static_http_server(fixtures)
        vars_["handoff_html"] = f"{base}/handoff.html"
    elif prepare == "scroll_probe_flow":
        page = (ROOT / "examples" / "demo" / "scroll-probe" / "index.html").resolve()
        src = (ROOT / "examples" / "flows" / "scroll-until-found" / "flow.yaml").read_text(
            encoding="utf-8"
        )
        src = src.replace(
            "file:///ABSOLUTE/PATH/TO/open-frame/examples/demo/scroll-probe/index.html",
            page.as_uri(),
        )
        dest = work_dir / "scroll-until-found.flow.yaml"
        dest.write_text(src, encoding="utf-8")
        vars_["scroll_flow_path"] = str(dest)
    return vars_


def _apply_vars(value: Any, vars_: dict[str, str]) -> Any:
    if isinstance(value, str):
        out = value
        for key, replacement in vars_.items():
            out = out.replace("{{" + key + "}}", replacement)
        return out
    if isinstance(value, list):
        return [_apply_vars(item, vars_) for item in value]
    if isinstance(value, dict):
        return {key: _apply_vars(item, vars_) for key, item in value.items()}
    return value


def _run_deterministic(scenario: dict[str, Any], *, work_dir: Path) -> dict[str, Any]:
    """Execute scenario['steps'] via Open Frame tools; score pass_checks."""
    started = time.perf_counter()
    vars_ = _prepare_scenario(scenario, work_dir=work_dir)
    scenario = _apply_vars(scenario, vars_)
    setup = scenario.get("setup") or {}
    app = setup.get("app")
    if app:
        try:
            _focus_app(str(app))
        except Exception as exc:  # noqa: BLE001
            return {
                "status": "blocked",
                "notes": f"Could not focus app '{app}': {exc}",
                "envelopes": [],
                "metrics": metrics_from_usage(
                    None, wall_seconds=time.perf_counter() - started, steps=0
                ),
            }

    envelopes: list[dict[str, Any]] = []
    for step in scenario.get("steps") or []:
        tool = str(step.get("tool", "")).strip()
        args = dict(step.get("args") or {})
        mcp_tool = {
            "desktop_capture": "capture",
            "desktop_find": "find",
            "desktop_click_dry_run": "click",
            "desktop_scroll": "scroll",
            "desktop_run_flow": "run_flow",
        }.get(tool, tool)
        if mcp_tool == "click":
            args.setdefault("dry_run", True)
        envelope = call_openframe(mcp_tool, args)
        envelopes.append({"step_tool": tool, "mcp_tool": mcp_tool, "envelope": envelope})

    status, notes = _score(scenario, envelopes=envelopes, agent_final=None)
    return {
        "status": status,
        "notes": notes,
        "envelopes": envelopes,
        "agent_final": None,
        "metrics": metrics_from_usage(
            None,
            wall_seconds=time.perf_counter() - started,
            steps=len(envelopes),
        ),
    }


def _score(
    scenario: dict[str, Any],
    *,
    envelopes: list[dict[str, Any]],
    agent_final: str | None,
) -> tuple[str, str]:
    checks = scenario.get("pass_checks") or []
    failures: list[str] = []
    by_tool: dict[str, list[dict[str, Any]]] = {}
    for item in envelopes:
        by_tool.setdefault(item["step_tool"], []).append(item["envelope"])
        by_tool.setdefault(item["mcp_tool"], []).append(item["envelope"])

    for check in checks:
        kind = check.get("type")
        if kind == "envelope_ok":
            tool = check["tool"]
            found = by_tool.get(tool) or []
            if not found or not found[-1].get("ok"):
                failures.append(f"envelope_ok failed for {tool}")
        elif kind == "envelope_error_code":
            tool = check["tool"]
            code = check["code"]
            found = by_tool.get(tool) or []
            actual = ((found[-1].get("error") or {}) if found else {}).get("code")
            if actual != code:
                failures.append(f"expected error.code={code} for {tool}, got {actual!r}")
        elif kind == "count_gte":
            tool = check["tool"]
            value = int(check["value"])
            found = by_tool.get(tool) or []
            count = int(((found[-1].get("data") or {}) if found else {}).get("count") or 0)
            if count < value:
                failures.append(f"count_gte {value} failed for {tool} (count={count})")
        elif kind == "target_source_contains":
            tool = check["tool"]
            needle = str(check["value"])
            found = by_tool.get(tool) or []
            targets = ((found[-1].get("data") or {}) if found else {}).get("targets") or []
            sources = [str(t.get("source", "")) for t in targets]
            if not any(needle in s for s in sources):
                failures.append(f"no target source containing {needle!r} (got {sources})")
        elif kind == "agent_final_regex":
            pattern = str(check["pattern"])
            if not agent_final or not re.search(pattern, agent_final, re.IGNORECASE):
                failures.append(f"agent_final_regex {pattern!r} did not match {agent_final!r}")
        elif kind == "openframe_unused":
            if envelopes:
                failures.append("openframe_unused failed: Open Frame tools were called")
        elif kind == "details_truthy":
            tool = check["tool"]
            key = check["key"]
            found = by_tool.get(tool) or []
            data = (found[-1].get("data") or {}) if found else {}
            hit = data.get(key)
            if hit is None:
                for step in data.get("steps") or []:
                    if isinstance(step, dict) and step.get(key):
                        hit = step.get(key)
                        break
                    details = step.get("details") if isinstance(step, dict) else None
                    if isinstance(details, dict) and details.get(key):
                        hit = details.get(key)
                        break
            if not hit:
                failures.append(f"details_truthy {key} missing for {tool}")
        else:
            failures.append(f"unknown check type {kind!r}")

    if failures:
        return "fail", "; ".join(failures)
    return "pass", "all checks passed"


def metrics_from_usage(
    usage: Any,
    *,
    wall_seconds: float,
    steps: int | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Map browser-use usage (or None) into a stable metrics dict.

    Missing usage is explicit: token/cost fields stay null and
    ``usage_complete`` is False. Never zero-fill LLM stats.
    """
    metrics: dict[str, Any] = {
        "wall_seconds": round(float(wall_seconds), 3),
        "steps": steps,
        "model": model,
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
        "cached_tokens": None,
        "cost_usd": None,
        "usage_complete": False,
    }
    data: dict[str, Any] | None = None
    if usage is None:
        return metrics
    if hasattr(usage, "model_dump"):
        dumped = usage.model_dump()
        if isinstance(dumped, dict):
            data = dumped
    elif isinstance(usage, dict):
        data = usage
    if not data:
        return metrics
    prompt = data.get("total_prompt_tokens")
    completion = data.get("total_completion_tokens")
    total = data.get("total_tokens")
    if prompt is None and completion is None and total is None:
        return metrics
    metrics["prompt_tokens"] = prompt
    metrics["completion_tokens"] = completion
    metrics["total_tokens"] = total
    metrics["cached_tokens"] = data.get("total_prompt_cached_tokens")
    metrics["cost_usd"] = data.get("total_cost")
    metrics["usage_complete"] = True
    return metrics


def _history_step_count(history: Any) -> int | None:
    if history is None:
        return None
    items = getattr(history, "history", None)
    if items is not None:
        return len(items)
    outputs = getattr(history, "all_model_outputs", None)
    if outputs is not None:
        return len(outputs)
    return None


def _model_name(llm: Any) -> str | None:
    if llm is None:
        return None
    name = getattr(llm, "model", None)
    return str(name) if name else None


def _use_judge() -> bool:
    return os.environ.get("OPENFRAME_MARKET_VALIDATION_USE_JUDGE", "").lower() in {
        "1",
        "true",
        "yes",
    }


def _build_llm():  # type: ignore[no-untyped-def]
    """Prefer Anthropic when configured; otherwise OpenAI."""
    if os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get(
        "OPENFRAME_MARKET_VALIDATION_FORCE_OPENAI"
    ):
        from browser_use import ChatAnthropic

        model = os.environ.get(
            "OPENFRAME_MARKET_VALIDATION_MODEL", "claude-haiku-4-5-20251001"
        )
        return ChatAnthropic(model=model)
    from browser_use import ChatOpenAI

    model = os.environ.get("OPENFRAME_MARKET_VALIDATION_MODEL", "gpt-4.1-mini")
    return ChatOpenAI(model=model)


def _resolve_browser_executable() -> str | None:
    """Locate a Chromium/Chrome binary for browser-use.

    browser-use's default discovery still looks for ``Chromium.app`` under
    ``ms-playwright``, while modern Playwright ships ``Google Chrome for Testing``.
    Prefer an explicit override, then known Playwright layouts, then system Chrome.
    """
    override = os.environ.get("OPENFRAME_BROWSER_EXECUTABLE")
    if override and Path(override).is_file():
        return override

    roots: list[Path] = []
    env_root = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if env_root:
        roots.append(Path(env_root))
    roots.append(Path.home() / "Library" / "Caches" / "ms-playwright")
    roots.append(Path.home() / ".cache" / "ms-playwright")

    patterns = (
        "chromium-*/chrome-mac*/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
        "chromium-*/chrome-mac*/Chromium.app/Contents/MacOS/Chromium",
        "chromium-*/chrome-linux*/chrome",
        "chromium-*/chrome-win/chrome.exe",
    )
    matches: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for pattern in patterns:
            matches.extend(sorted(root.glob(pattern)))
    for candidate in reversed(matches):
        if candidate.is_file():
            return str(candidate.resolve())

    for system_path in (
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
    ):
        path = Path(system_path)
        if path.is_file():
            return str(path)
    return None


async def _run_agent(scenario: dict[str, Any], *, work_dir: Path) -> dict[str, Any]:
    """Run browser-use Agent for browser-only / hybrid scenarios."""
    started = time.perf_counter()

    def _blocked(notes: str, envelopes: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        return {
            "status": "blocked",
            "notes": notes,
            "envelopes": envelopes or [],
            "agent_final": None,
            "metrics": metrics_from_usage(None, wall_seconds=time.perf_counter() - started),
        }

    try:
        from browser_use import Agent, Browser, Tools
    except ImportError as exc:
        return _blocked(f"browser-use not installed: {exc}")

    if not (
        os.environ.get("OPENAI_API_KEY")
        or os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("BROWSER_USE_API_KEY")
    ):
        return _blocked("Set OPENAI_API_KEY or ANTHROPIC_API_KEY for agent scenarios")

    vars_ = _prepare_scenario(scenario, work_dir=work_dir)
    scenario = _apply_vars(scenario, vars_)

    mode = scenario.get("mode", "hybrid")
    # Hybrid schemas get large; trim unused browser actions so the LLM keeps
    # navigate/done + Open Frame desktop_* tools in a reliable output format.
    exclude: list[str] | None = None
    if mode == "hybrid":
        exclude = [
            "click",
            "close",
            "dropdown_options",
            "evaluate",
            "find_elements",
            "find_text",
            "go_back",
            "input",
            "read_file",
            "replace_file",
            "save_as_pdf",
            "scroll",
            "search",
            "search_page",
            "select_dropdown",
            "send_keys",
            "switch",
            "upload_file",
            "write_file",
        ]
    tools = Tools(exclude_actions=exclude)
    of_envelopes: list[dict[str, Any]] = []
    original = None

    if mode in {"hybrid", "openframe-only"}:
        import browser_use_openframe_tools as of_tools

        original = of_tools.call_openframe

        def recording_call(tool: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
            envelope = original(tool, args)
            mapped = {
                "capture": "desktop_capture",
                "find": "desktop_find",
                "click": "desktop_click_dry_run",
                "scroll": "desktop_scroll",
                "run_flow": "desktop_run_flow",
            }.get(tool, tool)
            of_envelopes.append(
                {"step_tool": mapped, "mcp_tool": tool, "envelope": envelope}
            )
            return envelope

        of_tools.call_openframe = recording_call  # type: ignore[attr-defined]
        register_openframe_tools(tools)

    setup = scenario.get("setup") or {}
    if setup.get("app"):
        try:
            _focus_app(str(setup["app"]))
        except Exception as exc:  # noqa: BLE001
            if original is not None:
                import browser_use_openframe_tools as of_tools

                of_tools.call_openframe = original  # type: ignore[attr-defined]
            return _blocked(f"Could not focus app '{setup['app']}': {exc}", of_envelopes)

    llm = _build_llm()
    task = str(scenario.get("prompt") or "").strip()
    if not task:
        if original is not None:
            import browser_use_openframe_tools as of_tools

            of_tools.call_openframe = original  # type: ignore[attr-defined]
        return _blocked("scenario prompt is empty", of_envelopes)

    browser_kwargs: dict[str, Any] = {"headless": True}
    executable = _resolve_browser_executable()
    if executable:
        browser_kwargs["executable_path"] = executable
    browser = Browser(**browser_kwargs)

    agent = Agent(
        task=task,
        llm=llm,
        tools=tools,
        browser=browser,
        max_failures=3,
        use_vision=False,
        flash_mode=True,
        use_judge=_use_judge(),
        calculate_cost=True,
    )
    history = None
    try:
        history = await agent.run(max_steps=int(scenario.get("max_steps", 12)))
    except Exception as exc:  # noqa: BLE001
        if original is not None:
            import browser_use_openframe_tools as of_tools

            of_tools.call_openframe = original  # type: ignore[attr-defined]
        message = str(exc)
        metrics = metrics_from_usage(
            getattr(history, "usage", None) if history is not None else None,
            wall_seconds=time.perf_counter() - started,
            steps=_history_step_count(history),
            model=_model_name(llm),
        )
        if "uvx" in message or "BrowserLaunch" in message or "playwright" in message.casefold():
            hint = (
                f" Detected executable candidate: {executable}."
                if executable
                else " No local Chromium/Chrome executable was discovered."
            )
            return {
                "status": "blocked",
                "notes": (
                    "browser-use could not launch a browser "
                    f"({type(exc).__name__}: {message}).{hint} "
                    "Install Chromium via `python -m playwright install chromium`, "
                    "ensure `uv`/`uvx` is on PATH, or set "
                    "OPENFRAME_BROWSER_EXECUTABLE to a Chrome/Chromium binary."
                ),
                "envelopes": of_envelopes,
                "agent_final": None,
                "metrics": metrics,
            }
        return {
            "status": "fail",
            "notes": f"agent run raised {type(exc).__name__}: {message}",
            "envelopes": of_envelopes,
            "agent_final": None,
            "metrics": metrics,
        }
    finally:
        if original is not None:
            import browser_use_openframe_tools as of_tools

            of_tools.call_openframe = original  # type: ignore[attr-defined]

    final = None
    try:
        final = history.final_result() if hasattr(history, "final_result") else str(history)
    except Exception:  # noqa: BLE001
        final = str(history)

    status, notes = _score(scenario, envelopes=of_envelopes, agent_final=str(final or ""))
    return {
        "status": status,
        "notes": notes,
        "envelopes": of_envelopes,
        "agent_final": final,
        "history": str(history),
        "metrics": metrics_from_usage(
            getattr(history, "usage", None),
            wall_seconds=time.perf_counter() - started,
            steps=_history_step_count(history),
            model=_model_name(llm),
        ),
    }


def _write_run_artifacts(
    *,
    scenario: dict[str, Any],
    result: dict[str, Any],
    out_dir: Path,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    scenario_id = scenario["id"]
    raw_path = out_dir / f"{scenario_id}.json"
    raw_path.write_text(json.dumps({"scenario": scenario, "result": result}, indent=2, default=str), encoding="utf-8")

    md_path = out_dir / f"{scenario_id}.md"
    metrics = result.get("metrics") or {}
    md_path.write_text(
        "\n".join(
            [
                f"# Scenario `{scenario_id}` — {scenario.get('name', '')}",
                "",
                f"- Status: **{result.get('status')}**",
                f"- Mode: `{scenario.get('mode')}`",
                f"- Profiles: {', '.join(scenario.get('profiles') or [])}",
                f"- Notes: {result.get('notes')}",
                "",
                "## Metrics",
                "",
                f"- wall_seconds: {metrics.get('wall_seconds')}",
                f"- steps: {metrics.get('steps')}",
                f"- model: {metrics.get('model')}",
                f"- prompt_tokens: {metrics.get('prompt_tokens')}",
                f"- completion_tokens: {metrics.get('completion_tokens')}",
                f"- total_tokens: {metrics.get('total_tokens')}",
                f"- cached_tokens: {metrics.get('cached_tokens')}",
                f"- cost_usd: {metrics.get('cost_usd')}",
                f"- usage_complete: {metrics.get('usage_complete')}",
                "",
                "## Agent final",
                "",
                "```",
                str(result.get("agent_final") or "(none)"),
                "```",
                "",
                "## Open Frame envelopes",
                "",
                f"Count: {len(result.get('envelopes') or [])}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return md_path


def _write_scorecard(out_dir: Path, rows: list[dict[str, Any]]) -> Path:
    path = out_dir / "scorecard.md"
    lines = [
        f"# Market validation scorecard — {out_dir.name}",
        "",
        "| Scenario | Mode | Status | Notes |",
        "|---|---|---|---|",
    ]
    for row in rows:
        notes = str(row.get("notes", "")).replace("|", "/")
        lines.append(
            f"| `{row['id']}` | `{row.get('mode')}` | **{row.get('status')}** | {notes} |"
        )
    passed = sum(1 for r in rows if r.get("status") == "pass")
    failed = sum(1 for r in rows if r.get("status") == "fail")
    blocked = sum(1 for r in rows if r.get("status") == "blocked")
    lines.extend(
        [
            "",
            f"Totals: pass={passed} fail={failed} blocked={blocked}",
            "",
            "## Verdict",
            "",
        ]
    )
    if failed:
        lines.append("Not market-ready for failed scenarios — investigate notes above.")
    elif passed and not blocked:
        lines.append("All executed scenarios passed under current environment.")
    else:
        lines.append("Partial run (blocked scenarios). Re-run after fixing environment.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def median(values: list[Any]) -> float | None:
    nums = [float(v) for v in values if v is not None]
    if not nums:
        return None
    nums.sort()
    n = len(nums)
    mid = n // 2
    if n % 2:
        return nums[mid]
    return (nums[mid - 1] + nums[mid]) / 2


def summarize_arm_trials(trials: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate one arm. Blocked trials are listed but excluded from pass_rate/medians."""
    blocked = [t for t in trials if t.get("status") == "blocked"]
    scored = [t for t in trials if t.get("status") != "blocked"]
    passed = [t for t in scored if t.get("status") == "pass"]
    failed = [t for t in scored if t.get("status") == "fail"]
    denom = len(passed) + len(failed)
    pass_rate = (len(passed) / denom) if denom else 0.0

    def _vals(key: str) -> list[Any]:
        out: list[Any] = []
        for trial in scored:
            metrics = trial.get("metrics") or {}
            value = metrics.get(key)
            if value is not None:
                out.append(value)
        return out

    return {
        "n": len(trials),
        "n_blocked": len(blocked),
        "n_pass": len(passed),
        "n_fail": len(failed),
        "pass_rate": pass_rate,
        "median_wall_seconds": median(_vals("wall_seconds")),
        "median_total_tokens": median(_vals("total_tokens")),
        "median_cost_usd": median(_vals("cost_usd")),
        "median_steps": median(_vals("steps")),
        "blocked_notes": [t.get("notes") for t in blocked],
    }


def compare_ab_verdict(
    thesis: str, browser_only: dict[str, Any], hybrid: dict[str, Any]
) -> dict[str, str]:
    """Mechanical verdict. Never claims cheaper from a capability-only pair."""
    if thesis == "capability":
        if hybrid["pass_rate"] >= PASS_RATE_THRESHOLD and browser_only["pass_rate"] == 0:
            return {
                "kind": "capability",
                "summary": (
                    "Open Frame required: hybrid met the pass threshold; "
                    "browser-only did not pass. Not an efficiency claim."
                ),
            }
        return {
            "kind": "inconclusive",
            "summary": (
                "Capability pair did not show a clean hybrid-only pass vs browser-only fail."
            ),
        }
    if thesis == "efficiency":
        if (
            browser_only["pass_rate"] >= PASS_RATE_THRESHOLD
            and hybrid["pass_rate"] >= PASS_RATE_THRESHOLD
        ):
            hybrid_cost = hybrid.get("median_cost_usd")
            browser_cost = browser_only.get("median_cost_usd")
            if (
                hybrid_cost is not None
                and browser_cost is not None
                and hybrid["pass_rate"] >= browser_only["pass_rate"]
            ):
                if hybrid_cost < browser_cost:
                    return {
                        "kind": "efficiency",
                        "summary": (
                            "Hybrid is cheaper on median cost_usd with pass rate "
                            "at least as high as browser-only."
                        ),
                    }
                if browser_cost < hybrid_cost:
                    return {
                        "kind": "efficiency",
                        "summary": "Browser-only is cheaper on median cost_usd; both arms passed.",
                    }
            hybrid_tokens = hybrid.get("median_total_tokens")
            browser_tokens = browser_only.get("median_total_tokens")
            if hybrid_tokens is not None and browser_tokens is not None:
                if hybrid_tokens < browser_tokens:
                    return {
                        "kind": "efficiency",
                        "summary": (
                            "Hybrid used fewer median tokens; dollar cost was missing or tied."
                        ),
                    }
                if browser_tokens < hybrid_tokens:
                    return {
                        "kind": "efficiency",
                        "summary": (
                            "Browser-only used fewer median tokens; dollar cost was missing or tied."
                        ),
                    }
            return {
                "kind": "inconclusive",
                "summary": "Both arms passed but cost/token medians are missing or tied.",
            }
        return {
            "kind": "inconclusive",
            "summary": "Efficiency pair did not reach the pass-rate threshold on both arms.",
        }
    return {"kind": "inconclusive", "summary": f"Unknown thesis {thesis!r}."}


def _delta(hybrid_val: Any, browser_val: Any) -> float | None:
    if hybrid_val is None or browser_val is None:
        return None
    return float(hybrid_val) - float(browser_val)


def _arm_to_scenario(pair: dict[str, Any], arm: dict[str, Any]) -> dict[str, Any]:
    suffix = str(arm.get("prompt_suffix") or "").strip()
    job = str(pair.get("job") or "").strip()
    prompt = f"{job}\n{suffix}".strip() if suffix else job
    setup: dict[str, Any] = {}
    if pair.get("prepare"):
        setup["prepare"] = pair["prepare"]
    if pair.get("app"):
        setup["app"] = pair["app"]
    return {
        "id": f"{pair['id']}-{arm['id']}",
        "name": pair.get("name", pair["id"]),
        "profiles": pair.get("profiles") or [],
        "mode": arm["mode"],
        "max_steps": int(pair.get("max_steps") or 12),
        "prompt": prompt,
        "setup": setup,
        "pass_checks": arm.get("pass_checks") or [],
        "thesis": pair.get("thesis"),
        "arm": arm["id"],
        "pair": pair["id"],
    }


def _list_ab_pairs() -> list[Path]:
    return sorted(AB_DIR.glob("ab*.yaml"))


def _write_ab_comparison(
    out_dir: Path,
    pair: dict[str, Any],
    arms: dict[str, dict[str, Any]],
    verdict: dict[str, str],
) -> Path:
    browser = arms["browser-only"]
    hybrid = arms["hybrid"]
    payload = {
        "pair": pair["id"],
        "thesis": pair.get("thesis"),
        "verdict": verdict,
        "arms": arms,
        "delta_hybrid_minus_browser": {
            "wall_seconds": _delta(hybrid["median_wall_seconds"], browser["median_wall_seconds"]),
            "total_tokens": _delta(hybrid["median_total_tokens"], browser["median_total_tokens"]),
            "cost_usd": _delta(hybrid["median_cost_usd"], browser["median_cost_usd"]),
            "steps": _delta(hybrid["median_steps"], browser["median_steps"]),
        },
    }
    json_path = out_dir / "ab-comparison.json"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    def _fmt(value: Any) -> str:
        if value is None:
            return "—"
        if isinstance(value, float):
            return f"{value:.4g}"
        return str(value)

    lines = [
        f"# A/B comparison — {pair['id']} ({pair.get('name', '')})",
        "",
        f"- Thesis: `{pair.get('thesis')}`",
        f"- Verdict: **{verdict['kind']}** — {verdict['summary']}",
        "",
        "| Arm | pass_rate | n_pass | n_fail | n_blocked | median wall_s | median tokens | median $ | median steps |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for arm_id, stats in arms.items():
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{arm_id}`",
                    _fmt(stats["pass_rate"]),
                    str(stats["n_pass"]),
                    str(stats["n_fail"]),
                    str(stats["n_blocked"]),
                    _fmt(stats["median_wall_seconds"]),
                    _fmt(stats["median_total_tokens"]),
                    _fmt(stats["median_cost_usd"]),
                    _fmt(stats["median_steps"]),
                ]
            )
            + " |"
        )
    delta = payload["delta_hybrid_minus_browser"]
    lines.extend(
        [
            "",
            "Deltas are `hybrid - browser-only` (negative means hybrid cheaper/faster/fewer).",
            "",
            f"- Δ wall_seconds: {_fmt(delta['wall_seconds'])}",
            f"- Δ total_tokens: {_fmt(delta['total_tokens'])}",
            f"- Δ cost_usd: {_fmt(delta['cost_usd'])}",
            f"- Δ steps: {_fmt(delta['steps'])}",
            "",
        ]
    )
    if browser.get("blocked_notes") or hybrid.get("blocked_notes"):
        lines.append("## Blocked trials")
        lines.append("")
        for arm_id, stats in arms.items():
            for note in stats.get("blocked_notes") or []:
                lines.append(f"- `{arm_id}`: {note}")
        lines.append("")
    md_path = out_dir / "ab-comparison.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path


def _run_ab_pair(
    pair: dict[str, Any],
    *,
    out_dir: Path,
    repeats: int,
    warmup: int,
) -> tuple[dict[str, dict[str, Any]], dict[str, str], int]:
    """Run warmup + N trials per arm. Returns (arm_stats, verdict, exit_hint)."""
    arm_trials: dict[str, list[dict[str, Any]]] = {}
    for arm in pair.get("arms") or []:
        arm_id = str(arm["id"])
        arm_trials[arm_id] = []
        scenario = _arm_to_scenario(pair, arm)
        mode = scenario["mode"]
        total_runs = warmup + repeats
        for index in range(total_runs):
            is_warmup = index < warmup
            label = "warmup" if is_warmup else f"t{index - warmup + 1}"
            print(f"==> {pair['id']} {arm_id} {label} ({mode})")
            work_dir = out_dir / "_work" / pair["id"] / arm_id / label
            if mode == "openframe-only":
                result = _run_deterministic(scenario, work_dir=work_dir)
            else:
                result = asyncio.run(_run_agent(scenario, work_dir=work_dir))
            trial_id = f"{pair['id']}-{arm_id}-{label}"
            scenario_copy = dict(scenario)
            scenario_copy["id"] = trial_id
            if not is_warmup:
                _write_run_artifacts(scenario=scenario_copy, result=result, out_dir=out_dir)
                arm_trials[arm_id].append(
                    {
                        "status": result.get("status"),
                        "notes": result.get("notes"),
                        "metrics": result.get("metrics"),
                        "trial": trial_id,
                    }
                )
            print(f"    {result.get('status')}: {result.get('notes')}")
            _stop_http_servers()

    stats = {arm_id: summarize_arm_trials(trials) for arm_id, trials in arm_trials.items()}
    verdict = compare_ab_verdict(
        str(pair.get("thesis") or ""),
        stats.get("browser-only") or summarize_arm_trials([]),
        stats.get("hybrid") or summarize_arm_trials([]),
    )
    _write_ab_comparison(out_dir, pair, stats, verdict)
    thesis = str(pair.get("thesis") or "")
    exit_fail = 0
    hybrid_fail = (stats.get("hybrid") or {}).get("n_fail", 0)
    browser_fail = (stats.get("browser-only") or {}).get("n_fail", 0)
    if thesis == "capability":
        if hybrid_fail:
            exit_fail = 1
    elif browser_fail or hybrid_fail:
        exit_fail = 1
    return stats, verdict, exit_fail


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", action="append", help="Scenario id (e.g. s1). Repeatable.")
    parser.add_argument("--all", action="store_true", help="Run all scenarios in scenarios/")
    parser.add_argument(
        "--ab",
        action="append",
        help="A/B pair id (e.g. ab1). Repeatable. Loads scenarios/ab/*.yaml",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=3,
        help="Trials per arm for --ab (default 3)",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=0,
        help="Discarded warmup trials per arm before scoring --ab repeats",
    )
    parser.add_argument(
        "--deterministic-only",
        action="store_true",
        help="Skip browser-use agent scenarios (browser-only / hybrid)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        help="Output directory (default docs/market-validation-runs/<stamp>)",
    )
    args = parser.parse_args(argv)

    if args.ab:
        if args.repeats < 1:
            parser.error("--repeats must be >= 1")
        if args.warmup < 0:
            parser.error("--warmup must be >= 0")
        wanted = {str(item).lower() for item in args.ab}
        pairs = [
            _load_scenario(path)
            for path in _list_ab_pairs()
            if path.stem.lower() in wanted or path.stem.lower().removeprefix("ab") in wanted
        ]
        if not pairs:
            parser.error(f"no A/B pairs matched {args.ab}")
        stamp_dir = args.out_dir or (RUNS_DIR / _stamp())
        any_fail = 0
        try:
            for pair in pairs:
                pair_dir = stamp_dir / pair["id"]
                _stats, verdict, fail = _run_ab_pair(
                    pair, out_dir=pair_dir, repeats=args.repeats, warmup=args.warmup
                )
                print(f"Wrote {pair_dir / 'ab-comparison.md'} ({verdict['kind']})")
                any_fail = any_fail or fail
        finally:
            _stop_http_servers()
        return any_fail

    paths = _list_scenarios()
    if not args.all:
        if not args.scenario:
            parser.error("pass --scenario ID or --all")
        wanted = {s.lower().removeprefix("s") for s in args.scenario}
        # allow s1 or 1
        paths = [
            p
            for p in paths
            if p.stem.lower() in {f"s{w}" if not w.startswith("s") else w for w in wanted}
            or p.stem.lower() in {s.lower() for s in args.scenario}
        ]
        if not paths:
            parser.error(f"no scenarios matched {args.scenario}")

    out_dir = args.out_dir or (RUNS_DIR / _stamp())
    rows: list[dict[str, Any]] = []

    try:
        for path in paths:
            scenario = _load_scenario(path)
            mode = scenario.get("mode", "openframe-only")
            print(f"==> {scenario['id']} ({mode})")
            work_dir = out_dir / "_work" / scenario["id"]
            if mode in {"browser-only", "hybrid"} and args.deterministic_only:
                result = {
                    "status": "blocked",
                    "notes": "skipped (--deterministic-only)",
                    "envelopes": [],
                    "agent_final": None,
                    "metrics": metrics_from_usage(None, wall_seconds=0.0, steps=0),
                }
            elif mode == "openframe-only":
                result = _run_deterministic(scenario, work_dir=work_dir)
            else:
                result = asyncio.run(_run_agent(scenario, work_dir=work_dir))

            _write_run_artifacts(scenario=scenario, result=result, out_dir=out_dir)
            rows.append(
                {
                    "id": scenario["id"],
                    "mode": mode,
                    "status": result.get("status"),
                    "notes": result.get("notes"),
                }
            )
            print(f"    {result.get('status')}: {result.get('notes')}")
            _stop_http_servers()
    finally:
        _stop_http_servers()

    scorecard = _write_scorecard(out_dir, rows)
    print(f"Wrote {scorecard}")
    # Non-zero if any fail (blocked is ok for CI without keys).
    if any(r.get("status") == "fail" for r in rows):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
