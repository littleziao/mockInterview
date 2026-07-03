from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.app.interview_review import (
    ABILITY_DIMENSIONS,
    InterviewReview,
    list_completed_interview_history,
    read_completed_interview_by_session,
    save_completed_interview,
)
from apps.api.app.interview_session import InterviewSession, TranscriptMessage, read_session, save_session
from apps.api.app.main import app
from apps.api.app.resume_analysis import ResumeAnalysis, read_interview, save_interview


VALID_ANALYSIS = ResumeAnalysis(
    background_summary="候选人有全栈项目经验",
    key_projects=["Mock Interview"],
    technical_stack=["React", "FastAPI"],
    follow_up_topics=["项目职责", "技术取舍"],
    risk_points=["指标不够明确"],
    unclear_points=[],
    target_role_notes="前端工程师",
    focus_topics=["项目复盘"],
    low_priority_follow_up_topics=["弱相关经历"],
)


def _review(score: int) -> InterviewReview:
    return InterviewReview(
        overall_evaluation=f"本次整体评分为 {score}。",
        highlights=["能基于真实项目回答"],
        main_issues=["结果指标不够明确"],
        question_reviews=["第 1 个主问题：回答覆盖背景。"],
        improved_expression_examples=["按 背景-行动-结果 表达。"],
        sample_answers=["示范性回答：这是一种可参考表达，不是唯一标准答案。"],
        knowledge_references=["结构化表达"],
        learning_framework=["整理项目指标"],
        next_practice_suggestions=["下一次重点练习项目深挖。"],
        ability_scores=[
            {"dimension": dimension, "score": score, "rationale": "基于本次回答。"}
            for dimension in ABILITY_DIMENSIONS
        ],
    )


def _interview(target_role: str, *, interview_mode: str = "single_round") -> int:
    return save_interview(
        resume_markdown="# 张三\n\n## 项目经历\n- Mock Interview",
        target_role=target_role,
        interview_mode=interview_mode,
        analysis=VALID_ANALYSIS,
    ).id


def _session(
    *,
    interview_id: int,
    status: str,
    answer: str,
    round_kind: str = "single_round",
) -> InterviewSession:
    return save_session(
        InterviewSession(
            id=0,
            interview_id=interview_id,
            style="study",
            status=status,
            transcript=[
                TranscriptMessage(
                    role="interviewer",
                    content="请介绍你的核心项目。",
                    kind="main_question",
                    main_question_index=0,
                ),
                TranscriptMessage(
                    role="candidate",
                    content=answer,
                    main_question_index=0,
                ),
            ],
            main_question_count=1,
            current_main_question_follow_ups=0,
            round_kind=round_kind,
        )
    )


def _seed_history() -> tuple[InterviewSession, InterviewSession, InterviewSession]:
    frontend_interview = _interview("前端工程师")
    backend_interview = _interview("后端工程师")

    older_completed = _session(interview_id=frontend_interview, status="ended", answer="我负责前端工作台。")
    newer_completed = _session(interview_id=backend_interview, status="ended", answer="我负责 API 和 SQLite。")
    abandoned = _session(interview_id=frontend_interview, status="abandoned", answer="这场练习放弃了。")

    save_completed_interview(older_completed, _review(3))
    save_completed_interview(newer_completed, _review(5))
    return older_completed, newer_completed, abandoned


