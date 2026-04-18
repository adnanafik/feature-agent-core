"""Provider registry with factory function."""

from __future__ import annotations

from typing import Any

from agent.llm.anthropic_provider import AnthropicProvider
from agent.llm.base import LLMProvider
from agent.llm.bedrock_provider import BedrockProvider

PROVIDERS: dict[str, type[LLMProvider]] = {
    "anthropic": AnthropicProvider,
    "bedrock": BedrockProvider,
}


def create_provider(provider_type: str, credentials: dict[str, Any]) -> LLMProvider:
    """Create an LLM provider by type name.

    Args:
        provider_type: One of the registered provider names (e.g. "anthropic", "bedrock").
        credentials: Provider-specific credentials dict.

    Returns:
        An instantiated LLMProvider.

    Raises:
        ValueError: If provider_type is not registered.
    """
    cls = PROVIDERS.get(provider_type)
    if cls is None:
        raise ValueError(
            f"Unknown provider type '{provider_type}'. "
            f"Available: {', '.join(sorted(PROVIDERS.keys()))}"
        )
    return cls(credentials=credentials)
