from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .ai_provider import (
    AIProviderRequestError,
    analyze_resume_with_provider,
    generate_interview_review_with_provider,
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
    InterviewRecord,
    ResumeAnalysis,
    ResumeAnalysisValidationError,
    ResumeAnalysisRecord,
    delete_resume_analysis_record,
    initialize_resume_analysis_schema,
    list_resume_analysis_records,
    read_resume_analysis_record,
    read_interview,
    save_resume_analysis_record,
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
    InterviewerAction,
    list_in_progress_sessions,
    list_sessions_for_interview,
    read_session,
    resolve_interviewer_action,
    save_session,
    update_session,
)
from .interview_rounds import (
    decide_next_round_kind,
    get_round_template,
    plan_rounds,
)
from .interview_review import (
    ABILITY_DIMENSIONS,
    CompletedInterviewHistoryRecord,
    InterviewReview,
    InterviewReviewValidationError,
    delete_completed_interview_history_record,
    initialize_interview_review_schema,
    list_completed_interview_history,
    list_completed_target_roles,
    read_completed_interview_by_session,
    save_completed_interview,
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    initialize_interview_review_schema()
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


class ResumeAnalysisRecordListItemPayload(BaseModel):
    id: int
    target_role: str = Field(serialization_alias="targetRole")
    summary: str
    key_projects: list[str] = Field(serialization_alias="keyProjects")
    technical_stack: list[str] = Field(serialization_alias="technicalStack")
    follow_up_topics: list[str] = Field(serialization_alias="followUpTopics")
    created_at: str = Field(serialization_alias="createdAt")
    last_used_at: str = Field(serialization_alias="lastUsedAt")
    use_count: int = Field(serialization_alias="useCount")


class ResumeAnalysisRecordsPayload(BaseModel):
    records: list[ResumeAnalysisRecordListItemPayload]


class ResumeAnalysisRecordPayload(BaseModel):
    id: int
    resume_markdown: str = Field(serialization_alias="resumeMarkdown")
    target_role: str = Field(serialization_alias="targetRole")
    analysis: ResumeAnalysisPayload
    created_at: str = Field(serialization_alias="createdAt")
    last_used_at: str = Field(serialization_alias="lastUsedAt")
    use_count: int = Field(serialization_alias="useCount")


class ConfirmInterviewPayload(BaseModel):
    resume_markdown: str = Field(alias="resumeMarkdown")
    target_role: str = Field(default="", alias="targetRole")
    interview_mode: str = Field(default="single_round", alias="interviewMode")
    include_hr_round: bool = Field(default=False, alias="includeHrRound")
    source_resume_analysis_record_id: int | None = Field(
        default=None,
        alias="sourceResumeAnalysisRecordId",
    )
    analysis: ResumeAnalysis


class InterviewPayload(BaseModel):
    id: int
    resume_markdown: str = Field(serialization_alias="resumeMarkdown")
    target_role: str = Field(serialization_alias="targetRole")
    interview_mode: str = Field(serialization_alias="interviewMode")
    include_hr_round: bool = Field(serialization_alias="includeHrRound")
    source_resume_analysis_record_id: int | None = Field(
        default=None,
        serialization_alias="sourceResumeAnalysisRecordId",
    )
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


def _to_resume_analysis_record_list_item_payload(
    record: ResumeAnalysisRecord,
) -> ResumeAnalysisRecordListItemPayload:
    return ResumeAnalysisRecordListItemPayload(
        id=record.id,
        target_role=record.target_role,
        summary=record.analysis.background_summary,
        key_projects=record.analysis.key_projects,
        technical_stack=record.analysis.technical_stack,
        follow_up_topics=record.analysis.follow_up_topics,
        created_at=record.created_at,
        last_used_at=record.last_used_at,
        use_count=record.use_count,
    )


def _to_resume_analysis_record_payload(record: ResumeAnalysisRecord) -> ResumeAnalysisRecordPayload:
    return ResumeAnalysisRecordPayload(
        id=record.id,
        resume_markdown=record.resume_markdown,
        target_role=record.target_role,
        analysis=_to_resume_analysis_payload(record.analysis),
        created_at=record.created_at,
        last_used_at=record.last_used_at,
        use_count=record.use_count,
    )


def _to_interview_payload(interview: InterviewRecord) -> InterviewPayload:
    return InterviewPayload(
        id=interview.id,
        resume_markdown=interview.resume_markdown,
        target_role=interview.target_role,
        interview_mode=interview.interview_mode,
        include_hr_round=interview.include_hr_round,
        source_resume_analysis_record_id=interview.source_resume_analysis_record_id,
        analysis=_to_resume_analysis_payload(interview.analysis),
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

    save_resume_analysis_record(
        resume_markdown=resume_markdown,
        target_role=payload.target_role.strip(),
        analysis=analysis,
    )

    return _to_resume_analysis_payload(analysis)


@app.get("/resume-analysis-records", response_model=ResumeAnalysisRecordsPayload)
def get_resume_analysis_records() -> ResumeAnalysisRecordsPayload:
    return ResumeAnalysisRecordsPayload(
        records=[
            _to_resume_analysis_record_list_item_payload(record)
            for record in list_resume_analysis_records()
        ],
    )


@app.get("/resume-analysis-records/{record_id}", response_model=ResumeAnalysisRecordPayload)
def get_resume_analysis_record(record_id: int) -> ResumeAnalysisRecordPayload:
    record = read_resume_analysis_record(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="简历分析记录不存在")
    return _to_resume_analysis_record_payload(record)


@app.delete("/resume-analysis-records/{record_id}", status_code=204)
def delete_resume_analysis_record_endpoint(record_id: int) -> Response:
    deleted = delete_resume_analysis_record(record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="简历分析记录不存在")
    return Response(status_code=204)


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
        include_hr_round=payload.include_hr_round,
        source_resume_analysis_record_id=payload.source_resume_analysis_record_id,
        analysis=payload.analysis,
    )
    if interview is None:
        raise HTTPException(status_code=404, detail="来源简历分析记录不存在")
    return _to_interview_payload(interview)


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
    round_kind: str = Field(default="single_round", serialization_alias="roundKind")
    round_title: str = Field(default="", serialization_alias="roundTitle")
    round_focus: str = Field(default="", serialization_alias="roundFocus")
    transcript: list[TranscriptMessagePayload]
    review: "InterviewReviewPayload | None" = None
    review_error: str = Field(default="", serialization_alias="reviewError")


class ResumeableSessionPayload(BaseModel):
    """进行中面试列表项：携带面试摘要，供前端展示恢复入口。不含完整对话。"""

    id: int
    interview_id: int = Field(serialization_alias="interviewId")
    style: str
    status: str
    main_question_count: int = Field(serialization_alias="mainQuestionCount")
    current_main_question_follow_ups: int = Field(serialization_alias="currentMainQuestionFollowUps")
    main_question_limit: int = Field(serialization_alias="mainQuestionLimit")
    follow_up_limit: int = Field(serialization_alias="followUpLimit")
    round_kind: str = Field(default="single_round", serialization_alias="roundKind")
    round_title: str = Field(default="", serialization_alias="roundTitle")
    round_focus: str = Field(default="", serialization_alias="roundFocus")
    target_role: str = Field(serialization_alias="targetRole")
    interview_mode: str = Field(serialization_alias="interviewMode")


class RoundProgressPayload(BaseModel):
    """多轮面试某轮的进度条目：模板信息 + 当前状态 + 关联 session。"""

    kind: str
    title: str
    focus: str
    status: str
    session_id: int | None = Field(default=None, serialization_alias="sessionId")


class StartSessionPayload(BaseModel):
    style: str = "study"


class AnswerSessionPayload(BaseModel):
    answer: str


class AbilityScorePayload(BaseModel):
    dimension: str
    score: int
    rationale: str


class InterviewReviewPayload(BaseModel):
    overall_evaluation: str = Field(serialization_alias="overallEvaluation")
    highlights: list[str]
    main_issues: list[str] = Field(serialization_alias="mainIssues")
    question_reviews: list[str] = Field(serialization_alias="questionReviews")
    improved_expression_examples: list[str] = Field(serialization_alias="improvedExpressionExamples")
    sample_answers: list[str] = Field(serialization_alias="sampleAnswers")
    knowledge_references: list[str] = Field(serialization_alias="knowledgeReferences")
    learning_framework: list[str] = Field(serialization_alias="learningFramework")
    next_practice_suggestions: list[str] = Field(serialization_alias="nextPracticeSuggestions")
    ability_scores: list[AbilityScorePayload] = Field(serialization_alias="abilityScores")


class HistoryRecordPayload(BaseModel):
    id: int
    interview_id: int = Field(serialization_alias="interviewId")
    session_id: int = Field(serialization_alias="sessionId")
    target_role: str = Field(serialization_alias="targetRole")
    interview_mode: str = Field(serialization_alias="interviewMode")
    style: str
    round_kind: str = Field(serialization_alias="roundKind")
    round_title: str = Field(serialization_alias="roundTitle")
    completed_at: str = Field(serialization_alias="completedAt")
    review: InterviewReviewPayload
    transcript: list[TranscriptMessagePayload]


class TrendPointPayload(BaseModel):
    history_record_id: int = Field(serialization_alias="historyRecordId")
    completed_at: str = Field(serialization_alias="completedAt")
    score: int


class TrendDimensionPayload(BaseModel):
    dimension: str
    average_score: float = Field(serialization_alias="averageScore")
    points: list[TrendPointPayload]


class HistoryPayload(BaseModel):
    records: list[HistoryRecordPayload]
    target_roles: list[str] = Field(serialization_alias="targetRoles")
    trends: list[TrendDimensionPayload]


def _to_transcript_payload(message: TranscriptMessage) -> TranscriptMessagePayload:
    return TranscriptMessagePayload(
        role=message.role,
        content=message.content,
        kind=message.kind,
        main_question_index=message.main_question_index,
    )


def _round_fields(round_kind: str) -> dict[str, str]:
    template = get_round_template(round_kind)
    if template is None:
        return {"round_kind": round_kind, "round_title": "", "round_focus": ""}
    return {
        "round_kind": template.kind,
        "round_title": template.title,
        "round_focus": template.focus,
    }


def _to_session_payload(session: InterviewSession) -> InterviewSessionPayload:
    payload = InterviewSessionPayload(
        id=session.id,
        interview_id=session.interview_id,
        style=session.style,
        status=session.status,
        main_question_count=session.main_question_count,
        current_main_question_follow_ups=session.current_main_question_follow_ups,
        main_question_limit=DEFAULT_MAIN_QUESTIONS,
        follow_up_limit=DEFAULT_MAX_FOLLOW_UPS,
        transcript=[_to_transcript_payload(message) for message in session.transcript],
        **_round_fields(session.round_kind),
    )
    completed_record = read_completed_interview_by_session(session.id)
    if completed_record is not None:
        payload.review = _to_review_payload(completed_record.review)
    return payload


def _to_review_payload(review: InterviewReview) -> InterviewReviewPayload:
    return InterviewReviewPayload(
        overall_evaluation=review.overall_evaluation,
        highlights=review.highlights,
        main_issues=review.main_issues,
        question_reviews=review.question_reviews,
        improved_expression_examples=review.improved_expression_examples,
        sample_answers=review.sample_answers,
        knowledge_references=review.knowledge_references,
        learning_framework=review.learning_framework,
        next_practice_suggestions=review.next_practice_suggestions,
        ability_scores=[
            AbilityScorePayload(
                dimension=score.dimension,
                score=score.score,
                rationale=score.rationale,
            )
            for score in review.ability_scores
        ],
    )


def _to_history_record_payload(record: CompletedInterviewHistoryRecord) -> HistoryRecordPayload:
    round_fields = _round_fields(record.round_kind)
    return HistoryRecordPayload(
        id=record.id,
        interview_id=record.interview_id,
        session_id=record.session_id,
        target_role=record.target_role,
        interview_mode=record.interview_mode,
        style=record.style,
        round_kind=round_fields["round_kind"],
        round_title=round_fields["round_title"],
        completed_at=record.completed_at,
        review=_to_review_payload(record.review),
        transcript=[_to_transcript_payload(message) for message in record.transcript],
    )


def _build_trends(records: list[CompletedInterviewHistoryRecord]) -> list[TrendDimensionPayload]:
    chronological_records = list(reversed(records))
    trends: list[TrendDimensionPayload] = []
    for dimension in ABILITY_DIMENSIONS:
        points: list[TrendPointPayload] = []
        for record in chronological_records:
            score = next(
                (
                    ability_score.score
                    for ability_score in record.review.ability_scores
                    if ability_score.dimension == dimension
                ),
                None,
            )
            if score is None:
                continue
            points.append(
                TrendPointPayload(
                    history_record_id=record.id,
                    completed_at=record.completed_at,
                    score=score,
                )
            )

        average = sum(point.score for point in points) / len(points) if points else 0
        trends.append(
            TrendDimensionPayload(
                dimension=dimension,
                average_score=round(average, 2),
                points=points,
            )
        )

    return trends


def _require_active_provider():
    active_provider = read_ai_provider_store().active_provider
    if active_provider is None:
        raise HTTPException(status_code=400, detail="请先新增并选择一个模型供应商")
    return active_provider


def _resolve_round_kind(interview: InterviewRecord) -> str:
    """决定本次新建 session 所属轮次。

    单轮面试固定 single_round（维持原行为）。多轮面试按默认轮次模板顺序推进：
    存在尚未结束的轮次（in_progress / awaiting_review）时拒绝新建，避免同一面试出现多个进行中轮次；
    全部轮次已结束/放弃时提示所有轮次已完成；否则启动下一个待进行轮次。
    """

    if interview.interview_mode != "multi_round":
        return "single_round"

    existing = list_sessions_for_interview(interview.id)
    if any(session.status in ("in_progress", "awaiting_review") for session in existing):
        raise HTTPException(status_code=409, detail="当前轮次尚未结束，请先完成或放弃后再进入下一轮")

    planned = plan_rounds(interview.interview_mode, interview.include_hr_round)
    existing_summary = [
        {"round_kind": session.round_kind, "status": session.status} for session in existing
    ]
    next_kind = decide_next_round_kind(planned, existing_summary)
    if next_kind is None:
        raise HTTPException(status_code=409, detail="所有轮次已完成")

    return next_kind


def _ended_session_from(session: InterviewSession) -> InterviewSession:
    return InterviewSession(
        id=session.id,
        interview_id=session.interview_id,
        style=session.style,
        status="ended",
        transcript=list(session.transcript),
        main_question_count=session.main_question_count,
        current_main_question_follow_ups=session.current_main_question_follow_ups,
        round_kind=session.round_kind,
    )


def _awaiting_review_session_from(session: InterviewSession) -> InterviewSession:
    return InterviewSession(
        id=session.id,
        interview_id=session.interview_id,
        style=session.style,
        status="awaiting_review",
        transcript=list(session.transcript),
        main_question_count=session.main_question_count,
        current_main_question_follow_ups=session.current_main_question_follow_ups,
        round_kind=session.round_kind,
    )


def _generate_review_for_session(
    *,
    session: InterviewSession,
    interview: InterviewRecord,
    active_provider: AIProviderSettings,
) -> InterviewSessionPayload:
    payload = _to_session_payload(session)
    try:
        review = generate_interview_review_with_provider(
            active_provider,
            session=session,
            analysis=interview.analysis,
            target_role=interview.target_role,
        )
    except (InterviewReviewValidationError, AIProviderRequestError, ValueError) as error:
        payload.review_error = str(error)
        return payload

    ended_session = _ended_session_from(session)
    update_session(ended_session)
    save_completed_interview(ended_session, review)
    payload = _to_session_payload(ended_session)
    payload.review = _to_review_payload(review)
    return payload


@app.post("/interviews/{interview_id}/sessions", response_model=InterviewSessionPayload)
def post_interview_session(interview_id: int, payload: StartSessionPayload | None = None) -> InterviewSessionPayload:
    interview = read_interview(interview_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="面试记录不存在")

    style = (payload.style if payload else "study") or "study"
    if style.strip() not in ("study", "pressure"):
        raise HTTPException(status_code=400, detail="面试风格只能是 study 或 pressure")

    active_provider = _require_active_provider()

    round_kind = _resolve_round_kind(interview)

    draft_session = InterviewSession(
        id=0,
        interview_id=interview_id,
        style=style.strip(),
        status="in_progress",
        transcript=[],
        main_question_count=0,
        current_main_question_follow_ups=0,
        round_kind=round_kind,
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
        round_kind=draft_session.round_kind,
    )
    return _to_session_payload(save_session(started_session))


@app.get("/interview-sessions/in-progress", response_model=list[ResumeableSessionPayload])
def get_in_progress_sessions() -> list[ResumeableSessionPayload]:
    payloads: list[ResumeableSessionPayload] = []
    for session in list_in_progress_sessions():
        interview = read_interview(session.interview_id)
        if interview is None:
            continue
        payloads.append(
            ResumeableSessionPayload(
                id=session.id,
                interview_id=session.interview_id,
                style=session.style,
                status=session.status,
                main_question_count=session.main_question_count,
                current_main_question_follow_ups=session.current_main_question_follow_ups,
                main_question_limit=DEFAULT_MAIN_QUESTIONS,
                follow_up_limit=DEFAULT_MAX_FOLLOW_UPS,
                target_role=interview.target_role,
                interview_mode=interview.interview_mode,
                **_round_fields(session.round_kind),
            )
        )
    return payloads


@app.get("/history", response_model=HistoryPayload)
def get_history(target_role: str = "") -> HistoryPayload:
    records = list_completed_interview_history(target_role=target_role)
    return HistoryPayload(
        records=[_to_history_record_payload(record) for record in records],
        target_roles=list_completed_target_roles(),
        trends=_build_trends(records),
    )


@app.delete("/history/{history_record_id}", status_code=204)
def delete_history_record(history_record_id: int) -> Response:
    deleted = delete_completed_interview_history_record(history_record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="已完成面试记录不存在")
    return Response(status_code=204)


@app.get("/interview-sessions/{session_id}", response_model=InterviewSessionPayload)
def get_interview_session(session_id: int) -> InterviewSessionPayload:
    session = read_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="进行中面试不存在")
    if session.status == "ended" and read_completed_interview_by_session(session_id) is None:
        raise HTTPException(status_code=404, detail="已完成面试记录不存在")
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
        raise HTTPException(status_code=400, detail="该面试已结束或等待复盘确认，无法继续作答")

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
        round_kind=session.round_kind,
    )
    # 每次回答后立即保存，保证刷新或重新打开后可继续。
    update_session(session_with_answer)

    if (
        session_with_answer.main_question_count >= DEFAULT_MAIN_QUESTIONS
        and session_with_answer.current_main_question_follow_ups >= DEFAULT_MAX_FOLLOW_UPS
    ):
        message, main_question_count, follow_ups = apply_interviewer_action(
            session_with_answer,
            InterviewerAction(kind="end_interview", message="本场面试的信息已经足够，我们进入复盘。"),
        )
        ending_session = InterviewSession(
            id=session_with_answer.id,
            interview_id=session_with_answer.interview_id,
            style=session_with_answer.style,
            status="in_progress",
            transcript=[*session_with_answer.transcript, message],
            main_question_count=main_question_count,
            current_main_question_follow_ups=follow_ups,
            round_kind=session_with_answer.round_kind,
        )
        awaiting_review_session = _awaiting_review_session_from(ending_session)
        update_session(awaiting_review_session)
        return _to_session_payload(awaiting_review_session)

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

    if resolved_action.kind == "end_interview":
        ending_session = InterviewSession(
            id=session_with_answer.id,
            interview_id=session_with_answer.interview_id,
            style=session_with_answer.style,
            status="in_progress",
            transcript=[*session_with_answer.transcript, message],
            main_question_count=main_question_count,
            current_main_question_follow_ups=follow_ups,
            round_kind=session_with_answer.round_kind,
        )
        awaiting_review_session = _awaiting_review_session_from(ending_session)
        update_session(awaiting_review_session)
        return _to_session_payload(awaiting_review_session)

    advanced_session = InterviewSession(
        id=session_with_answer.id,
        interview_id=session_with_answer.interview_id,
        style=session_with_answer.style,
        status="in_progress",
        transcript=[*session_with_answer.transcript, message],
        main_question_count=main_question_count,
        current_main_question_follow_ups=follow_ups,
        round_kind=session_with_answer.round_kind,
    )
    update_session(advanced_session)
    return _to_session_payload(advanced_session)


