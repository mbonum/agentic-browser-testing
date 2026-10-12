"""Run configuration for the eval harness.

Defaults mirror the production Run tab / Agent Settings so eval numbers
are representative of real usage. Override per-invocation from the CLI.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class RunConfig:
    # LLM
    provider: str = os.getenv("DEFAULT_LLM", "openai")
    model_name: str | None = None          # None => provider default in llm_provider
    temperature: float = 0.0               # harness default is deterministic (plan P0.3)
    base_url: str | None = None
    api_key: str | None = None

    # Agent
    max_steps: int = 100
    max_actions: int = 10
    max_input_tokens: int = 128000
    use_vision: bool = False               # matches current UI default
    tool_calling_method: str | None = "auto"

    # Browser
    headless: bool = True                  # eval default: headless for CI
    window_w: int = 1280
    window_h: int = 1100

    # Harness
    repeat: int = 1                        # runs per case (flake measurement)
    save_playwright_script: bool = False   # exercise script export too if True
    generate_gif: bool = False

    def resolved_model(self) -> str:
        # Best-effort model label for pricing/reporting when model_name is None.
        return self.model_name or f"{self.provider}-default"
