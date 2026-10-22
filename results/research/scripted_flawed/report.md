# agent-eval report: `scripted_flawed` (replay-v1)

- Suite: `research` v1 (17 tasks)
- Generated: 2026-10-12T04:50:57Z
- Token counts: estimated (len/4 heuristic)
- Estimated cost: $0.0000 ($0.0000 per success)
- Mean latency: not reported (replay provider or no calls)
- Baseline note: This run used a deterministic replay provider. The numbers describe the harness and the task suite, not any language model.

## Summary by tier

| Tier | What it measures | Tasks | Passed | Success | Mean steps | Tool calls | Tool errors | Tool error rate | Validation errors |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | single lookup | 4 | 3 | 75.0% | 1.75 | 3 | 0 | 0.0% | 0 |
| 2 | multi-page | 6 | 2 | 33.3% | 2.5 | 9 | 0 | 0.0% | 0 |
| 3 | error recovery | 4 | 0 | 0.0% | 2.5 | 6 | 4 | 66.7% | 0 |
| 4 | budget pressure | 3 | 0 | 0.0% | 5.0 | 15 | 1 | 6.7% | 0 |
| all |  | 17 | 5 | 29.4% | 2.76 | 33 | 5 | 15.2% | 0 |

Tokens: 17988 in / 1071 out.

## Failure breakdown

| Category | Count |
| --- | --- |
| gave_up_after_error | 4 |
| step_budget | 3 |
| wrong_answer | 5 |

## Per task

| Task | Tier | Result | Steps | Tool calls | Tool errors | Stop | Detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `r1_fetch_owner` | 1 | FAIL | 1 | 0 | 0 | answered | wrong_answer: answer: missing ['ops team'] in 'Atlas is maintained by the platform team.' |
| `r1_fetch_uptime` | 1 | pass | 2 | 1 | 0 | answered |  |
| `r1_search_root_cause` | 1 | pass | 2 | 1 | 0 | answered |  |
| `r1_search_windows` | 1 | pass | 2 | 1 | 0 | answered |  |
| `r2_fact_two_pages` | 2 | FAIL | 2 | 1 | 0 | answered | wrong_answer: answer: missing ['2026-03-14', 'https://atlas.example/docs/changelog'] in 'Release 1.2.0 r |
| `r2_link_chain` | 2 | FAIL | 3 | 2 | 0 | answered | wrong_answer: answer: does not match /retries[^0-9]{0,40}\b3\b/ in 'Atlas retries a deployment 5 times b |
| `r2_reconcile_price` | 2 | FAIL | 2 | 1 | 0 | answered | wrong_answer: answer: missing ['$40', 'https://atlas.example/pricing'] in 'The Team plan costs $35 per s |
| `r2_reconcile_retries` | 2 | FAIL | 2 | 1 | 0 | answered | wrong_answer: answer: missing ['8', 'https://atlas.example/docs/limits'] in 'Webhook deliveries are retr |
| `r2_search_then_fetch` | 2 | pass | 3 | 2 | 0 | answered |  |
| `r2_seats_cost` | 2 | pass | 3 | 2 | 0 | answered |  |
| `r3_404_search_again` | 3 | FAIL | 2 | 1 | 1 | answered | gave_up_after_error: answer: missing ['$40'] in 'The pricing page https://atlas.example/pricing/2025 no longer  |
| `r3_timeout_mirror` | 3 | FAIL | 3 | 2 | 1 | answered | gave_up_after_error: answer: missing ['600'] in 'The mirror at https://mirror.example/atlas/docs/limits timed o |
| `r3_bad_url_scheme` | 3 | FAIL | 2 | 1 | 1 | answered | gave_up_after_error: answer: missing ['pip install atlas-cli'] in 'The URL atlas.example/docs/install could not |
| `r3_dead_link_report` | 3 | FAIL | 3 | 2 | 1 | answered | gave_up_after_error: answer: missing ['retired', '$40'] in 'I could not complete the task: the 2025 price list  |
| `r4_incident_chain` | 4 | FAIL | 5 | 5 | 0 | step_budget | step_budget: answer: missing ['TLS certificate', '42 minutes'] in '' |
| `r4_price_gap` | 4 | FAIL | 5 | 5 | 0 | step_budget | step_budget: answer: does not match /\$5\b/\b5 dollars/ in '' |
| `r4_two_sources_retries` | 4 | FAIL | 5 | 5 | 1 | step_budget | step_budget: answer: missing ['5', '8', 'https://wiki.example/atlas', 'https://atlas.example/docs/limit |
