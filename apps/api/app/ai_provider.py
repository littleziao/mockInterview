from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

from .ai_settings import AIProviderSettings


@dataclass(frozen=True)
class ProviderTestResult:
    status: str
    message: str


class AIProvider(Protocol):
    def test_connection(self) -> ProviderTestResult:
        raise NotImplementedError


class FakeAIProvider:
    def __init__(self, settings: AIProviderSettings) -> None:
        self.settings = settings

    def test_connection(self) -> ProviderTestResult:
        if self.settings.base_url == "fake://failure":
            return ProviderTestResult(status="failure", message="Fake AI Provider 连接失败")

        return ProviderTestResult(status="success", message="AI Provider 连接测试成功")


class OpenAICompatibleProvider:
    def __init__(self, settings: AIProviderSettings) -> None:
        self.settings = settings

    def test_connection(self) -> ProviderTestResult:
        endpoint = self.settings.base_url.rstrip("/") + "/chat/completions"
        try:
            response = httpx.post(
                endpoint,
                headers={"Authorization": f"Bearer {self.settings.api_key}"},
                json={
                    "model": self.settings.model,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 1,
                },
                timeout=10,
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            return ProviderTestResult(status="failure", message=f"AI Provider 连接失败：{error}")

        return ProviderTestResult(status="success", message="AI Provider 连接测试成功")


def build_ai_provider(settings: AIProviderSettings) -> AIProvider:
    if settings.base_url.startswith("fake://"):
        return FakeAIProvider(settings)

    return OpenAICompatibleProvider(settings)


def test_ai_provider_connection(settings: AIProviderSettings) -> ProviderTestResult:
    if not settings.is_configured:
        return ProviderTestResult(status="missing", message="请先保存 baseUrl、apiKey 和 model")

    return build_ai_provider(settings).test_connection()
