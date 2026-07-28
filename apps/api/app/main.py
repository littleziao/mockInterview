from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Iterator

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .ai_provider import (
    AIProviderRequestError,
    analyze_resume_with_provider,
    generate_interview_review_with_provider,
    stream_next_interviewer_action_with_provider,
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
from .database import database_health, get_database_settings, initialize_database
from .logging_config import configure_logging
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
    validate_target_job_description,
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
    delete_completed_interview_history_record,
    initialize_interview_review_schema,
    list_completed_interview_history,
    list_completed_target_roles,
    read_completed_interview_by_session,
    save_completed_interview,
    update_completed_interview_review,
)


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    initialize_interview_review_schema()
    database_status = database_health()
    logger.info(
        "Mock Interview API 启动 database=%s migration=%s",
        get_database_settings().path,
        database_status.get("migration", "unknown"),
    )
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


@app.exception_handler(HTTPException)
async def log_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
    """统一记录 HTTP 错误日志：5xx 记 ERROR，4xx 记 WARNING。

    行为与 FastAPI 默认的 HTTPException 响应完全一致，仅额外补一条带 detail 的日志，
    便于本地排错（access log 只有状态码，看不到原因）。
    """
    level = logging.ERROR if exc.status_code >= 500 else logging.WARNING
    logger.log(
        level,
        "HTTP %s %s -> %s: %s",
        request.method,
        request.url.path,
        exc.status_code,
        exc.detail,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=getattr(exc, "headers", None),
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


class JobDescriptionAnalysisPayload(BaseModel):
    core_responsibilities: list[str] = Field(serialization_alias="coreResponsibilities")
    required_requirements: list[str] = Field(serialization_alias="requiredRequirements")
    bonus_points: list[str] = Field(serialization_alias="bonusPoints")
    likely_probes: list[str] = Field(serialization_alias="likelyProbes")
    matching_evidence: list[str] = Field(serialization_alias="matchingEvidence")
    role_gaps: list[str] = Field(serialization_alias="roleGaps")


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
    inferred_target_role: str | None = Field(default=None, serialization_alias="inferredTargetRole")
    job_description_analysis: JobDescriptionAnalysisPayload | None = Field(
        default=None, serialization_alias="jobDescriptionAnalysis"
    )


class GenerateResumeAnalysisPayload(BaseModel):
    resume_markdown: str = Field(alias="resumeMarkdown")
    target_role: str = Field(default="", alias="targetRole")
    target_job_description: str = Field(default="", alias="targetJobDescription")


class ResumeAnalysisRecordListItemPayload(BaseModel):
    id: int
    target_role: str = Field(serialization_alias="targetRole")
    has_target_job_description: bool = Field(serialization_alias="hasTargetJobDescription")
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
    target_job_description: str = Field(serialization_alias="targetJobDescription")
    analysis: ResumeAnalysisPayload
    created_at: str = Field(serialization_alias="createdAt")
    last_used_at: str = Field(serialization_alias="lastUsedAt")
    use_count: int = Field(serialization_alias="useCount")


class ConfirmInterviewPayload(BaseModel):
    resume_markdown: str = Field(alias="resumeMarkdown")
    target_role: str = Field(default="", alias="targetRole")
    target_job_description: str = Field(default="", alias="targetJobDescription")
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
    target_job_description: str = Field(serialization_alias="targetJobDescription")
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
    job_description_analysis = (
        JobDescriptionAnalysisPayload(
            core_responsibilities=analysis.job_description_analysis.core_responsibilities,
            required_requirements=analysis.job_description_analysis.required_requirements,
            bonus_points=analysis.job_description_analysis.bonus_points,
            likely_probes=analysis.job_description_analysis.likely_probes,
            matching_evidence=analysis.job_description_analysis.matching_evidence,
            role_gaps=analysis.job_description_analysis.role_gaps,
        )
        if analysis.job_description_analysis is not None
        else None
    )
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
        inferred_target_role=analysis.inferred_target_role,
        job_description_analysis=job_description_analysis,
    )


