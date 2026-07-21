from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient

from apps.api.app.main import app
from apps.api.app.resume_analysis import (
    list_resume_analysis_records,
    read_interview,
    read_resume_analysis_record,
    validate_resume_analysis,
)


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
                "interviewMode": "multi_round",
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
    assert read_response.json()["interviewMode"] == "multi_round"
    assert read_response.json()["analysis"]["focusTopics"] == ["状态管理表达", "项目复盘"]
    assert read_response.json()["analysis"]["lowPriorityFollowUpTopics"] == ["弱相关外包经历"]


def test_successful_resume_analysis_generation_creates_history_record(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock_interview.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client)
        response = client.post(
            "/resume-analyses/generate",
            json={
                "resumeMarkdown": "# 张三\n\n## 项目经历\n- Mock Interview",
                "targetRole": "前端工程师",
            },
        )

    records = list_resume_analysis_records()

    assert response.status_code == 200
    assert len(records) == 1
    record = records[0]
    assert record.resume_markdown == "# 张三\n\n## 项目经历\n- Mock Interview"
    assert record.target_role == "前端工程师"
    assert record.analysis.background_summary == "张三 具备项目交付和工程实现经验。"
    assert record.created_at
    assert record.last_used_at == record.created_at
    assert record.use_count == 0


def test_resume_analysis_generation_accepts_and_saves_target_job_description(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock_interview.sqlite3"))
    target_job_description = "职责：负责 React 工作台体验；要求：TypeScript、接口协作。"

    with TestClient(app) as client:
        _configure_provider(client)
        response = client.post(
            "/resume-analyses/generate",
            json={
                "resumeMarkdown": "# 张三\n\n## 项目经历\n- Mock Interview",
                "targetRole": "前端工程师",
                "targetJobDescription": target_job_description,
            },
        )
        list_response = client.get("/resume-analysis-records")
        record_id = list_resume_analysis_records()[0].id
        detail_response = client.get(f"/resume-analysis-records/{record_id}")

    record = list_resume_analysis_records()[0]

    assert response.status_code == 200
    assert response.json()["targetRoleNotes"] == "目标岗位 JD 已作为校准输入，后续面试应优先核对岗位职责、技术要求和简历匹配证据。"
    assert record.target_job_description == target_job_description
    assert list_response.json()["records"][0]["hasTargetJobDescription"] is True
    assert "targetJobDescription" not in list_response.json()["records"][0]
    assert detail_response.json()["targetJobDescription"] == target_job_description
    # 有 JD 时返回结构化岗位 JD 分析；目标岗位已填则不返回推断岗位。
    assert response.json()["inferredTargetRole"] is None
    jd_analysis = response.json()["jobDescriptionAnalysis"]
    assert jd_analysis is not None
    assert jd_analysis["coreResponsibilities"] == ["围绕目标岗位 JD 校准的重点职责推进练习"]
    assert jd_analysis["requiredRequirements"] == ["JD 标注的必备技术能力"]
    assert jd_analysis["bonusPoints"] == ["JD 中可作为加分项突出的经历"]
    assert jd_analysis["likelyProbes"] == ["JD 中可能被追问的职责与技术点"]
    assert jd_analysis["matchingEvidence"] == ["简历项目与 JD 职责匹配的部分"]
    assert jd_analysis["roleGaps"] == ["JD 要求但简历未直接体现的部分"]


def test_resume_analysis_generation_rejects_overlong_target_job_description(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock_interview.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client)
        response = client.post(
            "/resume-analyses/generate",
            json={
                "resumeMarkdown": "# 张三\n\n## 项目经历\n- Mock Interview",
                "targetRole": "前端工程师",
                "targetJobDescription": "前" * 8001,
            },
        )

    assert response.status_code == 400
    assert response.json() == {"detail": "目标岗位 JD 不能超过 8000 字符"}
    assert list_resume_analysis_records() == []


def test_existing_resume_analysis_records_without_target_job_description_read_as_empty(
    monkeypatch, tmp_path: Path
) -> None:
    database_path = tmp_path / "mock_interview.sqlite3"
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(database_path))
    legacy_analysis = validate_resume_analysis(
        {
            "background_summary": "旧记录摘要",
            "key_projects": ["旧项目"],
            "technical_stack": ["React"],
            "follow_up_topics": ["项目职责"],
        }
    )

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE resume_analysis_records (
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
            """
            INSERT INTO resume_analysis_records (
                resume_markdown,
                target_role,
                analysis_json
            )
            VALUES (?, ?, ?)
            """,
            ("# 旧简历", "前端工程师", legacy_analysis.model_dump_json()),
        )

    records = list_resume_analysis_records()
    detail = read_resume_analysis_record(records[0].id)

    assert records[0].target_job_description == ""
    assert detail is not None
    assert detail.target_job_description == ""


