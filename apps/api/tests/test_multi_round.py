from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.app.ai_provider import OpenAICompatibleProvider
from apps.api.app.ai_settings import AIProviderSettings
from apps.api.app.interview_review import (
    ABILITY_DIMENSIONS,
    read_completed_interview_by_session,
)
from apps.api.app.interview_rounds import ROUND_TEMPLATES
from apps.api.app.interview_session import InterviewerAction, InterviewSession, save_session
from apps.api.app.main import app
from apps.api.app.resume_analysis import validate_resume_analysis


VALID_RESUME = "# 张三\n\n## 项目经历\n- Mock Interview 面试系统"

VALID_ANALYSIS = {
    "background_summary": "候选人有全栈项目经验",
    "key_projects": ["Mock Interview"],
    "technical_stack": ["React", "FastAPI"],
    "follow_up_topics": ["项目职责", "技术取舍"],
    "risk_points": ["指标不够明确"],
    "unclear_points": [],
    "target_role_notes": "前端工程师",
    "focus_topics": ["项目复盘"],
    "low_priority_follow_up_topics": ["弱相关经历"],
}

VALID_REVIEW = {
    "overall_evaluation": "本次回答覆盖项目背景，但技术取舍与结果指标还可以加强。",
    "highlights": ["能基于真实项目回答"],
    "main_issues": ["结果指标不够明确"],
    "question_reviews": ["第 1 个主问题：回答覆盖背景。"],
    "improved_expression_examples": ["按 背景-行动-结果 表达。"],
    "sample_answers": ["示范性回答：这是一种可参考表达，不是唯一标准答案。"],
    "knowledge_references": ["结构化表达"],
    "learning_framework": ["整理项目指标"],
    "next_practice_suggestions": ["下一次重点练习项目深挖。"],
    "ability_scores": [
        {"dimension": dimension, "score": 3, "rationale": "基于本次回答。"}
        for dimension in ABILITY_DIMENSIONS
    ],
}


def _configure_provider(client: TestClient, base_url: str = "fake://success") -> None:
    client.put(
        "/settings/ai-provider",
        json={
            "activeProviderId": "primary",
            "providers": [
                {
                    "id": "primary",
                    "name": "主供应商",
                    "baseUrl": base_url,
                    "apiKey": "secret-key",
                    "model": "mock-model",
                }
            ],
        },
    )


def _create_interview(
    client: TestClient,
    *,
    mode: str = "multi_round",
    include_hr: bool = False,
) -> int:
    response = client.post(
        "/interviews",
        json={
            "resumeMarkdown": VALID_RESUME,
            "targetRole": "前端工程师",
            "interviewMode": mode,
            "includeHrRound": include_hr,
            "analysis": VALID_ANALYSIS,
        },
    )
    assert response.status_code == 200, response.text
    return int(response.json()["id"])


def _start_session(client: TestClient, interview_id: int, style: str = "study") -> dict:
    response = client.post(f"/interviews/{interview_id}/sessions", json={"style": style})
    return response.json()


def _seed_session(
    *,
    interview_id: int,
    round_kind: str,
    status: str,
) -> InterviewSession:
    return save_session(
        InterviewSession(
            id=0,
            interview_id=interview_id,
            style="study",
            status=status,
            transcript=[],
            main_question_count=1,
            current_main_question_follow_ups=0,
            round_kind=round_kind,
        )
    )


# ---------------------------------------------------------------------------
# 迁移向后兼容：旧库（无新列）初始化后旧行读出默认值
# ---------------------------------------------------------------------------


