# MCP server setup

Open Frame can run as a local **MCP stdio server** so Claude Desktop, Cursor,
and other MCP clients can call its tools directly.

```bash
open-frame mcp serve
```

This is a thin protocol shim over the existing tool adapter. Tool results use
the Open Frame envelope (`ok`, `tool`, `run_id`, `data`, `error`, `artifacts`).
Failures stay in-band (`ok: false` + `error.code`), not as MCP protocol errors.

Contract version: **`v0.2.0`** (envelope shape unchanged from the earlier
checkpoint label).

## Prerequisites

1. macOS (capture / accessibility are macOS-only in this beta).
2. Install Open Frame with the MCP extra (plus OCR/act/flow for useful tools):

```bash
pip install "off-camber-open-frame[mcp,ocr,act,flow]"
# from a clone:
pip install -e ".[mcp,ocr,act,flow]"
```

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

See also [Contributing](CONTRIBUTING.md) for permission setup details and
[Release gates](RELEASE_GATES.md) for the local live gate that includes an MCP
stdio smoke check.
