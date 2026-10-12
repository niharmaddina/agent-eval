"""Command-line entry point: ``agent-eval run|list-tasks|check-suite``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agent_eval.providers import PROVIDER_NAMES, ProviderUnavailable, get_provider
from agent_eval.runner import run_suite
from agent_eval.tasks import DEFAULT_SUITE, TIERS, load_suite


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="agent-eval", description="Evaluate tool-calling agents offline."
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="run a suite against a provider")
    run.add_argument("--provider", required=True, choices=PROVIDER_NAMES)
    run.add_argument("--suite", default=str(DEFAULT_SUITE), help="path to a suite YAML")
    run.add_argument("--out", default=None, help="output directory (default results/<provider>/)")
    run.add_argument("--model", default=None, help="model id override for real providers")
    run.add_argument("--only", default=None, help="comma-separated task ids")
    run.add_argument("--tier", type=int, choices=sorted(TIERS), default=None)

    ls = sub.add_parser("list-tasks", help="print task ids and tiers")
    ls.add_argument("--suite", default=str(DEFAULT_SUITE))

    chk = sub.add_parser("check-suite", help="validate a suite file and exit")
    chk.add_argument("--suite", default=str(DEFAULT_SUITE))
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        suite = load_suite(args.suite)
    except (OSError, ValueError, KeyError) as exc:
        print(f"suite error: {exc}", file=sys.stderr)
        return 2

    if args.cmd == "list-tasks":
        for t in suite.tasks:
            print(f"{t.id}\ttier {t.tier}\t{t.prompt.splitlines()[0][:70]}")
        return 0
    if args.cmd == "check-suite":
        print(f"ok: {suite.name} v{suite.version}, {len(suite.tasks)} tasks")
        return 0

    try:
        provider = get_provider(args.provider, model=args.model)
    except ProviderUnavailable as exc:
        print(f"provider unavailable: {exc}", file=sys.stderr)
        return 2
    out = Path(args.out) if args.out else Path("results") / args.provider
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
