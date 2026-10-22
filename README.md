# agent-eval

An offline-first harness for evaluating tool-calling LLM agents. Give it a provider and it runs
a tiered task suite through a bounded tool loop against a deterministic sandbox (in-memory file
system, safe calculator, fake ticketing API, fake web with search and fetch), checks the final
state and answer programmatically, and writes a markdown report, a JSON summary and a per-task
transcript. `agent-eval compare` diffs two result directories task by task; `agent-eval replay`
prints one transcript as readable text.

Built to be trusted before it is pointed at a model: everything runs with no network and no API
key, provider and tool failures are recorded rather than raised, every checker is a program (no
LLM judge), and the committed baselines regenerate byte-for-byte in CI. Real model providers
(Anthropic, OpenAI-compatible) plug in behind the same interface.

Status: v0.2.0, Python 3.11, `mypy --strict` and `ruff` clean, 126 offline tests, CI on every
push. Two suites: `basic` (29 tasks, three tiers, file system / calculator / tickets) and
`research` (17 tasks, four tiers, web search and fetch).

```bash
python3.11 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
agent-eval run --provider scripted --suite agent_eval/tasks/research.yaml --out results/research/scripted/
agent-eval compare results/research/scripted/ results/research/scripted_flawed/
agent-eval replay results/research/scripted_flawed/transcripts/r3_404_search_again.json
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
  harness, the checkers and the reports can be developed, tested and run in CI without spending
  tokens. A deliberately broken `scripted_flawed` provider gives the failure-analysis code and
  the `compare` command something real to analyse. Model providers (`anthropic`,
  `openai_compat`) are enabled only when their API key is present.
- **Tiers that isolate a capability.** Each suite groups tasks so that a drop in one tier points
  at one skill: picking and grounding a single call, chaining calls and leaving the right
  state, recovering from an error, or planning under a step budget. See *Design notes*.

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
    web.py             web_search, web_fetch over fixtures/web.json (13 pages, 2 error URLs)
    sandbox.py         Sandbox.fresh(): new FS + ticket store + web store per task
  tasks/
    basic.yaml         29 tasks in three tiers, each with checks and a replay script
    research.yaml      17 tasks in four tiers, each with a script and an explicit script_flawed
    checkers.py        file_equals, answer_contains, ticket_field, ... (10 kinds)
  agent/loop.py        bounded loop: validate args, execute, budget, transcript
  providers/
    scripted.py        scripted and scripted_flawed replay providers
    anthropic_provider.py   official anthropic SDK, Messages API with tools
    openai_compat.py   chat-completions protocol (OpenAI or compatible servers)
  metrics.py           per-tier success, mean steps, tool-error rate, tokens, cost, latency
  report.py            report.md + results.json + per-task transcripts
  compare.py           task-by-task diff of two result directories (markdown + JSON)
  replay.py            transcript pretty-printer with argument re-validation
  runner.py, cli.py    agent-eval run | list-tasks | check-suite | compare | replay
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
agent-eval check-suite --suite agent_eval/tasks/research.yaml
agent-eval run --provider scripted        --suite agent_eval/tasks/basic.yaml    --out results/basic/scripted/
agent-eval run --provider scripted_flawed --suite agent_eval/tasks/basic.yaml    --out results/basic/scripted_flawed/
agent-eval run --provider scripted        --suite agent_eval/tasks/research.yaml --out results/research/scripted/
agent-eval run --provider scripted_flawed --suite agent_eval/tasks/research.yaml --out results/research/scripted_flawed/
agent-eval compare results/basic/scripted/ results/basic/scripted_flawed/ --out results/basic/compare/
agent-eval replay results/basic/scripted_flawed/transcripts/t3_search_fallback.json
pytest && ruff check . && mypy agent_eval
```

