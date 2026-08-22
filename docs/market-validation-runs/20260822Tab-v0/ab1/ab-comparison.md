# A/B comparison — ab1 (Efficiency — web heading extraction)

- Thesis: `efficiency`
- Verdict: **efficiency** — Hybrid is cheaper on median cost_usd with pass rate at least as high as browser-only.

| Arm | pass_rate | n_pass | n_fail | n_blocked | median wall_s | median tokens | median $ | median steps |
|---|---|---|---|---|---|---|---|---|
| `browser-only` | 1 | 3 | 0 | 0 | 15.03 | 3.932e+04 | 0.02594 | 6 |
| `hybrid` | 1 | 3 | 0 | 0 | 11.91 | 2.962e+04 | 0.01595 | 5 |

Deltas are `hybrid - browser-only` (negative means hybrid cheaper/faster/fewer).

- Δ wall_seconds: -3.122
- Δ total_tokens: -9707
- Δ cost_usd: -0.009993
- Δ steps: -1

