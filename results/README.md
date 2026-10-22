# results/

Committed subdirectories are **scripted baselines**: deterministic replay runs of the
`scripted` and `scripted_flawed` providers over each suite, plus the `compare` output between
them.

```
results/
  basic/      scripted/  scripted_flawed/  compare/     agent_eval/tasks/basic.yaml (29 tasks)
  research/   scripted/  scripted_flawed/  compare/     agent_eval/tasks/research.yaml (17 tasks)
```

Each run directory holds `report.md`, `results.json` and `transcripts/<task_id>.json`; each
`compare/` holds `compare.md` and `compare.json` for `scripted` (A) against `scripted_flawed`
(B). They describe the harness and the suites, not any language model. `results.json` carries
`meta.is_model_result: false` and `report.md` carries a baseline note for the same reason.

CI regenerates every file here with `SOURCE_DATE_EPOCH` pinned to the committed timestamp and
fails on any diff. To regenerate locally after a change:

```bash
export SOURCE_DATE_EPOCH="$(python -c 'import json,datetime as dt; t=json.load(open("results/basic/scripted/results.json"))["meta"]["generated_at"]; print(int(dt.datetime.strptime(t,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.UTC).timestamp()))')"
for suite in basic research; do
  agent-eval run --provider scripted        --suite agent_eval/tasks/$suite.yaml --out results/$suite/scripted/
  agent-eval run --provider scripted_flawed --suite agent_eval/tasks/$suite.yaml --out results/$suite/scripted_flawed/
  agent-eval compare results/$suite/scripted/ results/$suite/scripted_flawed/ --out results/$suite/compare/
done
```

Model runs (`results/<suite>/anthropic/`, `results/<suite>/openai_compat/`) are git-ignored by
default; commit them deliberately, labelled with model id and date.
