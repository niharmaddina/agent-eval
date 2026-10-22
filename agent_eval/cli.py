"""Command-line entry point: ``agent-eval run|list-tasks|check-suite|compare|replay``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from agent_eval.compare import compare, load_results, render_markdown, write_compare
from agent_eval.providers import PROVIDER_NAMES, ProviderUnavailable, get_provider
from agent_eval.replay import render_transcript
from agent_eval.runner import run_suite
from agent_eval.tasks import DEFAULT_SUITE, Suite, load_suite


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="agent-eval", description="Evaluate tool-calling agents offline."
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="run a suite against a provider")
    run.add_argument("--provider", required=True, choices=PROVIDER_NAMES)
    run.add_argument("--suite", default=str(DEFAULT_SUITE), help="path to a suite YAML")
    run.add_argument(
        "--out", default=None, help="output directory (default results/<suite>/<provider>/)"
    )
    run.add_argument("--model", default=None, help="model id override for real providers")
    run.add_argument("--only", default=None, help="comma-separated task ids")
    run.add_argument("--tier", type=int, default=None, help="run one tier of the suite")

    ls = sub.add_parser("list-tasks", help="print task ids and tiers")
    ls.add_argument("--suite", default=str(DEFAULT_SUITE))

    chk = sub.add_parser("check-suite", help="validate a suite file and exit")
    chk.add_argument("--suite", default=str(DEFAULT_SUITE))

    cmp = sub.add_parser("compare", help="diff two result directories of the same suite")
    cmp.add_argument("a", help="baseline results directory (or results.json)")
    cmp.add_argument("b", help="candidate results directory (or results.json)")
    cmp.add_argument("--out", default=None, help="write compare.md and compare.json here")
    cmp.add_argument("--json", action="store_true", help="print JSON instead of markdown")

    rp = sub.add_parser("replay", help="pretty-print one transcript JSON")
    rp.add_argument("transcript", help="path to transcripts/<task_id>.json")
    rp.add_argument("--full", action="store_true", help="do not truncate tool results")
    return p


def _load(path: str) -> Suite | None:
    try:
        return load_suite(path)
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as exc:
        print(f"suite error: {exc}", file=sys.stderr)
        return None


def _cmd_compare(args: argparse.Namespace) -> int:
    try:
        result = compare(load_results(Path(args.a)), load_results(Path(args.b)))
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"compare error: {exc}", file=sys.stderr)
        return 2
    if args.out:
        json_path, md_path = write_compare(Path(args.out), result)
        s = result["summary"]
        print(
            f"{result['a']['provider']} -> {result['b']['provider']} on {result['a']['suite']}: "
            f"passed {s['passed_a']} -> {s['passed_b']}, newly passing {s['newly_passing']}, "
            f"newly failing {s['newly_failing']}"
        )
        print(f"  wrote {md_path} and {json_path}")
        return 0
    if args.json:
        print(json.dumps(result, indent=1, sort_keys=True))
    else:
        sys.stdout.write(render_markdown(result))
    return 0


def _cmd_replay(args: argparse.Namespace) -> int:
    try:
        record = json.loads(Path(args.transcript).read_text(encoding="utf-8"))
        if not isinstance(record, dict) or "task_id" not in record:
            raise ValueError("not a transcript file (missing 'task_id')")
        sys.stdout.write(render_transcript(record, full=args.full))
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"replay error: {exc}", file=sys.stderr)
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.cmd == "compare":
        return _cmd_compare(args)
    if args.cmd == "replay":
        return _cmd_replay(args)

    suite = _load(args.suite)
    if suite is None:
        return 2
    if args.cmd == "list-tasks":
        for t in suite.tasks:
            label = suite.tiers.get(t.tier, "")
            print(f"{t.id}\ttier {t.tier} ({label})\t{t.prompt.splitlines()[0][:70]}")
        return 0
    if args.cmd == "check-suite":
        tiers = ", ".join(f"{k}={v}" for k, v in suite.tiers.items())
        print(f"ok: {suite.name} v{suite.version}, {len(suite.tasks)} tasks, tiers {tiers}")
        return 0

    if args.tier is not None and args.tier not in suite.tiers:
        print(f"suite error: tier {args.tier} not in {sorted(suite.tiers)}", file=sys.stderr)
        return 2
    try:
        provider = get_provider(args.provider, model=args.model)
    except ProviderUnavailable as exc:
        print(f"provider unavailable: {exc}", file=sys.stderr)
        return 2
    out = Path(args.out) if args.out else Path("results") / suite.name / args.provider
    only = set(args.only.split(",")) if args.only else None
    result = run_suite(provider, suite, out, only=only, tier=args.tier)
    o = result["overall"]
    print(f"{provider.name} ({provider.model}) on {suite.name}: {o['passed']}/{o['total']} passed")
    for t in result["tiers"]:
        print(f"  tier {t['tier']} ({t['label']}): {t['passed']}/{t['total']}")
    if result["failures"]:
        print("  failures:", ", ".join(f"{k}={v}" for k, v in result["failures"].items()))
    print(f"  wrote {out / 'report.md'} and {out / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
