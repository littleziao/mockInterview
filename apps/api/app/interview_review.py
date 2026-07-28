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

JD_MATCH_ANALYSIS_FIELD_ALIASES = {
    "matching_evidence": (
        "matching_evidence",
        "matchingEvidence",
        "匹配证据",
    ),
    "role_gaps": (
        "role_gaps",
        "roleGaps",
        "exposed_role_gaps",
        "暴露的岗位缺口",
        "岗位缺口",
    ),
    "project_expression_improvements": (
        "project_expression_improvements",
        "projectExpressionImprovements",
        "项目表达如何更贴 JD",
        "项目表达改进",
    ),
    "next_practice_jd_priorities": (
        "next_practice_jd_priorities",
        "nextPracticeJdPriorities",
        "下一轮优先补齐的 JD 要求",
        "下轮 JD 优先级",
    ),
}

JD_MATCH_ANALYSIS_OBJECT_ALIASES = (
    "jd_match_analysis",
    "jdMatchAnalysis",
    "JD 匹配分析",
    "JD匹配分析",
)

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


class JDMatchAnalysis(BaseModel):
    matching_evidence: list[str] = Field(default_factory=list)
    role_gaps: list[str] = Field(default_factory=list)
    project_expression_improvements: list[str] = Field(default_factory=list)
    next_practice_jd_priorities: list[str] = Field(default_factory=list)


class InterviewReview(BaseModel):
    # 列表字段允许为空：AI 返回稀疏结构时不再整体校验失败（前端空数组按“暂无”渲染）。
    overall_evaluation: str = Field(min_length=1)
    highlights: list[str] = Field(default_factory=list)
    main_issues: list[str] = Field(default_factory=list)
    question_reviews: list[str] = Field(default_factory=list)
    improved_expression_examples: list[str] = Field(default_factory=list)
    sample_answers: list[str] = Field(default_factory=list)
    knowledge_references: list[str] = Field(default_factory=list)
    learning_framework: list[str] = Field(default_factory=list)
    next_practice_suggestions: list[str] = Field(default_factory=list)
    ability_scores: list[AbilityScore] = Field(min_length=len(ABILITY_DIMENSIONS), max_length=len(ABILITY_DIMENSIONS))
    jd_match_analysis: JDMatchAnalysis | None = None


class InterviewReviewValidationError(ValueError):
    pass


@dataclass(frozen=True)
class CompletedInterviewRecord:
    id: int
    interview_id: int
    session_id: int
    transcript: list[TranscriptMessage]
    review: InterviewReview | None
    review_status: str = "ready"
    review_error: str = ""


@dataclass(frozen=True)
class CompletedInterviewHistoryRecord:
    id: int
    interview_id: int
    session_id: int
    target_role: str
    interview_mode: str
    style: str
    round_kind: str
    completed_at: str
    transcript: list[TranscriptMessage]
    review: InterviewReview | None
    review_status: str = "ready"
    review_error: str = ""


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

    # 缺失或维度名不匹配的维度补默认值，保证永远返回恰好 6 个、顺序对齐 ABILITY_DIMENSIONS，
    # 让 schema 的 min/max=6 与顺序校验稳定通过。
    default_rationale = "基于本次面试表现给出的能力评分。"
    completed: list[dict[str, object]] = []
    for dimension in ABILITY_DIMENSIONS:
        if dimension in by_dimension:
            completed.append(by_dimension[dimension])
        else:
            completed.append(
                {"dimension": dimension, "score": 3, "rationale": default_rationale}
            )
    return completed


def _normalize_jd_match_analysis(sub_data: object) -> dict[str, list[str]] | None:
    if not isinstance(sub_data, dict):
        return None

    normalized: dict[str, list[str]] = {}
    for field_name, aliases in JD_MATCH_ANALYSIS_FIELD_ALIASES.items():
        value = next((sub_data[alias] for alias in aliases if alias in sub_data), None)
        normalized[field_name] = _coerce_list(value)

    if not any(normalized.values()):
        return None

    return normalized


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

    jd_match_sub_data = next(
        (unwrapped_data[alias] for alias in JD_MATCH_ANALYSIS_OBJECT_ALIASES if alias in unwrapped_data),
        None,
    )
    jd_match_analysis = _normalize_jd_match_analysis(jd_match_sub_data)
    if jd_match_analysis is not None:
        normalized["jd_match_analysis"] = jd_match_analysis

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
        _migrate_completed_interviews_review_status(connection)
        _migrate_backfill_orphan_reviews(connection)