`--only t1_read_readme,t3_ticket_404` and `--tier 3` restrict a run; `--out` defaults to
`results/<suite>/<provider>/`. Each run writes `report.md`, `results.json` and
`transcripts/<task_id>.json`. Output is fully deterministic except for the `Generated:`
timestamp; set `SOURCE_DATE_EPOCH` to pin that too. CI regenerates all four committed baselines
and both compare outputs with the timestamp pinned to the committed one and fails on any
`git diff` under `results/`, so the baselines always match the code at the same commit.

## Suites

### `basic`: file system, calculator, tickets

Tier 1 (single tool) measures whether the agent can pick the right tool, pass schema-valid
arguments and ground its answer in the result. Tier 2 (multi-step) measures whether it can
chain reads, computation and writes and leave the sandbox in the right final state. Tier 3
(error recovery) starts every task with an obvious first call that fails (missing file,
directory read as a file, 404 ticket, 409 on a closed ticket, bad argument name, invalid enum
value, nonexistent tool) and measures whether the agent reads the error and takes another route.
The suite pins its tool set to the nine file-system, calculator and ticket tools, so the web
tools are not offered here.

### `research`: a deterministic fake web

The `web` tool pair works over `agent_eval/tools/fixtures/web.json`: 13 small pages on four
hosts (an `atlas.example` site with docs, pricing, changelog and a blog post; a community wiki
that is out of date; a status page with an incident report; a third-party review with a stale
price) plus two *designated error URLs*, a retired pricing page that returns 404 and a docs
mirror that times out. Pages link to each other, so there are chains to follow and dead links
to hit.

- `web_search(query)` tokenises the query (lower-case alphanumerics, stop words removed) and
  ranks every page by distinct query tokens found in its title (weight 2) and body (weight 1);
  ties break on URL so results are stable. It returns up to 5 hits, each with URL, title and
  the first body line that mentions a query term. Error URLs are in the index with a title and
  snippet, like stale search entries, so a search can lead to a 404.
- `web_fetch(url)` returns the page's title, body and outgoing links, or raises a `ToolError`
  for a designated 404, a designated timeout, an unknown URL (404) or a URL without `https://`.
  Every fetch attempt is logged on the sandbox (`sandbox.web.fetched`).

The suite declares its own tiers and restricts each task to the tools it needs:

| Tier | Label | Tasks | What it isolates |
| --- | --- | --- | --- |
| 1 | single lookup | 4 | one search or one fetch, answer grounded in the result |
| 2 | multi-page | 6 | a fact split across two pages, a three-hop link chain, two pairs of sources that disagree (the checker requires both URLs and both figures), search-then-fetch, fetch-then-calculate |
| 3 | error recovery | 4 | a 404 on the given URL (search again), a timeout on a linked mirror (use the official page), a URL without a scheme (fix it), and a dead link where the right move is to report it and give the fallback figure already in hand |
| 4 | budget pressure | 3 | `max_steps: 5` with a shortest correct path of exactly 3 tool calls (3 calls + 1 answer = 4 steps), so one wasted call is survivable and two are not |

Every research task carries both a `script` (the intended path, replayed by `scripted`) and an
explicit `script_flawed` with a `notes` line saying what flaw it models: answering from memory
with the stale wiki's fact, stopping a hop early and guessing, citing one source, giving up
after an error, or wandering into unrelated pages until the step budget runs out. When a task
declares `script_flawed`, `scripted_flawed` replays it verbatim; tasks without one (all of
`basic`) get the two generic flaws described in *Design notes*.

## Results: scripted baselines

Deterministic replay runs produced on 2026-10-12 with the command lines above and
`SOURCE_DATE_EPOCH=1791780657` (generated 2026-10-12T04:50:57Z). They characterise the harness and the
suites. **They are not model results.** Token counts for replay providers are a length/4
estimate; cost is zero because no API is called; latency is not reported because nothing is
measured.

### `basic`, `scripted`

