"""Provider registry: named providers from config → built ``LLMProvider`` instances.

The registry owns everything about WHICH provider talks to the run and HOW it
is constructed, so the four construction sites (CLI, ``Harness`` API, both
benchmarks) stop duplicating ``OpenAIProvider(...)`` wiring:

- ``resolve`` / ``select`` turn a model ref (``<provider>/<model>``) into a
  provider instance, via the config-level :func:`resolve_model_ref` grammar.
- Credentials walk the provider's ordered ``env`` variable names in the
  environment only — never the config file.
- Built instances are cached per (provider id, model id); ``close_all``
  releases them.

This is the runtime side of the opencode-style ``providers`` config: a named
map keyed by provider id, with per-provider credential source (``env``),
endpoint, OpenRouter routing, and model catalog, plus a general ``llm`` section
for call behavior shared by every provider.
"""

from __future__ import annotations

import os

from ..config import (
    HarnessConfig,
    LLMSettings,
    ModelSpec,
    ProviderConfig,
    ResolvedModel,
    resolve_model_ref,
)
from .provider import LLMProvider
from .openai_provider import OpenAIProvider

__all__ = ["ProviderCredentialError", "ProviderRegistry"]


class ProviderCredentialError(RuntimeError):
    """No credential resolved for a provider from the environment."""

    def __init__(self, provider_id: str, env: list[str]) -> None:
        self.provider_id = provider_id
        self.env = list(env)
        super().__init__(
            f"no credential for provider '{provider_id}': set one of "
            f"{', '.join(env)} in the environment (credentials are never read "
            f"from the config file)"
        )


class ProviderRegistry:
    """Named providers from config → lazily built, cached ``LLMProvider`` instances.

    ``model_ref``/``provider`` select the active model; ``api_key``/``base_url``
    are run-scoped overrides for the active provider's credential and endpoint
    (the config file never carries secrets).
    """

    def __init__(
        self,
        providers: dict[str, ProviderConfig],
        llm: LLMSettings,
        model_ref: str,
        *,
        provider: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._providers = providers
        self._llm = llm
        self._model_ref = model_ref
        self._provider_override = provider
        self._api_key_override = api_key
        self._base_url_override = base_url
        self._built: dict[tuple[str, str], LLMProvider] = {}
        self._active: LLMProvider | None = None
        self._active_ref = resolve_model_ref(
            providers, model_ref, provider=self._provider_override
        )

    @classmethod
    def from_config(
        cls,
        config: HarnessConfig,
        *,
        model_ref: str | None = None,
        provider: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> ProviderRegistry:
        """Build a registry from a harness config."""

        return cls(
            dict(config.providers),
            config.llm,
            model_ref or config.root_model,
            provider=provider,
            api_key=api_key,
            base_url=base_url,
        )

    def resolve(self, model_ref: str | None = None) -> ResolvedModel:
        """Resolve a model ref to the active provider + model (pure)."""

        return resolve_model_ref(self._providers, self._model_ref, model_ref)

    def api_key_for(self, provider_id: str) -> str | None:
        """Credential from the environment only: walk the provider's ordered
        ``env`` names; the first set variable wins."""

        for name in self._providers[provider_id].env:
            value = os.environ.get(name)
            if value:
                return value
        return None

    def base_url_for(self, provider_id: str) -> str:
        """The endpoint the provider's requests go to."""

        return self._providers[provider_id].base_url

    def build(
        self,
        provider_id: str,
        *,
        model_id: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> LLMProvider:
        """Construct and cache the provider for ``provider_id`` + ``model_id``.

        Repeated builds of the same provider+model pair return the cached
        instance; different models on the same provider get distinct instances
        (each with its own ``default_model``). ``model_id`` selects the catalog
        key whose ``model_id`` is sent upstream (default: the provider's first
        models key). ``api_key``/``base_url`` default to the provider's resolved
        credential/endpoint; the registry-level overrides apply when building
        the active provider.
        """

        pc = self._providers[provider_id]
        if not pc.models:
            raise ValueError(f"provider '{provider_id}' has no models configured; add a models entry")
        model_key = model_id or next(iter(pc.models))
        cached = self._built.get((provider_id, model_key))
        if cached is not None:
            return cached
        spec = pc.models.get(model_key) or ModelSpec()
        active_provider = provider_id == self.model_info.provider_id
        llm = OpenAIProvider(
            model=spec.model_id or model_key,
            base_url=(
                base_url
                or (self._base_url_override if active_provider and self._base_url_override else None)
                or pc.base_url
            ),
            api_key=(
                api_key
                or (self._api_key_override if active_provider and self._api_key_override else None)
                or self.api_key_for(provider_id)
            ),
            verify_ssl=self._llm.verify_ssl,
            stream=self._llm.stream,
            provider_ignore=pc.provider_ignore or None,
            provider_allow_fallbacks=pc.provider_allow_fallbacks,
            provider_force=pc.provider_force,
            timeout=self._llm.call_timeout_seconds,
        )
        self._built[(provider_id, model_key)] = llm
        return llm

    def select(self, model_ref: str | None = None) -> LLMProvider:
        """Resolve + build the provider for ``model_ref`` and mark it active.

        Raises ``ProviderCredentialError`` when no credential resolves — the
        caller decides how to report a keyless run (the CLI gate keeps
        today's "no provider, agent fails with a recorded reason" behavior).
        """

        resolved = self.resolve(model_ref)
        api_key = self._api_key_override or self.api_key_for(resolved.provider_id)
        if api_key is None:
            raise ProviderCredentialError(
                resolved.provider_id, self._providers[resolved.provider_id].env
            )
        llm = self.build(
            resolved.provider_id,
            model_id=resolved.model_id,
            api_key=api_key,
            base_url=self._base_url_override,
        )
        self._active = llm
        return llm

    def provider_for(self, model_ref: str | None = None) -> LLMProvider:
        """Build (or return the cached) provider for ``model_ref`` WITHOUT
        changing the active selection.

        Unlike :meth:`select`, the runtime's active provider is untouched —
        use this for per-task model overrides (e.g. delegated children on a
        model profile) where each consumer keeps its own instance. Raises
        ``ProviderCredentialError`` when no credential resolves.
        """

        resolved = self.resolve(model_ref)
        api_key = self._api_key_override or self.api_key_for(resolved.provider_id)
        if api_key is None:
            raise ProviderCredentialError(
                resolved.provider_id, self._providers[resolved.provider_id].env
            )
        return self.build(
            resolved.provider_id,
            model_id=resolved.model_id,
            api_key=api_key,
            base_url=self._base_url_override,
        )

    @property
    def active_provider_id(self) -> str:
        """The provider id the active selection resolved to."""

        return self.model_info.provider_id

    @property
    def model_info(self) -> ResolvedModel:
        """The active model fully resolved (provider, upstream id, metadata)."""

        return self._active_ref

    async def close_all(self) -> None:
        """Release every built provider (idempotent)."""

        for llm in self._built.values():
            await llm.aclose()
        self._built.clear()
        self._active = None


def build_provider(
    config: HarnessConfig,
    *,
    model_ref: str | None = None,
    provider: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> LLMProvider:
    """Shared single-source provider factory for the construction sites
    (CLI, ``Harness`` API, benchmarks): registry → select the active model."""

    registry = ProviderRegistry.from_config(
        config, model_ref=model_ref, provider=provider,
        api_key=api_key, base_url=base_url,
    )
    return registry.select()
