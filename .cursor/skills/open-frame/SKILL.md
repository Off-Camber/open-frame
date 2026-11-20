---
name: open-frame
description: >-
  Brief a Cursor agent that is about to call Open Frame. Use when the task
  uses Open Frame, open-frame, a desktop capture, or an MCP click, key, or
  type on a Mac. Cursor loads this skill. Claude Desktop and any other client
  do not.
---

# Open Frame

This is a briefing, not the contract. Read `docs/MCP_SERVER.md` for the tool contract and `docs/VISION.md` for the product boundary. Do not treat this file as either document.

Open Frame executes a step the agent has already chosen. It does not plan from a bare sentence, move the caret, or send input on its own.

The server already states these rules in its tool text:

- Search a window capture and pass its `image_path` as `frame_path`.
- Pass `dry_run=false` to send input.
- Stop on `ambiguous_target`.

A live click includes `clicked_label`. A live click, key, or type includes `caret`. A dry run omits `caret`.