| Tier | What it measures | Tasks | Passed | Success | Mean steps | Tool calls | Tool errors | Tool error rate | Validation errors |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | single tool | 10 | 10 | 100.0% | 2.0 | 10 | 0 | 0.0% | 0 |
| 2 | multi-step | 10 | 10 | 100.0% | 3.7 | 27 | 0 | 0.0% | 0 |
| 3 | error recovery | 9 | 9 | 100.0% | 4.0 | 27 | 6 | 22.2% | 3 |
| all |  | 29 | 29 | 100.0% | 3.21 | 64 | 6 | 9.4% | 3 |

Tokens: 73868 in / 1103 out.

No failures.

Every tier-3 task is passed by following the recovery steps written into its script; the 6
tool errors and 3 validation errors in tier 3 are the intentional first calls that fail.

### `basic`, `scripted_flawed`

| Tier | What it measures | Tasks | Passed | Success | Mean steps | Tool calls | Tool errors | Tool error rate | Validation errors |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | single tool | 10 | 10 | 100.0% | 2.0 | 10 | 0 | 0.0% | 0 |
| 2 | multi-step | 10 | 4 | 40.0% | 3.1 | 21 | 0 | 0.0% | 0 |
| 3 | error recovery | 9 | 0 | 0.0% | 2.0 | 9 | 6 | 66.7% | 3 |
| all |  | 29 | 14 | 48.3% | 2.38 | 40 | 6 | 15.0% | 3 |

Tokens: 53777 in / 926 out.

Failure breakdown:

| Category | Count |
| --- | --- |
| gave_up_after_error | 9 |
| wrong_answer | 1 |
| wrong_state | 5 |

All 9 tier-3 failures are `gave_up_after_error` (the agent answered immediately after an error
without another tool call); 5 tier-2 failures are `wrong_state` (the dropped call was the write
or update), 1 is `wrong_answer` (the dropped call was the calculation the answer depended on),
and the 4 tier-2 tasks with two-call scripts are unaffected.

### `research`, `scripted`

| Tier | What it measures | Tasks | Passed | Success | Mean steps | Tool calls | Tool errors | Tool error rate | Validation errors |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | single lookup | 4 | 4 | 100.0% | 2.0 | 4 | 0 | 0.0% | 0 |
| 2 | multi-page | 6 | 6 | 100.0% | 3.33 | 14 | 0 | 0.0% | 0 |
| 3 | error recovery | 4 | 4 | 100.0% | 3.5 | 10 | 4 | 40.0% | 0 |
| 4 | budget pressure | 3 | 3 | 100.0% | 4.0 | 9 | 0 | 0.0% | 0 |
| all |  | 17 | 17 | 100.0% | 3.18 | 37 | 4 | 10.8% | 0 |

Tokens: 21199 in / 1549 out.

No failures.

The 4 tool errors are the designated failures in tier 3 (404, timeout, scheme-less URL, dead
link); no validation errors occur because every scripted call is schema-valid. Tier 4 uses 4 of
its 5 steps on every task.

### `research`, `scripted_flawed`

| Tier | What it measures | Tasks | Passed | Success | Mean steps | Tool calls | Tool errors | Tool error rate | Validation errors |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | single lookup | 4 | 3 | 75.0% | 1.75 | 3 | 0 | 0.0% | 0 |
| 2 | multi-page | 6 | 2 | 33.3% | 2.5 | 9 | 0 | 0.0% | 0 |
| 3 | error recovery | 4 | 0 | 0.0% | 2.5 | 6 | 4 | 66.7% | 0 |
| 4 | budget pressure | 3 | 0 | 0.0% | 5.0 | 15 | 1 | 6.7% | 0 |
| all |  | 17 | 5 | 29.4% | 2.76 | 33 | 5 | 15.2% | 0 |

Tokens: 17988 in / 1071 out.

Failure breakdown:

| Category | Count |
| --- | --- |
| gave_up_after_error | 4 |
| step_budget | 3 |
| wrong_answer | 5 |

