# MCP server setup

Open Frame can run as a local **MCP stdio server** so Claude Desktop, Cursor,
and other MCP clients can call its tools directly.

```bash
open-frame mcp serve
```

This is a thin protocol shim over the existing tool adapter. Tool results use
the Open Frame envelope (`ok`, `tool`, `run_id`, `data`, `error`, `artifacts`).
Failures stay in-band (`ok: false` + `error.code`), not as MCP protocol errors.

Contract version: **`v0.2.2`** (envelope keys unchanged; adds `busy`.
`timeout`, summarized `run_flow` steps, and wall-clock tool timeouts remain).

## Prerequisites

1. macOS (capture / accessibility are macOS-only in this beta).
2. Install Open Frame with the MCP extra (plus OCR/act/flow for useful tools):

```bash
pip install "off-camber-open-frame[mcp,ocr,act,flow]"
# from a clone:
pip install -e ".[mcp,ocr,act,flow]"
```

Install Open Frame in its own virtualenv. The mcp extra is deliberately pinned
to `mcp>=1.0,<2`. mcp 2.x is a separate API, and a shared environment can
replace this package with that release.

3. System Tesseract:

```bash
brew install tesseract
```

4. Grant **Screen Recording** and **Accessibility** to the exact app that will
   host the server (Terminal, iTerm, Cursor, Claude Desktop, etc.).

5. Confirm the environment:

```bash
open-frame doctor
```

Fix anything marked `fail` before connecting a client. Missing optional extras
show as `skip` and do not block doctor.

## Claude Desktop

Edit Claude Desktop MCP config (macOS path typically
`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "open-frame": {
      "command": "/absolute/path/to/python",
      "args": ["-m", "openframe.cli", "mcp", "serve"]
    }
  }
}
```

Use the Python interpreter from the virtualenv where Open Frame is installed.
After saving, restart Claude Desktop and confirm the Open Frame tools appear
(`capture`, `find`, `click`, `type`, `key`, `scroll`, `run_flow`, `get_run_artifacts`).

## Cursor

Add an MCP server entry in Cursor settings (MCP servers JSON), for example:

```json
{
  "mcpServers": {
    "open-frame": {
      "command": "/absolute/path/to/python",
      "args": ["-m", "openframe.cli", "mcp", "serve"]
    }
  }
}
```

Restart Cursor / reload MCP servers, then verify the tools are listed (including `scroll`).

## One call at a time

The server runs one tool call at a time. A call that arrives while another is
running, or while a call that already returned `timeout` has not finished
winding down, returns `ok: false` with `error.code: "busy"`.

`click`, `type`, `key`, `scroll`, and `run_flow` send real clicks and
keystrokes unless the arguments include `"dry_run": true`.

Long flows are bounded by a wall-clock timeout
(`OPENFRAME_MCP_RUN_FLOW_TIMEOUT_SEC`, default 300s; other tools use
`OPENFRAME_MCP_TOOL_TIMEOUT_SEC`, default 60s). A non-numeric value is ignored
and the default is used; a warning is written to stderr. A timeout returns
`ok: false` with `error.code: "timeout"`. `click` and `run_flow` include the
`run_id` for that call (the one you passed, or one allocated before the call
started). The worker does not start another click, keystroke, scroll, drag, or
flow step after the timeout. When that worker has finished, `get_run_artifacts`
with the timeout's `run_id` lists whatever the run wrote.

## Payload bounds

- `run_flow` returns **summarized** steps by default (`step_id`, `success`,
  `duration_ms`, `error`). Pass `include_step_details: true` only when you need
  full inline details; prefer `get_run_artifacts` + `artifacts.run_dir` for
  large runs.
- `find` inlines at most 50 targets (`targets_truncated: true` when capped).

## First dry-run call

From any MCP client, prefer a non-actuating call first:

- `type` with `{"text": "hello", "dry_run": true}`
- or `click` with `{"query": "Submit", "dry_run": true}` once Screen Recording
  is confirmed via `open-frame doctor`

## Troubleshooting

| Symptom | What to do |
|---|---|
| Server won't start / import error for `mcp` | `pip install -e '.[mcp]'` then retry |
| Client shows no tools | Confirm `command` points at the venv Python; restart the client |
| Capture / find failures | Run `open-frame doctor` and fix Screen Recording / Accessibility / tesseract |
| Permission prompts never appear | Grant permissions to the **client host** process, not only Terminal |
| Tool returns `busy` | Wait until the in-flight call finishes. A timed-out call still counts until its worker stops |
| Tool returns `timeout` | The envelope `run_id` is the one `get_run_artifacts` accepts after the worker finishes. Raise `OPENFRAME_MCP_*_TIMEOUT_SEC` if the flow needs longer |
| Huge `run_flow` payloads | Default is summarized steps; use `get_run_artifacts` or opt into `include_step_details` |

See also [Contributing](CONTRIBUTING.md) for permission setup details and
[Release gates](RELEASE_GATES.md) for the local live gate that includes an MCP
stdio smoke check.
