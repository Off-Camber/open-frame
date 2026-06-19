# MCP pilot

This example demonstrates a compact, deterministic MCP-style loop over Open Frame tools.

## Run

```bash
python examples/mcp-pilot/pilot.py
```

The pilot calls:

1. `open-frame mcp list-tools --json`
2. `open-frame mcp call capture --args-json ...`
3. `open-frame mcp call find --args-json ...`
4. `open-frame mcp call click --args-json ...`
5. `open-frame mcp call run_flow --args-json ...`
6. `open-frame mcp call get_run_artifacts --args-json ...`

All tool calls return the same envelope shape:

- `ok`
- `tool`
- `run_id`
- `data`
- `error`
- `artifacts`