def test_repository_lists_only_completed_interviews_and_can_filter_by_target_role(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock.sqlite3"))
    _seed_history()

    all_records = list_completed_interview_history()
    frontend_records = list_completed_interview_history(target_role="前端工程师")

    assert [record.target_role for record in all_records] == ["后端工程师", "前端工程师"]
    assert [record.target_role for record in frontend_records] == ["前端工程师"]
    assert all(record.review.overall_evaluation for record in all_records)
    assert all(record.transcript for record in all_records)


def test_history_api_returns_records_target_roles_and_six_dimension_trends(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock.sqlite3"))
    older_completed, newer_completed, abandoned = _seed_history()

    with TestClient(app) as client:
        response = client.get("/history")
        filtered = client.get("/history", params={"target_role": "前端工程师"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert [record["sessionId"] for record in body["records"]] == [
        newer_completed.id,
        older_completed.id,
    ]
    assert abandoned.id not in [record["sessionId"] for record in body["records"]]
    assert body["targetRoles"] == ["前端工程师", "后端工程师"]
    assert [trend["dimension"] for trend in body["trends"]] == list(ABILITY_DIMENSIONS)
    assert body["trends"][0]["points"] == [
        {
            "historyRecordId": body["records"][1]["id"],
            "completedAt": body["records"][1]["completedAt"],
            "score": 3,
        },
        {
            "historyRecordId": body["records"][0]["id"],
            "completedAt": body["records"][0]["completedAt"],
            "score": 5,
        },
    ]
    assert body["trends"][0]["averageScore"] == 4

    assert filtered.status_code == 200
    assert [record["targetRole"] for record in filtered.json()["records"]] == ["前端工程师"]
    assert filtered.json()["trends"][0]["points"][0]["score"] == 3


def test_delete_completed_history_record_removes_review_transcript_and_rebuilds_trends(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock.sqlite3"))
    older_completed, newer_completed, _ = _seed_history()
    deleted_record = read_completed_interview_by_session(older_completed.id)
    assert deleted_record is not None

    with TestClient(app) as client:
        response = client.delete(f"/history/{deleted_record.id}")
        history_response = client.get("/history")
        deleted_session_response = client.get(f"/interview-sessions/{older_completed.id}")

    assert response.status_code == 204, response.text
    assert deleted_session_response.status_code == 404
    assert deleted_session_response.json() == {"detail": "已完成面试记录不存在"}
    assert read_completed_interview_by_session(older_completed.id) is None
    scrubbed_session = read_session(older_completed.id)
    assert scrubbed_session is not None
    assert scrubbed_session.status == "ended"
    assert scrubbed_session.transcript == []
    assert read_interview(older_completed.interview_id) is not None

    assert history_response.status_code == 200
    body = history_response.json()
    assert [record["sessionId"] for record in body["records"]] == [newer_completed.id]
    assert body["trends"][0]["points"] == [
        {
            "historyRecordId": body["records"][0]["id"],
            "completedAt": body["records"][0]["completedAt"],
            "score": 5,
        }
    ]
    assert body["trends"][0]["averageScore"] == 5


def test_delete_one_multi_round_completed_history_record_keeps_other_rounds(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock.sqlite3"))
    interview_id = _interview("前端工程师", interview_mode="multi_round")
    peer_round = _session(
        interview_id=interview_id,
        status="ended",
        answer="我负责同事技术面。",
        round_kind="peer_technical",
    )
    senior_round = _session(
        interview_id=interview_id,
        status="ended",
        answer="我负责资深技术面。",
        round_kind="senior_technical",
    )
    save_completed_interview(peer_round, _review(2))
    save_completed_interview(senior_round, _review(4))
    peer_record = read_completed_interview_by_session(peer_round.id)
    senior_record = read_completed_interview_by_session(senior_round.id)
    assert peer_record is not None
    assert senior_record is not None

    with TestClient(app) as client:
        response = client.delete(f"/history/{peer_record.id}")
        history_response = client.get("/history")

    assert response.status_code == 204, response.text
    assert read_completed_interview_by_session(peer_round.id) is None
    assert read_completed_interview_by_session(senior_round.id) is not None
    body = history_response.json()
    assert [record["sessionId"] for record in body["records"]] == [senior_round.id]
    assert body["records"][0]["roundKind"] == "senior_technical"
    assert body["trends"][0]["points"][0]["score"] == 4


def test_delete_completed_history_record_returns_404_for_missing_record(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock.sqlite3"))

    with TestClient(app) as client:
        response = client.delete("/history/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "已完成面试记录不存在"}