The three failure categories map to the three kinds of flaw written into the suite: 5
`wrong_answer` (stale memory, one hop short, one source cited), 4 `gave_up_after_error` (every
tier-3 task), 3 `step_budget` (every tier-4 task; the flawed scripts spend 5 steps on calls and
never reach their answer). Per-task rows are in `results/research/scripted_flawed/report.md`.

## Comparing two runs

`agent-eval compare A/ B/` reads two `results.json` files from the same suite and reports,
task by task, what changed from A (baseline) to B (candidate): newly passing, newly failing,
step and token deltas, and a per-tier table. Without `--out` it prints markdown; `--json`
prints the same structure as JSON; `--out DIR` writes `compare.md` (with an all-tasks table)
and `compare.json`. Different suites are refused. The committed
`results/research/compare/compare.md` begins:

```
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
| `r2_link_chain` | 2 | 4 -> 3 (-1) | 1406 -> 902 (-504) | answered | wrong_answer: answer: does not match /retr(?:y\|ies)\D{0,40}\b3\b\|\b3\b\D{0,40}retr(?:y\|ies)/ in 'Atlas r |
| ... | | | | | |
```

`results/basic/compare/compare.md` shows the same for the basic suite: 29 -> 14 passed, 15
newly failing, 24 fewer steps and 20268 fewer estimated tokens, all of it in tiers 2 and 3.

## Reading one transcript

`agent-eval replay transcripts/<task>.json` prints the turns, each tool call with its arguments
and a fresh validation verdict against the current schema (`[args ok]`, `[args invalid: ...]`,
`[unknown tool]`), each tool result (truncated unless `--full`), the budgets consumed and the
final verdict with the checker's reasons. The flawed run of `r3_404_search_again`:

```
# r3_404_search_again - scripted_flawed (replay-v1) - FAIL
stop: answered | steps: 2/10 | tool calls: 1 | tool errors: 1 | validation errors: 0
tokens: 596 in / 37 out = 633/20000 budget (estimated) | latency: not reported

step 1  assistant (tool_use; 280 in / 13 out)
  -> web_fetch {"url": "https://atlas.example/pricing/2025"}  [args ok]
  <- web_fetch ERROR: error: 404 Not Found: https://atlas.example/pricing/2025 (this page has been removed)
step 2  assistant (end_turn; 316 in / 24 out)
  The pricing page https://atlas.example/pricing/2025 no longer exists, so I cannot report the price.

verdict: FAIL (gave_up_after_error)
  - answer: missing ['$40'] in 'The pricing page https://atlas.example/pricing/2025 no longer exists, so I cannot report the price.'
```

A validation failure shows up on the call itself, from the `scripted` run of `t3_bad_argument`:

```
step 1  assistant (tool_use; 751 in / 8 out)
  -> fs_read {"file": "/config/app.json"}  [args invalid: $: missing required key 'path'; $: unknown key 'file']
  <- fs_read ERROR: invalid arguments: $: missing required key 'path'; $: unknown key 'file'
step 2  assistant (tool_use; 779 in / 8 out)
```

## Metrics

`results.json` carries `overall` and per-tier aggregates (`total`, `passed`, `success_rate`,
`mean_steps`, `tool_calls`, `tool_errors`, `tool_error_rate`, `validation_errors`,
`input_tokens`, `output_tokens`, `tokens_estimated`, `estimated_cost_usd`,
`cost_per_success_usd`, `mean_latency_ms`), a failure breakdown, stop-reason counts and a
per-task list with `steps`, `tokens`, `latency_ms`, `failure_category` and the checker
messages. Two fields are new in v0.2.0:

- **`cost_per_success_usd`** is `estimated_cost_usd / passed`, `null` when nothing passed or the
  model is not in the price table. Replay providers cost $0 by definition, so their figure is
  $0.0000.
