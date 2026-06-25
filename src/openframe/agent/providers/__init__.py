"""Concrete agent providers (Phase A).

Providers wrap a specific LLM backend and implement the :class:`Provider`
contract so :class:`AgentRunner` can drive Open Frame's deterministic tools.
"""

from .anthropic_provider import AnthropicProvider

__all__ = ["AnthropicProvider"]