@app.post("/interview-sessions/{session_id}/end", response_model=InterviewSessionPayload)
def post_interview_session_end(session_id: int) -> InterviewSessionPayload:
    session = read_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="进行中面试不存在")
    if session.status != "in_progress":
        raise HTTPException(status_code=400, detail="该面试已结束或等待复盘确认")

    awaiting_review_session = _awaiting_review_session_from(session)
    update_session(awaiting_review_session)
    return _to_session_payload(awaiting_review_session)


@app.post("/interview-sessions/{session_id}/abandon", response_model=InterviewSessionPayload)
def post_interview_session_abandon(session_id: int) -> InterviewSessionPayload:
    session = read_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="进行中面试不存在")
    if session.status != "in_progress":
        raise HTTPException(status_code=400, detail="只有进行中的面试可以放弃")

    abandoned_session = InterviewSession(
        id=session.id,
        interview_id=session.interview_id,
        style=session.style,
        status="abandoned",
        transcript=list(session.transcript),
        main_question_count=session.main_question_count,
        current_main_question_follow_ups=session.current_main_question_follow_ups,
        round_kind=session.round_kind,
    )
    update_session(abandoned_session)
    return _to_session_payload(abandoned_session)


@app.post("/interview-sessions/{session_id}/review", response_model=InterviewSessionPayload)
def post_interview_session_review(session_id: int) -> InterviewSessionPayload:
    session = read_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="进行中面试不存在")
    if session.status == "ended":
        return _to_session_payload(session)
    if session.status != "awaiting_review":
        raise HTTPException(status_code=400, detail="请先结束面试，再生成复盘")

    interview = read_interview(session.interview_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="面试记录不存在")
    active_provider = _require_active_provider()

    return _generate_review_for_session(
        session=session,
        interview=interview,
        active_provider=active_provider,
    )


def _round_status_from_session_status(status: str) -> str:
    if status == "ended":
        return "completed"
    return status


@app.get(
    "/interviews/{interview_id}/rounds",
    response_model=list[RoundProgressPayload],
)
def get_interview_rounds(interview_id: int) -> list[RoundProgressPayload]:
    interview = read_interview(interview_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="面试记录不存在")

    planned = plan_rounds(interview.interview_mode, interview.include_hr_round)
    if not planned:
        return []

    sessions = list_sessions_for_interview(interview_id)
    session_by_kind = {session.round_kind: session for session in sessions}

    payloads: list[RoundProgressPayload] = []
    for template in planned:
        session = session_by_kind.get(template.kind)
        payloads.append(
            RoundProgressPayload(
                kind=template.kind,
                title=template.title,
                focus=template.focus,
                status="pending" if session is None else _round_status_from_session_status(session.status),
                session_id=session.id if session is not None else None,
            )
        )
    return payloads


@app.get("/interviews/{interview_id}", response_model=InterviewPayload)
def get_interview(interview_id: int) -> InterviewPayload:
    interview = read_interview(interview_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="面试记录不存在")

    return _to_interview_payload(interview)
