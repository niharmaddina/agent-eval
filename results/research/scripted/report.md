# agent-eval report: `scripted` (replay-v1)

- Suite: `research` v1 (17 tasks)
- Generated: 2026-10-12T04:50:57Z
- Token counts: estimated (len/4 heuristic)
- Estimated cost: $0.0000 ($0.0000 per success)
- Mean latency: not reported (replay provider or no calls)
- Baseline note: This run used a deterministic replay provider. The numbers describe the harness and the task suite, not any language model.

## Summary by tier

| Tier | What it measures | Tasks | Passed | Success | Mean steps | Tool calls | Tool errors | Tool error rate | Validation errors |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | single lookup | 4 | 4 | 100.0% | 2.0 | 4 | 0 | 0.0% | 0 |
| 2 | multi-page | 6 | 6 | 100.0% | 3.33 | 14 | 0 | 0.0% | 0 |
| 3 | error recovery | 4 | 4 | 100.0% | 3.5 | 10 | 4 | 40.0% | 0 |
| 4 | budget pressure | 3 | 3 | 100.0% | 4.0 | 9 | 0 | 0.0% | 0 |
| all |  | 17 | 17 | 100.0% | 3.18 | 37 | 4 | 10.8% | 0 |

Tokens: 21199 in / 1549 out.

## Failure breakdown

No failures.

## Per task

| Task | Tier | Result | Steps | Tool calls | Tool errors | Stop | Detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `r1_fetch_owner` | 1 | pass | 2 | 1 | 0 | answered |  |
| `r1_fetch_uptime` | 1 | pass | 2 | 1 | 0 | answered |  |
| `r1_search_root_cause` | 1 | pass | 2 | 1 | 0 | answered |  |
| `r1_search_windows` | 1 | pass | 2 | 1 | 0 | answered |  |
| `r2_fact_two_pages` | 2 | pass | 3 | 2 | 0 | answered |  |
| `r2_link_chain` | 2 | pass | 4 | 3 | 0 | answered |  |
| `r2_reconcile_price` | 2 | pass | 3 | 2 | 0 | answered |  |
| `r2_reconcile_retries` | 2 | pass | 4 | 3 | 0 | answered |  |
| `r2_search_then_fetch` | 2 | pass | 3 | 2 | 0 | answered |  |
| `r2_seats_cost` | 2 | pass | 3 | 2 | 0 | answered |  |
| `r3_404_search_again` | 3 | pass | 4 | 3 | 1 | answered |  |
| `r3_timeout_mirror` | 3 | pass | 4 | 3 | 1 | answered |  |
| `r3_bad_url_scheme` | 3 | pass | 3 | 2 | 1 | answered |  |
| `r3_dead_link_report` | 3 | pass | 3 | 2 | 1 | answered |  |
| `r4_incident_chain` | 4 | pass | 4 | 3 | 0 | answered |  |
| `r4_price_gap` | 4 | pass | 4 | 3 | 0 | answered |  |
| `r4_two_sources_retries` | 4 | pass | 4 | 3 | 0 | answered |  |
