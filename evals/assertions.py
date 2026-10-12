"""Lightweight, grounded assertions evaluated against saved run history.

This is the *independent* success signal that replaces trusting the
model's own prose. It is deliberately simple for P0.1 — it reads the
``AgentHistory.json`` the run produced (final result text, visited URLs,
extracted content, action errors). P1.2 will extend this with real
DOM/Playwright assertions compiled from an ``ASSERTIONS`` block in the
prompt; the metric contract here (a list of pass/fail checks →
``independent_pass``) stays the same so the harness does not change.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class AssertionResult:
    type: str
    passed: bool
    detail: str
    spec: dict[str, Any]


def _steps(history: dict[str, Any]) -> list[dict]:
    return history.get("history", []) or []


def _non_blank_urls(history: dict[str, Any]) -> list[str]:
    urls = []
    for step in _steps(history):
        url = ((step or {}).get("state") or {}).get("url") or ""
        if url and url != "about:blank":
            urls.append(url)
    return urls


def _all_results(history: dict[str, Any]) -> list[dict]:
    out = []
    for step in _steps(history):
        out.extend((step or {}).get("result") or [])
    return out


def _final_result_text(history: dict[str, Any]) -> str:
    results = _all_results(history)
    for r in reversed(results):
        if r.get("is_done") and r.get("extracted_content"):
            return str(r.get("extracted_content"))
    for r in reversed(results):
        if r.get("extracted_content"):
            return str(r.get("extracted_content"))
    return ""


def _corpus(history: dict[str, Any]) -> str:
    """All model-visible text produced during the run (for text-presence checks)."""
    parts: list[str] = []
    for step in _steps(history):
        step = step or {}
        cs = ((step.get("model_output") or {}).get("current_state") or {})
        for k in ("evaluation_previous_goal", "memory", "next_goal"):
            if cs.get(k):
                parts.append(str(cs[k]))
        for r in step.get("result") or []:
            if r.get("extracted_content"):
                parts.append(str(r["extracted_content"]))
            if r.get("error"):
                parts.append(str(r["error"]))
    return "\n".join(parts)


def _errors(history: dict[str, Any]) -> list[str]:
    return [str(r["error"]) for r in _all_results(history) if r.get("error")]


def _is_done(history: dict[str, Any]) -> bool:
    return any(r.get("is_done") for r in _all_results(history))


def _contains(haystack: str, needle: str, ignore_case: bool) -> bool:
    if ignore_case:
        return needle.lower() in haystack.lower()
    return needle in haystack


def evaluate_assertion(history: dict[str, Any], spec: dict[str, Any]) -> AssertionResult:
    a_type = spec.get("type", "")
    value = spec.get("value")
    ic = bool(spec.get("ignore_case", True))

    if a_type == "no_errors":
        errs = _errors(history)
        return AssertionResult(a_type, not errs, f"{len(errs)} action error(s)", spec)

    if a_type == "is_done":
        done = _is_done(history)
        return AssertionResult(a_type, done, f"is_done={done}", spec)

    if a_type == "final_url_contains":
        urls = _non_blank_urls(history)
        final_url = urls[-1] if urls else ""
        ok = _contains(final_url, str(value), ic)
        return AssertionResult(a_type, ok, f"final_url={final_url!r}", spec)

    if a_type == "any_url_contains":
        urls = _non_blank_urls(history)
        ok = any(_contains(u, str(value), ic) for u in urls)
        return AssertionResult(a_type, ok, f"{len(urls)} url(s) checked", spec)

    if a_type == "final_result_contains":
        txt = _final_result_text(history)
        ok = _contains(txt, str(value), ic)
        return AssertionResult(a_type, ok, f"final_result={txt[:120]!r}", spec)

    if a_type == "final_result_not_contains":
        txt = _final_result_text(history)
        ok = not _contains(txt, str(value), ic)
        return AssertionResult(a_type, ok, f"final_result={txt[:120]!r}", spec)

    if a_type == "history_contains_text":
        ok = _contains(_corpus(history), str(value), ic)
        return AssertionResult(a_type, ok, f"searched run text for {value!r}", spec)

    if a_type == "history_not_contains_text":
        ok = not _contains(_corpus(history), str(value), ic)
        return AssertionResult(a_type, ok, f"searched run text for {value!r}", spec)

    if a_type == "min_steps":
        n = len(_steps(history))
        ok = n >= int(value)
        return AssertionResult(a_type, ok, f"steps={n} min={value}", spec)

    if a_type == "max_steps":
        n = len(_steps(history))
        ok = n <= int(value)
        return AssertionResult(a_type, ok, f"steps={n} max={value}", spec)

    return AssertionResult(a_type or "unknown", False, f"unknown assertion type {a_type!r}", spec)


def evaluate_all(history: dict[str, Any], specs: list[dict[str, Any]]) -> list[AssertionResult]:
    return [evaluate_assertion(history, s) for s in (specs or [])]
