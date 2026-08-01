"""Cost estimation utilities for agent usage totals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from openframe.agent.base import UsageStats


@dataclass(frozen=True, slots=True)
class ModelPricing:
    """USD rates per million tokens for one model."""

    input: float
    output: float
    cache_creation_input: float = 0.0
    cache_read_input: float = 0.0


MODEL_PRICING_PER_MTOK: dict[str, ModelPricing] = {
    "claude-haiku-4-5-20251001": ModelPricing(
        input=1.0,
        output=5.0,
        cache_creation_input=1.25,
        cache_read_input=0.10,
    ),
}


def estimate_cost(
    usage: UsageStats,
    model: str | None,
    *,
    pricing: Mapping[str, ModelPricing | tuple[float, float]] | None = None,
) -> float | None:
    """Estimate USD cost, returning ``None`` when model pricing is unknown."""
    if model is None:
        return None
    table = pricing if pricing is not None else MODEL_PRICING_PER_MTOK
    rate = table.get(model)
    if rate is None:
        return None
    if isinstance(rate, tuple):
        rate = ModelPricing(input=rate[0], output=rate[1])
    return (
        (usage.input_tokens / 1_000_000.0) * rate.input
        + (usage.cache_creation_input_tokens / 1_000_000.0)
        * rate.cache_creation_input
        + (usage.cache_read_input_tokens / 1_000_000.0) * rate.cache_read_input
        + (usage.output_tokens / 1_000_000.0) * rate.output
    )
