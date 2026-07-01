from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

from pydantic import BaseModel, Field, ValidationError

from .database import connect, initialize_database
from .resume_analysis import initialize_resume_analysis_schema


DEFAULT_MAIN_QUESTIONS = 6
DEFAULT_MAX_FOLLOW_UPS = 2

INTERVIEWER_ACTION_KINDS = ("main_question", "follow_up", "clarify")

FALLBACK_NEXT_MAIN_QUESTION = "这个问题先到这里。我们换个方向，聊聊另一个和目标岗位相关的核心项目或技术取舍。"
FALLBACK_FINAL_CLARIFY = "主要问题已经覆盖完了。最后你还有什么想补充、澄清或特别希望我了解的吗？"


ACTION_FIELD_ALIASES = {
    "kind": ("kind", "action", "type", "decision", "动作", "类型"),
    "message": ("message", "content", "question", "text", "问题", "内容"),
}

ACTION_KIND_ALIASES = {
    "main_question": (
        "main_question",
        "new_main_question",
        "main",
        "question",
        "new_question",
        "主问题",
    ),
    "follow_up": ("follow_up", "followup", "follow-up", "deepen", "追问"),
    "clarify": ("clarify", "clarification", "rephrase", "narrow", "澄清", "换问法"),
}


class InterviewerAction(BaseModel):
    """AI 以真人面试官视角产生的下一步动作（结构化 AI 输出）。"""

    kind: str
    message: str = Field(min_length=1)


class InterviewerActionValidationError(ValueError):
    pass


class TranscriptMessage(BaseModel):
    """一条面试对话消息。interviewer 由 AI 产生，candidate 为用户文字回答。"""

    role: str
    content: str
    kind: str = ""
    main_question_index: int = 0


@dataclass(frozen=True)
class InterviewSession:
    id: int
    interview_id: int
    style: str
    status: str
    transcript: list[TranscriptMessage]
    main_question_count: int
    current_main_question_follow_ups: int


def _unwrap_action_payload(data: object) -> object:
    if not isinstance(data, dict):
        return data

    for wrapper_key in ("action", "data", "result", "decision", "interviewer_action", "动作"):
        wrapped_data = data.get(wrapper_key)
        if isinstance(wrapped_data, dict):
            return wrapped_data

    return data


def _normalize_action_kind(value: object) -> str | None:
    if value is None:
        return None

    text = str(value).strip().lower().replace(" ", "_").replace("-", "_")
    for canonical, aliases in ACTION_KIND_ALIASES.items():
        for alias in aliases:
            if text == alias.lower():
                return canonical

    return None


def _normalize_interviewer_action(data: object) -> object:
    unwrapped_data = _unwrap_action_payload(data)
    if not isinstance(unwrapped_data, dict):
        return unwrapped_data

    normalized: dict[str, object] = {}
    for field_name, aliases in ACTION_FIELD_ALIASES.items():
        value = next((unwrapped_data[alias] for alias in aliases if alias in unwrapped_data), None)
        if value is not None:
            if field_name == "kind":
                canonical_kind = _normalize_action_kind(value)
                normalized[field_name] = canonical_kind if canonical_kind else value
            else:
                normalized[field_name] = str(value).strip()

    return normalized


def validate_interviewer_action(data: object) -> InterviewerAction:
    try:
        action = InterviewerAction.model_validate(_normalize_interviewer_action(data))
    except ValidationError as error:
        raise InterviewerActionValidationError("AI 返回的面试官动作结构无效") from error

    if action.kind not in INTERVIEWER_ACTION_KINDS:
        raise InterviewerActionValidationError("AI 返回的面试官动作结构无效")

    return action


