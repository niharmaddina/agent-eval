"""Provider registry: pick a provider by name."""

from __future__ import annotations

from agent_eval.providers.base import Provider, ProviderError, ProviderUnavailable

PROVIDER_NAMES = ["scripted", "scripted_flawed", "anthropic", "openai_compat"]


def get_provider(name: str, model: str | None = None) -> Provider:
    if name == "scripted":
        from agent_eval.providers.scripted import ScriptedProvider

        return ScriptedProvider(flawed=False)
    if name == "scripted_flawed":
        from agent_eval.providers.scripted import ScriptedProvider

        return ScriptedProvider(flawed=True)
    if name == "anthropic":
        from agent_eval.providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider(model=model)
    if name == "openai_compat":
        from agent_eval.providers.openai_compat import OpenAICompatProvider

        return OpenAICompatProvider(model=model)
    raise ProviderUnavailable(f"unknown provider '{name}'; choose from {PROVIDER_NAMES}")


__all__ = ["PROVIDER_NAMES", "Provider", "ProviderError", "ProviderUnavailable", "get_provider"]
