from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.app.interview_session import (
    DEFAULT_MAIN_QUESTIONS,
    DEFAULT_MAX_FOLLOW_UPS,
    InterviewSession,
    TranscriptMessage,
    apply_interviewer_action,
    append_candidate_answer,
    resolve_interviewer_action,
    validate_interviewer_action,
)
from apps.api.app.main import app


VALID_RESUME = "# 张三\n\n## 项目经历\n- Mock Interview 面试系统"


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


def _create_confirmed_interview(client: TestClient) -> int:
    response = client.post(
        "/interviews",
        json={
            "resumeMarkdown": VALID_RESUME,
            "targetRole": "前端工程师",
            "analysis": {
                "background_summary": "候选人有全栈项目经验",
                "key_projects": ["Mock Interview"],
                "technical_stack": ["React", "FastAPI"],
                "follow_up_topics": ["项目职责", "技术取舍"],
                "risk_points": ["指标不够明确"],
                "unclear_points": [],
                "target_role_notes": "前端工程师",
                "focus_topics": ["项目复盘"],
                "low_priority_follow_up_topics": ["弱相关经历"],
            },
        },
    )
    assert response.status_code == 200
    return int(response.json()["id"])


def _start_session(client: TestClient, interview_id: int, style: str = "study") -> dict:
    response = client.post(f"/interviews/{interview_id}/sessions", json={"style": style})
    assert response.status_code == 200, response.text
    return response.json()


