from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .ai_provider import (
    AIProviderRequestError,
    analyze_resume_with_provider,
    generate_next_interviewer_action_with_provider,
    test_ai_provider_connection,
)
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
from .interview_session import (
    DEFAULT_MAIN_QUESTIONS,
    DEFAULT_MAX_FOLLOW_UPS,
    InterviewerActionValidationError,
    InterviewSession,
    TranscriptMessage,
    apply_interviewer_action,
    append_candidate_answer,
    initialize_interview_session_schema,
    read_session,
    resolve_interviewer_action,
    save_session,
    update_session,
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    initialize_interview_session_schema()
    yield


app = FastAPI(
    title="Mock Interview API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
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
    interview_mode: str = Field(default="single_round", alias="interviewMode")
    analysis: ResumeAnalysis


class InterviewPayload(BaseModel):
    id: int
    resume_markdown: str = Field(serialization_alias="resumeMarkdown")
    target_role: str = Field(serialization_alias="targetRole")
    interview_mode: str = Field(serialization_alias="interviewMode")
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
    except AIProviderRequestError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return _to_resume_analysis_payload(analysis)


@app.post("/interviews", response_model=InterviewPayload)
def post_interview(payload: ConfirmInterviewPayload) -> InterviewPayload:
    resume_markdown = payload.resume_markdown.strip()
    if not resume_markdown:
        raise HTTPException(status_code=400, detail="Markdown 简历不能为空")
    interview_mode = payload.interview_mode.strip() or "single_round"
    if interview_mode not in ("single_round", "multi_round"):
        raise HTTPException(status_code=400, detail="面试模式只能是 single_round 或 multi_round")

    interview = save_interview(
        resume_markdown=resume_markdown,
        target_role=payload.target_role.strip(),
        interview_mode=interview_mode,
        analysis=payload.analysis,
    )
    return InterviewPayload(
        id=interview.id,
        resume_markdown=interview.resume_markdown,
        target_role=interview.target_role,
        interview_mode=interview.interview_mode,
        analysis=_to_resume_analysis_payload(interview.analysis),
    )


class TranscriptMessagePayload(BaseModel):
    role: str
    content: str
    kind: str = ""
    main_question_index: int = Field(default=0, alias="mainQuestionIndex")


class InterviewSessionPayload(BaseModel):
    id: int
    interview_id: int = Field(serialization_alias="interviewId")
    style: str
    status: str
    main_question_count: int = Field(serialization_alias="mainQuestionCount")
    current_main_question_follow_ups: int = Field(serialization_alias="currentMainQuestionFollowUps")
    main_question_limit: int = Field(serialization_alias="mainQuestionLimit")
    follow_up_limit: int = Field(serialization_alias="followUpLimit")
    transcript: list[TranscriptMessagePayload]


class StartSessionPayload(BaseModel):
    style: str = "study"


class AnswerSessionPayload(BaseModel):
    answer: str


def _to_transcript_payload(message: TranscriptMessage) -> TranscriptMessagePayload:
    return TranscriptMessagePayload(
        role=message.role,
        content=message.content,
        kind=message.kind,
        main_question_index=message.main_question_index,
    )


def _to_session_payload(session: InterviewSession) -> InterviewSessionPayload:
    return InterviewSessionPayload(
        id=session.id,
        interview_id=session.interview_id,
        style=session.style,
        status=session.status,
        main_question_count=session.main_question_count,
        current_main_question_follow_ups=session.current_main_question_follow_ups,
        main_question_limit=DEFAULT_MAIN_QUESTIONS,
        follow_up_limit=DEFAULT_MAX_FOLLOW_UPS,
        transcript=[_to_transcript_payload(message) for message in session.transcript],
    )


def _require_active_provider():
    active_provider = read_ai_provider_store().active_provider
    if active_provider is None:
        raise HTTPException(status_code=400, detail="请先新增并选择一个模型供应商")
    return active_provider


@app.post("/interviews/{interview_id}/sessions", response_model=InterviewSessionPayload)
def post_interview_session(interview_id: int, payload: StartSessionPayload | None = None) -> InterviewSessionPayload:
    interview = read_interview(interview_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="面试记录不存在")

    style = (payload.style if payload else "study") or "study"
    if style.strip() not in ("study", "pressure"):
        raise HTTPException(status_code=400, detail="面试风格只能是 study 或 pressure")

    active_provider = _require_active_provider()

    draft_session = InterviewSession(
        id=0,
        interview_id=interview_id,
        style=style.strip(),
        status="in_progress",
        transcript=[],
        main_question_count=0,
        current_main_question_follow_ups=0,
    )
    try:
        action = generate_next_interviewer_action_with_provider(
            active_provider,
            session=draft_session,
            analysis=interview.analysis,
            target_role=interview.target_role,
            starting=True,
        )
        resolved_action = resolve_interviewer_action(action, draft_session, starting=True)
        message, main_question_count, follow_ups = apply_interviewer_action(
            draft_session, resolved_action, starting=True
        )
    except InterviewerActionValidationError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except AIProviderRequestError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    started_session = InterviewSession(
        id=draft_session.id,
        interview_id=draft_session.interview_id,
        style=draft_session.style,
        status="in_progress",
        transcript=[message],
        main_question_count=main_question_count,
        current_main_question_follow_ups=follow_ups,
    )
    return _to_session_payload(save_session(started_session))


@app.get("/interview-sessions/{session_id}", response_model=InterviewSessionPayload)
def get_interview_session(session_id: int) -> InterviewSessionPayload:
    session = read_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="进行中面试不存在")
    return _to_session_payload(session)


@app.post("/interview-sessions/{session_id}/answers", response_model=InterviewSessionPayload)
def post_interview_session_answer(
    session_id: int,
    payload: AnswerSessionPayload,
) -> InterviewSessionPayload:
    session = read_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="进行中面试不存在")
    if session.status != "in_progress":
        raise HTTPException(status_code=400, detail="该面试已结束，无法继续作答")

    answer = payload.answer.strip()
    if not answer:
        raise HTTPException(status_code=400, detail="回答内容不能为空")

    interview = read_interview(session.interview_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="面试记录不存在")

    active_provider = _require_active_provider()

    candidate_message = append_candidate_answer(session, answer)
    session_with_answer = InterviewSession(
        id=session.id,
        interview_id=session.interview_id,
        style=session.style,
        status=session.status,
        transcript=[*session.transcript, candidate_message],
        main_question_count=session.main_question_count,
        current_main_question_follow_ups=session.current_main_question_follow_ups,
    )
    # 每次回答后立即保存，保证刷新或重新打开后可继续。
    update_session(session_with_answer)

    try:
        action = generate_next_interviewer_action_with_provider(
            active_provider,
            session=session_with_answer,
            analysis=interview.analysis,
            target_role=interview.target_role,
            starting=False,
        )
        resolved_action = resolve_interviewer_action(action, session_with_answer, starting=False)
        message, main_question_count, follow_ups = apply_interviewer_action(
            session_with_answer, resolved_action
        )
    except InterviewerActionValidationError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except AIProviderRequestError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    advanced_session = InterviewSession(
        id=session_with_answer.id,
        interview_id=session_with_answer.interview_id,
        style=session_with_answer.style,
        status="in_progress",
        transcript=[*session_with_answer.transcript, message],
        main_question_count=main_question_count,
        current_main_question_follow_ups=follow_ups,
    )
    update_session(advanced_session)
    return _to_session_payload(advanced_session)


@app.post("/interview-sessions/{session_id}/end", response_model=InterviewSessionPayload)
def post_interview_session_end(session_id: int) -> InterviewSessionPayload:
    session = read_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="进行中面试不存在")
    if session.status != "in_progress":
        raise HTTPException(status_code=400, detail="该面试已结束")

    ended_session = InterviewSession(
        id=session.id,
        interview_id=session.interview_id,
        style=session.style,
        status="ended",
        transcript=list(session.transcript),
        main_question_count=session.main_question_count,
        current_main_question_follow_ups=session.current_main_question_follow_ups,
    )
    update_session(ended_session)
    return _to_session_payload(ended_session)


@app.get("/interviews/{interview_id}", response_model=InterviewPayload)
def get_interview(interview_id: int) -> InterviewPayload:
    interview = read_interview(interview_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="面试记录不存在")

    return InterviewPayload(
        id=interview.id,
        resume_markdown=interview.resume_markdown,
        target_role=interview.target_role,
        interview_mode=interview.interview_mode,
        analysis=_to_resume_analysis_payload(interview.analysis),
    )
