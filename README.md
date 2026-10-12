# agent-eval

An offline-first harness for evaluating tool-calling LLM agents. Give it a provider and it runs
a tiered task suite through a bounded tool loop against a deterministic sandbox (in-memory file
system, safe calculator, fake ticketing API), checks the final state and answer programmatically,
and writes a markdown report, a JSON summary and a per-task transcript. The whole suite runs with
no network and no API key, provider and tool failures are recorded rather than raised, and the
committed baselines regenerate byte-for-byte in CI. Real model providers (Anthropic,
OpenAI-compatible) plug in behind the same interface.

Status: v0.1.0, Python 3.11, `mypy --strict` and `ruff` clean, 80 offline tests, CI on every push.

```bash
python3.11 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
agent-eval run --provider scripted --suite agent_eval/tasks/basic.yaml --out results/scripted/
```

## Motivation

Evaluating an agent that calls tools is harder than evaluating a chat completion because the
thing under test is a trajectory: several model calls, several tool executions, and a final
state. Three design choices follow from that.

- **Deterministic tools.** Every tool is pure Python over an in-memory state that is rebuilt
  from a fixture before each task. Two runs of the same transcript give the same results, so a
  difference between two reports is a difference in the agent, not in the environment. There
  is nothing to mock and nothing to clean up.
- **Offline first.** The `scripted` provider replays a per-task script of tool calls, so the
  harness, the checkers and the report can be developed, tested and run in CI without spending
  tokens. A deliberately broken `scripted_flawed` provider gives the failure-analysis code
  something real to analyse. Model providers (`anthropic`, `openai_compat`) are enabled only
  when their API key is present.
- **Tiers that isolate a capability.** Tier 1 (single tool) measures whether the agent can
  pick the right tool, pass schema-valid arguments and ground its answer in the result. Tier 2
  (multi-step) measures whether it can chain reads, computation and writes and leave the
  sandbox in the right final state. Tier 3 (error recovery) starts every task with an obvious
  first call that fails (missing file, directory read as a file, 404 ticket, 409 on a closed
  ticket, bad argument name, invalid enum value, nonexistent tool) and measures whether the
  agent reads the error and takes another route instead of giving up or hallucinating.

Checkers look at the sandbox's final state and/or the final answer, never at the transcript,
so an agent is free to reach the goal by any route within budget.

## Architecture

```
agent_eval/
  types.py             Message / ToolCall / ToolResult / Usage / Budget / RunRecord
  tools/
    base.py            Tool(name, description, input_schema, execute) and ToolError
    schema.py          JSON-schema argument validation (types, required, unknown keys, enum)
    filesystem.py      fs_read, fs_write, fs_list, fs_search over an in-memory FS
    calculator.py      calculator: ast-based arithmetic, no eval
    tickets.py         tickets_list/get/update/add_note over a JSON fixture
    sandbox.py         Sandbox.fresh(): new FS + ticket store per task
  tasks/
    basic.yaml         29 tasks in three tiers, each with checks and a replay script
    checkers.py        file_equals, answer_contains, ticket_field, ... (10 kinds)
  agent/loop.py        bounded loop: validate args, execute, budget, transcript
  providers/
    scripted.py        scripted and scripted_flawed replay providers
    anthropic_provider.py   official anthropic SDK, Messages API with tools
    openai_compat.py   chat-completions protocol (OpenAI or compatible servers)
  metrics.py           per-tier success, mean steps, tool-error rate, tokens, cost
  report.py            report.md + results.json + per-task transcripts
  runner.py, cli.py    agent-eval run | list-tasks | check-suite
```

One **step** is one provider call. For each step the loop validates every requested tool call
against the tool's JSON schema (required keys, types, unknown keys, enum values), executes the
valid ones against the sandbox, converts `ToolError` into an error result the agent can read,
and appends the results. It stops when the provider answers without tool calls (`answered`),
when `max_steps` or `max_tokens` is reached (`step_budget`, `token_budget`), when the provider
fails (`provider_error`), or on a refusal or truncated answer. Validation failures and domain
tool errors are counted separately. The loop fails closed: an exception escaping a provider or a
tool is recorded in the transcript (as `provider_error`, or as an error tool result the agent can
read) instead of propagating, so one bad task cannot abort a suite run; a malformed check fails
its task with a `checker:` reason rather than raising.

