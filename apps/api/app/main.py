from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .ai_provider import analyze_resume_with_provider, test_ai_provider_connection
from .ai_settings import (
    AIProviderSettingsStore,
    AIProviderSettings,
    merge_with_existing_api_keys,
    read_ai_provider_store,
    save_ai_provider_store,
    to_public_store,
)
from .database import database_health, initialize_database
from .resume_analysis import (
    ResumeAnalysis,
    ResumeAnalysisValidationError,
    initialize_resume_analysis_schema,
    read_interview,
    save_interview,
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    initialize_database()
    initialize_resume_analysis_schema()
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


class ResumeAnalysisPayload(BaseModel):
    background_summary: str = Field(serialization_alias="backgroundSummary")
    key_projects: list[str] = Field(serialization_alias="keyProjects")
    technical_stack: list[str] = Field(serialization_alias="technicalStack")
    follow_up_topics: list[str] = Field(serialization_alias="followUpTopics")
    risk_points: list[str] = Field(serialization_alias="riskPoints")
    unclear_points: list[str] = Field(serialization_alias="unclearPoints")
    target_role_notes: str = Field(serialization_alias="targetRoleNotes")
    focus_topics: list[str] = Field(serialization_alias="focusTopics")
    low_priority_follow_up_topics: list[str] = Field(serialization_alias="lowPriorityFollowUpTopics")


class GenerateResumeAnalysisPayload(BaseModel):
    resume_markdown: str = Field(alias="resumeMarkdown")
    target_role: str = Field(default="", alias="targetRole")


class ConfirmInterviewPayload(BaseModel):
    resume_markdown: str = Field(alias="resumeMarkdown")
    target_role: str = Field(default="", alias="targetRole")
    analysis: ResumeAnalysis


class InterviewPayload(BaseModel):
    id: int
    resume_markdown: str = Field(serialization_alias="resumeMarkdown")
    target_role: str = Field(serialization_alias="targetRole")
    analysis: ResumeAnalysisPayload


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


def _to_resume_analysis_payload(analysis: ResumeAnalysis) -> ResumeAnalysisPayload:
    return ResumeAnalysisPayload(
        background_summary=analysis.background_summary,
        key_projects=analysis.key_projects,
        technical_stack=analysis.technical_stack,
        follow_up_topics=analysis.follow_up_topics,
        risk_points=analysis.risk_points,
        unclear_points=analysis.unclear_points,
        target_role_notes=analysis.target_role_notes,
        focus_topics=analysis.focus_topics,
        low_priority_follow_up_topics=analysis.low_priority_follow_up_topics,
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


@app.post("/resume-analyses/generate", response_model=ResumeAnalysisPayload)
def post_resume_analysis(payload: GenerateResumeAnalysisPayload) -> ResumeAnalysisPayload:
    resume_markdown = payload.resume_markdown.strip()
    if not resume_markdown:
        raise HTTPException(status_code=400, detail="Markdown 简历不能为空")

    active_provider = read_ai_provider_store().active_provider
    if active_provider is None:
        raise HTTPException(status_code=400, detail="请先新增并选择一个模型供应商")

    try:
        analysis = analyze_resume_with_provider(
            active_provider,
            resume_markdown=resume_markdown,
            target_role=payload.target_role.strip(),
        )
    except ResumeAnalysisValidationError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return _to_resume_analysis_payload(analysis)


@app.post("/interviews", response_model=InterviewPayload)
def post_interview(payload: ConfirmInterviewPayload) -> InterviewPayload:
    resume_markdown = payload.resume_markdown.strip()
    if not resume_markdown:
        raise HTTPException(status_code=400, detail="Markdown 简历不能为空")

    interview = save_interview(
        resume_markdown=resume_markdown,
        target_role=payload.target_role.strip(),
        analysis=payload.analysis,
    )
    return InterviewPayload(
        id=interview.id,
        resume_markdown=interview.resume_markdown,
        target_role=interview.target_role,
        analysis=_to_resume_analysis_payload(interview.analysis),
    )


@app.get("/interviews/{interview_id}", response_model=InterviewPayload)
def get_interview(interview_id: int) -> InterviewPayload:
    interview = read_interview(interview_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="面试记录不存在")

    return InterviewPayload(
        id=interview.id,
        resume_markdown=interview.resume_markdown,
        target_role=interview.target_role,
        analysis=_to_resume_analysis_payload(interview.analysis),
    )