- **Latency placeholders.** Each live provider measures the wall time of its API call and
  returns it on `ProviderResponse.latency_ms`; the loop records it per assistant turn in the
  transcript and sums it into `RunRecord.latency_ms`, and metrics report `mean_latency_ms` per
  tier. Replay providers return nothing, so every latency field is `null` and the report says
  "not reported" rather than printing a misleading zero. Transcripts also record the task's
  `budget` so `replay` can show `steps: 5/5` without the suite file.

Failure categories: `provider_error`, `step_budget`, `token_budget`, `refusal`, `truncated`
(from the stop reason), then `gave_up_after_error` (answered right after an error result),
`wrong_answer`, `wrong_state`, `wrong_answer_and_state`, `checker_error`.

## Adding a task

Append to a suite file (or write a new one and pass `--suite`):

```yaml
suite: research
version: 1
tiers: {1: single lookup, 2: multi-page, 3: error recovery, 4: budget pressure}   # optional
tools: [web_search, web_fetch]            # optional suite-wide default tool set
tasks:
  - id: r2_my_task
    tier: 2
    tools: [web_fetch, calculator]          # optional: overrides the suite default
    budget: {max_steps: 6, max_tokens: 8000}   # optional
    setup: {files: {/data/extra.csv: "a,b\n1,2\n"}}   # optional extra seed files
    notes: "Flawed: reads one page and guesses."
    check:
      - answer_contains: ["480", "https://atlas.example/pricing"]
    script:                               # intended path, replayed by `scripted`
      - call: {tool: web_fetch, args: {url: https://atlas.example/pricing}}
      - call: {tool: calculator, args: {expression: "12 * 40"}}
      - answer: "12 seats cost ${last} per month (https://atlas.example/pricing)."
    script_flawed:                        # optional explicit flaw, replayed by `scripted_flawed`
      - call: {tool: web_fetch, args: {url: https://atlas.example/pricing}}
      - answer: "12 seats cost about $500 per month."
```

Check kinds: `file_equals`, `file_contains`, `file_absent`, `file_line_count`,
`answer_contains` (string or list, case-insensitive), `answer_not_contains`, `answer_matches`
(regex), `ticket_field`, `ticket_note_contains`, `ticket_note_count`. All checks must pass.
In scripted answers, `{last}` and `{rN}` are replaced with the last / N-th successful tool
result so the replayed answer depends on what the tools returned. `agent-eval check-suite`
validates the file before anything runs: required keys, the `tiers` mapping, check kinds and
their arguments (including regex syntax), both scripts' steps, and that every name in `tools:`
exists. The end-to-end tests additionally assert that every non-recovery script is
schema-valid and that every recovery script hits at least one error.

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
`Sandbox` so it is rebuilt per task (`web.py` is the worked example: a `WebStore` built from a
fixture, held on `Sandbox.web`). Suites that pin a `tools:` list will not see a new tool until
they opt in.

## Running against a real model

```bash
export ANTHROPIC_API_KEY=...                    # key is read by the SDK, never stored
export AGENT_EVAL_ANTHROPIC_MODEL=claude-opus-5 # default if unset
agent-eval run --provider anthropic --suite agent_eval/tasks/research.yaml --out results/research/anthropic/

export OPENAI_API_KEY=...                       # OPENAI_BASE_URL works for compatible servers
export AGENT_EVAL_OPENAI_MODEL=<model id>       # required; nothing is assumed
agent-eval run --provider openai_compat --suite agent_eval/tasks/basic.yaml --out results/basic/openai_compat/
```

Install the extra first (`pip install -e ".[anthropic]"` or `".[openai]"`). Model runs report
real token counts from the API, wall time per call, and an estimated cost from the price table in
`agent_eval/metrics.py` (Anthropic list prices as cached on 2026-06-24; `n/a` for models not in
the table). The Anthropic provider reports a `refusal` stop reason rather than routing to a
fallback model, so every outcome is attributable to the model under test. `results/*/anthropic/`
and `results/*/openai_compat/` are git-ignored; commit model results deliberately and label them
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

## Design notes

