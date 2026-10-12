"""Drive the real browser-use agent over eval cases and record metrics.

Mirrors how src/webui/components/browser_use_agent_tab.py builds and runs
the agent (same CustomBrowser / CustomController / BrowserUseAgent wiring),
minus the Gradio UI, so results are representative.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from evals.assertions import evaluate_all
from evals.cases import Case
from evals.config import RunConfig
from evals.metrics import compute_metrics
from evals.task_prep import resolve_task
from evals.usage import UsageCallbackHandler

logger = logging.getLogger(__name__)

RUNS_DIR = Path("evals/runs")


def _model_label(llm: Any, cfg: RunConfig) -> str:
    for attr in ("model_name", "model", "model_id"):
        val = getattr(llm, attr, None)
        if val:
            return str(val)
    return cfg.resolved_model()


async def run_case_once(case: Case, cfg: RunConfig, out_dir: Path, repeat_idx: int) -> dict[str, Any]:
    """Run one case a single time; returns a metrics dict (never raises)."""
    # Imports kept local so `load_cases`/dry-run work without a browser stack.
    from browser_use.browser.browser import BrowserConfig
    from browser_use.browser.context import BrowserContextConfig

    from src.agent.browser_use.browser_use_agent import BrowserUseAgent
    from src.browser.custom_browser import CustomBrowser
    from src.controller.custom_controller import CustomController
    from src.utils import llm_provider

    run_label = f"{case.id}#{repeat_idx}"
    case_dir = out_dir / case.id / str(repeat_idx)
    case_dir.mkdir(parents=True, exist_ok=True)
    history_path = case_dir / "history.json"

    usage = UsageCallbackHandler()
    browser = None
    browser_context = None
    controller = None
    error: str | None = None
    model_label = cfg.resolved_model()
    t0 = time.perf_counter()

    try:
        task, resolved_secrets, resolved_phones = resolve_task(case.task)
        if resolved_phones:
            logger.info("[%s] resolved phone placeholders: %s", run_label, ", ".join(resolved_phones))

        llm = llm_provider.get_llm_model(
            provider=cfg.provider,
            model_name=cfg.model_name,
            temperature=cfg.temperature,
            base_url=cfg.base_url,
            api_key=cfg.api_key,
        )
        llm.callbacks = [usage]
        model_label = _model_label(llm, cfg)

        controller = CustomController()

        has_secrets = bool(resolved_secrets)
        browser = CustomBrowser(
            config=BrowserConfig(
                headless=cfg.headless,
                new_context_config=BrowserContextConfig(
                    window_width=cfg.window_w,
                    window_height=cfg.window_h,
                    allowed_domains=["*"] if has_secrets else None,
                ),
            )
        )
        browser_context = await browser.new_context(
            config=BrowserContextConfig(
                save_downloads_path="./tmp/downloads",
                window_width=cfg.window_w,
                window_height=cfg.window_h,
                allowed_domains=["*"] if has_secrets else None,
            )
        )

        sensitive_data = {f"SECRET_{i}": s for i, s in enumerate(resolved_secrets) if s} or None

        agent = BrowserUseAgent(
            task=task,
            llm=llm,
            browser=browser,
            browser_context=browser_context,
            controller=controller,
            use_vision=cfg.use_vision,
            max_input_tokens=cfg.max_input_tokens,
            max_actions_per_step=cfg.max_actions,
            tool_calling_method=cfg.tool_calling_method,
            source="eval",
            sensitive_data=sensitive_data,
        )
        agent.state.agent_id = run_label
        agent.settings.generate_gif = (
            str(case_dir / "run.gif") if cfg.generate_gif else False
        )
        agent.settings.save_playwright_script_path = (
            str(case_dir / "script.py") if cfg.save_playwright_script else None
        )

        max_steps = case.max_steps or cfg.max_steps
        await agent.run(max_steps=max_steps)
        agent.save_history(str(history_path))

    except Exception as exc:  # a failed run is a data point, not a crash
        error = f"{type(exc).__name__}: {exc}"
        logger.error("[%s] run failed: %s", run_label, error, exc_info=True)
    finally:
        if browser_context:
            try:
                await browser_context.close()
            except Exception:
                pass
        if browser:
            try:
                await browser.close()
            except Exception:
                pass
        if controller:
            try:
                await controller.close_mcp_client()
            except Exception:
                pass

    wall_clock = round(time.perf_counter() - t0, 3)

    history: dict[str, Any] = {}
    if history_path.exists():
        try:
            history = json.loads(history_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.error("[%s] could not read history: %s", run_label, exc)

    assertion_results = evaluate_all(history, case.assertions)
    metrics = compute_metrics(
        history=history,
        assertion_results=assertion_results,
        usage=usage.snapshot(),
        model_name=model_label,
        expected_status=case.expected_status,
        wall_clock_override_s=wall_clock,
        error=error,
    )
    metrics.update({"case_id": case.id, "repeat": repeat_idx, "run_label": run_label,
                    "history_path": str(history_path)})
    return metrics


def _summarize_case(case: Case, runs: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(runs)
    def rate(pred) -> float | None:
        vals = [pred(r) for r in runs]
        vals = [v for v in vals if v is not None]
        return round(sum(1 for v in vals if v) / len(vals), 3) if vals else None

    indep_pass_rate = rate(lambda r: r.get("independent_pass"))
    steps = [r["steps"] for r in runs if r.get("steps") is not None]
    costs = [r["est_cost_usd"] for r in runs]
    tokens = [r["total_tokens"] for r in runs]
    walls = [r["wall_clock_s"] for r in runs if r.get("wall_clock_s") is not None]

    self_vs_exp = [r.get("self_vs_expected") for r in runs if r.get("self_vs_expected")]
    indep_vs_exp = [r.get("independent_vs_expected") for r in runs if r.get("independent_vs_expected")]

    def frac(items, label):
        return round(items.count(label) / len(items), 3) if items else None

    return {
        "case_id": case.id,
        "description": case.description,
        "expected_status": case.expected_status,
        "repeats": n,
        "independent_pass_rate": indep_pass_rate,
        "flake": (indep_pass_rate not in (None, 0.0, 1.0)),
        "avg_steps": round(sum(steps) / len(steps), 1) if steps else None,
        "avg_total_tokens": round(sum(tokens) / len(tokens)) if tokens else None,
        "avg_cost_usd": round(sum(costs) / len(costs), 6) if costs else None,
        "avg_wall_clock_s": round(sum(walls) / len(walls), 2) if walls else None,
        # how wrong is self-grading vs human label (the P0.1 headline)
        "self_false_pass_rate": frac(self_vs_exp, "false_pass"),
        "self_false_fail_rate": frac(self_vs_exp, "false_fail"),
        "self_correct_rate": frac(self_vs_exp, "correct"),
        "independent_correct_rate": frac(indep_vs_exp, "correct"),
        "grader_agreement_rate": round(
            sum(1 for r in runs if r.get("grader_agreement")) /
            sum(1 for r in runs if r.get("grader_agreement") is not None), 3
        ) if any(r.get("grader_agreement") is not None for r in runs) else None,
        "errors": [r["error"] for r in runs if r.get("error")],
    }


async def run_suite(cases: list[Case], cfg: RunConfig, label: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = f"{stamp}_{label}" if label else stamp
    out_dir = RUNS_DIR / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    all_runs: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for case in cases:
        case_runs: list[dict[str, Any]] = []
        for i in range(cfg.repeat):
            logger.info("Running case %s (repeat %d/%d)", case.id, i + 1, cfg.repeat)
            m = await run_case_once(case, cfg, out_dir, i)
            case_runs.append(m)
            all_runs.append(m)
        summaries.append(_summarize_case(case, case_runs))

    results = {
        "run_id": run_id,
        "label": label,
        "created": stamp,
        "config": cfg.__dict__,
        "summaries": summaries,
        "runs": all_runs,
    }
    results_path = out_dir / "results.json"
    results_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    logger.info("Wrote %s", results_path)
    return results_path


def run_suite_sync(cases: list[Case], cfg: RunConfig, label: str) -> Path:
    return asyncio.run(run_suite(cases, cfg, label))
