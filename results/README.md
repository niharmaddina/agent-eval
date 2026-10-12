# results/

Committed subdirectories are **scripted baselines**: deterministic replay runs of the
`scripted` and `scripted_flawed` providers over `agent_eval/tasks/basic.yaml`. They describe
the harness and the suite, not any language model. `results.json` carries
`meta.is_model_result: false` and `report.md` carries a baseline note for the same reason.

Model runs (`results/anthropic/`, `results/openai_compat/`) are git-ignored by default; commit
them deliberately, labelled with model id and date.
