"""Render an eval run to Markdown and diff it against a baseline.

Usage:
    python -m evals report evals/runs/<run_id>
    python -m evals report evals/runs/<run_id> --baseline evals/runs/<baseline_id>
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_results(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if path.is_dir():
        path = path / "results.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _fmt(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


def _pct(v: Any) -> str:
    return "—" if v is None else f"{round(v * 100)}%"


def _overall(results: dict[str, Any]) -> dict[str, Any]:
    runs = results.get("runs", [])
    def avg(key):
        xs = [r[key] for r in runs if r.get(key) is not None]
        return round(sum(xs) / len(xs), 6) if xs else None
    sve = [r.get("self_vs_expected") for r in runs if r.get("self_vs_expected")]
    unpriced = sorted({r["model"] for r in runs if not r.get("cost_priced", True)})
    missing_usage = sum(1 for r in runs if not r.get("tokens_captured"))
    return {
        "total_runs": len(runs),
        "avg_steps": avg("steps"),
        "avg_total_tokens": avg("total_tokens"),
        "avg_cost_usd": avg("est_cost_usd"),
        "avg_wall_clock_s": avg("wall_clock_s"),
        "self_false_pass_rate": round(sve.count("false_pass") / len(sve), 3) if sve else None,
        "self_false_fail_rate": round(sve.count("false_fail") / len(sve), 3) if sve else None,
        "self_correct_rate": round(sve.count("correct") / len(sve), 3) if sve else None,
        "unpriced_models": unpriced,
        "runs_missing_usage": missing_usage,
    }


def render_markdown(results: dict[str, Any], baseline: dict[str, Any] | None = None) -> str:
    lines: list[str] = []
    cfg = results.get("config", {})
    lines.append(f"# Eval report — `{results.get('run_id')}`")
    lines.append("")
    lines.append(
        f"Provider: `{cfg.get('provider')}`  ·  model: `{cfg.get('model_name') or 'provider-default'}`  "
        f"·  temp: {cfg.get('temperature')}  ·  vision: {cfg.get('use_vision')}  ·  repeats: {cfg.get('repeat')}"
    )
    lines.append("")

    ov = _overall(results)
    lines.append("## Overall")
    lines.append("")
    lines.append("| metric | value |" + (" | baseline | Δ |" if baseline else ""))
    lines.append("|---|---|" + ("---|---|" if baseline else ""))
    base_ov = _overall(baseline) if baseline else {}
    for key, label in [
        ("total_runs", "runs"),
        ("self_false_pass_rate", "self-grade FALSE PASS rate"),
        ("self_false_fail_rate", "self-grade FALSE FAIL rate"),
        ("self_correct_rate", "self-grade correct rate"),
        ("avg_steps", "avg steps"),
        ("avg_total_tokens", "avg total tokens"),
        ("avg_cost_usd", "avg cost $"),
        ("avg_wall_clock_s", "avg wall-clock s"),
    ]:
        val = ov.get(key)
        row = f"| {label} | {_fmt(val)} |"
        if baseline:
            bval = base_ov.get(key)
            delta = "—"
            if isinstance(val, (int, float)) and isinstance(bval, (int, float)):
                delta = f"{val - bval:+g}"
            row += f" {_fmt(bval)} | {delta} |"
        lines.append(row)
    lines.append("")

    if ov["unpriced_models"]:
        lines.append(f"> ⚠️ Unpriced models (cost shown as 0): {', '.join(ov['unpriced_models'])} — add to `evals/pricing.py`.")
    if ov["runs_missing_usage"]:
        lines.append(f"> ⚠️ {ov['runs_missing_usage']} run(s) had no captured token usage (output tokens may read 0).")
    lines.append("")

    lines.append("## Per-case")
    lines.append("")
    lines.append("| case | expected | indep pass | self correct | self FP | self FF | agree | flake | avg steps | avg tok | avg $ | avg s |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for s in results.get("summaries", []):
        lines.append(
            f"| {s['case_id']} | {_fmt(s['expected_status'])} | {_pct(s['independent_pass_rate'])} | "
            f"{_pct(s['self_correct_rate'])} | {_pct(s['self_false_pass_rate'])} | {_pct(s['self_false_fail_rate'])} | "
            f"{_pct(s['grader_agreement_rate'])} | {_fmt(s['flake'])} | {_fmt(s['avg_steps'])} | "
            f"{_fmt(s['avg_total_tokens'])} | {_fmt(s['avg_cost_usd'])} | {_fmt(s['avg_wall_clock_s'])} |"
        )
    lines.append("")

    errs = [(s["case_id"], e) for s in results.get("summaries", []) for e in s.get("errors", [])]
    if errs:
        lines.append("## Errors")
        lines.append("")
        for cid, e in errs:
            lines.append(f"- **{cid}**: {e}")
        lines.append("")

    lines.append(
        "_FP = false pass (self says pass, human says fail); FF = false fail. "
        "Independent pass = grounded assertions. Lower FP/FF and higher agreement after P1.2 is the goal._"
    )
    return "\n".join(lines)


def build_report(run: str | Path, baseline: str | Path | None = None) -> Path:
    results = _load_results(run)
    base = _load_results(baseline) if baseline else None
    md = render_markdown(results, base)
    out_dir = Path(run) if Path(run).is_dir() else Path(run).parent
    out_path = out_dir / "report.md"
    out_path.write_text(md, encoding="utf-8")
    return out_path
