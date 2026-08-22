# A/B comparison stamp — 20260822Tab-v0

N=3 repeats per arm, Anthropic Haiku, `flash_mode`, judge off, `calculate_cost=True`.

| Pair | Thesis | Verdict |
|---|---|---|
| [AB1](ab1/ab-comparison.md) | efficiency (web H1) | **efficiency** — hybrid cheaper on median `$` (3/3 vs 3/3) |
| [AB2](ab2/ab-comparison.md) | capability (native Notes find) | **capability** — hybrid 3/3 pass; browser-only 3/3 fail. Not a cost claim. |

Reproduce:

```bash
python examples/market-validation/run_scenario.py --ab ab1 --ab ab2 --repeats 3
```

Note: the hybrid arm uses a trimmed browser-use tool schema (see `run_scenario.py`), so AB1 savings mix Open Frame availability with a smaller action space. AB2 remains the capability test.
