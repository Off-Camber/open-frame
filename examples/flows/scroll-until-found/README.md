# Safari below-fold scroll probe

Demonstrates `scroll_until_found` on a tall local HTML page.

## Run

```bash
chmod +x scripts/run_scroll_probe.sh
./scripts/run_scroll_probe.sh --json
```

The script resolves `examples/demo/scroll-probe/index.html` to a `file://` URL,
opens it in Safari, then finds `OFSCROLLMARKER` with bounded scrolling.
Non-destructive (find only).
