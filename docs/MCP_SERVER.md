# MCP server setup

Open Frame can run as a local **MCP stdio server** so Claude Desktop, Cursor,
and other MCP clients can call its tools directly.

```bash
open-frame mcp serve
```

This is a thin protocol shim over the existing tool adapter. Tool results use
the Open Frame envelope (`ok`, `tool`, `run_id`, `data`, `error`, `artifacts`).
Failures stay in-band (`ok: false` + `error.code`), not as MCP protocol errors.

Contract version: **`v0.3.0`**. Envelope keys are unchanged. See
[Upgrade from 0.2.x](#upgrade-from-02x).

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

## Tool arguments

These are the MCP defaults. `open-frame click` and `open-frame run` on the
command line still send input unless you pass `--dry-run`.

### `capture`

`mode` defaults to `screen` (`screen`, `window`, or `region`). `window_title`
and `window_id` select a window. `x`, `y`, `width`, and `height` select a
region. `out_path` is optional.

### `find`

`query` is required. `strategy` defaults to `first` (`first` or `all`).
`frame_path` omitted captures the screen. `template` and `template_threshold`
are optional. `ok: true` with `count` 0 means the text was not on screen.

### `click`

`query` is required. `anchor` defaults to `center`. `kind` defaults to `click`
(`click`, `double`, or `right`). `dry_run` defaults to `true`; pass `false` to
send the click. `expect_one` defaults to `false`. `selector` is optional
(`first`, `top_most`, `left_most`, `right_most`, `highest_confidence`).
`frame_path`, `template`, `template_threshold`, and `run_id` are optional.

A full-screen `find` searches the whole display, including the chat that asked
for the text. That extra match makes `click` with `expect_one` return
`ambiguous_target`, and a `selector` such as `left_most` can choose the chat
text instead of the window you meant. Capture the target window, then pass
that frame's `image_path` as `frame_path` to `find` and `click`:

```json
{"mode": "window", "window_title": "TextEdit"}
```

Use the returned `frame.image_path` on the later calls. A dry-run `click` and
a live `click` can share that same path.

### `type`

`text` must be non-empty. `interval` defaults to `0`. `dry_run` defaults to
`true`; pass `false` to send keystrokes.

### `key`

Pass exactly one of `key` or `combo`. `dry_run` defaults to `true`; pass
`false` to send the key.

### `scroll`

`clicks` is required (positive up, negative down). `x` and `y` are optional.
`dry_run` defaults to `true`; pass `false` to scroll.

### `run_flow`

`flow_path` is required. `dry_run` defaults to `true`; pass `false` to run the
flow for real. `include_step_details` defaults to `false`. `run_id` is optional.

### `get_run_artifacts`

`run_id` is required.

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

`click`, `type`, `key`, `scroll`, and `run_flow` default `dry_run` to true.
They send input only when the arguments include `"dry_run": false`.

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
  full inline details. That payload is capped at 32,000 characters; the
  response then sets `step_details_truncated: true` and `steps_omitted`. Prefer
  `get_run_artifacts` and `artifacts.run_dir` for large runs.
- `find` inlines at most 50 targets (`targets_truncated: true` when capped).

## First dry-run call

From any MCP client, prefer a non-actuating call first:

- `type` with `{"text": "hello", "dry_run": true}`
- or `click` with `{"query": "Submit", "dry_run": true}` once Screen Recording
  is confirmed via `open-frame doctor`

## Upgrade from 0.2.x

Contract `v0.3.0`. Envelope keys are unchanged. An existing 0.2.x client must:

- Send `"dry_run": false` on `click`, `type`, `key`, `scroll`, and `run_flow` when the call should send input. Omitting `dry_run` now previews the action.
- Treat `permission_denied` as a missing Screen Recording or Accessibility grant. The message names the process that needs the grant.
- Treat `screen_unavailable` as a locked or sleeping display. Wake and unlock the Mac. That code is not a missing grant.
- Pass exactly one of `key` or `combo` to `key`.
- Pass non-empty `text` to `type`.
- Expect `run_flow` with `include_step_details: true` to set `step_details_truncated` and `steps_omitted` when the inline steps exceed 32,000 characters.

## Troubleshooting

| Symptom | What to do |
|---|---|
| Server won't start / import error for `mcp` | `pip install "off-camber-open-frame[mcp]"` then retry |
| Client shows no tools | Confirm `command` points at the venv Python; restart the client |
| Capture / find failures | Run `open-frame doctor` and fix Screen Recording / Accessibility / tesseract |
| Tool returns `screen_unavailable` | The screen is locked or the display is asleep. Wake and unlock it. This is not a missing grant |
| Tool returns `permission_denied` | Screen Recording or Accessibility is missing for the process named in the message |
| Permission prompts never appear | Grant permissions to the **client host** process, not only Terminal |
| Tool returns `busy` | Wait until the in-flight call finishes. A timed-out call still counts until its worker stops |
| Tool returns `timeout` | The envelope `run_id` is the one `get_run_artifacts` accepts after the worker finishes. Raise `OPENFRAME_MCP_*_TIMEOUT_SEC` if the flow needs longer |
| Huge `run_flow` payloads | Default is summarized steps; use `get_run_artifacts` or opt into `include_step_details` |

See also [Troubleshooting](TROUBLESHOOTING.md),
[Contributing](CONTRIBUTING.md) for permission setup details, and
[Release gates](RELEASE_GATES.md) for the local live gate that includes an MCP
stdio smoke check.
