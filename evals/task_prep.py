"""Resolve a task string exactly like the production Run tab does.

Mirrors the ``<get X from .env>`` secret substitution and the
``{{PHONE}}`` pool resolution in
``src/webui/components/browser_use_agent_tab.py`` so eval runs are
representative. Kept gradio-free so the harness can run headless.
"""
from __future__ import annotations

import os
import re

from src.utils.phone_number_pool import resolve_phone_placeholders

_ENV_TOKEN = re.compile(r"<get\s+(.*?)\s+from\s+\.env>", flags=re.IGNORECASE)


def resolve_task(task: str) -> tuple[str, list[str], list[str]]:
    """Return (resolved_task, resolved_secrets, resolved_phone_numbers).

    ``resolved_secrets`` are the concrete secret values substituted in, used
    to build the agent's ``sensitive_data`` map (so they get scrubbed from
    artifacts). May raise ``PhoneNumberPoolError`` if the pool is exhausted —
    the caller should surface that rather than swallow it.
    """
    resolved_secrets: list[str] = []

    def env_replacer(match: "re.Match[str]") -> str:
        var_name = match.group(1).strip()
        if var_name.lower() == "it":
            var_name = "PASSWORD"
        val = os.getenv(var_name)
        if val is not None:
            resolved_secrets.append(val)
            return val
        return match.group(0)

    task = _ENV_TOKEN.sub(env_replacer, task)
    task, resolved_phone_numbers = resolve_phone_placeholders(task)
    return task, resolved_secrets, resolved_phone_numbers
