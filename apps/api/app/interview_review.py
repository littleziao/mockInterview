from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass

from pydantic import BaseModel, Field, ValidationError

from .database import connect, initialize_database
from .interview_session import InterviewSession, TranscriptMessage, initialize_interview_session_schema
from .resume_analysis import ResumeAnalysis


ABILITY_DIMENSIONS = (
    "专业知识准确性",
    "项目经验表达",
    "问题分析能力",
    "技术深度",
    "沟通结构化",
    "岗位匹配度",
)

REVIEW_FIELD_ALIASES = {
    "overall_evaluation": ("overall_evaluation", "overallEvaluation", "summary", "总体评价"),
    "highlights": ("highlights", "strengths", "亮点"),
    "main_issues": ("main_issues", "mainIssues", "problems", "主要问题"),
    "question_reviews": ("question_reviews", "questionReviews", "per_question_reviews", "逐题点评"),
    "improved_expression_examples": (
        "improved_expression_examples",
        "improvedExpressionExamples",
        "expression_examples",
        "可改进表达示例",
    ),
    "sample_answers": ("sample_answers", "sampleAnswers", "reference_answers", "参考答案"),
    "knowledge_references": ("knowledge_references", "knowledgeReferences", "knowledge_points", "知识点参考"),
    "learning_framework": ("learning_framework", "learningFramework", "study_plan", "学习框架"),
    "next_practice_suggestions": (
        "next_practice_suggestions",
        "nextPracticeSuggestions",
        "next_steps",
        "下一次练习建议",
    ),
    "ability_scores": ("ability_scores", "abilityScores", "scores", "能力评分"),
}

LIST_FIELDS = {
    "highlights",
    "main_issues",
    "question_reviews",
    "improved_expression_examples",
    "sample_answers",
    "knowledge_references",
    "learning_framework",
    "next_practice_suggestions",
}


class AbilityScore(BaseModel):
    dimension: str
    score: int = Field(ge=1, le=5)
    rationale: str = Field(min_length=1)


class InterviewReview(BaseModel):
    overall_evaluation: str = Field(min_length=1)
    highlights: list[str] = Field(min_length=1)
    main_issues: list[str] = Field(min_length=1)
    question_reviews: list[str] = Field(min_length=1)
    improved_expression_examples: list[str] = Field(min_length=1)
    sample_answers: list[str] = Field(min_length=1)
    knowledge_references: list[str] = Field(min_length=1)
    learning_framework: list[str] = Field(min_length=1)
    next_practice_suggestions: list[str] = Field(min_length=1)
    ability_scores: list[AbilityScore] = Field(min_length=len(ABILITY_DIMENSIONS), max_length=len(ABILITY_DIMENSIONS))


class InterviewReviewValidationError(ValueError):
    pass


@dataclass(frozen=True)
class CompletedInterviewRecord:
    id: int
    interview_id: int
    session_id: int
    transcript: list[TranscriptMessage]
    review: InterviewReview


def _unwrap_review_payload(data: object) -> object:
    if not isinstance(data, dict):
        return data

    for wrapper_key in ("review", "data", "result", "interview_review", "interviewReview", "复盘"):
        wrapped_data = data.get(wrapper_key)
        if isinstance(wrapped_data, dict):
            return wrapped_data

    return data


def _coerce_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [_stringify_review_item(item) for item in value if _stringify_review_item(item)]

    if isinstance(value, dict):
        return [_stringify_review_item(value)] if _stringify_review_item(value) else []

    if isinstance(value, str):
        return [
            line.strip(" -*\t")
            for line in value.replace("；", "\n").replace(";", "\n").splitlines()
            if line.strip(" -*\t")
        ]

    if value is None:
        return []

    return [str(value).strip()] if str(value).strip() else []


def _stringify_review_item(value: object) -> str:
    if isinstance(value, dict):
        parts: list[str] = []
        for item_value in value.values():
            if isinstance(item_value, list):
                parts.extend(str(part).strip() for part in item_value if str(part).strip())
            elif isinstance(item_value, dict):
                nested = _stringify_review_item(item_value)
                if nested:
                    parts.append(nested)
            elif item_value is not None and str(item_value).strip():
                parts.append(str(item_value).strip())
        return "；".join(parts)

    return str(value).strip() if value is not None else ""


def _coerce_score(value: object) -> int:
    if isinstance(value, dict):
        nested_value = next(
            (
                value[key]
                for key in ("score", "value", "rating", "分数", "评分", "得分")
                if key in value
            ),
            None,
        )
        return _coerce_score(nested_value)

    if isinstance(value, (int, float)):
        numeric_value = float(value)
        if numeric_value > 5:
            return max(1, min(5, round(numeric_value / 20)))
        return int(numeric_value)

    text = str(value).strip()
    qualitative_scores = {
        "优秀": 5,
        "很好": 5,
        "良好": 4,
        "较好": 4,
        "一般": 3,
        "中等": 3,
        "较弱": 2,
        "不足": 2,
        "很弱": 1,
    }
    if text in qualitative_scores:
        return qualitative_scores[text]

    fraction_match = re.search(r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)", text)
    if fraction_match:
        numerator = float(fraction_match.group(1))
        denominator = float(fraction_match.group(2))
        if denominator > 0:
            return max(1, min(5, round(numerator / denominator * 5)))

    number_match = re.search(r"\d+(?:\.\d+)?", text)
    if number_match:
        return _coerce_score(float(number_match.group(0)))

    try:
        return int(float(text))
    except ValueError:
        return 0