def _normalize_transcript_message(data: object) -> object:
    if not isinstance(data, dict):
        return data

    role = str(data.get("role", "")).strip().lower()
    kind_raw = data.get("kind", "")
    if role == "candidate":
        kind = ""
    elif kind_raw is None:
        kind = ""
    else:
        canonical_kind = _normalize_action_kind(kind_raw)
        kind = canonical_kind if canonical_kind else str(kind_raw)

    return {
        "role": role or "candidate",
        "content": str(data.get("content", "")).strip(),
        "kind": kind,
        "main_question_index": int(data.get("main_question_index", 0)),
    }


def _validate_transcript_message(data: object) -> TranscriptMessage:
    normalized = _normalize_transcript_message(data)
    try:
        message = TranscriptMessage.model_validate(normalized)
    except ValidationError as error:
        raise InterviewerActionValidationError("进行中面试对话记录结构无效") from error

    if message.role not in ("interviewer", "candidate"):
        raise InterviewerActionValidationError("进行中面试对话记录结构无效")
    if message.role == "interviewer" and message.kind not in INTERVIEWER_ACTION_KINDS:
        raise InterviewerActionValidationError("进行中面试对话记录结构无效")

    return message


def _validate_transcript(raw_transcript: object) -> list[TranscriptMessage]:
    if not isinstance(raw_transcript, list):
        return []

    return [_validate_transcript_message(item) for item in raw_transcript]


def initialize_interview_session_schema() -> None:
    initialize_database()
    initialize_resume_analysis_schema()
    with connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS interview_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                interview_id INTEGER NOT NULL,
                style TEXT NOT NULL DEFAULT 'study',
                status TEXT NOT NULL DEFAULT 'in_progress',
                transcript_json TEXT NOT NULL DEFAULT '[]',
                main_question_count INTEGER NOT NULL DEFAULT 0,
                current_main_question_follow_ups INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (interview_id) REFERENCES interviews(id)
            )
            """
        )
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations (version) VALUES (?)",
            ("0003_interview_sessions",),
        )


def _build_session_from_row(row: sqlite3.Row) -> InterviewSession:
    transcript = _validate_transcript(json.loads(str(row["transcript_json"])))
    return InterviewSession(
        id=int(row["id"]),
        interview_id=int(row["interview_id"]),
        style=str(row["style"]),
        status=str(row["status"]),
        transcript=transcript,
        main_question_count=int(row["main_question_count"]),
        current_main_question_follow_ups=int(row["current_main_question_follow_ups"]),
    )


def save_session(session: InterviewSession) -> InterviewSession:
    initialize_interview_session_schema()
    transcript_json = json.dumps(
        [message.model_dump() for message in session.transcript],
        ensure_ascii=False,
    )
    with connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO interview_sessions (
                id, interview_id, style, status, transcript_json,
                main_question_count, current_main_question_follow_ups
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session.id,
                session.interview_id,
                session.style,
                session.status,
                transcript_json,
                session.main_question_count,
                session.current_main_question_follow_ups,
            ),
        )
        inserted_id = int(cursor.lastrowid or session.id)

    if session.id:
        return session

    return InterviewSession(
        id=inserted_id,
        interview_id=session.interview_id,
        style=session.style,
        status=session.status,
        transcript=list(session.transcript),
        main_question_count=session.main_question_count,
        current_main_question_follow_ups=session.current_main_question_follow_ups,
    )


def update_session(session: InterviewSession) -> InterviewSession:
    initialize_interview_session_schema()
    transcript_json = json.dumps(
        [message.model_dump() for message in session.transcript],
        ensure_ascii=False,
    )
    with connect() as connection:
        cursor = connection.execute(
            """
            UPDATE interview_sessions
            SET style = ?, status = ?, transcript_json = ?,
                main_question_count = ?, current_main_question_follow_ups = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                session.style,
                session.status,
                transcript_json,
                session.main_question_count,
                session.current_main_question_follow_ups,
                session.id,
            ),
        )
        if cursor.rowcount == 0:
            raise ValueError("进行中面试不存在")

    return session


