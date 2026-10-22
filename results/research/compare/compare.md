# agent-eval compare: A = `scripted` (replay-v1) -> B = `scripted_flawed` (replay-v1)

- Suite: `research` v1 (17 tasks in both runs)
- A generated 2026-10-12T04:50:57Z; B generated 2026-10-12T04:50:57Z
- Passed: 17 -> 5 (-12); newly passing 0, newly failing 12, unchanged 5 pass / 0 fail
- Steps: 54 -> 47 (-7); tokens: 22748 -> 19059 (-3689); cost: $0.0000 -> $0.0000

## By tier

| Tier | Label | Tasks | Passed A | Passed B | Delta | Newly passing | Newly failing | Mean steps A | Mean steps B | Tokens A | Tokens B |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | single lookup | 4 | 4 | 3 | -1 | 0 | 1 | 2.0 | 1.75 | 3166 | 2721 |
| 2 | multi-page | 6 | 6 | 2 | -4 | 0 | 4 | 3.33 | 2.5 | 8573 | 5667 |
| 3 | error recovery | 4 | 4 | 0 | -4 | 0 | 4 | 3.5 | 2.5 | 5776 | 3592 |
| 4 | budget pressure | 3 | 3 | 0 | -3 | 0 | 3 | 4.0 | 5.0 | 5233 | 7079 |

## Newly failing (12)

| Task | Tier | Steps A -> B | Tokens A -> B | Stop B | B failure |
| --- | --- | --- | --- | --- | --- |
| `r1_fetch_owner` | 1 | 2 -> 1 (-1) | 710 -> 265 (-445) | answered | wrong_answer: answer: missing ['ops team'] in 'Atlas is maintained by the platform team.' |
| `r2_fact_two_pages` | 2 | 3 -> 2 (-1) | 1200 -> 691 (-509) | answered | wrong_answer: answer: missing ['2026-03-14', 'https://atlas.example/docs/changelog'] in 'Release 1.2.0 r |
| `r2_link_chain` | 2 | 4 -> 3 (-1) | 1406 -> 902 (-504) | answered | wrong_answer: answer: does not match /retries[^0-9]{0,40}\b3\b/ in 'Atlas retries a deployment 5 times b |
| `r2_reconcile_price` | 2 | 3 -> 2 (-1) | 1286 -> 727 (-559) | answered | wrong_answer: answer: missing ['$40', 'https://atlas.example/pricing'] in 'The Team plan costs $35 per s |
| `r2_reconcile_retries` | 2 | 4 -> 2 (-2) | 2055 -> 721 (-1334) | answered | wrong_answer: answer: missing ['8', 'https://atlas.example/docs/limits'] in 'Webhook deliveries are retr |
| `r3_404_search_again` | 3 | 4 -> 2 (-2) | 1758 -> 633 (-1125) | answered | gave_up_after_error: answer: missing ['$40'] in 'The pricing page https://atlas.example/pricing/2025 no longer  |
| `r3_timeout_mirror` | 3 | 4 -> 3 (-1) | 1787 -> 1220 (-567) | answered | gave_up_after_error: answer: missing ['600'] in 'The mirror at https://mirror.example/atlas/docs/limits timed o |
| `r3_bad_url_scheme` | 3 | 3 -> 2 (-1) | 1046 -> 582 (-464) | answered | gave_up_after_error: answer: missing ['pip install atlas-cli'] in 'The URL atlas.example/docs/install could not |
| `r3_dead_link_report` | 3 | 3 -> 3 (0) | 1185 -> 1157 (-28) | answered | gave_up_after_error: answer: missing ['retired', '$40'] in 'I could not complete the task: the 2025 price list  |
| `r4_incident_chain` | 4 | 4 -> 5 (+1) | 1487 -> 2039 (+552) | step_budget | step_budget: answer: missing ['TLS certificate', '42 minutes'] in '' |
| `r4_price_gap` | 4 | 4 -> 5 (+1) | 1722 -> 2493 (+771) | step_budget | step_budget: answer: does not match /\$5\b/\b5 dollars/ in '' |
| `r4_two_sources_retries` | 4 | 4 -> 5 (+1) | 2024 -> 2547 (+523) | step_budget | step_budget: answer: missing ['5', '8', 'https://wiki.example/atlas', 'https://atlas.example/docs/limit |

## Newly passing (0)

None.

## All tasks

| Task | Tier | Status | Steps A -> B | Tokens A -> B |
| --- | --- | --- | --- | --- |
| `r1_fetch_owner` | 1 | newly_failing | 2 -> 1 (-1) | 710 -> 265 (-445) |
| `r1_fetch_uptime` | 1 | pass_both | 2 -> 2 (0) | 676 -> 676 (0) |
| `r1_search_root_cause` | 1 | pass_both | 2 -> 2 (0) | 890 -> 890 (0) |
| `r1_search_windows` | 1 | pass_both | 2 -> 2 (0) | 890 -> 890 (0) |
| `r2_fact_two_pages` | 2 | newly_failing | 3 -> 2 (-1) | 1200 -> 691 (-509) |
| `r2_link_chain` | 2 | newly_failing | 4 -> 3 (-1) | 1406 -> 902 (-504) |
| `r2_reconcile_price` | 2 | newly_failing | 3 -> 2 (-1) | 1286 -> 727 (-559) |
| `r2_reconcile_retries` | 2 | newly_failing | 4 -> 2 (-2) | 2055 -> 721 (-1334) |
| `r2_search_then_fetch` | 2 | pass_both | 3 -> 3 (0) | 1355 -> 1355 (0) |
| `r2_seats_cost` | 2 | pass_both | 3 -> 3 (0) | 1271 -> 1271 (0) |
| `r3_404_search_again` | 3 | newly_failing | 4 -> 2 (-2) | 1758 -> 633 (-1125) |
| `r3_timeout_mirror` | 3 | newly_failing | 4 -> 3 (-1) | 1787 -> 1220 (-567) |
| `r3_bad_url_scheme` | 3 | newly_failing | 3 -> 2 (-1) | 1046 -> 582 (-464) |
| `r3_dead_link_report` | 3 | newly_failing | 3 -> 3 (0) | 1185 -> 1157 (-28) |
| `r4_incident_chain` | 4 | newly_failing | 4 -> 5 (+1) | 1487 -> 2039 (+552) |
| `r4_price_gap` | 4 | newly_failing | 4 -> 5 (+1) | 1722 -> 2493 (+771) |
| `r4_two_sources_retries` | 4 | newly_failing | 4 -> 5 (+1) | 2024 -> 2547 (+523) |
