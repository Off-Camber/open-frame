<p align="center">
  <img src="docs/assets/open-frame-logo.png" alt="Open Frame" width="520" />
</p>

# Open Frame

Open-source desktop automation engine for AI agents and scripts.

**Open Frame** sees what is on screen, finds targets, interacts with UI, and verifies outcomes. It is built to be deterministic, scriptable, and auditable.

<p align="center">
  <img src="docs/assets/calibration.gif" alt="Open Frame calibration flow running" width="720" />
</p>

<sub>Above: <code>open-frame run examples/flows/calibration-token/flow.yaml --dry-run --json</code> showing deterministic step execution with structured per-step output.</sub>

> Open Frame is an independent project and is not affiliated with or endorsed by any third-party automation vendor.

Open Frame is the deterministic execution layer behind AI agents, not the agent itself.

### How this differs from assistant UX tools

- Open Frame executes deterministic capture/recognize/act/verify primitives.
- External LLM agents (or scripts) decide what tool call to make next.
- The engine returns compact structured outputs and artifact paths for debugging.

## Status

Active development. `v0.1.2` is live on PyPI as [`off-camber-open-frame`](https://pypi.org/project/off-camber-open-frame/). See the [changelog](CHANGELOG.md) for release history.

## Who this is for

- Developers automating desktop workflows.
- Teams who want agent-callable UI execution without bloating context windows.
- Contributors building recognizers, flows, or integrations.

## 60-second start

```bash
pip install off-camber-open-frame
open-frame capture --out screen.png
open-frame find "Submit" --frame screen.png --json
open-frame mcp list-tools --json
```

If `open-frame` is not on your PATH yet, run through Python directly:

```bash
python -m openframe.cli mcp list-tools --json
```

## Local development (repo clone)

Use this when developing or testing from source. No extra env variable is required.

```bash
python3 -m venv .venv311
source .venv311/bin/activate
pip install -e .[dev,ocr,act,flow]
python -m openframe.cli mcp list-tools --json
```

## Next steps

- [Flow setup](docs/FLOW_SETUP.md) — define and run YAML flows.
- [API](docs/API.md) — use `Session` and MCP-oriented integration guidance.
- [Act setup](docs/ACT_SETUP.md) and [Verify setup](docs/VERIFY_SETUP.md) — run safely with evidence.
- [Full docs index](docs/README.md) — contributor and planning docs.

## License

Apache License 2.0 — free to use, modify, and self-host. See [LICENSE](LICENSE).
