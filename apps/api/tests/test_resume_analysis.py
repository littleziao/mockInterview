from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.app.main import app
from apps.api.app.resume_analysis import validate_resume_analysis


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


def test_resume_analysis_rejects_invalid_ai_structure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock_interview.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client, "fake://invalid-analysis")
        response = client.post(
            "/resume-analyses/generate",
            json={
                "resumeMarkdown": "# 张三\n\n## 项目经历\n- 面试系统",
                "targetRole": "前端工程师",
            },
        )

    assert response.status_code == 502
    assert response.json() == {"detail": "AI 返回的简历分析结构无效"}


def test_resume_analysis_accepts_common_ai_key_and_list_variants() -> None:
    analysis = validate_resume_analysis(
        {
            "analysis": {
                "backgroundSummary": "候选人有全栈项目经验",
                "关键项目": "Mock Interview\nAI Provider 设置",
                "technicalStack": ["React", "FastAPI"],
                "可能追问点": ["项目职责", "技术取舍"],
                "风险点": "指标不够明确",
                "表达不清之处": "",
                "targetRoleNotes": "前端工程师",
                "希望重点练习的内容": "项目复盘",
                "不希望重点追问的内容": "弱相关经历",
            }
        }
    )

    assert analysis.background_summary == "候选人有全栈项目经验"
    assert analysis.key_projects == ["Mock Interview", "AI Provider 设置"]
    assert analysis.risk_points == ["指标不够明确"]
    assert analysis.unclear_points == []
    assert analysis.low_priority_follow_up_topics == ["弱相关经历"]


def test_user_edits_confirms_and_reads_saved_resume_analysis(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock_interview.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client)
        generated_response = client.post(
            "/resume-analyses/generate",
            json={
                "resumeMarkdown": "# 张三\n\n## 项目经历\n- Mock Interview",
                "targetRole": "前端工程师",
            },
        )
        generated_analysis = generated_response.json()
        generated_analysis["backgroundSummary"] = "用户编辑后的背景摘要"
        generated_analysis["focusTopics"] = ["状态管理表达", "项目复盘"]
        generated_analysis["lowPriorityFollowUpTopics"] = ["弱相关外包经历"]

        save_response = client.post(
            "/interviews",
            json={
                "resumeMarkdown": "# 张三\n\n## 项目经历\n- Mock Interview",
                "targetRole": "前端工程师",
                "analysis": {
                    "background_summary": generated_analysis["backgroundSummary"],
                    "key_projects": generated_analysis["keyProjects"],
                    "technical_stack": generated_analysis["technicalStack"],
                    "follow_up_topics": generated_analysis["followUpTopics"],
                    "risk_points": generated_analysis["riskPoints"],
                    "unclear_points": generated_analysis["unclearPoints"],
                    "target_role_notes": generated_analysis["targetRoleNotes"],
                    "focus_topics": generated_analysis["focusTopics"],
                    "low_priority_follow_up_topics": generated_analysis["lowPriorityFollowUpTopics"],
                },
            },
        )
        read_response = client.get(f"/interviews/{save_response.json()['id']}")

    assert generated_response.status_code == 200
    assert save_response.status_code == 200
    assert read_response.status_code == 200
    assert read_response.json()["analysis"]["backgroundSummary"] == "用户编辑后的背景摘要"
    assert read_response.json()["analysis"]["focusTopics"] == ["状态管理表达", "项目复盘"]
    assert read_response.json()["analysis"]["lowPriorityFollowUpTopics"] == ["弱相关外包经历"]
