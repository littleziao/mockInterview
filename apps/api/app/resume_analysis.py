from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

from pydantic import BaseModel, Field, ValidationError

from .database import connect, initialize_database


FIELD_ALIASES = {
    "background_summary": ("background_summary", "backgroundSummary", "summary", "background", "背景摘要"),
    "key_projects": ("key_projects", "keyProjects", "projects", "project_experience", "关键项目", "关键项目经历"),
    "technical_stack": ("technical_stack", "technicalStack", "skills", "tech_stack", "技术栈", "技术能力"),
    "follow_up_topics": (
        "follow_up_topics",
        "followUpTopics",
        "possible_follow_ups",
        "follow_ups",
        "possible_questions",
        "可能追问点",
        "追问点",
    ),
    "risk_points": ("risk_points", "riskPoints", "risks", "red_flags", "风险点"),
    "unclear_points": ("unclear_points", "unclearPoints", "ambiguities", "unclear_areas", "表达不清之处", "不清楚的地方"),
    "target_role_notes": ("target_role_notes", "targetRoleNotes", "role_notes", "target_notes", "目标岗位补充说明", "目标岗位说明"),
    "focus_topics": ("focus_topics", "focusTopics", "practice_focus", "focus_areas", "希望重点练习的内容", "重点练习内容"),
    "low_priority_follow_up_topics": (
        "low_priority_follow_up_topics",
        "lowPriorityFollowUpTopics",
        "avoid_topics",
        "lower_priority_topics",
        "不希望重点追问的内容",
        "低优先级追问方向",
    ),
}

LIST_FIELDS = {
    "key_projects",
    "technical_stack",
    "follow_up_topics",
    "risk_points",
    "unclear_points",
    "focus_topics",
    "low_priority_follow_up_topics",
}


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
    interview_mode: str
    analysis: ResumeAnalysis
    include_hr_round: bool = False
    source_resume_analysis_record_id: int | None = None


@dataclass(frozen=True)
class ResumeAnalysisRecord:
    id: int
    resume_markdown: str
    target_role: str
    analysis: ResumeAnalysis
    created_at: str
    last_used_at: str
    use_count: int


def _unwrap_analysis_payload(data: object) -> object:
    if not isinstance(data, dict):
        return data

    for wrapper_key in ("analysis", "data", "result", "resume_analysis", "resumeAnalysis", "简历分析"):
        wrapped_data = data.get(wrapper_key)
        if isinstance(wrapped_data, dict):
            return wrapped_data

    return data


def _coerce_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    if isinstance(value, str):
        return [
            line.strip(" -*\t")
            for line in value.replace("；", "\n").replace(";", "\n").splitlines()
            if line.strip(" -*\t")
        ]

    if value is None:
        return []

    return [str(value).strip()] if str(value).strip() else []


def _normalize_resume_analysis_data(data: object) -> object:
    unwrapped_data = _unwrap_analysis_payload(data)
    if not isinstance(unwrapped_data, dict):
        return unwrapped_data

    normalized: dict[str, object] = {}
    for field_name, aliases in FIELD_ALIASES.items():
        value = next((unwrapped_data[alias] for alias in aliases if alias in unwrapped_data), None)
        if field_name in LIST_FIELDS:
            normalized[field_name] = _coerce_list(value)
        elif value is not None:
            normalized[field_name] = str(value).strip()

    return normalized


def validate_resume_analysis(data: object) -> ResumeAnalysis:
    try:
        return ResumeAnalysis.model_validate(_normalize_resume_analysis_data(data))
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
                interview_mode TEXT NOT NULL DEFAULT 'single_round',
                analysis_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        columns = {
            str(row["name"])
            for row in connection.execute("PRAGMA table_info(interviews)").fetchall()
        }
        if "interview_mode" not in columns:
            connection.execute(
                "ALTER TABLE interviews ADD COLUMN interview_mode TEXT NOT NULL DEFAULT 'single_round'"
            )
        if "include_hr_round" not in columns:
            connection.execute(
                "ALTER TABLE interviews ADD COLUMN include_hr_round INTEGER NOT NULL DEFAULT 0"
            )
        if "source_resume_analysis_record_id" not in columns:
            connection.execute(
                "ALTER TABLE interviews ADD COLUMN source_resume_analysis_record_id INTEGER"
            )
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations (version) VALUES (?)",
            ("0002_interviews",),
        )
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations (version) VALUES (?)",
            ("0006_interview_include_hr",),
        )
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations (version) VALUES (?)",
            ("0008_interview_source_resume_analysis",),
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS resume_analysis_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resume_markdown TEXT NOT NULL,
                target_role TEXT NOT NULL DEFAULT '',
                analysis_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_used_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                use_count INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations (version) VALUES (?)",
            ("0007_resume_analysis_records",),
        )


