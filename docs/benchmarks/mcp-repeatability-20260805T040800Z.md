# MCP repeatability benchmark 20260805T040800Z

- Mode: `dry-run`
- Repetitions per flow: `5`
- Flows: `2`
- Total runs: `10`
- Pass rate: `100.0%`
- Median elapsed: `1465 ms`
- P95 elapsed: `1802 ms`

## Per-flow metrics

| Flow | Runs | Passes | Pass rate | Median ms | P95 ms |
|------|------|--------|-----------|-----------|--------|
| `examples/flows/mcp-dry-run-wait/flow.yaml` | 5 | 5 | 100.0% | 1173 | 1210 |
| `examples/flows/mcp-dry-run-actions/flow.yaml` | 5 | 5 | 100.0% | 1746 | 1802 |

## Sample results

| Flow | Repetition | Run ID | Exit | OK | Success | Elapsed ms | Error code |
|------|------------|--------|------|----|---------|------------|------------|
| `examples/flows/mcp-dry-run-wait/flow.yaml` | 1 | `mcp-bench-mcp-dry-run-wait-20260805T040800Z-01` | 0 | true | true | 1210 | `` |
| `examples/flows/mcp-dry-run-wait/flow.yaml` | 2 | `mcp-bench-mcp-dry-run-wait-20260805T040800Z-02` | 0 | true | true | 1177 | `` |
| `examples/flows/mcp-dry-run-wait/flow.yaml` | 3 | `mcp-bench-mcp-dry-run-wait-20260805T040800Z-03` | 0 | true | true | 1157 | `` |
| `examples/flows/mcp-dry-run-wait/flow.yaml` | 4 | `mcp-bench-mcp-dry-run-wait-20260805T040800Z-04` | 0 | true | true | 1173 | `` |
| `examples/flows/mcp-dry-run-wait/flow.yaml` | 5 | `mcp-bench-mcp-dry-run-wait-20260805T040800Z-05` | 0 | true | true | 1170 | `` |
| `examples/flows/mcp-dry-run-actions/flow.yaml` | 1 | `mcp-bench-mcp-dry-run-actions-20260805T040800Z-01` | 0 | true | true | 1802 | `` |
| `examples/flows/mcp-dry-run-actions/flow.yaml` | 2 | `mcp-bench-mcp-dry-run-actions-20260805T040800Z-02` | 0 | true | true | 1746 | `` |
| `examples/flows/mcp-dry-run-actions/flow.yaml` | 3 | `mcp-bench-mcp-dry-run-actions-20260805T040800Z-03` | 0 | true | true | 1720 | `` |
| `examples/flows/mcp-dry-run-actions/flow.yaml` | 4 | `mcp-bench-mcp-dry-run-actions-20260805T040800Z-04` | 0 | true | true | 1742 | `` |
| `examples/flows/mcp-dry-run-actions/flow.yaml` | 5 | `mcp-bench-mcp-dry-run-actions-20260805T040800Z-05` | 0 | true | true | 1755 | `` |
