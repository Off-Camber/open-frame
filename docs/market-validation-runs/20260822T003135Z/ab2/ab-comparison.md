# A/B comparison — ab2 (Capability — native Notes find)

- Thesis: `capability`
- Verdict: **capability** — Open Frame required: hybrid met the pass threshold; browser-only did not pass. Not an efficiency claim.

| Arm | pass_rate | n_pass | n_fail | n_blocked | median wall_s | median tokens | median $ | median steps |
|---|---|---|---|---|---|---|---|---|
| `browser-only` | 0 | 0 | 3 | 0 | 6.721 | 1e+04 | 0.004265 | 2 |
| `hybrid` | 1 | 3 | 0 | 0 | 16.94 | 2.209e+04 | 0.009252 | 4 |

Deltas are `hybrid - browser-only` (negative means hybrid cheaper/faster/fewer).

- Δ wall_seconds: 10.22
- Δ total_tokens: 1.209e+04
- Δ cost_usd: 0.004988
- Δ steps: 2