def _record_from_row(row: sqlite3.Row) -> ResumeAnalysisRecord:
    return ResumeAnalysisRecord(
        id=int(row["id"]),
        resume_markdown=str(row["resume_markdown"]),
        target_role=str(row["target_role"]),
        analysis=validate_resume_analysis(json.loads(str(row["analysis_json"]))),
        created_at=str(row["created_at"]),
        last_used_at=str(row["last_used_at"]),
        use_count=int(row["use_count"]),
    )


def save_resume_analysis_record(
    *,
    resume_markdown: str,
    target_role: str,
    analysis: ResumeAnalysis,
) -> ResumeAnalysisRecord:
    initialize_resume_analysis_schema()
    with connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO resume_analysis_records (resume_markdown, target_role, analysis_json)
            VALUES (?, ?, ?)
            """,
            (resume_markdown, target_role, analysis.model_dump_json()),
        )
        record_id = int(cursor.lastrowid)
        row = connection.execute(
            """
            SELECT id, resume_markdown, target_role, analysis_json, created_at, last_used_at, use_count
            FROM resume_analysis_records
            WHERE id = ?
            """,
            (record_id,),
        ).fetchone()

    if row is None:
        raise RuntimeError("简历分析记录保存失败")
    return _record_from_row(row)


def list_resume_analysis_records() -> list[ResumeAnalysisRecord]:
    initialize_resume_analysis_schema()
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT id, resume_markdown, target_role, analysis_json, created_at, last_used_at, use_count
            FROM resume_analysis_records
            ORDER BY id DESC
            """
        ).fetchall()

    return [_record_from_row(row) for row in rows]


def read_resume_analysis_record(record_id: int) -> ResumeAnalysisRecord | None:
    initialize_resume_analysis_schema()
    with connect() as connection:
        row = connection.execute(
            """
            SELECT id, resume_markdown, target_role, analysis_json, created_at, last_used_at, use_count
            FROM resume_analysis_records
            WHERE id = ?
            """,
            (record_id,),
        ).fetchone()

    return _record_from_row(row) if row is not None else None


def delete_resume_analysis_record(record_id: int) -> bool:
    """删除单条简历分析记录。

    该操作只影响简历分析历史，不级联删除面试、复盘或趋势数据。
    面试记录中保留的来源简历分析记录引用为悬空引用，仅用于追溯，不影响面试生命周期。
    """
    initialize_resume_analysis_schema()
    with connect() as connection:
        existing = connection.execute(
            "SELECT id FROM resume_analysis_records WHERE id = ?",
            (record_id,),
        ).fetchone()
        if existing is None:
            return False

        connection.execute(
            "DELETE FROM resume_analysis_records WHERE id = ?",
            (record_id,),
        )

    return True


def save_interview(
    *,
    resume_markdown: str,
    target_role: str,
    interview_mode: str = "single_round",
    include_hr_round: bool = False,
    source_resume_analysis_record_id: int | None = None,
    analysis: ResumeAnalysis,
) -> InterviewRecord | None:
    initialize_resume_analysis_schema()
    normalized_mode = interview_mode.strip() or "single_round"
    with connect() as connection:
        if source_resume_analysis_record_id is not None:
            update_cursor = connection.execute(
                """
                UPDATE resume_analysis_records
                SET resume_markdown = ?,
                    target_role = ?,
                    analysis_json = ?,
                    last_used_at = CURRENT_TIMESTAMP,
                    use_count = use_count + 1
                WHERE id = ?
                """,
                (
                    resume_markdown,
                    target_role,
                    analysis.model_dump_json(),
                    source_resume_analysis_record_id,
                ),
            )
            if update_cursor.rowcount == 0:
                return None

        cursor = connection.execute(
            """
            INSERT INTO interviews (
                resume_markdown,
                target_role,
                interview_mode,
                include_hr_round,
                source_resume_analysis_record_id,
                analysis_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                resume_markdown,
                target_role,
                normalized_mode,
                1 if include_hr_round else 0,
                source_resume_analysis_record_id,
                analysis.model_dump_json(),
            ),
        )
        interview_id = int(cursor.lastrowid)

    return InterviewRecord(
        id=interview_id,
        resume_markdown=resume_markdown,
        target_role=target_role,
        interview_mode=normalized_mode,
        include_hr_round=include_hr_round,
        source_resume_analysis_record_id=source_resume_analysis_record_id,
        analysis=analysis,
    )


def read_interview(interview_id: int) -> InterviewRecord | None:
    initialize_resume_analysis_schema()
    with connect() as connection:
        row: sqlite3.Row | None = connection.execute(
            """
            SELECT
                id,
                resume_markdown,
                target_role,
                interview_mode,
                include_hr_round,
                source_resume_analysis_record_id,
                analysis_json
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
        interview_mode=str(row["interview_mode"]),
        include_hr_round=bool(row["include_hr_round"]) if "include_hr_round" in row.keys() else False,
        source_resume_analysis_record_id=(
            int(row["source_resume_analysis_record_id"])
            if "source_resume_analysis_record_id" in row.keys()
            and row["source_resume_analysis_record_id"] is not None
            else None
        ),
        analysis=validate_resume_analysis(json.loads(str(row["analysis_json"]))),
    )
