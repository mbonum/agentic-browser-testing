"""LangChain callback that records real token usage per run.

browser-use records *input* tokens per step in history metadata, but not
output tokens. Attaching this handler to the chat model instance
(``llm.callbacks = [UsageCallbackHandler()]``) captures both input and
output tokens and the number of LLM calls, across providers, by reading
``usage_metadata`` off the returned messages (and falling back to the
provider's ``llm_output`` token_usage block).

Caveat: the custom ``DeepSeekR1ChatOpenAI`` wrapper in
``src/utils/llm_provider.py`` calls the raw OpenAI client and bypasses
LangChain callbacks, so its usage will not be captured here.
"""
from __future__ import annotations

import logging
from typing import Any

from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.outputs import LLMResult

logger = logging.getLogger(__name__)


class UsageCallbackHandler(BaseCallbackHandler):
    def __init__(self) -> None:
        self.input_tokens = 0
        self.output_tokens = 0
        self.call_count = 0
        self.captured_any = False  # False => no usage found; totals are unreliable

    def _add_from_usage_metadata(self, usage: dict[str, Any]) -> bool:
        if not usage:
            return False
        # AIMessage.usage_metadata: input_tokens / output_tokens
        inp = usage.get("input_tokens")
        out = usage.get("output_tokens")
        if inp is None and out is None:
            # provider token_usage style: prompt_tokens / completion_tokens
            inp = usage.get("prompt_tokens")
            out = usage.get("completion_tokens")
        if inp is None and out is None:
            return False
        self.input_tokens += int(inp or 0)
        self.output_tokens += int(out or 0)
        return True

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        self.call_count += 1
        found = False
        try:
            for generation_list in response.generations:
                for gen in generation_list:
                    message = getattr(gen, "message", None)
                    usage = getattr(message, "usage_metadata", None) if message else None
                    if usage and self._add_from_usage_metadata(dict(usage)):
                        found = True
            if not found and response.llm_output:
                token_usage = response.llm_output.get("token_usage") or response.llm_output.get("usage")
                if token_usage and self._add_from_usage_metadata(dict(token_usage)):
                    found = True
        except Exception as exc:  # never let telemetry break a run
            logger.debug("UsageCallbackHandler failed to parse usage: %s", exc)
        if found:
            self.captured_any = True

    def snapshot(self) -> dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.input_tokens + self.output_tokens,
            "call_count": self.call_count,
            "captured_any": self.captured_any,
        }
