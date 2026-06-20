# MCP repeatability benchmark

Use this benchmark to measure `run_flow` reliability and runtime through the MCP surface.

It is the evidence task for Action Plan checkpoint item `C.8`.

## What it measures

- pass rate across repeated `mcp call run_flow` executions
- median elapsed runtime
- p95 elapsed runtime
- per-run error codes for failures

## Run the benchmark

Dry-run on one flow:

```bash
.venv311/bin/python scripts/mcp_repeatability_benchmark.py \
  --flow examples/flows/outlook-new-email/flow.yaml \
  --repetitions 5 \
  --mode dry-run
```

Dry-run on multiple representative flows:

```bash
.venv311/bin/python scripts/mcp_repeatability_benchmark.py \
  --flow examples/flows/outlook-new-email/flow.yaml \
  --flow examples/flows/outlook-browser-outlook/flow.yaml \
  --flow examples/flows/outlook-m365-email/flow.yaml \
  --repetitions 5 \
  --mode dry-run
```

Live run (real actions):

```bash
.venv311/bin/python scripts/mcp_repeatability_benchmark.py \
  --flow examples/flows/outlook-new-email/flow.yaml \
  --repetitions 3 \
  --mode live
```

## Outputs

Reports are written to `docs/benchmarks/`:

- `mcp-repeatability-<timestamp>.json` (machine-readable)
- `mcp-repeatability-<timestamp>.md` (quick human summary)

Each sample includes:

- `run_id`
- `elapsed_ms`
- `ok` and `success`
- `error_code` and `error_message`
- artifact pointers from MCP response

## Suggested release-gate interpretation

For checkpoint validation, start with:

- dry-run pass rate >= 95% on representative flows
- stable error codes on failures (no envelope drift)
- no large runtime regressions vs previous report
