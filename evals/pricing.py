"""Token pricing lookup for cost estimation.

Prices are USD per 1,000 tokens. The table is intentionally small and
editable — keep it in sync with your providers' current rates. Model
names are matched by longest-substring, so an entry like ``"claude-3-5-sonnet"``
matches ``"claude-3-5-sonnet-20241022"``.

Per the "no silent caps" rule: when a model is not in the table we return
``priced=False`` and a zero cost so the report can flag it rather than
silently imply $0.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# model-name substring -> (input $/1k, output $/1k)
# NOTE: update these to your current contractual rates. Values below are
# order-of-magnitude placeholders for common models; unknown models are
# reported as unpriced rather than guessed.
PRICE_TABLE: dict[str, tuple[float, float]] = {
    "claude-3-5-sonnet": (0.003, 0.015),
    "claude-3-5-haiku": (0.0008, 0.004),
    "claude-3-opus": (0.015, 0.075),
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4o": (0.0025, 0.01),
    "gemini-1.5-flash": (0.000075, 0.0003),
    "gemini-1.5-pro": (0.00125, 0.005),
    "deepseek-chat": (0.00027, 0.0011),
}


@dataclass
class CostEstimate:
    input_tokens: int
    output_tokens: int
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float
    priced: bool  # False => model not in PRICE_TABLE, cost is 0 and should be flagged


def _match_rates(model_name: str) -> tuple[float, float] | None:
    if not model_name:
        return None
    name = model_name.lower()
    best_key = None
    for key in PRICE_TABLE:
        if key in name and (best_key is None or len(key) > len(best_key)):
            best_key = key
    return PRICE_TABLE[best_key] if best_key else None


def estimate_cost(model_name: str, input_tokens: int, output_tokens: int) -> CostEstimate:
    rates = _match_rates(model_name or "")
    if rates is None:
        logger.warning(
            "No pricing for model %r — cost reported as 0 and flagged unpriced. "
            "Add it to evals/pricing.py PRICE_TABLE.",
            model_name,
        )
        return CostEstimate(input_tokens, output_tokens, 0.0, 0.0, 0.0, priced=False)
    in_rate, out_rate = rates
    in_cost = input_tokens / 1000.0 * in_rate
    out_cost = output_tokens / 1000.0 * out_rate
    return CostEstimate(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        input_cost_usd=round(in_cost, 6),
        output_cost_usd=round(out_cost, 6),
        total_cost_usd=round(in_cost + out_cost, 6),
        priced=True,
    )
