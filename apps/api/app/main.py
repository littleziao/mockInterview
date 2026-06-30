from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .ai_provider import test_ai_provider_connection
from .ai_settings import (
    AIProviderSettingsStore,
    AIProviderSettings,
    merge_with_existing_api_keys,
    read_ai_provider_store,
    save_ai_provider_store,
    to_public_store,
)
from .database import database_health, initialize_database


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    initialize_database()
    yield


app = FastAPI(
    title="Mock Interview API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AIProviderPayload(BaseModel):
    id: str
    name: str
    base_url: str = Field(alias="baseUrl")
    api_key: str = Field(default="", alias="apiKey")
    model: str


class AIProviderStorePayload(BaseModel):
    active_provider_id: str = Field(alias="activeProviderId")
    providers: list[AIProviderPayload]


class PublicAIProviderPayload(BaseModel):
    id: str
    name: str
    base_url: str = Field(serialization_alias="baseUrl")
    model: str
    has_api_key: bool = Field(serialization_alias="hasApiKey")
    is_configured: bool = Field(serialization_alias="isConfigured")


class PublicAIProviderStorePayload(BaseModel):
    active_provider_id: str = Field(serialization_alias="activeProviderId")
    providers: list[PublicAIProviderPayload]


class ProviderTestResultPayload(BaseModel):
    status: str
    message: str


@app.get("/health")
def health() -> dict[str, object]:
    database = database_health()
    return {
        "status": "ok",
        "service": "mock-interview-api",
        "database": database,
    }


def _to_public_payload(store: AIProviderSettingsStore) -> PublicAIProviderStorePayload:
    public_store = to_public_store(store)
    return PublicAIProviderStorePayload(
        active_provider_id=public_store.active_provider_id,
        providers=[
            PublicAIProviderPayload(
                id=provider.id,
                name=provider.name,
                base_url=provider.base_url,
                model=provider.model,
                has_api_key=provider.has_api_key,
                is_configured=provider.is_configured,
            )
            for provider in public_store.providers
        ],
    )


@app.get("/settings/ai-provider", response_model=PublicAIProviderStorePayload)
def get_ai_provider_settings() -> PublicAIProviderStorePayload:
    return _to_public_payload(read_ai_provider_store())


@app.put("/settings/ai-provider", response_model=PublicAIProviderStorePayload)
def put_ai_provider_settings(payload: AIProviderStorePayload) -> PublicAIProviderStorePayload:
    incoming_store = AIProviderSettingsStore(
        active_provider_id=payload.active_provider_id.strip(),
        providers=tuple(
            AIProviderSettings(
                id=provider.id.strip(),
                name=provider.name.strip(),
                base_url=provider.base_url.strip(),
                api_key=provider.api_key.strip(),
                model=provider.model.strip(),
            )
            for provider in payload.providers
            if provider.id.strip()
        ),
    )
    settings = save_ai_provider_store(
        merge_with_existing_api_keys(
            incoming_store=incoming_store,
            existing_store=read_ai_provider_store(),
        )
    )
    return _to_public_payload(settings)


@app.post("/settings/ai-provider/test", response_model=ProviderTestResultPayload)
def post_ai_provider_test() -> ProviderTestResultPayload:
    active_provider = read_ai_provider_store().active_provider
    if active_provider is None:
        return ProviderTestResultPayload(status="missing", message="请先新增并选择一个模型供应商")

    result = test_ai_provider_connection(active_provider)
    return ProviderTestResultPayload(status=result.status, message=result.message)
