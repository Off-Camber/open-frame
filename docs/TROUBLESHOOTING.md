# Troubleshooting

## No matching distribution

`No matching distribution found for off-camber-open-frame` together with
`from versions: none` means pip never saw the package. Open Frame requires
Python 3.11 or newer. The `python3` that ships with the Xcode command-line
tools is older, and its pip (21.x) cannot read the current PyPI index, so the
error does not mention the Python requirement.

Check the interpreter, recreate the virtual environment with it, and install
with that environment's pip:

```bash
python3.11 --version
python3.11 -m venv ~/open-frame-env
source ~/open-frame-env/bin/activate
python -m pip install --upgrade pip
python -m pip install "off-camber-open-frame[mcp,ocr,act,flow,template]"
```

Use `/opt/homebrew/bin/python3.11` when `python3.11` is not on `PATH`. Upgrading
pip inside a Python 3.9 environment still cannot install the package.

## Doctor reports an extra as not installed

`open-frame doctor` inspects the interpreter that launched it. The `python`
line prints that path. A `skip` row whose detail starts with `optional, not
installed` is an extra you did not install. `extra_agent` is that row after
the standard install, because the `agent` extra is separate. Its line is a
`note`. A `fail` line is a `hint` and is the row to act on.

`skip` for `mcp` or `template` after you installed those extras means the
distribution is absent from **this** interpreter.

On a shared Mac, `/opt/homebrew/bin/open-frame` may belong to the account that
installed Homebrew. Running that binary checks Homebrew's Python, which does
not see packages installed in `~/open-frame-env`. Confirm with the environment
you created:

```bash
source ~/open-frame-env/bin/activate
python -m pip show mcp numpy
python -m openframe.cli doctor
```

`python -m pip check` can be clean in the virtual environment while a different
`open-frame` still reports `mcp` and `template` as skipped. Install again only
when `python -m pip show` inside that same environment says the distribution
is missing.

When the report says `installed but not importable`, the distribution is
present and the import failed. That is a broken install for this interpreter,
not a cue to point doctor at a different Python.

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
`PATH`. On macOS, from an account that can write to Homebrew:

```bash
brew install tesseract
tesseract --version
```

When `brew` cannot write to `/opt/homebrew/Cellar`, another account owns
Homebrew. Run `brew install tesseract` from that account. Leave ownership of
`/opt/homebrew` unchanged, and do not grant this account administrator rights
just to install Tesseract. After the owning account installs it, other
accounts use the same binary. If it is still not on `PATH`, call
`/opt/homebrew/bin/tesseract`.

OCR cannot run without it. A `find` can still return accessibility matches.
A missing binary is not a Screen Recording or Accessibility denial.

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
