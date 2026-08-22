# A/B comparison — ab2 (Capability — native Notes find)

- Thesis: `capability`
- Verdict: **capability** — Open Frame required: hybrid met the pass threshold; browser-only did not pass. Not an efficiency claim.

| Arm | pass_rate | n_pass | n_fail | n_blocked | median wall_s | median tokens | median $ | median steps |
|---|---|---|---|---|---|---|---|---|
| `browser-only` | 0 | 0 | 3 | 0 | 6.355 | 9947 | 0.00396 | 2 |
| `hybrid` | 1 | 3 | 0 | 0 | 23.23 | 4.412e+04 | 0.01895 | 7 |

Deltas are `hybrid - browser-only` (negative means hybrid cheaper/faster/fewer).

- Δ wall_seconds: 16.87
- Δ total_tokens: 3.418e+04
- Δ cost_usd: 0.01499
- Δ steps: 5

