# Market validation harness (browser-use + Open Frame)

Scores whether Open Frame holds up as the **desktop** execution layer beside
an established agent ([browser-use](https://github.com/browser-use/browser-use)).

See also: [docs/MARKET_VALIDATION.md](../../docs/MARKET_VALIDATION.md).

## Install

```bash
pip install -e ".[dev,ocr,act,flow,mcp,template]"
pip install "browser-use>=0.13"
# Agent scenarios (S1, S3) need an LLM key and a browser-use-capable Chromium:
export ANTHROPIC_API_KEY=...   # or OPENAI_API_KEY=...
pip install uv playwright      # browser-use may invoke `uvx` to fetch Chromium
python -m playwright install chromium
# Optional if discovery fails (Chrome for Testing path differs from Chromium.app):
# export OPENFRAME_BROWSER_EXECUTABLE="/path/to/Google Chrome for Testing"
```

Grant **Screen Recording** and **Accessibility** to the host running the harness.

## Run

```bash
# Deterministic Open Frame scenarios only (no LLM): S2, S4, S5, S6
python examples/market-validation/run_scenario.py --all --deterministic-only

# Single scenario
python examples/market-validation/run_scenario.py --scenario s5

# Includes browser-use agent scenarios when keys are set
python examples/market-validation/run_scenario.py --scenario s1
python examples/market-validation/run_scenario.py --scenario s3
```

Outputs land in `docs/market-validation-runs/<stamp>/` (`scorecard.md` + per-scenario files).

Each scenario JSON includes `result.metrics`:

| Field | Meaning |
|---|---|
| `wall_seconds` | Wall clock for the scenario body (`agent.run` or Open Frame steps) |
| `steps` | Agent history length, or Open Frame envelope count |
| `model` | LLM id when an agent ran; `null` for `openframe-only` |
| `prompt_tokens` / `completion_tokens` / `total_tokens` / `cached_tokens` | From browser-use `history.usage` |
| `cost_usd` | Estimated $ from browser-use pricing when available |
| `usage_complete` | `true` only when usage was returned; never invent zeros for missing LLM stats |

Agent runs use `calculate_cost=True` and `use_judge=False` (opt in with `OPENFRAME_MARKET_VALIDATION_USE_JUDGE=1`).

## Policy

- Clicks from the harness use **dry_run** unless a scenario explicitly needs actuation
  (S4 scroll flow actuates scroll only).
- Call Open Frame tools **sequentially** (one at a time).
- No MFA automation — desktop sessions must already be usable.

## Layout

| Path | Role |
|---|---|
| `browser_use_openframe_tools.py` | `desktop_*` custom tools → `call_mcp_tool` |
| `run_scenario.py` | Loader, scorer, agent/deterministic runners |
| `scenarios/s*.yaml` | Scenario metadata + pass checks |
| `fixtures/handoff.html` | Hybrid browser fixture for S3 |
