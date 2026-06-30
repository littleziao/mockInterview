from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_AI_CONFIG_PATH = Path("data/ai-provider.json")
DEFAULT_PROVIDER_ID = "default"


@dataclass(frozen=True)
class AIProviderSettings:
    id: str
    name: str
    base_url: str
    api_key: str
    model: str

    @property
    def is_configured(self) -> bool:
        return bool(self.name and self.base_url and self.api_key and self.model)


@dataclass(frozen=True)
class AIProviderSettingsStore:
    providers: tuple[AIProviderSettings, ...]
    active_provider_id: str

    @property
    def active_provider(self) -> AIProviderSettings | None:
        return next((provider for provider in self.providers if provider.id == self.active_provider_id), None)


@dataclass(frozen=True)
class PublicAIProviderSettings:
    id: str
    name: str
    base_url: str
    model: str
    has_api_key: bool
    is_configured: bool


@dataclass(frozen=True)
class PublicAIProviderSettingsStore:
    providers: tuple[PublicAIProviderSettings, ...]
    active_provider_id: str


def get_ai_config_path() -> Path:
    configured_path = os.getenv("MOCK_INTERVIEW_AI_CONFIG_PATH")
    return Path(configured_path) if configured_path else DEFAULT_AI_CONFIG_PATH


def empty_ai_provider_store() -> AIProviderSettingsStore:
    return AIProviderSettingsStore(providers=(), active_provider_id="")


def _provider_from_data(data: dict[str, object], fallback_id: str) -> AIProviderSettings:
    provider_id = str(data.get("id") or fallback_id).strip()
    return AIProviderSettings(
        id=provider_id,
        name=str(data.get("name") or "默认供应商").strip(),
        base_url=str(data.get("baseUrl", "")).strip(),
        api_key=str(data.get("apiKey", "")).strip(),
        model=str(data.get("model", "")).strip(),
    )


def _store_from_data(data: dict[str, object]) -> AIProviderSettingsStore:
    if "providers" not in data:
        provider = _provider_from_data(data, DEFAULT_PROVIDER_ID)
        return AIProviderSettingsStore(
            providers=(provider,),
            active_provider_id=provider.id if provider.is_configured else "",
        )

    providers_data = data.get("providers", [])
    providers = tuple(
        _provider_from_data(provider, f"provider-{index + 1}")
        for index, provider in enumerate(providers_data)
        if isinstance(provider, dict)
    )
    active_provider_id = str(data.get("activeProviderId", "")).strip()
    if providers and active_provider_id not in {provider.id for provider in providers}:
        active_provider_id = providers[0].id

    return AIProviderSettingsStore(providers=providers, active_provider_id=active_provider_id)


def read_ai_provider_store(path: Path | None = None) -> AIProviderSettingsStore:
    active_path = path or get_ai_config_path()
    if not active_path.exists():
        return empty_ai_provider_store()

    data = json.loads(active_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return empty_ai_provider_store()

    return _store_from_data(data)


def save_ai_provider_store(store: AIProviderSettingsStore, path: Path | None = None) -> AIProviderSettingsStore:
    active_path = path or get_ai_config_path()
    active_path.parent.mkdir(parents=True, exist_ok=True)
    active_path.write_text(
        json.dumps(
            {
                "activeProviderId": store.active_provider_id,
                "providers": [
                    {
                        "id": provider.id,
                        "name": provider.name,
                        "baseUrl": provider.base_url,
                        "apiKey": provider.api_key,
                        "model": provider.model,
                    }
                    for provider in store.providers
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    active_path.chmod(0o600)
    return store


def merge_with_existing_api_keys(
    incoming_store: AIProviderSettingsStore,
    existing_store: AIProviderSettingsStore,
) -> AIProviderSettingsStore:
    existing_api_keys = {provider.id: provider.api_key for provider in existing_store.providers}
    providers = tuple(
        AIProviderSettings(
            id=provider.id,
            name=provider.name,
            base_url=provider.base_url,
            api_key=provider.api_key or existing_api_keys.get(provider.id, ""),
            model=provider.model,
        )
        for provider in incoming_store.providers
    )
    active_provider_id = incoming_store.active_provider_id
    if providers and active_provider_id not in {provider.id for provider in providers}:
        active_provider_id = providers[0].id

    return AIProviderSettingsStore(providers=providers, active_provider_id=active_provider_id)


def to_public_provider_settings(settings: AIProviderSettings) -> PublicAIProviderSettings:
    return PublicAIProviderSettings(
        id=settings.id,
        name=settings.name,
        base_url=settings.base_url,
        model=settings.model,
        has_api_key=bool(settings.api_key),
        is_configured=settings.is_configured,
    )


def to_public_store(store: AIProviderSettingsStore) -> PublicAIProviderSettingsStore:
    return PublicAIProviderSettingsStore(
        providers=tuple(to_public_provider_settings(provider) for provider in store.providers),
        active_provider_id=store.active_provider_id,
    )
