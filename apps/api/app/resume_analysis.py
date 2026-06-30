from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

from pydantic import BaseModel, Field, ValidationError

from .database import connect, initialize_database


class ResumeAnalysis(BaseModel):
    background_summary: str = Field(min_length=1)
    key_projects: list[str] = Field(min_length=1)
    technical_stack: list[str] = Field(min_length=1)
    follow_up_topics: list[str] = Field(min_length=1)
    risk_points: list[str] = Field(default_factory=list)
    unclear_points: list[str] = Field(default_factory=list)
    target_role_notes: str = ""
    focus_topics: list[str] = Field(default_factory=list)
    low_priority_follow_up_topics: list[str] = Field(default_factory=list)


class ResumeAnalysisValidationError(ValueError):
    pass


@dataclass(frozen=True)
class InterviewRecord:
    id: int
    resume_markdown: str
    target_role: str
    analysis: ResumeAnalysis


def validate_resume_analysis(data: object) -> ResumeAnalysis:
    try:
        return ResumeAnalysis.model_validate(data)
    except ValidationError as error:
        raise ResumeAnalysisValidationError("AI 返回的简历分析结构无效") from error


def initialize_resume_analysis_schema() -> None:
    initialize_database()
    with connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS interviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resume_markdown TEXT NOT NULL,
                target_role TEXT NOT NULL DEFAULT '',
                analysis_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations (version) VALUES (?)",
            ("0002_interviews",),
        )


def save_interview(
    *,
    resume_markdown: str,
    target_role: str,
    analysis: ResumeAnalysis,
) -> InterviewRecord:
    initialize_resume_analysis_schema()
    with connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO interviews (resume_markdown, target_role, analysis_json)
            VALUES (?, ?, ?)
            """,
            (
                resume_markdown,
                target_role,
                analysis.model_dump_json(),
            ),
        )
        interview_id = int(cursor.lastrowid)

    return InterviewRecord(
        id=interview_id,
        resume_markdown=resume_markdown,
        target_role=target_role,
        analysis=analysis,
    )


def read_interview(interview_id: int) -> InterviewRecord | None:
    initialize_resume_analysis_schema()
    with connect() as connection:
        row: sqlite3.Row | None = connection.execute(
            """
            SELECT id, resume_markdown, target_role, analysis_json
            FROM interviews
            WHERE id = ?
            """,
            (interview_id,),
        ).fetchone()

    if row is None:
        return None

    return InterviewRecord(
        id=int(row["id"]),
        resume_markdown=str(row["resume_markdown"]),
        target_role=str(row["target_role"]),
        analysis=validate_resume_analysis(json.loads(str(row["analysis_json"]))),
    )
