# Agent examples

Reference scripts for Phase A agent integration.

## Read-only probe

Runs a safe end-to-end agent loop (`AgentRunner` + `AnthropicProvider`) that
captures the screen, runs a find-style check, and reports the result.

```bash
python examples/agents/read_only_probe.py
```

Optional flags:

- `--task "..."` override the natural-language task
- `--max-steps 8` cap agent turns
- `--model claude-haiku-4-5-20251001` override model for this run

Prerequisites:

- `pip install -e ".[agent]"`
- `ANTHROPIC_API_KEY` exported in your shell
- macOS Screen Recording permission granted for terminal/python process
