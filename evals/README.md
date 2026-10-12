# Eval harness (plan P0.1)

Measures the QA Browser Agent on labeled cases so every later change
(deterministic arithmetic, independent verification, replay, CLM) can be
proven — not assumed — against a snapshot baseline. This is the **gate**
for the rest of the roadmap: land it before changing agent behavior.

It drives the **real** agent (same `CustomBrowser` / `CustomController` /
`BrowserUseAgent` wiring as the Run tab, minus Gradio), so numbers are
representative.

## Quick start

```bash
# 1. Validate case files, assertion types, and pricing — no browser launched
python -m evals validate

# 2. Snapshot the current behavior as the baseline (runs each case 3x for flake)
python -m evals run --label baseline --repeat 3

# 3. Later, after a change, run again and diff against the baseline
python -m evals run --label after-p1.1 --baseline evals/runs/<baseline_run_id>
```

Results land in `evals/runs/<run_id>/` (`results.json` + `report.md`,
plus per-case `history.json`). `evals/runs/` is git-ignored.

## What it measures

The P0.1 headline is **how untrustworthy self-grading is today**:

| metric | meaning |
|---|---|
| `self_grade` | what the tool reports now (model grades its own prose — see `results_tab.py`) |
| `independent_pass` | grounded assertions against the run history (the honest signal) |
| `expected_status` | your human ground-truth label on the case |
| `self_false_pass_rate` | self says **pass**, human says **fail** — the dangerous one |
| `self_false_fail_rate` | self says **fail**, human says **pass** |
| `grader_agreement_rate` | self_grade vs independent agreement |
| cost/speed | steps, input/output tokens, est $ (see `pricing.py`), wall-clock, action errors, flake |

Driving `self_false_pass_rate` toward 0 is the goal of P1.1 (deterministic
arithmetic) and P1.2 (independent verification); this harness is how you
prove it moved.

## Case format

One YAML file per case in `evals/cases/` (see `_template.yaml`). It points
at an existing `prompts/*.md` (or inline `task:`), sets the human
`expected_status` label, and lists `assertions`. Secret (`<get X from .env>`)
and phone-pool (`{{...}}`) tokens are resolved exactly like production.

> Set `expected_status` per case from your own knowledge of the app — it is
> the ground truth the self-grader is scored against. The example cases ship
> with `TODO` notes where you should confirm the label and success markers.

## Notes / limitations (P0.1 scope)

- Assertions are **text/URL/history** checks for now; P1.2 replaces them with
  real DOM/Playwright assertions compiled from an `ASSERTIONS` block in the
  prompt. The metric contract (`independent_pass`) stays the same.
- Output tokens come from LangChain `usage_metadata` via a callback on the
  model; the custom `DeepSeekR1ChatOpenAI` wrapper bypasses callbacks, so its
  output tokens won't be captured (flagged in the report).
- Unpriced models report `$0` and are flagged — add rates to `pricing.py`.
- `galaxy-migration` consumes a phone-pool pair per run; keep `--repeat` small
  for it or it will exhaust `prompts/phone_number_pool.json`.
