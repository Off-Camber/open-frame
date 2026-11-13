# Troubleshooting

## Permissions were granted to the wrong app

Screen Recording and Accessibility apply to the process that captures or
clicks. A terminal grant does not cover Cursor, and a Cursor grant does not
cover Terminal.

`open-frame doctor` names the process that needs the grant. For an MCP client,
grant the client app (Cursor or Claude Desktop), not the terminal that printed
the config. Restart that app after changing the grant.

`permission_denied` means the grant is missing for the named process.
`screen_unavailable` means the screen is locked or the display is asleep. Wake
the display and unlock it. That result is not a missing grant.

## Tesseract is missing

`open-frame doctor` fails the `tesseract` check when the binary is not on
`PATH`. On macOS:

```bash
brew install tesseract
```

OCR cannot run without it. A `find` can still return accessibility matches.

## `open-frame` is not on PATH

The install lives in the virtualenv. Activate that environment, or call the
module with its interpreter:

```bash
python -m openframe.cli doctor
```

## The MCP client points at the wrong Python

`open-frame doctor --mcp` prints a config whose `command` is the current
interpreter. Use that path. A system Python that does not have Open Frame
installed will start a server with no tools, or fail to start.

## Artifacts

Runs are stored in `~/.openframe/runs`, or in `OPENFRAME_RUNS_DIR` when that
variable is set. Tool results include the absolute path. Remove old runs with:

```bash
open-frame runs prune --older-than 7d --keep 20
```

`--older-than` deletes runs older than that age. `--keep` then retains that
many of the newest runs that remain. Pass either flag, or both.

## `find` exits 0 and `count` is 0

The command worked, and that text was not on screen. A capture failure or a
missing permission exits non-zero.