def read_session(session_id: int) -> InterviewSession | None:
    initialize_interview_session_schema()
    with connect() as connection:
        row: sqlite3.Row | None = connection.execute(
            """
            SELECT id, interview_id, style, status, transcript_json,
                   main_question_count, current_main_question_follow_ups
            FROM interview_sessions
            WHERE id = ?
            """,
            (session_id,),
        ).fetchone()

    if row is None:
        return None

    return _build_session_from_row(row)


def create_new_session(*, interview_id: int, style: str) -> InterviewSession:
    normalized_style = style.strip() or "study"
    return save_session(
        InterviewSession(
            id=0,
            interview_id=interview_id,
            style=normalized_style,
            status="in_progress",
            transcript=[],
            main_question_count=0,
            current_main_question_follow_ups=0,
        )
    )


def latest_interviewer_message(transcript: list[TranscriptMessage]) -> TranscriptMessage | None:
    for message in reversed(transcript):
        if message.role == "interviewer":
            return message
    return None


def current_main_question_index(session: InterviewSession) -> int:
    """当前主问题的 0-based 序号；尚未提出任何主问题时为 -1。"""

    return session.main_question_count - 1 if session.main_question_count > 0 else -1


def answers_in_current_main_question(
    transcript: list[TranscriptMessage],
    main_question_index: int,
) -> int:
    return sum(
        1
        for message in transcript
        if message.role == "candidate" and message.main_question_index == main_question_index
    )


def resolve_interviewer_action(
    raw_action: object,
    session: InterviewSession,
    *,
    starting: bool,
    max_main_questions: int = DEFAULT_MAIN_QUESTIONS,
    max_follow_ups: int = DEFAULT_MAX_FOLLOW_UPS,
) -> InterviewerAction:
    """校验 AI 动作，并按单轮面试的主问题与追问上限对越界动作进行降级。"""

    action = validate_interviewer_action(raw_action)

    if starting:
        return InterviewerAction(kind="main_question", message=action.message)

    main_question_cap_reached = session.main_question_count >= max_main_questions
    follow_up_cap_reached = session.current_main_question_follow_ups >= max_follow_ups

    if action.kind == "follow_up" and follow_up_cap_reached:
        if main_question_cap_reached:
            return InterviewerAction(kind="clarify", message=FALLBACK_FINAL_CLARIFY)
        return InterviewerAction(kind="main_question", message=FALLBACK_NEXT_MAIN_QUESTION)

    if action.kind == "main_question" and main_question_cap_reached:
        return InterviewerAction(kind="clarify", message=FALLBACK_FINAL_CLARIFY)

    return action


def apply_interviewer_action(
    session: InterviewSession,
    action: InterviewerAction,
    *,
    starting: bool = False,
) -> tuple[TranscriptMessage, int, int]:
    """将校验后的动作落为一条面试官消息，返回 (消息, 新主问题数, 新当前追问数)。"""

    main_question_index = session.main_question_count if starting else current_main_question_index(session)
    if main_question_index < 0:
        main_question_index = 0

    if starting or action.kind == "main_question":
        new_main_question_count = session.main_question_count + 1
        new_follow_ups = 0
        message_index = new_main_question_count - 1
    elif action.kind == "follow_up":
        new_main_question_count = session.main_question_count
        new_follow_ups = session.current_main_question_follow_ups + 1
        message_index = main_question_index
    else:  # clarify
        new_main_question_count = session.main_question_count
        new_follow_ups = session.current_main_question_follow_ups
        message_index = main_question_index

    message = TranscriptMessage(
        role="interviewer",
        content=action.message,
        kind=action.kind,
        main_question_index=message_index,
    )
    return message, new_main_question_count, new_follow_ups


def append_candidate_answer(
    session: InterviewSession,
    answer: str,
) -> TranscriptMessage:
    return TranscriptMessage(
        role="candidate",
        content=answer,
        kind="",
        main_question_index=max(current_main_question_index(session), 0),
    )
