import json

from agent_eval.cli import main
from agent_eval.providers.scripted import ScriptedProvider
from agent_eval.replay import RESULT_CHARS, render_transcript
from agent_eval.runner import run_task
from agent_eval.tasks import RESEARCH_SUITE, load_suite

BASIC = {t.id: t for t in load_suite().tasks}
RESEARCH = {t.id: t for t in load_suite(RESEARCH_SUITE).tasks}


def test_replay_shows_turns_calls_results_budget_and_verdict():
    rec = run_task(ScriptedProvider(flawed=True), RESEARCH["r3_timeout_mirror"]).to_dict()
    out = render_transcript(rec)
    lines = out.splitlines()
    assert lines[0] == "# r3_timeout_mirror - scripted_flawed (replay-v1) - FAIL"
    assert lines[1].startswith("stop: answered | steps: 3/10 | tool calls: 2 | tool errors: 1")
    assert "/20000 budget (estimated) | latency: not reported" in lines[2]
    assert '  -> web_fetch {"url": "https://wiki.example/atlas"}  [args ok]' in lines
    assert "  <- web_fetch ok: # Atlas (community wiki)" in lines
    assert any(ln.startswith("  <- web_fetch ERROR: error: timeout:") for ln in lines)
    assert "  The mirror at https://mirror.example/atlas/docs/limits timed out" in out
    assert "verdict: FAIL (gave_up_after_error)" in lines
    assert lines[-1].startswith("  - answer: missing ['600']")
    assert not any(ln != ln.rstrip() for ln in lines)


def test_replay_revalidates_arguments_and_flags_unknown_tools():
    out = render_transcript(run_task(ScriptedProvider(), BASIC["t3_bad_argument"]).to_dict())
    assert "[args invalid: $: missing required key 'path'; $: unknown key 'file']" in out
    assert "verdict: PASS" in out and "[args ok]" in out
    out = render_transcript(run_task(ScriptedProvider(), BASIC["t3_unknown_tool"]).to_dict())
    assert '-> fs_delete {"path": "/notes/todo.txt"}  [unknown tool]' in out


def test_replay_truncates_long_results_unless_full():
    rec = run_task(ScriptedProvider(), RESEARCH["r1_search_windows"]).to_dict()
    short, full = render_transcript(rec), render_transcript(rec, full=True)
    assert "... (+" in short and "... (+" not in full
    assert len(rec["transcript"][1]["content"]) > RESULT_CHARS
    assert "5. https://atlas.example/docs - Atlas documentation" in full


def test_replay_shows_step_budget_exhaustion_and_latency():
    rec = run_task(ScriptedProvider(flawed=True), RESEARCH["r4_incident_chain"]).to_dict()
    rec["latency_ms"] = 1234.5
    rec["transcript"][0]["latency_ms"] = 600.2
    out = render_transcript(rec)
    assert "stop: step_budget | steps: 5/5" in out and "latency: 1234 ms" in out
    assert "step 1  assistant (tool_use; " in out and ", 600 ms)" in out
    assert "verdict: FAIL (step_budget)" in out


def test_replay_tolerates_older_transcripts_without_budget():
    rec = run_task(ScriptedProvider(), BASIC["t1_calc_power"]).to_dict()
    del rec["budget"], rec["latency_ms"]
    out = render_transcript(rec)
    assert "steps: 2/?" in out and "/? budget" in out and "verdict: PASS" in out


def test_replay_reports_provider_errors():
    rec = run_task(ScriptedProvider(), BASIC["t1_calc_power"]).to_dict()
    rec["transcript"] = [{"step": 1, "type": "provider_error", "error": "HTTP 429"}]
    rec["stop_reason"], rec["passed"], rec["failures"] = "provider_error", False, []
    out = render_transcript(rec)
    assert "step 1  provider error: HTTP 429" in out
    assert "verdict: FAIL (provider_error)" in out and "no check failures recorded" in out


def test_cli_replay(tmp_path, capsys):
    path = tmp_path / "t.json"
    rec = run_task(ScriptedProvider(), RESEARCH["r1_search_windows"]).to_dict()
    path.write_text(json.dumps(rec))
    assert main(["replay", str(path)]) == 0
    out = capsys.readouterr().out
    assert out.startswith("# r1_search_windows - scripted (replay-v1) - PASS") and "... (+" in out
    assert main(["replay", str(path), "--full"]) == 0 and "... (+" not in capsys.readouterr().out
    assert main(["replay", str(tmp_path / "missing.json")]) == 2
    assert "replay error" in capsys.readouterr().err
    path.write_text('{"meta": {}}')
    assert main(["replay", str(path)]) == 2
    assert "missing 'task_id'" in capsys.readouterr().err