def _migrate_completed_interviews_review_status(connection: sqlite3.Connection) -> None:
    """0010：复盘异步化——review_json 改可空 + 新增 review_status / review_error。

    SQLite 无法直接修改列约束，用「建新表 → 拷贝 → 替换」重建，幂等。
    """
    already_migrated = connection.execute(
        "SELECT 1 FROM schema_migrations WHERE version = ?",
        ("0010_completed_interviews_review_status",),
    ).fetchone()
    if already_migrated:
        return

    columns = {row["name"] for row in connection.execute("PRAGMA table_info(completed_interviews)")}
    if "review_status" in columns:
        # 老表已含新列（例如手动补过），仅登记迁移版本。
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations (version) VALUES (?)",
            ("0010_completed_interviews_review_status",),
        )
        return

    connection.execute(
        """
        CREATE TABLE completed_interviews_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            interview_id INTEGER NOT NULL,
            session_id INTEGER NOT NULL UNIQUE,
            transcript_json TEXT NOT NULL,
            review_json TEXT,
            review_status TEXT NOT NULL DEFAULT 'ready',
            review_error TEXT NOT NULL DEFAULT '',
            completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (interview_id) REFERENCES interviews(id),
            FOREIGN KEY (session_id) REFERENCES interview_sessions(id)
        )
        """
    )
    connection.execute(
        """
        INSERT INTO completed_interviews_new (
            id, interview_id, session_id, transcript_json, review_json,
            review_status, review_error, completed_at
        )
        SELECT id, interview_id, session_id, transcript_json, review_json,
               'ready', '', completed_at
        FROM completed_interviews
        """
    )
    connection.execute("DROP TABLE completed_interviews")
    connection.execute("ALTER TABLE completed_interviews_new RENAME TO completed_interviews")
    connection.execute(
        "INSERT OR IGNORE INTO schema_migrations (version) VALUES (?)",
        ("0010_completed_interviews_review_status",),
    )


def _migrate_backfill_orphan_reviews(connection: sqlite3.Connection) -> None:
    """0011：补齐已结束但无 completed_interviews 记录的 session（老代码复盘失败遗留）。

    让这些孤儿 session 进入历史列表，可重新触发复盘生成。幂等：NOT EXISTS 保证只补缺。
    """
    already = connection.execute(
        "SELECT 1 FROM schema_migrations WHERE version = ?",
        ("0011_backfill_orphan_reviews",),
    ).fetchone()
    if already:
        return
    connection.execute(
        """
        INSERT INTO completed_interviews (
            interview_id, session_id, transcript_json, review_json, review_status, review_error
        )
        SELECT
            s.interview_id, s.id, s.transcript_json, NULL, 'pending', ''
        FROM interview_sessions s
        WHERE s.status IN ('awaiting_review', 'ended')
          AND NOT EXISTS (
              SELECT 1 FROM completed_interviews c WHERE c.session_id = s.id
          )
        """
    )
    connection.execute(
        "INSERT OR IGNORE INTO schema_migrations (version) VALUES (?)",
        ("0011_backfill_orphan_reviews",),
    )


