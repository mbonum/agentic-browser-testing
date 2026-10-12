"""CLI for the eval harness.

    # validate case files + assertions + pricing, no browser launched
    python -m evals validate

    # run the suite and write results + report (snapshot your baseline first)
    python -m evals run --label baseline --repeat 3
    python -m evals run --cases login-logout-core test-pro30 --provider anthropic

    # render / diff reports
    python -m evals report evals/runs/<run_id>
    python -m evals report evals/runs/<run_id> --baseline evals/runs/<baseline_id>
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from evals.cases import load_cases
from evals.config import RunConfig
from evals.pricing import estimate_cost

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("evals")

DEFAULT_CASES_DIR = "evals/cases"


def _cmd_validate(args: argparse.Namespace) -> int:
    cases = load_cases(args.cases_dir, select_ids=args.cases or None)
    if not cases:
        print(f"No cases found in {args.cases_dir}")
        return 1
    ok = True
    for c in cases:
        problems = c.validate()
        status = "OK" if not problems else "INVALID"
        print(f"[{status}] {c.id}  ({len(c.assertions)} assertions, expected={c.expected_status})")
        for p in problems:
            ok = False
            print(f"    - {p}")
        # also check each assertion type resolves
        from evals.assertions import evaluate_assertion
        for a in c.assertions:
            res = evaluate_assertion({"history": []}, a)
            if res.type == "unknown" or "unknown assertion" in res.detail:
                ok = False
                print(f"    - unknown assertion type: {a}")
    # pricing sanity
    cfg = RunConfig()
    est = estimate_cost(cfg.resolved_model(), 1000, 1000)
    if not est.priced:
        print(f"[warn] default model '{cfg.resolved_model()}' is unpriced; costs will show 0 until added to pricing.py")
    print(f"\n{len(cases)} case(s) checked. {'All valid.' if ok else 'Problems found.'}")
    return 0 if ok else 1


def _cmd_run(args: argparse.Namespace) -> int:
    from evals.runner import run_suite_sync  # local import: pulls browser stack

    cases = load_cases(args.cases_dir, select_ids=args.cases or None)
    if not cases:
        print(f"No cases found in {args.cases_dir}")
        return 1
    invalid = [(c.id, c.validate()) for c in cases if c.validate()]
    if invalid:
        for cid, probs in invalid:
            print(f"[INVALID] {cid}: {probs}")
        print("Fix case files or run `python -m evals validate`. Aborting.")
        return 1

    cfg = RunConfig(repeat=args.repeat)
    if args.provider:
        cfg.provider = args.provider
    if args.model:
        cfg.model_name = args.model
    if args.temperature is not None:
        cfg.temperature = args.temperature
    if args.max_steps is not None:
        cfg.max_steps = args.max_steps
    cfg.headless = not args.headful
    cfg.use_vision = args.vision
    cfg.save_playwright_script = args.save_script

    print(f"Running {len(cases)} case(s) x{cfg.repeat} on {cfg.provider}/{cfg.model_name or 'default'} "
          f"(temp={cfg.temperature}, vision={cfg.use_vision}, headless={cfg.headless})")
    results_path = run_suite_sync(cases, cfg, args.label)

    from evals.report import build_report
    report_path = build_report(results_path.parent, baseline=args.baseline)
    print(f"\nResults: {results_path}\nReport:  {report_path}")
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    from evals.report import build_report
    out = build_report(args.run, baseline=args.baseline)
    print(f"Report written: {out}")
    print(out.read_text(encoding="utf-8"))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evals", description="QA Browser Agent eval harness (P0.1)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_val = sub.add_parser("validate", help="validate case files without launching a browser")
    p_val.add_argument("--cases-dir", default=DEFAULT_CASES_DIR)
    p_val.add_argument("--cases", nargs="*", help="only these case ids")
    p_val.set_defaults(func=_cmd_validate)

    p_run = sub.add_parser("run", help="run the suite and write results + report")
    p_run.add_argument("--cases-dir", default=DEFAULT_CASES_DIR)
    p_run.add_argument("--cases", nargs="*", help="only these case ids")
    p_run.add_argument("--label", default="run", help="label appended to the run id (e.g. 'baseline')")
    p_run.add_argument("--provider", help="LLM provider (default: $DEFAULT_LLM)")
    p_run.add_argument("--model", help="model name (default: provider default)")
    p_run.add_argument("--temperature", type=float, help="override temperature (default 0.0)")
    p_run.add_argument("--max-steps", type=int, dest="max_steps")
    p_run.add_argument("--repeat", type=int, default=1, help="runs per case (flake measurement)")
    p_run.add_argument("--headful", action="store_true", help="show the browser window")
    p_run.add_argument("--vision", action="store_true", help="enable screenshots to the model")
    p_run.add_argument("--save-script", action="store_true", dest="save_script",
                       help="also export the Playwright script per run")
    p_run.add_argument("--baseline", help="baseline run dir to diff the report against")
    p_run.set_defaults(func=_cmd_run)

    p_rep = sub.add_parser("report", help="render/diff a report from an existing run")
    p_rep.add_argument("run", help="run dir or results.json")
    p_rep.add_argument("--baseline", help="baseline run dir or results.json to diff against")
    p_rep.set_defaults(func=_cmd_report)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
