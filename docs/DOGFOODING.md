# Dogfooding log (beta robustness)

Short evidence that Open Frame MCP tools work from a real client host.

| When (UTC) | Client | What we did | Result |
|---|---|---|---|
| 2026-08-05 | Cursor (this workspace) | `open-frame mcp list-tools --json`; dry-run `type`; template icon probe; scroll probe via `./scripts/run_scroll_probe.sh` | Tools listed including `scroll`; dry-run ok; scroll marker found after 5 scrolls |
| 2026-08-05 | Local CLI | App matrix `./scripts/app_matrix_gate.sh` → `…20260805T040506Z` | **6/6 pass** (Finder + Calendar recovered after focus hardening) |
| 2026-08-05 | Local CLI | MCP dry-run repeatability (5× wait + 5× actions) → `docs/benchmarks/mcp-repeatability-20260805T040800Z.md` | **10/10 (100%)** |
| 2026-08-05 | Local CLI / MCP adapter | Prior agent acceptance evidence under `docs/acceptance-runs/` | Prior green runs on audited Mac |

## Notes

- Prefer sequential tool calls on one stdio server (see [MCP_SERVER.md](MCP_SERVER.md)).
- After timeouts, restart the MCP server process before continuing.
