from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .ai_provider import test_ai_provider_connection
from .ai_settings import (
    AIProviderSettings,
    read_ai_provider_settings,
    save_ai_provider_settings,
    to_public_settings,
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


class AIProviderSettingsPayload(BaseModel):
    base_url: str = Field(alias="baseUrl")
    api_key: str = Field(default="", alias="apiKey")
    model: str


class PublicAIProviderSettingsPayload(BaseModel):
    base_url: str = Field(serialization_alias="baseUrl")
    model: str
    has_api_key: bool = Field(serialization_alias="hasApiKey")
    is_configured: bool = Field(serialization_alias="isConfigured")


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


@app.get("/settings/ai-provider", response_model=PublicAIProviderSettingsPayload)
def get_ai_provider_settings() -> PublicAIProviderSettingsPayload:
    settings = to_public_settings(read_ai_provider_settings())
    return PublicAIProviderSettingsPayload(
        base_url=settings.base_url,
        model=settings.model,
        has_api_key=settings.has_api_key,
        is_configured=settings.is_configured,
    )


@app.put("/settings/ai-provider", response_model=PublicAIProviderSettingsPayload)
def put_ai_provider_settings(payload: AIProviderSettingsPayload) -> PublicAIProviderSettingsPayload:
    current_settings = read_ai_provider_settings()
    api_key = payload.api_key.strip() or current_settings.api_key
    settings = save_ai_provider_settings(
        AIProviderSettings(
            base_url=payload.base_url.strip(),
            api_key=api_key,
            model=payload.model.strip(),
        )
    )
    public_settings = to_public_settings(settings)
    return PublicAIProviderSettingsPayload(
        base_url=public_settings.base_url,
        model=public_settings.model,
        has_api_key=public_settings.has_api_key,
        is_configured=public_settings.is_configured,
    )


@app.post("/settings/ai-provider/test", response_model=ProviderTestResultPayload)
def post_ai_provider_test() -> ProviderTestResultPayload:
    result = test_ai_provider_connection(read_ai_provider_settings())
    return ProviderTestResultPayload(status=result.status, message=result.message)
