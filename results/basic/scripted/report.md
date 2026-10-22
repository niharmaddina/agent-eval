# agent-eval report: `scripted` (replay-v1)

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
| 2 | multi-step | 10 | 10 | 100.0% | 3.7 | 27 | 0 | 0.0% | 0 |
| 3 | error recovery | 9 | 9 | 100.0% | 4.0 | 27 | 6 | 22.2% | 3 |
| all |  | 29 | 29 | 100.0% | 3.21 | 64 | 6 | 9.4% | 3 |

Tokens: 73868 in / 1103 out.

## Failure breakdown

No failures.

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
| `t2_q1_vs_q2` | 2 | pass | 4 | 3 | 0 | answered |  |
| `t2_summary_file` | 2 | pass | 4 | 3 | 0 | answered |  |
| `t2_copy_file` | 2 | pass | 3 | 2 | 0 | answered |  |
| `t2_append_todo` | 2 | pass | 3 | 2 | 0 | answered |  |
| `t2_reassign_dana` | 2 | pass | 4 | 3 | 0 | answered |  |
| `t2_resolve_with_note` | 2 | pass | 4 | 3 | 0 | answered |  |
| `t2_config_bump` | 2 | pass | 4 | 3 | 0 | answered |  |
| `t2_open_tickets_report` | 2 | pass | 3 | 2 | 0 | answered |  |
| `t2_north_average` | 2 | pass | 5 | 4 | 0 | answered |  |
| `t3_missing_file` | 3 | pass | 4 | 3 | 1 | answered |  |
| `t3_wrong_dir` | 3 | pass | 5 | 4 | 1 | answered |  |
| `t3_dir_as_file` | 3 | pass | 4 | 3 | 1 | answered |  |
| `t3_search_fallback` | 3 | pass | 5 | 4 | 1 | answered |  |
| `t3_ticket_404` | 3 | pass | 4 | 3 | 1 | answered |  |
| `t3_closed_ticket` | 3 | pass | 5 | 4 | 1 | answered |  |
| `t3_invalid_status` | 3 | pass | 3 | 2 | 0 | answered |  |
| `t3_bad_argument` | 3 | pass | 3 | 2 | 0 | answered |  |
| `t3_unknown_tool` | 3 | pass | 3 | 2 | 0 | answered |  |
