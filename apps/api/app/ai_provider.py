from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Protocol

import httpx

from .ai_settings import AIProviderSettings
from .resume_analysis import ResumeAnalysis, ResumeAnalysisValidationError, validate_resume_analysis


@dataclass(frozen=True)
class ProviderTestResult:
    status: str
    message: str


class AIProvider(Protocol):
    def test_connection(self) -> ProviderTestResult:
        raise NotImplementedError

    def analyze_resume(self, *, resume_markdown: str, target_role: str) -> ResumeAnalysis:
        raise NotImplementedError


class FakeAIProvider:
    def __init__(self, settings: AIProviderSettings) -> None:
        self.settings = settings

    def test_connection(self) -> ProviderTestResult:
        if self.settings.base_url == "fake://failure":
            return ProviderTestResult(status="failure", message="Fake AI Provider 连接失败")

        return ProviderTestResult(status="success", message="AI Provider 连接测试成功")

    def analyze_resume(self, *, resume_markdown: str, target_role: str) -> ResumeAnalysis:
        if self.settings.base_url == "fake://invalid-analysis":
            return validate_resume_analysis({"background_summary": ""})

        first_line = next((line.strip("# ").strip() for line in resume_markdown.splitlines() if line.strip()), "候选人")
        return validate_resume_analysis(
            {
                "background_summary": f"{first_line} 具备项目交付和工程实现经验。",
                "key_projects": ["基于 Markdown 简历识别出的核心项目"],
                "technical_stack": ["TypeScript", "React", "FastAPI", "SQLite"],
                "follow_up_topics": ["项目职责边界", "技术选型取舍", "复杂问题排查"],
                "risk_points": ["需要进一步验证项目深度"],
                "unclear_points": ["部分项目结果指标不够明确"],
                "target_role_notes": target_role or "未填写目标岗位，后续面试将根据简历推断方向。",
                "focus_topics": ["项目经验表达", "技术深度"],
                "low_priority_follow_up_topics": ["与目标岗位弱相关的零散经历"],
            }
        )


class OpenAICompatibleProvider:
    def __init__(self, settings: AIProviderSettings) -> None:
        self.settings = settings

    def test_connection(self) -> ProviderTestResult:
        endpoint = self.settings.base_url.rstrip("/") + "/chat/completions"
        try:
            response = httpx.post(
                endpoint,
                headers={"Authorization": f"Bearer {self.settings.api_key}"},
                json={
                    "model": self.settings.model,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 1,
                },
                timeout=10,
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            return ProviderTestResult(status="failure", message=f"AI Provider 连接失败：{error}")

        return ProviderTestResult(status="success", message="AI Provider 连接测试成功")

    def analyze_resume(self, *, resume_markdown: str, target_role: str) -> ResumeAnalysis:
        endpoint = self.settings.base_url.rstrip("/") + "/chat/completions"
        response = httpx.post(
            endpoint,
            headers={"Authorization": f"Bearer {self.settings.api_key}"},
            json={
                "model": self.settings.model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "你是简历驱动模拟面试系统的后端分析器。"
                            "只返回 JSON，不要返回 Markdown 或解释。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            "请基于 Markdown 简历和目标岗位生成结构化简历分析。"
                            "JSON 字段必须包含 background_summary, key_projects, "
                            "technical_stack, follow_up_topics, risk_points, unclear_points, "
                            "target_role_notes, focus_topics, low_priority_follow_up_topics。"
                            f"\n目标岗位：{target_role or '未填写'}"
                            f"\nMarkdown 简历：\n{resume_markdown}"
                        ),
                    },
                ],
                "response_format": {"type": "json_object"},
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        return validate_resume_analysis(_load_json_content(content))


def _load_json_content(content: str) -> object:
    stripped_content = content.strip()
    fenced_match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped_content, flags=re.DOTALL)
    if fenced_match:
        stripped_content = fenced_match.group(1).strip()

    try:
        return json.loads(stripped_content)
    except json.JSONDecodeError as error:
        raise ResumeAnalysisValidationError("AI 返回的简历分析结构无效") from error


def build_ai_provider(settings: AIProviderSettings) -> AIProvider:
    if settings.base_url.startswith("fake://"):
        return FakeAIProvider(settings)

    return OpenAICompatibleProvider(settings)


def test_ai_provider_connection(settings: AIProviderSettings) -> ProviderTestResult:
    if not settings.is_configured:
        return ProviderTestResult(status="missing", message="请先保存供应商名称、baseUrl、apiKey 和 model")

    return build_ai_provider(settings).test_connection()


def analyze_resume_with_provider(
    settings: AIProviderSettings,
    *,
    resume_markdown: str,
    target_role: str,
) -> ResumeAnalysis:
    if not settings.is_configured:
        raise ValueError("请先保存供应商名称、baseUrl、apiKey 和 model")

    return build_ai_provider(settings).analyze_resume(resume_markdown=resume_markdown, target_role=target_role)
