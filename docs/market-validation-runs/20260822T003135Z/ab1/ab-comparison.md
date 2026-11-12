# A/B comparison — ab1 (Efficiency — web heading extraction)

- Thesis: `efficiency`
- Verdict: **efficiency** — Hybrid is cheaper on median cost_usd with pass rate at least as high as browser-only.

| Arm | pass_rate | n_pass | n_fail | n_blocked | median wall_s | median tokens | median $ | median steps |
|---|---|---|---|---|---|---|---|---|
| `browser-only` | 1 | 3 | 0 | 0 | 11.02 | 2.957e+04 | 0.0156 | 4 |
| `hybrid` | 1 | 3 | 0 | 0 | 10.66 | 2.237e+04 | 0.01212 | 4 |

Deltas are `hybrid - browser-only` (negative means hybrid cheaper/faster/fewer).

- Δ wall_seconds: -0.364
- Δ total_tokens: -7202
- Δ cost_usd: -0.003486
- Δ steps: 0

