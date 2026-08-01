from __future__ import annotations

from openframe.agent import UsageStats
from openframe.agent.cost import ModelPricing, estimate_cost


def test_estimate_cost_uses_default_model_pricing() -> None:
    usage = UsageStats(input_tokens=1_000_000, output_tokens=1_000_000, calls=2)

    cost = estimate_cost(usage, "claude-haiku-4-5-20251001")

    assert cost == 6.0


def test_estimate_cost_returns_none_for_unknown_model() -> None:
    usage = UsageStats(input_tokens=500_000, output_tokens=250_000, calls=1)

    cost = estimate_cost(usage, "unknown-model")

    assert cost is None


def test_estimate_cost_honors_pricing_override() -> None:
    usage = UsageStats(input_tokens=1_000_000, output_tokens=1_000_000, calls=1)

    cost = estimate_cost(usage, "custom-model", pricing={"custom-model": (2.0, 4.0)})

    assert cost == 6.0


def test_estimate_cost_includes_cache_token_rates() -> None:
    usage = UsageStats(
        input_tokens=1_000_000,
        cache_creation_input_tokens=1_000_000,
        cache_read_input_tokens=1_000_000,
        output_tokens=1_000_000,
        calls=1,
    )

    cost = estimate_cost(
        usage,
        "custom-model",
        pricing={
            "custom-model": ModelPricing(
                input=1.0,
                output=5.0,
                cache_creation_input=1.25,
                cache_read_input=0.1,
            )
        },
    )

    assert cost == 7.35
