"""Evaluation harness for the QA Browser Agent (plan P0.1).

Drives the real browser-use agent over labeled cases and records
accuracy / cost / speed metrics so any later change (deterministic
arithmetic, independent verification, replay, or CLM) can be A/B'd
against a snapshot baseline.

Entry point: ``python -m evals ...`` (see ``evals/__main__.py``) or the
``evals/README.md`` for usage.
"""