def _answer(client: TestClient, session_id: int, answer: str) -> dict:
    response = client.post(
        f"/interview-sessions/{session_id}/answers",
        json={"answer": answer},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _latest_interviewer(session: dict) -> dict:
    return next(message for message in reversed(session["transcript"]) if message["role"] == "interviewer")


def _answer_count_for_latest_main_question(session: dict) -> int:
    interviewer_messages = [m for m in session["transcript"] if m["role"] == "interviewer"]
    if not interviewer_messages:
        return 0
    latest_index = interviewer_messages[-1]["mainQuestionIndex"]
    return sum(
        1
        for message in session["transcript"]
        if message["role"] == "candidate" and message["mainQuestionIndex"] == latest_index
    )


def test_starting_a_single_round_interview_returns_first_main_question(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock_interview.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client)
        interview_id = _create_confirmed_interview(client)
        session = _start_session(client, interview_id)

    assert session["status"] == "in_progress"
    assert session["mainQuestionCount"] == 1
    assert session["currentMainQuestionFollowUps"] == 0
    assert session["mainQuestionLimit"] == DEFAULT_MAIN_QUESTIONS
    assert session["followUpLimit"] == DEFAULT_MAX_FOLLOW_UPS
    assert len(session["transcript"]) == 1
    first = session["transcript"][0]
    assert first["role"] == "interviewer"
    assert first["kind"] == "main_question"
    assert first["mainQuestionIndex"] == 0


def test_default_interview_style_is_study(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock_interview.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client)
        interview_id = _create_confirmed_interview(client)
        # 不传 body 时应使用默认学习梳理面。
        response = client.post(f"/interviews/{interview_id}/sessions")
        session = response.json()

    assert response.status_code == 200, response.text
    assert session["style"] == "study"


def test_can_select_pressure_style(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock_interview.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client)
        interview_id = _create_confirmed_interview(client)
        session = _start_session(client, interview_id, style="pressure")

    assert session["style"] == "pressure"


def test_interview_shows_only_one_question_at_a_time(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock_interview.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client)
        interview_id = _create_confirmed_interview(client)
        session = _start_session(client, interview_id)
        # 提交一次文字回答后，面试官只追加一条消息。
        advanced = _answer(client, session["id"], "我负责简历分析和 AI Provider 接入。")

    assert len(advanced["transcript"]) == len(session["transcript"]) + 2
    assert advanced["transcript"][-1]["role"] == "interviewer"


def test_answer_produces_follow_up(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock_interview.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client)
        interview_id = _create_confirmed_interview(client)
        session = _start_session(client, interview_id)
        advanced = _answer(client, session["id"], "我负责简历分析模块。")

    latest = _latest_interviewer(advanced)
    assert latest["kind"] == "follow_up"
    assert advanced["currentMainQuestionFollowUps"] == 1
    assert advanced["mainQuestionCount"] == 1


def test_answer_produces_lightweight_clarify(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock_interview.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client)
        interview_id = _create_confirmed_interview(client)
        session = _start_session(client, interview_id)
        _answer(client, session["id"], "我负责简历分析模块。")
        advanced = _answer(client, session["id"], "用到了 Pydantic 做结构校验。")

    latest = _latest_interviewer(advanced)
    assert latest["kind"] == "clarify"
    assert advanced["currentMainQuestionFollowUps"] == 1


def test_each_answer_persists_in_progress_interview(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock_interview.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client)
        interview_id = _create_confirmed_interview(client)
        session = _start_session(client, interview_id)
        after_answer = _answer(client, session["id"], "我负责简历分析模块。")

        # 模拟刷新：重新读取进行中面试，回答与追问都应被保存。
        reloaded = client.get(f"/interview-sessions/{session['id']}").json()

    assert reloaded["status"] == "in_progress"
    assert reloaded["transcript"] == after_answer["transcript"]
    assert any(message["role"] == "candidate" for message in reloaded["transcript"])


def test_user_can_manually_end_interview_with_full_transcript(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock_interview.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client)
        interview_id = _create_confirmed_interview(client)
        session = _start_session(client, interview_id)
        advanced = _answer(client, session["id"], "我负责简历分析模块。")
        ended = client.post(f"/interview-sessions/{session['id']}/end").json()
        reloaded = client.get(f"/interview-sessions/{session['id']}").json()

        # 已结束的面试不能再作答，保证对话上下文不再变化。
        second_answer = client.post(
            f"/interview-sessions/{session['id']}/answers",
            json={"answer": "补充内容"},
        )

    assert ended["status"] == "ended"
    assert ended["transcript"] == advanced["transcript"]
    assert reloaded["status"] == "ended"
    assert second_answer.status_code == 400


def test_starting_session_requires_existing_interview(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock_interview.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client)
        response = client.post("/interviews/404/sessions", json={"style": "study"})

    assert response.status_code == 404


def test_starting_session_requires_configured_provider(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock_interview.sqlite3"))

    with TestClient(app) as client:
        interview_id = _create_confirmed_interview(client)
        response = client.post(f"/interviews/{interview_id}/sessions", json={"style": "study"})

    assert response.status_code == 400
    assert response.json() == {"detail": "请先新增并选择一个模型供应商"}


def test_invalid_ai_action_structure_returns_502(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock_interview.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client, "fake://invalid-action")
        interview_id = _create_confirmed_interview(client)
        response = client.post(f"/interviews/{interview_id}/sessions", json={"style": "study"})

    assert response.status_code == 502
    assert response.json() == {"detail": "AI 返回的面试官动作结构无效"}


def test_validate_interviewer_action_accepts_common_variants() -> None:
    action = validate_interviewer_action({"action": {"type": "追问", "问题": "展开讲讲"}})
    assert action.kind == "follow_up"
    assert action.message == "展开讲讲"


def test_follow_up_beyond_limit_is_downgraded_to_new_main_question() -> None:
    session = InterviewSession(
        id=1,
        interview_id=1,
        style="study",
        status="in_progress",
        transcript=[],
        main_question_count=1,
        current_main_question_follow_ups=DEFAULT_MAX_FOLLOW_UPS,
    )

    resolved = resolve_interviewer_action(
        {"kind": "follow_up", "message": "继续深挖"},
        session,
        starting=False,
    )
    assert resolved.kind == "main_question"

    message, main_question_count, follow_ups = apply_interviewer_action(session, resolved)
    assert message.kind == "main_question"
    assert main_question_count == 2
    assert follow_ups == 0


def test_main_question_beyond_limit_is_downgraded_to_clarify() -> None:
    session = InterviewSession(
        id=1,
        interview_id=1,
        style="study",
        status="in_progress",
        transcript=[],
        main_question_count=DEFAULT_MAIN_QUESTIONS,
        current_main_question_follow_ups=DEFAULT_MAX_FOLLOW_UPS,
    )

    resolved = resolve_interviewer_action(
        {"kind": "main_question", "message": "再来一题"},
        session,
        starting=False,
    )
    assert resolved.kind == "clarify"

    message, main_question_count, follow_ups = apply_interviewer_action(session, resolved)
    assert message.kind == "clarify"
    assert main_question_count == DEFAULT_MAIN_QUESTIONS
    assert follow_ups == DEFAULT_MAX_FOLLOW_UPS


def test_candidate_answer_is_attributed_to_current_main_question() -> None:
    session = InterviewSession(
        id=1,
        interview_id=1,
        style="study",
        status="in_progress",
        transcript=[TranscriptMessage(role="interviewer", content="q", kind="main_question", main_question_index=2)],
        main_question_count=3,
        current_main_question_follow_ups=0,
    )

    message = append_candidate_answer(session, "我的回答")
    assert message.role == "candidate"
    assert message.main_question_index == 2


def test_full_session_runs_within_question_and_follow_up_limits(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock_interview.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client)
        interview_id = _create_confirmed_interview(client)
        session = _start_session(client, interview_id)
        session_id = session["id"]

        current = session
        # 驱动足够多轮回答，触发多次换题与澄清，但不得越过硬上限。
        for index in range(30):
            current = _answer(client, session_id, f"第 {index + 1} 段回答")
            assert current["mainQuestionCount"] <= DEFAULT_MAIN_QUESTIONS
            assert current["currentMainQuestionFollowUps"] <= DEFAULT_MAX_FOLLOW_UPS

        ended = client.post(f"/interview-sessions/{session_id}/end").json()

    assert ended["status"] == "ended"
    assert ended["mainQuestionCount"] == DEFAULT_MAIN_QUESTIONS
    main_questions = [
        message
        for message in ended["transcript"]
        if message["role"] == "interviewer" and message["kind"] == "main_question"
    ]
    assert len(main_questions) == DEFAULT_MAIN_QUESTIONS
    # 面试官视角全程不展示参考答案。
    assert all(
        "参考答案" not in message["content"]
        for message in ended["transcript"]
        if message["role"] == "interviewer"
    )
    assert _answer_count_for_latest_main_question(ended) >= 1
