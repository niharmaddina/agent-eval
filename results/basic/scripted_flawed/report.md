# agent-eval report: `scripted_flawed` (replay-v1)

- Suite: `basic` v1 (29 tasks)
- Generated: 2026-10-12T04:50:57Z
- Token counts: estimated (len/4 heuristic)
- Estimated cost: $0.0000 ($0.0000 per success)
- Mean latency: not reported (replay provider or no calls)
- Baseline note: This run used a deterministic replay provider. The numbers describe the harness and the task suite, not any language model.

## Summary by tier

| Tier | What it measures | Tasks | Passed | Success | Mean steps | Tool calls | Tool errors | Tool error rate | Validation errors |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | single tool | 10 | 10 | 100.0% | 2.0 | 10 | 0 | 0.0% | 0 |
| 2 | multi-step | 10 | 4 | 40.0% | 3.1 | 21 | 0 | 0.0% | 0 |
| 3 | error recovery | 9 | 0 | 0.0% | 2.0 | 9 | 6 | 66.7% | 3 |
| all |  | 29 | 14 | 48.3% | 2.38 | 40 | 6 | 15.0% | 3 |

Tokens: 53777 in / 926 out.

## Failure breakdown

| Category | Count |
| --- | --- |
| gave_up_after_error | 9 |
| wrong_answer | 1 |
| wrong_state | 5 |

## Per task

| Task | Tier | Result | Steps | Tool calls | Tool errors | Stop | Detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `t1_read_readme` | 1 | pass | 2 | 1 | 0 | answered |  |
| `t1_list_data` | 1 | pass | 2 | 1 | 0 | answered |  |
| `t1_write_hello` | 1 | pass | 2 | 1 | 0 | answered |  |
| `t1_search_login` | 1 | pass | 2 | 1 | 0 | answered |  |
| `t1_calc_percent` | 1 | pass | 2 | 1 | 0 | answered |  |
| `t1_calc_power` | 1 | pass | 2 | 1 | 0 | answered |  |
| `t1_ticket_get` | 1 | pass | 2 | 1 | 0 | answered |  |
| `t1_ticket_list_open` | 1 | pass | 2 | 1 | 0 | answered |  |
| `t1_ticket_note` | 1 | pass | 2 | 1 | 0 | answered |  |
| `t1_ticket_priority` | 1 | pass | 2 | 1 | 0 | answered |  |
| `t2_sum_q1` | 2 | pass | 3 | 2 | 0 | answered |  |
| `t2_q1_vs_q2` | 2 | FAIL | 3 | 2 | 0 | answered | wrong_answer: answer: missing ['530'] in 'Q2 exceeded Q1 by region,amount\nnorth,1500\nsouth,900\neast,6 |
| `t2_summary_file` | 2 | FAIL | 3 | 2 | 0 | answered | wrong_state: state: /docs/summary.txt content mismatch (got None) |
| `t2_copy_file` | 2 | pass | 3 | 2 | 0 | answered |  |
| `t2_append_todo` | 2 | pass | 3 | 2 | 0 | answered |  |
| `t2_reassign_dana` | 2 | FAIL | 3 | 2 | 0 | answered | wrong_state: state: ticket T-1003.assignee is 'dana', expected 'lee' |
| `t2_resolve_with_note` | 2 | FAIL | 3 | 2 | 0 | answered | wrong_state: state: ticket T-1002.status is 'in_progress', expected 'resolved' |
| `t2_config_bump` | 2 | FAIL | 3 | 2 | 0 | answered | wrong_state: state: /config/app.json does not contain '"retries": 6' |
| `t2_open_tickets_report` | 2 | pass | 3 | 2 | 0 | answered |  |
| `t2_north_average` | 2 | FAIL | 4 | 3 | 0 | answered | wrong_state: state: /reports/north_avg.txt content mismatch (got None) |
| `t3_missing_file` | 3 | FAIL | 2 | 1 | 1 | answered | gave_up_after_error: answer: missing ['renew certificates', 'rotate API keys', 'archive old tickets'] in 'I cou |
| `t3_wrong_dir` | 3 | FAIL | 2 | 1 | 1 | answered | gave_up_after_error: answer: missing ['Project Atlas'] in 'I could not complete the task because a tool failed: |
| `t3_dir_as_file` | 3 | FAIL | 2 | 1 | 1 | answered | gave_up_after_error: answer: missing ['1.2.0'] in 'I could not complete the task because a tool failed: error:  |
| `t3_search_fallback` | 3 | FAIL | 2 | 1 | 1 | answered | gave_up_after_error: answer: missing ['sales_q2.csv', '3010'] in 'I could not complete the task because a tool  |
| `t3_ticket_404` | 3 | FAIL | 2 | 1 | 1 | answered | gave_up_after_error: state: ticket T-1004.priority is 'low', expected 'high' |
| `t3_closed_ticket` | 3 | FAIL | 2 | 1 | 1 | answered | gave_up_after_error: state: ticket T-1006.status is 'closed', expected 'resolved' |
| `t3_invalid_status` | 3 | FAIL | 2 | 1 | 0 | answered | gave_up_after_error: state: ticket T-1002.status is 'in_progress', expected 'resolved' |
| `t3_bad_argument` | 3 | FAIL | 2 | 1 | 0 | answered | gave_up_after_error: answer: missing ['30'] in "I could not complete the task because a tool failed: invalid ar |
| `t3_unknown_tool` | 3 | FAIL | 2 | 1 | 0 | answered | gave_up_after_error: state: /notes/todo.txt content mismatch (got '- renew certificates\n- rotate API keys\n- a |
