"""Compute per-run metrics from saved history + usage.

The headline metrics for P0.1 are the ones that quantify how trustworthy
the current self-grading is:
  - self_grade        : what the tool reports today (model grades itself)
  - independent_pass  : grounded assertions (the honest signal)
  - expected_status   : human ground-truth label on the case
  - self_vs_expected  : correct | false_pass | false_fail   (the key number)
  - grader_agreement  : self_grade == independent_pass
Plus cost/speed: steps, input/output tokens, $, wall-clock, action errors.
"""
from __future__ import annotations

from typing import Any

from evals.assertions import AssertionResult
from evals.pricing import estimate_cost


def compute_self_grade(history: dict[str, Any]) -> str:
    """Replicates src/webui/components/results_tab.py pass/fail heuristic."""
    steps = history.get("history") or []
    if not steps:
        return "unknown"
    last = steps[-1] or {}
    cs = ((last.get("model_output") or {}).get("current_state") or {})
    evaluation = (cs.get("evaluation_previous_goal") or "")
    if "fail" in evaluation.lower() or "error" in evaluation.lower():
        return "fail"
    return "pass"


def _history_input_tokens(history: dict[str, Any]) -> int:
    total = 0
    for step in history.get("history") or []:
        md = (step or {}).get("metadata") or {}
        total += int(md.get("input_tokens") or 0)
    return total


def _action_error_count(history: dict[str, Any]) -> int:
    n = 0
    for step in history.get("history") or []:
        for r in (step or {}).get("result") or []:
            if r.get("error"):
                n += 1
    return n


def _wall_clock_seconds(history: dict[str, Any]) -> float | None:
    steps = history.get("history") or []
    starts, ends = [], []
    for step in steps:
        md = (step or {}).get("metadata") or {}
        if md.get("step_start_time") is not None:
            starts.append(md["step_start_time"])
        if md.get("step_end_time") is not None:
            ends.append(md["step_end_time"])
    if starts and ends:
        try:
            return round(max(ends) - min(starts), 3)
        except Exception:
            return None
    return None


def _classify(self_or_indep: str | bool | None, expected: str | None) -> str | None:
    """correct | false_pass | false_fail | None (if either side unknown)."""
    if expected not in ("pass", "fail"):
        return None
    if isinstance(self_or_indep, bool):
        got = "pass" if self_or_indep else "fail"
    else:
        got = self_or_indep
    if got not in ("pass", "fail"):
        return None
    if got == expected:
        return "correct"
    return "false_pass" if got == "pass" else "false_fail"


def compute_metrics(
    *,
    history: dict[str, Any],
    assertion_results: list[AssertionResult],
    usage: dict[str, Any],
    model_name: str,
    expected_status: str | None,
    wall_clock_override_s: float | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    steps = history.get("history") or []
    step_count = len(steps)

    self_grade = compute_self_grade(history)

    have_assertions = len(assertion_results) > 0
    independent_pass: bool | None = (
        all(a.passed for a in assertion_results) if have_assertions else None
    )

    # usage: prefer callback-captured tokens; fall back to history input tokens
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    if not usage.get("captured_any"):
        input_tokens = _history_input_tokens(history)  # output stays 0, flagged below
    cost = estimate_cost(model_name, input_tokens, output_tokens)

    wall_clock = wall_clock_override_s if wall_clock_override_s is not None else _wall_clock_seconds(history)

    grader_agreement: bool | None = None
    if independent_pass is not None:
        grader_agreement = (self_grade == ("pass" if independent_pass else "fail"))

    return {
        "error": error,
        "steps": step_count,
        "action_error_count": _action_error_count(history),
        # verdicts
        "self_grade": self_grade,
        "independent_pass": independent_pass,
        "expected_status": expected_status,
        "self_vs_expected": _classify(self_grade, expected_status),
        "independent_vs_expected": _classify(independent_pass, expected_status),
        "grader_agreement": grader_agreement,
        "assertions": [
            {"type": a.type, "passed": a.passed, "detail": a.detail, "spec": a.spec}
            for a in assertion_results
        ],
        # cost / speed
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "llm_calls": usage.get("call_count", 0),
        "tokens_captured": bool(usage.get("captured_any")),
        "est_cost_usd": cost.total_cost_usd,
        "cost_priced": cost.priced,
        "wall_clock_s": wall_clock,
        "model": model_name,
    }