def test_repeated_resume_analysis_generation_creates_independent_records(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock_interview.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client)
        for _ in range(2):
            response = client.post(
                "/resume-analyses/generate",
                json={
                    "resumeMarkdown": "# 张三\n\n## 项目经历\n- Mock Interview",
                    "targetRole": "前端工程师",
                },
            )
            assert response.status_code == 200

        list_response = client.get("/resume-analysis-records")

    assert list_response.status_code == 200
    body = list_response.json()
    assert [record["targetRole"] for record in body["records"]] == ["前端工程师", "前端工程师"]
    assert body["records"][0]["id"] != body["records"][1]["id"]
    assert body["records"][0]["summary"] == "张三 具备项目交付和工程实现经验。"
    assert body["records"][0]["createdAt"]
    assert body["records"][0]["lastUsedAt"] == body["records"][0]["createdAt"]
    assert body["records"][0]["useCount"] == 0
    assert "resumeMarkdown" not in body["records"][0]
    assert body["records"][0]["keyProjects"] == ["基于 Markdown 简历识别出的核心项目"]
    assert body["records"][0]["technicalStack"] == ["TypeScript", "React", "FastAPI", "SQLite"]
    assert body["records"][0]["followUpTopics"] == ["项目职责边界", "技术选型取舍", "复杂问题排查"]