The message format is provider-agnostic (`Message` with `tool_calls` and `tool_results`).
Each provider converts to and from its wire format; the Anthropic provider keeps the native
content blocks on the message so thinking blocks are echoed back unchanged.

## Install and run

```bash
python3.11 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
agent-eval check-suite
agent-eval run --provider scripted        --suite agent_eval/tasks/basic.yaml --out results/scripted/
agent-eval run --provider scripted_flawed --suite agent_eval/tasks/basic.yaml --out results/scripted_flawed/
pytest && ruff check . && mypy agent_eval
```

`--only t1_read_readme,t3_ticket_404` and `--tier 3` restrict a run. Each run writes
`report.md`, `results.json` and `transcripts/<task_id>.json` to `--out`. Output is fully
deterministic except for the `Generated:` timestamp; set `SOURCE_DATE_EPOCH` to pin that too. CI
regenerates both committed baselines with the timestamp pinned to the committed one and fails on
any `git diff` under `results/`, so the baselines always match the code at the same commit.

## Results: scripted baselines

These are deterministic replay runs produced on 2026-10-12 with the command lines above
(timestamp pinned with `SOURCE_DATE_EPOCH=1791765279`). They characterise the harness and the
suite. **They are not model results.** Token counts for replay providers are a length/4 estimate and cost is zero because
no API is called.

### `scripted` (generated 2026-10-12T00:34:39Z)

| Tier | What it measures | Tasks | Passed | Success | Mean steps | Tool calls | Tool errors | Tool error rate | Validation errors |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | single tool | 10 | 10 | 100.0% | 2.0 | 10 | 0 | 0.0% | 0 |
| 2 | multi-step | 10 | 10 | 100.0% | 3.7 | 27 | 0 | 0.0% | 0 |
| 3 | error recovery | 9 | 9 | 100.0% | 4.0 | 27 | 6 | 22.2% | 3 |
| all |  | 29 | 29 | 100.0% | 3.21 | 64 | 6 | 9.4% | 3 |

Tokens: 73868 in / 1103 out.

## Failure breakdown

No failures.

Every tier-3 task is passed by following the recovery steps written into its script; the 6
tool errors and 3 validation errors in tier 3 are the intentional first calls that fail.

### `scripted_flawed` (generated 2026-10-12T00:34:39Z)

The flawed provider drops the last tool call before the answer on scripts with three or more
calls, and stops with an apology after any tool error instead of recovering.

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

Reading the breakdown: all 9 tier-3 failures are `gave_up_after_error` (the agent answered
immediately after an error without another tool call); 5 tier-2 failures are `wrong_state`
(the skipped call was the write or update), 1 is `wrong_answer` (the skipped call was the
calculation the answer depended on), and the 4 tier-2 tasks with two-call scripts are
unaffected. Full per-task rows are in `results/scripted_flawed/report.md`.

## Adding a task

Append to `agent_eval/tasks/basic.yaml` (or write a new suite file and pass `--suite`):

```yaml
  - id: t2_my_task
    tier: 2
    prompt: Read /data/sales_q1.csv and write the south amount to /reports/south.txt.
    tools: [fs_read, fs_write]          # optional: restrict the tool set
    budget: {max_steps: 6, max_tokens: 8000}   # optional
    setup: {files: {/data/extra.csv: "a,b\n1,2\n"}}   # optional extra seed files
    check:
      - file_equals: {path: /reports/south.txt, content: "850\n"}
      - answer_contains: "850"
    script:                               # replay script for the scripted providers
      - call: {tool: fs_read, args: {path: /data/sales_q1.csv}}
      - call: {tool: fs_write, args: {path: /reports/south.txt, content: "850\n"}}
      - answer: "South amount: 850"
```

Check kinds: `file_equals`, `file_contains`, `file_absent`, `file_line_count`,
`answer_contains` (string or list, case-insensitive), `answer_not_contains`, `answer_matches`
(regex), `ticket_field`, `ticket_note_contains`, `ticket_note_count`. All checks must pass.
In scripted answers, `{last}` and `{rN}` are replaced with the last / N-th successful tool
result so the replayed answer depends on what the tools returned. `agent-eval check-suite`
validates the file before anything runs: required keys, known tiers, check kinds and their
arguments (including regex syntax), script steps, and that every name in `tools:` exists.
`tests/test_tasks_e2e.py` additionally asserts that every tier-1 and tier-2 script is
schema-valid and that every tier-3 script hits at least one error.