def test_migration_adds_round_kind_and_include_hr_with_defaults(monkeypatch, tmp_path: Path) -> None:
    import sqlite3

    db_path = tmp_path / "legacy.sqlite3"
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(db_path))
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))

    # 模拟迁移前的旧库：只有 schema_migrations，以及不带新列的 interviews / interview_sessions 旧表。
    connection = sqlite3.connect(db_path)
    connection.execute("CREATE TABLE schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT)")
    connection.execute("INSERT INTO schema_migrations (version) VALUES ('0001_initial')")
    connection.execute(
        """
        CREATE TABLE interviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resume_markdown TEXT NOT NULL,
            target_role TEXT NOT NULL DEFAULT '',
            interview_mode TEXT NOT NULL DEFAULT 'single_round',
            analysis_json TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE interview_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            interview_id INTEGER NOT NULL,
            style TEXT NOT NULL DEFAULT 'study',
            status TEXT NOT NULL DEFAULT 'in_progress',
            transcript_json TEXT NOT NULL DEFAULT '[]',
            main_question_count INTEGER NOT NULL DEFAULT 0,
            current_main_question_follow_ups INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    from apps.api.app.resume_analysis import ResumeAnalysis

    analysis = ResumeAnalysis.model_validate(VALID_ANALYSIS)
    connection.execute(
        "INSERT INTO interviews (resume_markdown, target_role, interview_mode, analysis_json) VALUES (?, ?, ?, ?)",
        ("# 旧简历", "后端工程师", "single_round", analysis.model_dump_json()),
    )
    legacy_interview_id = int(connection.execute("SELECT id FROM interviews").fetchone()[0])
    connection.execute(
        "INSERT INTO interview_sessions (interview_id, style, status) VALUES (?, 'study', 'in_progress')",
        (legacy_interview_id,),
    )
    legacy_session_id = int(connection.execute("SELECT id FROM interview_sessions").fetchone()[0])
    connection.commit()
    connection.close()

    # 触发迁移：初始化 schema 会补 round_kind / include_hr_round 列。
    from apps.api.app.interview_session import initialize_interview_session_schema

    initialize_interview_session_schema()

    from apps.api.app.resume_analysis import read_interview
    from apps.api.app.interview_session import read_session

    interview = read_interview(legacy_interview_id)
    session = read_session(legacy_session_id)
    assert interview is not None and session is not None
    # 旧行读出默认值，不报 KeyError。
    assert interview.interview_mode == "single_round"
    assert interview.include_hr_round is False
    assert session.round_kind == "single_round"


# ---------------------------------------------------------------------------
# POST /interviews 透传 includeHrRound
# ---------------------------------------------------------------------------


def test_confirm_interview_passthrough_include_hr_flag(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client)
        interview_id = _create_interview(client, include_hr=True)
        response = client.get(f"/interviews/{interview_id}")

    assert response.status_code == 200
    assert response.json()["interviewMode"] == "multi_round"
    assert response.json()["includeHrRound"] is True


# ---------------------------------------------------------------------------
# 多轮首轮 / 推进状态机
# ---------------------------------------------------------------------------


def test_multi_round_first_session_is_peer_technical(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client)
        interview_id = _create_interview(client)
        session = _start_session(client, interview_id)

    assert session["roundKind"] == "peer_technical"
    assert session["roundTitle"] == "同事技术面"
    assert "基础技术" in session["roundFocus"]


def test_answer_flow_preserves_round_kind_for_ai_decision(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock.sqlite3"))
    observed_round_kinds: list[str] = []

    def fake_next_action(*args, **kwargs):
        session = kwargs["session"]
        observed_round_kinds.append(session.round_kind)
        if kwargs["starting"]:
            return InterviewerAction(kind="main_question", message="请介绍你的核心项目。")
        return InterviewerAction(kind="follow_up", message="请补充这个方案的边界条件。")

    monkeypatch.setattr(
        "apps.api.app.main.generate_next_interviewer_action_with_provider",
        fake_next_action,
    )

    with TestClient(app) as client:
        _configure_provider(client)
        interview_id = _create_interview(client)
        started = _start_session(client, interview_id)
        response = client.post(
            f"/interview-sessions/{started['id']}/answers",
            json={"answer": "我负责核心链路设计。"},
        )
        advanced = response.json()

    assert response.status_code == 200, response.text
    assert advanced["roundKind"] == "peer_technical"
    assert observed_round_kinds == ["peer_technical", "peer_technical"]


def test_start_next_round_blocked_when_previous_in_progress(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client)
        interview_id = _create_interview(client)
        _start_session(client, interview_id)
        # 首轮还在进行中，禁止再开一轮。
        second = client.post(f"/interviews/{interview_id}/sessions", json={"style": "study"})

    assert second.status_code == 409
    assert "当前轮次尚未结束" in second.json()["detail"]


def test_start_next_round_blocked_when_awaiting_review(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client)
        interview_id = _create_interview(client)
        _seed_session(interview_id=interview_id, round_kind="peer_technical", status="awaiting_review")
        second = client.post(f"/interviews/{interview_id}/sessions", json={"style": "study"})

    assert second.status_code == 409


def test_start_next_round_after_ended_returns_senior(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client)
        interview_id = _create_interview(client)
        _seed_session(interview_id=interview_id, round_kind="peer_technical", status="ended")
        session = _start_session(client, interview_id)

    assert session["roundKind"] == "senior_technical"
    assert session["roundTitle"] == "资深技术面"


def test_start_next_round_after_abandon_allowed(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client)
        interview_id = _create_interview(client)
        # 同事技术面被放弃后视为已处理，可进入资深技术面。
        _seed_session(interview_id=interview_id, round_kind="peer_technical", status="abandoned")
        session = _start_session(client, interview_id)

    assert session["roundKind"] == "senior_technical"


def test_all_rounds_completed_returns_409(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client)
        interview_id = _create_interview(client, include_hr=True)
        for kind in ("peer_technical", "senior_technical", "manager_comprehensive", "hr"):
            _seed_session(interview_id=interview_id, round_kind=kind, status="ended")
        response = client.post(f"/interviews/{interview_id}/sessions", json={"style": "study"})

    assert response.status_code == 409
    assert "所有轮次已完成" in response.json()["detail"]


def test_single_round_session_keeps_single_round_kind(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client)
        interview_id = _create_interview(client, mode="single_round")
        session = _start_session(client, interview_id)

    assert session["roundKind"] == "single_round"
    assert session["roundTitle"] == ""


# ---------------------------------------------------------------------------
# GET /interviews/{id}/rounds
# ---------------------------------------------------------------------------


def test_get_rounds_multi_round_without_hr(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client)
        interview_id = _create_interview(client, include_hr=False)
        _start_session(client, interview_id)
        rounds = client.get(f"/interviews/{interview_id}/rounds").json()

    assert [item["kind"] for item in rounds] == [
        "peer_technical",
        "senior_technical",
        "manager_comprehensive",
    ]
    assert rounds[0]["status"] == "in_progress"
    assert rounds[0]["sessionId"] is not None
    assert rounds[1]["status"] == "pending"
    assert rounds[1]["sessionId"] is None
    assert all("focus" in item and item["focus"] for item in rounds)


def test_get_rounds_multi_round_with_hr_appends_last(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client)
        interview_id = _create_interview(client, include_hr=True)
        rounds = client.get(f"/interviews/{interview_id}/rounds").json()

    assert [item["kind"] for item in rounds][-1] == "hr"
    assert rounds[-1]["title"] == "HR 面"


def test_get_rounds_single_round_returns_empty(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client)
        interview_id = _create_interview(client, mode="single_round")
        rounds = client.get(f"/interviews/{interview_id}/rounds").json()

    assert rounds == []


def test_get_rounds_marks_ended_as_completed_and_abandoned(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client)
        interview_id = _create_interview(client)
        _seed_session(interview_id=interview_id, round_kind="peer_technical", status="ended")
        _seed_session(interview_id=interview_id, round_kind="senior_technical", status="abandoned")
        rounds = client.get(f"/interviews/{interview_id}/rounds").json()

    status_by_kind = {item["kind"]: item["status"] for item in rounds}
    assert status_by_kind["peer_technical"] == "completed"
    assert status_by_kind["senior_technical"] == "abandoned"
    assert status_by_kind["manager_comprehensive"] == "pending"


# ---------------------------------------------------------------------------
# 每轮独立复盘
# ---------------------------------------------------------------------------


def test_each_round_produces_independent_completed_record(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client)
        interview_id = _create_interview(client)

        first = _start_session(client, interview_id)
        client.post(f"/interview-sessions/{first['id']}/end")
        client.post(f"/interview-sessions/{first['id']}/review")

        second = _start_session(client, interview_id)
        client.post(f"/interview-sessions/{second['id']}/end")
        client.post(f"/interview-sessions/{second['id']}/review")

    first_record = read_completed_interview_by_session(first["id"])
    second_record = read_completed_interview_by_session(second["id"])

    assert first["roundKind"] == "peer_technical"
    assert second["roundKind"] == "senior_technical"
    assert first_record is not None and second_record is not None
    assert first_record.session_id != second_record.session_id
    assert first_record.review.overall_evaluation and second_record.review.overall_evaluation


# ---------------------------------------------------------------------------
# AI prompt 注入轮次考察重点（直接调用 prompt 构建方法，沿用现有测试模式）
# ---------------------------------------------------------------------------


def _provider() -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        AIProviderSettings(
            id="primary",
            name="主供应商",
            base_url="https://example.test/v1",
            api_key="secret-key",
            model="mock-model",
        )
    )


def _analysis():
    return validate_resume_analysis(VALID_ANALYSIS)


def _session(round_kind: str) -> InterviewSession:
    return InterviewSession(
        id=1,
        interview_id=1,
        style="study",
        status="in_progress",
        transcript=[],
        main_question_count=1,
        current_main_question_follow_ups=0,
        round_kind=round_kind,
    )


def test_action_prompt_contains_each_round_focus() -> None:
    provider = _provider()
    analysis = _analysis()
    for kind, template in ROUND_TEMPLATES.items():
        prompt = provider._build_interview_action_prompt(
            analysis=analysis,
            target_role="前端工程师",
            session=_session(kind),
            starting=False,
        )
        assert f"当前轮次：{template.title}" in prompt
        assert template.focus in prompt
        assert "你是这一轮的面试官" in prompt


def test_review_prompt_contains_each_round_focus() -> None:
    provider = _provider()
    analysis = _analysis()
    for kind, template in ROUND_TEMPLATES.items():
        prompt = provider._build_interview_review_prompt(
            analysis=analysis,
            target_role="前端工程师",
            session=_session(kind),
        )
        assert f"当前轮次：{template.title}" in prompt
        assert template.focus in prompt


def test_action_prompt_single_round_has_no_round_section() -> None:
    provider = _provider()
    prompt = provider._build_interview_action_prompt(
        analysis=_analysis(),
        target_role="前端工程师",
        session=_session("single_round"),
        starting=False,
    )
    assert "当前轮次" not in prompt
    assert "你是这一轮的面试官" not in prompt


VALID_JD_ANALYSIS = {
    "core_responsibilities": ["负责前端工程化"],
    "required_requirements": ["React", "TypeScript"],
    "bonus_points": ["全栈经验"],
    "likely_probes": ["性能优化取舍"],
    "matching_evidence": ["项目与 JD 职责匹配"],
    "role_gaps": ["JD 要求的某技术栈简历未体现"],
}


def _analysis_with_jd():
    return validate_resume_analysis({**VALID_ANALYSIS, "jobDescriptionAnalysis": VALID_JD_ANALYSIS})


def test_action_prompt_includes_jd_calibration_per_round() -> None:
    provider = _provider()
    analysis = _analysis_with_jd()
    # 各轮次 JD 校准指令的独特短语（避开与 round focus 重叠的通用词）。
    round_emphasis_phrases = [
        ("peer_technical", "围绕 JD 技术栈"),
        ("senior_technical", "JD 场景和岗位缺口"),
        ("manager_comprehensive", "匹配证据"),
        ("hr", "不做技术深挖"),
    ]
    for kind, phrase in round_emphasis_phrases:
        prompt = provider._build_interview_action_prompt(
            analysis=analysis,
            target_role="前端工程师",
            session=_session(kind),
            starting=False,
        )
        # JD 分析上下文进入提问 prompt（验收 1）。
        assert "岗位 JD 校准" in prompt
        assert "负责前端工程化" in prompt
        assert "岗位缺口" in prompt
        # 仍以简历驱动，不逐条拷问 JD 要求（验收 2）。
        assert "仍以简历驱动" in prompt
        # 岗位缺口轻量澄清规则，复用 clarify（验收 3、4）。
        assert "岗位缺口澄清规则" in prompt
        assert "clarify" in prompt
        # 按轮次差异化校准（验收 5）。
        assert phrase in prompt


def test_action_prompt_omits_jd_calibration_without_jd() -> None:
    provider = _provider()
    prompt = provider._build_interview_action_prompt(
        analysis=_analysis(),
        target_role="前端工程师",
        session=_session("peer_technical"),
        starting=False,
    )
    # 无 JD 时不注入 JD 校准段落，无 JD 面试流程零回归（验收 7）。
    assert "岗位 JD 校准" not in prompt
    assert "岗位缺口澄清规则" not in prompt
    assert "负责前端工程化" not in prompt