def _to_resume_analysis_record_list_item_payload(
    record: ResumeAnalysisRecord,
) -> ResumeAnalysisRecordListItemPayload:
    return ResumeAnalysisRecordListItemPayload(
        id=record.id,
        target_role=record.target_role,
        has_target_job_description=bool(record.target_job_description.strip()),
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
        target_job_description=record.target_job_description,
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
        target_job_description=interview.target_job_description,
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
    try:
        target_job_description = validate_target_job_description(payload.target_job_description)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    active_provider = read_ai_provider_store().active_provider
    if active_provider is None:
        raise HTTPException(status_code=400, detail="请先新增并选择一个模型供应商")

    try:
        analysis = analyze_resume_with_provider(
            active_provider,
            resume_markdown=resume_markdown,
            target_role=payload.target_role.strip(),
            target_job_description=target_job_description,
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
        target_job_description=target_job_description,
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
    try:
        target_job_description = validate_target_job_description(payload.target_job_description)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    interview_mode = payload.interview_mode.strip() or "single_round"
    if interview_mode not in ("single_round", "multi_round"):
        raise HTTPException(status_code=400, detail="面试模式只能是 single_round 或 multi_round")

    interview = save_interview(
        resume_markdown=resume_markdown,
        target_role=payload.target_role.strip(),
        target_job_description=target_job_description,
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
    review_status: str = Field(default="ready", serialization_alias="reviewStatus")
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


class JDMatchAnalysisPayload(BaseModel):
    matching_evidence: list[str] = Field(serialization_alias="matchingEvidence")
    role_gaps: list[str] = Field(serialization_alias="roleGaps")
    project_expression_improvements: list[str] = Field(serialization_alias="projectExpressionImprovements")
    next_practice_jd_priorities: list[str] = Field(serialization_alias="nextPracticeJdPriorities")


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
    jd_match_analysis: JDMatchAnalysisPayload | None = Field(
        default=None,
        serialization_alias="jdMatchAnalysis",
    )


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
        payload.review_status = completed_record.review_status
        payload.review_error = completed_record.review_error
        if completed_record.review is not None:
            payload.review = _to_review_payload(completed_record.review)
    return payload


def _to_review_payload(review: InterviewReview) -> InterviewReviewPayload:
    jd_match_analysis = (
        JDMatchAnalysisPayload(
            matching_evidence=review.jd_match_analysis.matching_evidence,
            role_gaps=review.jd_match_analysis.role_gaps,
            project_expression_improvements=review.jd_match_analysis.project_expression_improvements,
            next_practice_jd_priorities=review.jd_match_analysis.next_practice_jd_priorities,
        )
        if review.jd_match_analysis is not None
        else None
    )
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
        jd_match_analysis=jd_match_analysis,
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


def _finalize_awaiting_review(session: InterviewSession) -> InterviewSession:
    """结束面试：转 awaiting_review 并立即落库 completed_interview(pending)，记录永不丢。"""
    awaiting_review_session = _awaiting_review_session_from(session)
    update_session(awaiting_review_session)
    save_completed_interview(awaiting_review_session, status="pending")
    return awaiting_review_session


def _sse_frame(event: str, data: object) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _session_payload_dict(session: InterviewSession) -> dict:
    return _to_session_payload(session).model_dump(by_alias=True)


def _assemble_session(
    session: InterviewSession,
    message: TranscriptMessage,
    main_question_count: int,
    follow_ups: int,
) -> InterviewSession:
    return InterviewSession(
        id=session.id,
        interview_id=session.interview_id,
        style=session.style,
        status=session.status,
        transcript=[*session.transcript, message],
        main_question_count=main_question_count,
        current_main_question_follow_ups=follow_ups,
        round_kind=session.round_kind,
    )


def _would_downgrade(
    session: InterviewSession,
    observed_kind: str,
    *,
    starting: bool,
) -> bool:
    """AI 返回的 kind 是否会被 resolve_interviewer_action 降级为别的动作（fallback 文案）。"""
    try:
        probe = resolve_interviewer_action(
            InterviewerAction(kind=observed_kind, message="probe"),
            session,
            starting=starting,
        )
    except InterviewerActionValidationError:
        return False
    return probe.kind != observed_kind or probe.message != "probe"


def _stream_interviewer_action(
    *,
    provider_settings: AIProviderSettings,
    session: InterviewSession,
    analysis: ResumeAnalysis,
    target_role: str,
    starting: bool,
) -> Iterator[str]:
    """消费 provider 流式 chunk，转 SSE 帧；结束时落库并发 done。

    若 AI 的 kind 会被 resolve 降级（caps 边界的 fallback 文案），流期间抑制 delta，
    在 final 阶段用 reset 帧一次性写出最终文案，避免「逐字显示后又被替换」的闪烁。
    """
    suppressed = False
    try:
        for chunk in stream_next_interviewer_action_with_provider(
            provider_settings,
            session=session,
            analysis=analysis,
            target_role=target_role,
            starting=starting,
        ):
            if chunk.kind == "meta":
                if (
                    not starting
                    and chunk.action_kind
                    and _would_downgrade(session, chunk.action_kind, starting=starting)
                ):
                    suppressed = True
            elif chunk.kind == "delta":
                if not suppressed:
                    yield _sse_frame("delta", {"text": chunk.text})
            elif chunk.kind == "final":
                resolved = resolve_interviewer_action(chunk.action, session, starting=starting)
                message, main_question_count, follow_ups = apply_interviewer_action(
                    session, resolved, starting=starting
                )
                if suppressed:
                    yield _sse_frame("delta", {"text": resolved.message, "reset": True})
                assembled = _assemble_session(session, message, main_question_count, follow_ups)
                if starting:
                    saved = save_session(assembled)
                    yield _sse_frame("done", _session_payload_dict(saved))
                    return
                if resolved.kind == "end_interview":
                    target = _finalize_awaiting_review(assembled)
                    yield _sse_frame("done", _session_payload_dict(target))
                else:
                    update_session(assembled)
                    yield _sse_frame("done", _session_payload_dict(assembled))
                return
    except InterviewerActionValidationError as error:
        yield _sse_frame("error", {"detail": str(error), "status": 502})
    except AIProviderRequestError as error:
        yield _sse_frame("error", {"detail": str(error), "status": 502})
    except ValueError as error:
        yield _sse_frame("error", {"detail": str(error), "status": 400})


def _generate_review_task(session_id: int) -> None:
    """后台生成复盘：成功落 review+ready 并推进 session ended；失败落 failed 供前端重试。

    BackgroundTask 跑在 threadpool，任何未预期异常都必须落 failed，避免记录卡在 pending
    只能等前端轮询超时。
    """
    try:
        session = read_session(session_id)
        if session is None:
            logger.warning("复盘后台任务跳过：session 不存在 session_id=%s", session_id)
            return
        interview = read_interview(session.interview_id)
        if interview is None:
            logger.warning("复盘后台任务跳过：interview 不存在 session_id=%s", session_id)
            return
        provider = _require_active_provider()
        review = generate_interview_review_with_provider(
            provider,
            session=session,
            analysis=interview.analysis,
            target_role=interview.target_role,
        )
    except Exception as error:
        logger.exception("复盘后台任务失败 session_id=%s", session_id)
        try:
            update_completed_interview_review(
                session_id, status="failed", error=str(error) or "复盘生成失败"
            )
        except Exception:
            logger.exception("更新复盘失败状态也失败 session_id=%s", session_id)
        return

    update_completed_interview_review(session_id, status="ready", review=review)
    ended_session = _ended_session_from(session)
    update_session(ended_session)


@app.post("/interviews/{interview_id}/sessions")
def post_interview_session(
    interview_id: int,
    payload: StartSessionPayload | None = None,
):
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

    def event_stream() -> Iterator[str]:
        yield from _stream_interviewer_action(
            provider_settings=active_provider,
            session=draft_session,
            analysis=interview.analysis,
            target_role=interview.target_role,
            starting=True,
        )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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


@app.post("/interview-sessions/{session_id}/answers")
def post_interview_session_answer(
    session_id: int,
    payload: AnswerSessionPayload,
):
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

    early_end = (
        session_with_answer.main_question_count >= DEFAULT_MAIN_QUESTIONS
        and session_with_answer.current_main_question_follow_ups >= DEFAULT_MAX_FOLLOW_UPS
    )

    def event_stream() -> Iterator[str]:
        if early_end:
            message, main_question_count, follow_ups = apply_interviewer_action(
                session_with_answer,
                InterviewerAction(kind="end_interview", message="本场面试的信息已经足够，我们进入复盘。"),
            )
            ending_session = _assemble_session(
                session_with_answer, message, main_question_count, follow_ups
            )
            awaiting_review_session = _finalize_awaiting_review(ending_session)
            yield _sse_frame("done", _session_payload_dict(awaiting_review_session))
            return
        yield from _stream_interviewer_action(
            provider_settings=active_provider,
            session=session_with_answer,
            analysis=interview.analysis,
            target_role=interview.target_role,
            starting=False,
        )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/interview-sessions/{session_id}/end", response_model=InterviewSessionPayload)
def post_interview_session_end(session_id: int) -> InterviewSessionPayload:
    session = read_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="进行中面试不存在")
    if session.status != "in_progress":
        raise HTTPException(status_code=400, detail="该面试已结束或等待复盘确认")

    awaiting_review_session = _finalize_awaiting_review(session)
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
def post_interview_session_review(
    session_id: int,
    background_tasks: BackgroundTasks,
) -> InterviewSessionPayload:
    session = read_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="进行中面试不存在")
    if session.status == "ended":
        return _to_session_payload(session)
    if session.status != "awaiting_review":
        raise HTTPException(status_code=400, detail="请先结束面试，再生成复盘")

    existing = read_completed_interview_by_session(session_id)
    if existing is not None and existing.review_status == "ready":
        # 已有就绪复盘，幂等返回，不重复生成。
        return _to_session_payload(session)

    # 触发 / 重新触发后台生成：置 pending 并登记任务，立即返回不阻塞（治 499）。
    if existing is None:
        save_completed_interview(session, status="pending")
    else:
        update_completed_interview_review(session_id, status="pending", error="")
    background_tasks.add_task(_generate_review_task, session_id)

    refreshed = read_session(session_id)
    return _to_session_payload(refreshed)


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


# 后端托管前端构建产物（apps/web/dist）。放在所有 API 路由之后，
# html=True 让 SPA 路由刷新回落到 index.html。dist 不存在时跳过（开发模式）。
_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"
if _FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="frontend")