def save_completed_interview(
    session: InterviewSession,
    review: InterviewReview | None = None,
    *,
    status: str | None = None,
    error: str = "",
) -> CompletedInterviewRecord:
    initialize_interview_review_schema()
    effective_status = status or ("ready" if review is not None else "pending")
    transcript_json = json.dumps(
        [message.model_dump() for message in session.transcript],
        ensure_ascii=False,
    )
    review_json = review.model_dump_json() if review is not None else None
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO completed_interviews (
                interview_id, session_id, transcript_json, review_json,
                review_status, review_error
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                interview_id = excluded.interview_id,
                transcript_json = excluded.transcript_json,
                review_json = excluded.review_json,
                review_status = excluded.review_status,
                review_error = excluded.review_error
            """,
            (
                session.interview_id,
                session.id,
                transcript_json,
                review_json,
                effective_status,
                error,
            ),
        )
        row = connection.execute(
            "SELECT id FROM completed_interviews WHERE session_id = ?",
            (session.id,),
        ).fetchone()

    return CompletedInterviewRecord(
        id=int(row["id"]),
        interview_id=session.interview_id,
        session_id=session.id,
        transcript=list(session.transcript),
        review=review,
        review_status=effective_status,
        review_error=error,
    )


def update_completed_interview_review(
    session_id: int,
    *,
    status: str,
    review: InterviewReview | None = None,
    error: str = "",
) -> None:
    """仅更新复盘结果与状态，供后台生成任务使用。记录必须已存在。"""
    initialize_interview_review_schema()
    review_json = review.model_dump_json() if review is not None else None
    with connect() as connection:
        connection.execute(
            """
            UPDATE completed_interviews
            SET review_json = ?, review_status = ?, review_error = ?
            WHERE session_id = ?
            """,
            (review_json, status, error, session_id),
        )


def read_completed_interview_by_session(session_id: int) -> CompletedInterviewRecord | None:
    initialize_interview_review_schema()
    with connect() as connection:
        row: sqlite3.Row | None = connection.execute(
            """
            SELECT id, interview_id, session_id, transcript_json, review_json,
                   review_status, review_error
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
    review_json_text = row["review_json"]
    review = (
        validate_interview_review(json.loads(str(review_json_text)))
        if review_json_text
        else None
    )
    return CompletedInterviewRecord(
        id=int(row["id"]),
        interview_id=int(row["interview_id"]),
        session_id=int(row["session_id"]),
        transcript=transcript,
        review=review,
        review_status=str(row["review_status"]),
        review_error=str(row["review_error"] or ""),
    )


def delete_completed_interview_history_record(record_id: int) -> bool:
    initialize_interview_review_schema()
    with connect() as connection:
        row: sqlite3.Row | None = connection.execute(
            """
            SELECT session_id
            FROM completed_interviews
            WHERE id = ?
            """,
            (record_id,),
        ).fetchone()
        if row is None:
            return False

        session_id = int(row["session_id"])
        connection.execute(
            "DELETE FROM completed_interviews WHERE id = ?",
            (record_id,),
        )
        connection.execute(
            """
            UPDATE interview_sessions
            SET transcript_json = '[]', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (session_id,),
        )

    return True


def _build_history_record_from_row(row: sqlite3.Row) -> CompletedInterviewHistoryRecord:
    transcript = [
        TranscriptMessage.model_validate(item)
        for item in json.loads(str(row["transcript_json"]))
    ]
    review_json_text = row["review_json"]
    review = (
        validate_interview_review(json.loads(str(review_json_text)))
        if review_json_text
        else None
    )
    return CompletedInterviewHistoryRecord(
        id=int(row["id"]),
        interview_id=int(row["interview_id"]),
        session_id=int(row["session_id"]),
        target_role=str(row["target_role"]),
        interview_mode=str(row["interview_mode"]),
        style=str(row["style"]),
        round_kind=str(row["round_kind"]) if "round_kind" in row.keys() else "single_round",
        completed_at=str(row["completed_at"]),
        transcript=transcript,
        review=review,
        review_status=str(row["review_status"]) if "review_status" in row.keys() else "ready",
        review_error=str(row["review_error"] or "") if "review_error" in row.keys() else "",
    )


def list_completed_interview_history(*, target_role: str = "") -> list[CompletedInterviewHistoryRecord]:
    initialize_interview_review_schema()
    normalized_target_role = target_role.strip()
    conditions: list[str] = []
    parameters: tuple[str, ...] = ()
    if normalized_target_role:
        conditions.append("interviews.target_role = ?")
        parameters = (normalized_target_role,)
    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    with connect() as connection:
        rows = connection.execute(
            f"""
            SELECT
                completed_interviews.id,
                completed_interviews.interview_id,
                completed_interviews.session_id,
                completed_interviews.transcript_json,
                completed_interviews.review_json,
                completed_interviews.review_status,
                completed_interviews.review_error,
                completed_interviews.completed_at,
                interviews.target_role,
                interviews.interview_mode,
                interview_sessions.style,
                interview_sessions.round_kind
            FROM completed_interviews
            JOIN interviews ON interviews.id = completed_interviews.interview_id
            JOIN interview_sessions ON interview_sessions.id = completed_interviews.session_id
            {where_clause}
            ORDER BY completed_interviews.completed_at DESC, completed_interviews.id DESC
            """,
            parameters,
        ).fetchall()

    return [_build_history_record_from_row(row) for row in rows]


def list_completed_target_roles() -> list[str]:
    initialize_interview_review_schema()
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT DISTINCT target_role
            FROM interviews
            JOIN completed_interviews ON completed_interviews.interview_id = interviews.id
            WHERE target_role <> '' AND completed_interviews.review_json IS NOT NULL
            ORDER BY target_role ASC
            """
        ).fetchall()

    return [str(row["target_role"]) for row in rows]