**Why checkers are programmatic.** A check reads the sandbox's final state or the final answer
and compares it with a literal, a substring or a regex. There is no LLM judge. That keeps a
pass/fail decision deterministic, free and auditable: the reason a task failed is a one-line
string that names the file, ticket field or missing phrase. The price is that prompts must ask
for things a program can recognise (a number, a date, a URL, an exact file body), and tasks
whose answer could be phrased many ways need a regex or a state check. The conflict tasks in
`research` show the trade-off: the checker cannot judge whether a reconciliation is well
argued, so it requires both figures and both URLs, which is the evidence a good answer must
contain anyway.

**Why error injection is explicit.** Every failure an agent meets in the sandbox is written
down somewhere a reviewer can read: the `errors` list in `web.json`, a ticket id that does not
exist in `tickets.json`, a path that is not in `SEED_FILES`, a 409 rule in the ticket store.
Nothing is random and nothing is sampled, so a transcript is reproducible from the task id
alone. The same goes for the flawed baseline: `basic` derives it from the intended script with
two generic transformations (drop the last call before the answer on scripts with three or more
calls; stop with an apology after any error), and `research` declares a `script_flawed` per
task with a `notes` line naming the flaw it models. A failure category in a report therefore
traces back to a specific line in a YAML file, which is what makes the `compare` output
readable.

**What the tiers isolate.** The point of a tier is that a drop in it points at one skill.
`basic` separates grounding a single call (tier 1), chaining calls to the right final state
(tier 2) and recovering from an error (tier 3). `research` separates grounding (tier 1),
synthesis across pages, link following and source reconciliation (tier 2), recovery from web
failures (tier 3) and planning under a step cap (tier 4). Tier 4 is built so that the shortest
correct path is 3 tool calls and the cap is 5 steps: an agent that wastes one call still
passes, one that wastes two does not, and the report shows the difference as `step_budget`
rather than `wrong_answer`. The flawed baselines were chosen to light up exactly these
distinctions: in `basic` tier 1 stays at 100% while tiers 2 and 3 drop, and in `research` each
tier fails for a different category.

## Limitations

- The scripted providers are replay oracles. A 100% `scripted` score means the suite is
  consistent with itself, not that any model can solve it; the `scripted_flawed` numbers
  describe flaws that were written in by hand, not flaws observed in a model.
- Checkers are deliberately simple (substring, regex, exact file content, ticket fields).
  Tasks whose correct answer can be phrased many ways need an `answer_matches` regex or an
  explicit state check; there is no LLM judge.
- `web_search` is exact-token keyword overlap with no stemming, so `limits` and `limit` are
  different words. That is realistic for a small index but it means some natural queries rank
  a neighbouring page first; the research scripts use queries that work, and a model under test
  may need to rephrase.
- Token counts for replay providers are a heuristic; cost figures depend on a hand-maintained
  price table; latency is only measured for live providers.
- The model providers have not been run live in this repository. Their request and response
  shapes are verified offline against the installed SDKs (anthropic 1.13, openai 3.29) through
  a mock HTTP transport, but a first live run may still surface issues such as rate limits or
  model-specific stop reasons.
- One process, sequential tasks, no retries at the provider layer beyond the SDK defaults.
- The sandbox is text-only: no binary files, no permissions, no concurrency; the fake web has
  13 pages and no forms, redirects or pagination.

## Roadmap

- Run `claude-opus-5` and a compatible open-weight model through both suites and commit the
  labelled results next to the baselines, with real latency and cost-per-success figures.
- Repeated runs with per-task pass@k and variance for non-deterministic providers; `compare`
  across repeats.
- Trajectory-level checks as an optional supplement to state and answer checks, for example
  "every URL cited in the answer was actually fetched" using the sandbox's fetch log.
- A harder research tier: two recoveries in one task, and more tasks where the right move is
  to stop early and say so.
- An HTML report with transcript drill-down built on `replay`.

## License

MIT, Nihar Maddina, 2026.