## Adding a tool

Define a `Tool` with a JSON schema and a pure function over the sandbox, and add it to
`ALL_TOOLS` in `agent_eval/tools/__init__.py`:

```python
from agent_eval.tools.base import Tool, ToolError, obj_schema


def _word_count(sb, args):
    text = sb.fs.read(args["path"])  # raises ToolError if missing
    return str(len(text.split()))


WORD_COUNT = Tool(
    "fs_word_count",
    "Count whitespace-separated words in a file.",
    obj_schema({"path": {"type": "string"}}, ["path"]),
    _word_count,
)
```

Raise `ToolError` for conditions the agent should recover from; the loop turns it into an
error result and counts it. Schemas use `additionalProperties: false`, so unknown argument
names are rejected before the executor runs. If the tool needs new state, add it to
`Sandbox` so it is rebuilt per task.

## Running against a real model

```bash
export ANTHROPIC_API_KEY=...                    # key is read by the SDK, never stored
export AGENT_EVAL_ANTHROPIC_MODEL=claude-opus-5 # default if unset
agent-eval run --provider anthropic --suite agent_eval/tasks/basic.yaml --out results/anthropic/

export OPENAI_API_KEY=...                       # OPENAI_BASE_URL works for compatible servers
export AGENT_EVAL_OPENAI_MODEL=<model id>       # required; nothing is assumed
agent-eval run --provider openai_compat --suite agent_eval/tasks/basic.yaml --out results/openai_compat/
```

Install the extra first (`pip install -e ".[anthropic]"` or `".[openai]"`). Model runs report
real token counts from the API and an estimated cost from the price table in
`agent_eval/metrics.py` (Anthropic list prices as cached on 2026-06-24; `n/a` for models not in
the table). The Anthropic provider reports a `refusal` stop reason rather than routing to a
fallback model, so every outcome is attributable to the model under test. `results/anthropic/`
and `results/openai_compat/` are git-ignored; commit model results deliberately and label them
with the model id and date.

The Anthropic provider sends `max_tokens=16000` because current Claude models think by default
and thinking counts against that limit; the loop's own token budget bounds the whole run.

Neither key was set in the environment that produced this repository, so no model has been run
through the harness yet. The two provider modules are exercised offline in two ways: conversion
tests on the neutral-to-wire message shapes, and a round trip through the real SDK over a mock
HTTP transport (`tests/test_providers.py`) that asserts the request body (`system`, `tools`,
`tool_use` and `tool_result` blocks, thinking blocks echoed back unchanged) and the parsed
response, including an HTTP error path. Those two tests need the SDK extras installed and skip
otherwise; CI installs them.

## Limitations

- The scripted providers are replay oracles. A 100% `scripted` score means the suite is
  consistent with itself, not that any model can solve it.
- Checkers are deliberately simple (substring, regex, exact file content, ticket fields).
  Tasks whose correct answer can be phrased many ways need an `answer_matches` regex or an
  explicit state check; there is no LLM judge.
- Token counts for replay providers are a heuristic; cost figures depend on a hand-maintained
  price table.
- The model providers have not been run live in this repository. Their request and response
  shapes are verified offline against the installed SDKs (anthropic 1.13, openai 3.29) through
  a mock HTTP transport, but a first live run may still surface issues such as rate limits or
  model-specific stop reasons.
- One process, sequential tasks, no retries at the provider layer beyond the SDK defaults.
- The sandbox is text-only: no binary files, no permissions, no concurrency.

## Roadmap

- Run `claude-opus-5` and a compatible open-weight model through the suite and commit the
  labelled results next to the baselines.
- A `hard` suite: longer chains, tasks that need two recoveries, and budget-constrained tasks
  where the right move is to stop early and say so.
- Repeated runs with per-task pass@k and variance for non-deterministic providers.
- Trajectory-level checks (for example "did not call `fs_write` before reading") as an
  optional supplement to state and answer checks.
- An HTML report with transcript drill-down.

## License

MIT, Nihar Maddina, 2026.