def _normalize_ability_scores(value: object) -> list[dict[str, object]]:
    if isinstance(value, dict):
        raw_items = [
            {"dimension": str(dimension), "score": score, "rationale": "基于本次面试表现给出的能力评分。"}
            for dimension, score in value.items()
        ]
    elif isinstance(value, list):
        raw_items = [item for item in value if isinstance(item, dict)]
    else:
        raw_items = []

    by_dimension: dict[str, dict[str, object]] = {}
    for item in raw_items:
        dimension = str(
            item.get("dimension")
            or item.get("name")
            or item.get("能力维度")
            or item.get("维度")
            or ""
        ).strip()
        if dimension not in ABILITY_DIMENSIONS:
            continue
        by_dimension[dimension] = {
            "dimension": dimension,
            "score": _coerce_score(item),
            "rationale": str(
                item.get("rationale")
                or item.get("reason")
                or item.get("说明")
                or item.get("理由")
                or item.get("comment")
                or ""
            ).strip()
            or "基于本次面试表现给出的能力评分。",
        }

    return [by_dimension[dimension] for dimension in ABILITY_DIMENSIONS if dimension in by_dimension]


def _normalize_review_data(data: object) -> object:
    unwrapped_data = _unwrap_review_payload(data)
    if not isinstance(unwrapped_data, dict):
        return unwrapped_data

    normalized: dict[str, object] = {}
    for field_name, aliases in REVIEW_FIELD_ALIASES.items():
        value = next((unwrapped_data[alias] for alias in aliases if alias in unwrapped_data), None)
        if field_name in LIST_FIELDS:
            normalized[field_name] = _coerce_list(value)
        elif field_name == "ability_scores":
            normalized[field_name] = _normalize_ability_scores(value)
        elif value is not None:
            normalized[field_name] = str(value).strip()

    return normalized


def validate_interview_review(data: object) -> InterviewReview:
    try:
        review = InterviewReview.model_validate(_normalize_review_data(data))
    except ValidationError as error:
        raise InterviewReviewValidationError("AI 返回的复盘结构无效") from error

    if [score.dimension for score in review.ability_scores] != list(ABILITY_DIMENSIONS):
        raise InterviewReviewValidationError("AI 返回的复盘结构无效")

    return review


def initialize_interview_review_schema() -> None:
    initialize_database()
    initialize_interview_session_schema()
    with connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS completed_interviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                interview_id INTEGER NOT NULL,
                session_id INTEGER NOT NULL UNIQUE,
                transcript_json TEXT NOT NULL,
                review_json TEXT NOT NULL,
                completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (interview_id) REFERENCES interviews(id),
                FOREIGN KEY (session_id) REFERENCES interview_sessions(id)
            )
            """
        )
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations (version) VALUES (?)",
            ("0004_completed_interviews",),
        )


def save_completed_interview(session: InterviewSession, review: InterviewReview) -> CompletedInterviewRecord:
    initialize_interview_review_schema()
    transcript_json = json.dumps(
        [message.model_dump() for message in session.transcript],
        ensure_ascii=False,
    )
    with connect() as connection:
        cursor = connection.execute(
            """
            INSERT OR REPLACE INTO completed_interviews (
                interview_id, session_id, transcript_json, review_json
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                session.interview_id,
                session.id,
                transcript_json,
                review.model_dump_json(),
            ),
        )
        record_id = int(cursor.lastrowid)

    return CompletedInterviewRecord(
        id=record_id,
        interview_id=session.interview_id,
        session_id=session.id,
        transcript=list(session.transcript),
        review=review,
    )


def read_completed_interview_by_session(session_id: int) -> CompletedInterviewRecord | None:
    initialize_interview_review_schema()
    with connect() as connection:
        row: sqlite3.Row | None = connection.execute(
            """
            SELECT id, interview_id, session_id, transcript_json, review_json
            FROM completed_interviews
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()

    if row is None:
        return None

    transcript = [
        TranscriptMessage.model_validate(item)
        for item in json.loads(str(row["transcript_json"]))
    ]
    return CompletedInterviewRecord(
        id=int(row["id"]),
        interview_id=int(row["interview_id"]),
        session_id=int(row["session_id"]),
        transcript=transcript,
        review=validate_interview_review(json.loads(str(row["review_json"]))),
    )