def test_resume_analysis_record_can_be_read_with_full_resume_and_analysis(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock_interview.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client)
        client.post(
            "/resume-analyses/generate",
            json={
                "resumeMarkdown": "# 张三\n\n## 项目经历\n- Mock Interview",
                "targetRole": "前端工程师",
            },
        )
        record_id = list_resume_analysis_records()[0].id
        response = client.get(f"/resume-analysis-records/{record_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == record_id
    assert body["resumeMarkdown"] == "# 张三\n\n## 项目经历\n- Mock Interview"
    assert body["targetRole"] == "前端工程师"
    assert body["analysis"]["backgroundSummary"] == "张三 具备项目交付和工程实现经验。"


def test_confirming_interview_from_resume_analysis_record_updates_confirmed_version_and_usage(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock_interview.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client)
        client.post(
            "/resume-analyses/generate",
            json={
                "resumeMarkdown": "# 初始简历\n\n- Mock Interview",
                "targetRole": "前端工程师",
                "targetJobDescription": "初始 JD",
            },
        )
        source_record = list_resume_analysis_records()[0]

        response = client.post(
            "/interviews",
            json={
                "resumeMarkdown": "# 确认版简历\n\n- Mock Interview\n- 指标补充",
                "targetRole": "资深前端工程师",
                "targetJobDescription": "确认版 JD：负责复杂前端工程。",
                "interviewMode": "single_round",
                "sourceResumeAnalysisRecordId": source_record.id,
                "analysis": {
                    "background_summary": "用户确认后的背景摘要",
                    "key_projects": ["Mock Interview", "AI Provider 设置"],
                    "technical_stack": ["React", "FastAPI"],
                    "follow_up_topics": ["项目职责", "技术取舍"],
                    "risk_points": ["指标需要量化"],
                    "unclear_points": [],
                    "target_role_notes": "偏资深前端岗位",
                    "focus_topics": ["架构取舍"],
                    "low_priority_follow_up_topics": ["弱相关经历"],
                },
            },
        )
        read_response = client.get(f"/interviews/{response.json()['id']}")

    refreshed_record = list_resume_analysis_records()[0]
    interview = read_interview(response.json()["id"])

    assert response.status_code == 200
    assert response.json()["sourceResumeAnalysisRecordId"] == source_record.id
    assert read_response.json()["sourceResumeAnalysisRecordId"] == source_record.id
    assert interview is not None
    assert interview.source_resume_analysis_record_id == source_record.id
    assert refreshed_record.resume_markdown == "# 确认版简历\n\n- Mock Interview\n- 指标补充"
    assert refreshed_record.target_role == "资深前端工程师"
    assert refreshed_record.target_job_description == "确认版 JD：负责复杂前端工程。"
    assert interview.target_job_description == "确认版 JD：负责复杂前端工程。"
    assert read_response.json()["targetJobDescription"] == "确认版 JD：负责复杂前端工程。"
    assert refreshed_record.analysis.background_summary == "用户确认后的背景摘要"
    assert refreshed_record.use_count == 1
    assert refreshed_record.last_used_at >= source_record.last_used_at


def test_delete_resume_analysis_record_removes_it_from_history(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock_interview.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client)
        client.post(
            "/resume-analyses/generate",
            json={
                "resumeMarkdown": "# 张三\n\n## 项目经历\n- Mock Interview",
                "targetRole": "前端工程师",
            },
        )
        record_id = list_resume_analysis_records()[0].id

        delete_response = client.delete(f"/resume-analysis-records/{record_id}")
        list_response = client.get("/resume-analysis-records")
        detail_response = client.get(f"/resume-analysis-records/{record_id}")

    assert delete_response.status_code == 204, delete_response.text
    assert list_response.status_code == 200
    assert list_response.json() == {"records": []}
    assert detail_response.status_code == 404
    assert detail_response.json() == {"detail": "简历分析记录不存在"}
    assert read_resume_analysis_record(record_id) is None


def test_delete_resume_analysis_record_returns_404_for_missing_record(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock_interview.sqlite3"))

    with TestClient(app) as client:
        response = client.delete("/resume-analysis-records/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "简历分析记录不存在"}


def test_deleting_resume_analysis_record_keeps_linked_interview_usable(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock_interview.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client)
        client.post(
            "/resume-analyses/generate",
            json={
                "resumeMarkdown": "# 初始简历\n\n- Mock Interview",
                "targetRole": "前端工程师",
                "targetJobDescription": "JD 快照：React 平台体验。",
            },
        )
        source_record = list_resume_analysis_records()[0]

        confirm_response = client.post(
            "/interviews",
            json={
                "resumeMarkdown": "# 确认版简历\n\n- Mock Interview\n- 指标补充",
                "targetRole": "资深前端工程师",
                "targetJobDescription": "JD 快照：React 平台体验。",
                "interviewMode": "single_round",
                "sourceResumeAnalysisRecordId": source_record.id,
                "analysis": {
                    "background_summary": "用户确认后的背景摘要",
                    "key_projects": ["Mock Interview", "AI Provider 设置"],
                    "technical_stack": ["React", "FastAPI"],
                    "follow_up_topics": ["项目职责", "技术取舍"],
                    "risk_points": ["指标需要量化"],
                    "unclear_points": [],
                    "target_role_notes": "偏资深前端岗位",
                    "focus_topics": ["架构取舍"],
                    "low_priority_follow_up_topics": ["弱相关经历"],
                },
            },
        )
        interview_id = confirm_response.json()["id"]

        # 来源简历分析记录被删除：面试记录本身仍可读、可继续、可复盘，
        # 关联只用于追溯，不被简历分析记录的生命周期控制。
        delete_response = client.delete(f"/resume-analysis-records/{source_record.id}")
        interview_after_delete = client.get(f"/interviews/{interview_id}")
        history_after_delete = client.get("/resume-analysis-records")

    assert delete_response.status_code == 204, delete_response.text
    assert confirm_response.status_code == 200
    assert interview_after_delete.status_code == 200
    assert interview_after_delete.json()["id"] == interview_id
    assert interview_after_delete.json()["targetJobDescription"] == "JD 快照：React 平台体验。"
    # 追溯关联保留为原 id（悬空引用无害），面试生命周期不受影响。
    assert interview_after_delete.json()["sourceResumeAnalysisRecordId"] == source_record.id
    assert history_after_delete.json() == {"records": []}
    assert read_interview(interview_id) is not None
    assert read_interview(interview_id).source_resume_analysis_record_id == source_record.id
    assert read_interview(interview_id).target_job_description == "JD 快照：React 平台体验。"


def test_resume_analysis_generation_omits_jd_analysis_without_jd(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock_interview.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client)
        response = client.post(
            "/resume-analyses/generate",
            json={
                "resumeMarkdown": "# 张三\n\n## 项目经历\n- Mock Interview",
                "targetRole": "前端工程师",
            },
        )

    assert response.status_code == 200
    # 未提供 JD 时不编造岗位 JD 分析，也不返回推断岗位。
    assert response.json()["jobDescriptionAnalysis"] is None
    assert response.json()["inferredTargetRole"] is None


def test_resume_analysis_generation_infers_target_role_when_blank(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock_interview.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client)
        response = client.post(
            "/resume-analyses/generate",
            json={
                "resumeMarkdown": "# 张三\n\n## 项目经历\n- Mock Interview",
                "targetRole": "",
                "targetJobDescription": "职责：负责前端工程化和组件库建设。",
            },
        )

    assert response.status_code == 200
    # 只提供 JD、未填目标岗位时，返回推断岗位标题，同时仍生成 JD 分析。
    assert response.json()["inferredTargetRole"] == "前端工程师（推断）"
    assert response.json()["jobDescriptionAnalysis"] is not None


def test_validate_resume_analysis_tolerates_job_description_analysis_shapes() -> None:
    # camelCase 与中文别名都能归一为 JD 分析字段；空白推断岗位归一为 None。
    analysis = validate_resume_analysis(
        {
            "background_summary": "摘要",
            "key_projects": ["项目"],
            "technical_stack": ["React"],
            "follow_up_topics": ["追问"],
            "jobDescriptionAnalysis": {
                "coreResponsibilities": ["职责A", "职责B"],
                "必备要求": "TypeScript\nReact",
                "加分项": ["全栈"],
            },
            "inferredTargetRole": "  ",
        }
    )
    assert analysis.job_description_analysis is not None
    assert analysis.job_description_analysis.core_responsibilities == ["职责A", "职责B"]
    assert analysis.job_description_analysis.required_requirements == ["TypeScript", "React"]
    assert analysis.job_description_analysis.bonus_points == ["全栈"]
    assert analysis.inferred_target_role is None

    # JD 分析子对象不是 dict 时整体丢弃，主分析不受影响。
    invalid = validate_resume_analysis(
        {
            "background_summary": "摘要",
            "key_projects": ["项目"],
            "technical_stack": ["React"],
            "follow_up_topics": ["追问"],
            "岗位 JD 分析": "不是对象",
        }
    )
    assert invalid.job_description_analysis is None

    # JD 分析子对象六个字段全空时视为无 JD 分析。
    empty = validate_resume_analysis(
        {
            "background_summary": "摘要",
            "key_projects": ["项目"],
            "technical_stack": ["React"],
            "follow_up_topics": ["追问"],
            "jobDescriptionAnalysis": {},
        }
    )
    assert empty.job_description_analysis is None

    # 非空推断岗位保留。
    inferred = validate_resume_analysis(
        {
            "background_summary": "摘要",
            "key_projects": ["项目"],
            "technical_stack": ["React"],
            "follow_up_topics": ["追问"],
            "inferredTargetRole": "全栈工程师",
        }
    )
    assert inferred.inferred_target_role == "全栈工程师"


def test_confirming_interview_persists_jd_analysis_and_inferred_target_role(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock_interview.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client)
        response = client.post(
            "/interviews",
            json={
                "resumeMarkdown": "# 张三\n\n- Mock Interview",
                "targetRole": "",
                "targetJobDescription": "职责：前端工程化。",
                "interviewMode": "single_round",
                "analysis": {
                    "background_summary": "用户确认的摘要",
                    "key_projects": ["Mock Interview"],
                    "technical_stack": ["React"],
                    "follow_up_topics": ["项目职责"],
                    "risk_points": [],
                    "unclear_points": [],
                    "target_role_notes": "",
                    "focus_topics": [],
                    "low_priority_follow_up_topics": [],
                    "inferred_target_role": "前端工程师（推断）",
                    "job_description_analysis": {
                        "core_responsibilities": ["前端工程化"],
                        "required_requirements": ["React", "TypeScript"],
                        "bonus_points": ["全栈"],
                        "likely_probes": ["性能优化"],
                        "matching_evidence": ["项目匹配"],
                        "role_gaps": ["某技术栈缺失"],
                    },
                },
            },
        )
        read_response = client.get(f"/interviews/{response.json()['id']}")

    interview = read_interview(response.json()["id"])

    assert response.status_code == 200
    assert read_response.status_code == 200
    analysis_payload = read_response.json()["analysis"]
    assert analysis_payload["inferredTargetRole"] == "前端工程师（推断）"
    assert analysis_payload["jobDescriptionAnalysis"]["coreResponsibilities"] == ["前端工程化"]
    assert analysis_payload["jobDescriptionAnalysis"]["requiredRequirements"] == ["React", "TypeScript"]
    assert analysis_payload["jobDescriptionAnalysis"]["roleGaps"] == ["某技术栈缺失"]
    assert interview.analysis.inferred_target_role == "前端工程师（推断）"
    assert interview.analysis.job_description_analysis is not None
    assert interview.analysis.job_description_analysis.required_requirements == ["React", "TypeScript"]


def test_resume_analysis_record_detail_exposes_job_description_analysis(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock_interview.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client)
        client.post(
            "/resume-analyses/generate",
            json={
                "resumeMarkdown": "# 张三\n\n## 项目经历\n- Mock Interview",
                "targetRole": "前端工程师",
                "targetJobDescription": "职责：负责前端工程化。",
            },
        )
        record_id = list_resume_analysis_records()[0].id
        response = client.get(f"/resume-analysis-records/{record_id}")

    assert response.status_code == 200
    # 历史详情暴露完整目标岗位 JD 与结构化岗位 JD 分析。
    assert response.json()["targetJobDescription"] == "职责：负责前端工程化。"
    analysis = response.json()["analysis"]
    assert analysis["jobDescriptionAnalysis"] is not None
    assert analysis["jobDescriptionAnalysis"]["coreResponsibilities"] == ["围绕目标岗位 JD 校准的重点职责推进练习"]
    assert analysis["jobDescriptionAnalysis"]["roleGaps"] == ["JD 要求但简历未直接体现的部分"]
    assert analysis["inferredTargetRole"] is None


def test_confirming_interview_from_jd_record_updates_confirmed_jd_analysis(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock_interview.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client)
        client.post(
            "/resume-analyses/generate",
            json={
                "resumeMarkdown": "# 初始简历\n\n- Mock Interview",
                "targetRole": "前端工程师",
                "targetJobDescription": "初始 JD",
            },
        )
        source_record = list_resume_analysis_records()[0]

        response = client.post(
            "/interviews",
            json={
                "resumeMarkdown": "# 确认版简历\n\n- Mock Interview",
                "targetRole": "资深前端工程师",
                "targetJobDescription": "确认版 JD：负责复杂前端工程。",
                "interviewMode": "single_round",
                "sourceResumeAnalysisRecordId": source_record.id,
                "analysis": {
                    "background_summary": "用户确认后的背景摘要",
                    "key_projects": ["Mock Interview"],
                    "technical_stack": ["React"],
                    "follow_up_topics": ["项目职责"],
                    "risk_points": [],
                    "unclear_points": [],
                    "target_role_notes": "",
                    "focus_topics": [],
                    "low_priority_follow_up_topics": [],
                    "inferred_target_role": None,
                    "job_description_analysis": {
                        "core_responsibilities": ["用户确认的核心职责"],
                        "required_requirements": ["React", "TypeScript"],
                        "bonus_points": [],
                        "likely_probes": ["性能优化"],
                        "matching_evidence": [],
                        "role_gaps": ["用户确认的缺口"],
                    },
                },
            },
        )
        refreshed_record = list_resume_analysis_records()[0]

    assert response.status_code == 200
    # 来源记录更新为确认版本，包含目标岗位 JD 与岗位 JD 分析。
    assert refreshed_record.target_job_description == "确认版 JD：负责复杂前端工程。"
    assert refreshed_record.analysis.job_description_analysis is not None
    assert refreshed_record.analysis.job_description_analysis.core_responsibilities == ["用户确认的核心职责"]
    assert refreshed_record.analysis.job_description_analysis.role_gaps == ["用户确认的缺口"]


def test_repeated_jd_resume_analysis_generation_creates_independent_records(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock_interview.sqlite3"))

    with TestClient(app) as client:
        _configure_provider(client)
        for _ in range(2):
            response = client.post(
                "/resume-analyses/generate",
                json={
                    "resumeMarkdown": "# 张三\n\n## 项目经历\n- Mock Interview",
                    "targetRole": "前端工程师",
                    "targetJobDescription": "职责：负责前端工程化。",
                },
            )
            assert response.status_code == 200

    records = list_resume_analysis_records()
    # 重复解析同一份 JD 简历仍创建独立记录，且都携带岗位 JD 分析。
    assert len(records) == 2
    assert records[0].id != records[1].id
    assert records[0].target_job_description == "职责：负责前端工程化。"
    assert records[1].target_job_description == "职责：负责前端工程化。"
    assert records[0].analysis.job_description_analysis is not None
    assert records[1].analysis.job_description_analysis is not None
