import httpx
import pytest

from apps.api.app.ai_provider import (
    AIProviderRequestError,
    OpenAICompatibleProvider,
)
from apps.api.app.ai_settings import AIProviderSettings
from apps.api.app.interview_session import TranscriptMessage


def _provider() -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        AIProviderSettings(
            id="primary",
            name="主供应商",
            base_url="https://api.example.test/v1",
            api_key="secret-key",
            model="mock-model",
        )
    )


def test_review_transcript_grouped_by_main_question_for_prompt() -> None:
    transcript = [
        TranscriptMessage(role="interviewer", content="主问题1", kind="main_question", main_question_index=0),
        TranscriptMessage(role="candidate", content="回答1", kind="", main_question_index=0),
        TranscriptMessage(role="interviewer", content="追问1", kind="follow_up", main_question_index=0),
        TranscriptMessage(role="candidate", content="回答追问1", kind="", main_question_index=0),
        TranscriptMessage(role="interviewer", content="主问题2", kind="main_question", main_question_index=1),
        TranscriptMessage(role="candidate", content="回答2", kind="", main_question_index=1),
        TranscriptMessage(role="interviewer", content="本场面试信息已足够。", kind="end_interview", main_question_index=1),
    ]
    text, outline = _provider()._format_review_transcript_by_main_question(transcript)

    assert outline == ["主问题1", "主问题2"]
    assert "【第 1 个主问题】主问题1" in text
    assert "【第 2 个主问题】主问题2" in text
    # 追问归入第 1 个主问题段（出现在「第 2 个主问题」之前）
    assert text.index("追问1") < text.index("【第 2 个主问题】")
    assert "回答追问1" in text
    # end_interview 收尾不作为独立题目，不进入分段文本
    assert "本场面试信息已足够。" not in text


def test_provider_http_error_includes_model_error_body(monkeypatch) -> None:
    def fake_post(*args, **kwargs):
        request = httpx.Request("POST", "https://api.example.test/v1/chat/completions")
        return httpx.Response(
            401,
            json={
                "error": {
                    "message": "Incorrect API key provided",
                    "type": "invalid_request_error",
                    "code": "invalid_api_key",
                }
            },
            request=request,
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(AIProviderRequestError) as error:
        _provider().analyze_resume(resume_markdown="# 张三", target_role="前端工程师")

    message = str(error.value)
    assert "模型服务返回错误" in message
    assert "HTTP 401" in message
    assert "主供应商" in message
    assert "mock-model" in message
    assert "Incorrect API key provided" in message
    assert "invalid_api_key" in message


def test_provider_ssl_error_identifies_transport_layer(monkeypatch) -> None:
    def fake_post(*args, **kwargs):
        request = httpx.Request("POST", "https://api.example.test/v1/chat/completions")
        raise httpx.ConnectError(
            "[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1032)",
            request=request,
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(AIProviderRequestError) as error:
        _provider().analyze_resume(resume_markdown="# 张三", target_role="前端工程师")

    message = str(error.value)
    assert "AI Provider 网络连接失败" in message
    assert "TLS/SSL 握手失败" in message
    assert "主供应商" in message
    assert "https://api.example.test/v1/chat/completions" in message
    assert "UNEXPECTED_EOF_WHILE_READING" in message


def test_connection_test_reports_model_error_body(monkeypatch) -> None:
    def fake_post(*args, **kwargs):
        request = httpx.Request("POST", "https://api.example.test/v1/chat/completions")
        return httpx.Response(
            429,
            json={"error": {"message": "Rate limit exceeded", "code": "rate_limit_exceeded"}},
            request=request,
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    result = _provider().test_connection()

    assert result.status == "failure"
    assert "模型服务返回错误" in result.message
    assert "HTTP 429" in result.message
    assert "Rate limit exceeded" in result.message
