# agent-eval compare: A = `scripted` (replay-v1) -> B = `scripted_flawed` (replay-v1)

- Suite: `basic` v1 (29 tasks in both runs)
- A generated 2026-10-12T04:50:57Z; B generated 2026-10-12T04:50:57Z
- Passed: 29 -> 14 (-15); newly passing 0, newly failing 15, unchanged 14 pass / 0 fail
- Steps: 93 -> 69 (-24); tokens: 74971 -> 54703 (-20268); cost: $0.0000 -> $0.0000

## By tier

| Tier | Label | Tasks | Passed A | Passed B | Delta | Newly passing | Newly failing | Mean steps A | Mean steps B | Tokens A | Tokens B |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | single tool | 10 | 10 | 10 | 0 | 0 | 0 | 2.0 | 2.0 | 15539 | 15539 |
| 2 | multi-step | 10 | 10 | 4 | -6 | 0 | 6 | 3.7 | 3.1 | 30159 | 24945 |
| 3 | error recovery | 9 | 9 | 0 | -9 | 0 | 9 | 4.0 | 2.0 | 29273 | 14219 |

## Newly failing (15)

| Task | Tier | Steps A -> B | Tokens A -> B | Stop B | B failure |
| --- | --- | --- | --- | --- | --- |
| `t2_q1_vs_q2` | 2 | 4 -> 3 (-1) | 3200 -> 2373 (-827) | answered | wrong_answer: answer: missing ['530'] in 'Q2 exceeded Q1 by region,amount\nnorth,1500\nsouth,900\neast,6 |
| `t2_summary_file` | 2 | 4 -> 3 (-1) | 3332 -> 2444 (-888) | answered | wrong_state: state: /docs/summary.txt content mismatch (got None) |
| `t2_reassign_dana` | 2 | 4 -> 3 (-1) | 3285 -> 2408 (-877) | answered | wrong_state: state: ticket T-1003.assignee is 'dana', expected 'lee' |
| `t2_resolve_with_note` | 2 | 4 -> 3 (-1) | 3301 -> 2423 (-878) | answered | wrong_state: state: ticket T-1002.status is 'in_progress', expected 'resolved' |
| `t2_config_bump` | 2 | 4 -> 3 (-1) | 3241 -> 2376 (-865) | answered | wrong_state: state: /config/app.json does not contain '"retries": 6' |
| `t2_north_average` | 2 | 5 -> 4 (-1) | 4148 -> 3269 (-879) | answered | wrong_state: state: /reports/north_avg.txt content mismatch (got None) |
| `t3_missing_file` | 3 | 4 -> 2 (-2) | 3136 -> 1545 (-1591) | answered | gave_up_after_error: answer: missing ['renew certificates', 'rotate API keys', 'archive old tickets'] in 'I cou |
| `t3_wrong_dir` | 3 | 5 -> 2 (-3) | 3973 -> 1549 (-2424) | answered | gave_up_after_error: answer: missing ['Project Atlas'] in 'I could not complete the task because a tool failed: |
| `t3_dir_as_file` | 3 | 4 -> 2 (-2) | 3154 -> 1548 (-1606) | answered | gave_up_after_error: answer: missing ['1.2.0'] in 'I could not complete the task because a tool failed: error:  |
| `t3_search_fallback` | 3 | 5 -> 2 (-3) | 4114 -> 1604 (-2510) | answered | gave_up_after_error: answer: missing ['sales_q2.csv', '3010'] in 'I could not complete the task because a tool  |
| `t3_ticket_404` | 3 | 4 -> 2 (-2) | 3549 -> 1616 (-1933) | answered | gave_up_after_error: state: ticket T-1004.priority is 'low', expected 'high' |
| `t3_closed_ticket` | 3 | 5 -> 2 (-3) | 4160 -> 1579 (-2581) | answered | gave_up_after_error: state: ticket T-1006.status is 'closed', expected 'resolved' |
| `t3_invalid_status` | 3 | 3 -> 2 (-1) | 2430 -> 1609 (-821) | answered | gave_up_after_error: state: ticket T-1002.status is 'in_progress', expected 'resolved' |
| `t3_bad_argument` | 3 | 3 -> 2 (-1) | 2361 -> 1569 (-792) | answered | gave_up_after_error: answer: missing ['30'] in "I could not complete the task because a tool failed: invalid ar |
| `t3_unknown_tool` | 3 | 3 -> 2 (-1) | 2396 -> 1600 (-796) | answered | gave_up_after_error: state: /notes/todo.txt content mismatch (got '- renew certificates\n- rotate API keys\n- a |

## Newly passing (0)

None.

## All tasks

| Task | Tier | Status | Steps A -> B | Tokens A -> B |
| --- | --- | --- | --- | --- |
| `t1_read_readme` | 1 | pass_both | 2 -> 2 (0) | 1558 -> 1558 (0) |
| `t1_list_data` | 1 | pass_both | 2 -> 2 (0) | 1516 -> 1516 (0) |
| `t1_write_hello` | 1 | pass_both | 2 -> 2 (0) | 1562 -> 1562 (0) |
| `t1_search_login` | 1 | pass_both | 2 -> 2 (0) | 1527 -> 1527 (0) |
| `t1_calc_percent` | 1 | pass_both | 2 -> 2 (0) | 1522 -> 1522 (0) |
| `t1_calc_power` | 1 | pass_both | 2 -> 2 (0) | 1526 -> 1526 (0) |
| `t1_ticket_get` | 1 | pass_both | 2 -> 2 (0) | 1594 -> 1594 (0) |
| `t1_ticket_list_open` | 1 | pass_both | 2 -> 2 (0) | 1628 -> 1628 (0) |
| `t1_ticket_note` | 1 | pass_both | 2 -> 2 (0) | 1554 -> 1554 (0) |
| `t1_ticket_priority` | 1 | pass_both | 2 -> 2 (0) | 1552 -> 1552 (0) |
| `t2_sum_q1` | 2 | pass_both | 3 -> 3 (0) | 2343 -> 2343 (0) |
| `t2_q1_vs_q2` | 2 | newly_failing | 4 -> 3 (-1) | 3200 -> 2373 (-827) |
| `t2_summary_file` | 2 | newly_failing | 4 -> 3 (-1) | 3332 -> 2444 (-888) |
| `t2_copy_file` | 2 | pass_both | 3 -> 3 (0) | 2402 -> 2402 (0) |
| `t2_append_todo` | 2 | pass_both | 3 -> 3 (0) | 2408 -> 2408 (0) |
| `t2_reassign_dana` | 2 | newly_failing | 4 -> 3 (-1) | 3285 -> 2408 (-877) |
| `t2_resolve_with_note` | 2 | newly_failing | 4 -> 3 (-1) | 3301 -> 2423 (-878) |
| `t2_config_bump` | 2 | newly_failing | 4 -> 3 (-1) | 3241 -> 2376 (-865) |
| `t2_open_tickets_report` | 2 | pass_both | 3 -> 3 (0) | 2499 -> 2499 (0) |
| `t2_north_average` | 2 | newly_failing | 5 -> 4 (-1) | 4148 -> 3269 (-879) |
| `t3_missing_file` | 3 | newly_failing | 4 -> 2 (-2) | 3136 -> 1545 (-1591) |
| `t3_wrong_dir` | 3 | newly_failing | 5 -> 2 (-3) | 3973 -> 1549 (-2424) |
| `t3_dir_as_file` | 3 | newly_failing | 4 -> 2 (-2) | 3154 -> 1548 (-1606) |
| `t3_search_fallback` | 3 | newly_failing | 5 -> 2 (-3) | 4114 -> 1604 (-2510) |
| `t3_ticket_404` | 3 | newly_failing | 4 -> 2 (-2) | 3549 -> 1616 (-1933) |
| `t3_closed_ticket` | 3 | newly_failing | 5 -> 2 (-3) | 4160 -> 1579 (-2581) |
| `t3_invalid_status` | 3 | newly_failing | 3 -> 2 (-1) | 2430 -> 1609 (-821) |
| `t3_bad_argument` | 3 | newly_failing | 3 -> 2 (-1) | 2361 -> 1569 (-792) |
| `t3_unknown_tool` | 3 | newly_failing | 3 -> 2 (-1) | 2396 -> 1600 (-796) |
