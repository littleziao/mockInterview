from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_AI_CONFIG_PATH = Path("data/ai-provider.json")


@dataclass(frozen=True)
class AIProviderSettings:
    base_url: str
    api_key: str
    model: str

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)


@dataclass(frozen=True)
class PublicAIProviderSettings:
    base_url: str
    model: str
    has_api_key: bool
    is_configured: bool


def get_ai_config_path() -> Path:
    configured_path = os.getenv("MOCK_INTERVIEW_AI_CONFIG_PATH")
    return Path(configured_path) if configured_path else DEFAULT_AI_CONFIG_PATH


def empty_ai_provider_settings() -> AIProviderSettings:
    return AIProviderSettings(base_url="", api_key="", model="")


def read_ai_provider_settings(path: Path | None = None) -> AIProviderSettings:
    active_path = path or get_ai_config_path()
    if not active_path.exists():
        return empty_ai_provider_settings()

    data = json.loads(active_path.read_text(encoding="utf-8"))
    return AIProviderSettings(
        base_url=str(data.get("baseUrl", "")).strip(),
        api_key=str(data.get("apiKey", "")).strip(),
        model=str(data.get("model", "")).strip(),
    )


def save_ai_provider_settings(settings: AIProviderSettings, path: Path | None = None) -> AIProviderSettings:
    active_path = path or get_ai_config_path()
    active_path.parent.mkdir(parents=True, exist_ok=True)
    active_path.write_text(
        json.dumps(
            {
                "baseUrl": settings.base_url,
                "apiKey": settings.api_key,
                "model": settings.model,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    active_path.chmod(0o600)
    return settings


def to_public_settings(settings: AIProviderSettings) -> PublicAIProviderSettings:
    return PublicAIProviderSettings(
        base_url=settings.base_url,
        model=settings.model,
        has_api_key=bool(settings.api_key),
        is_configured=settings.is_configured,
    )
