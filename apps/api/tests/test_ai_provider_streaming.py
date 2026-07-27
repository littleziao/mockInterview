from __future__ import annotations

import pytest

from apps.api.app.ai_provider import (
    AIProviderRequestError,
    FakeAIProvider,
    InterviewerActionChunk,
    _StreamingMessageExtractor,
)
from apps.api.app.ai_settings import AIProviderSettings
from apps.api.app.interview_session import InterviewSession
from apps.api.app.resume_analysis import validate_resume_analysis


def _provider(base_url: str) -> FakeAIProvider:
    return FakeAIProvider(
        AIProviderSettings(
            id="primary",
            name="mock",
            base_url=base_url,
            api_key="secret",
            model="mock-model",
        )
    )


def _session() -> InterviewSession:
    return InterviewSession(
        id=1,
        interview_id=1,
        style="study",
        status="in_progress",
        transcript=[],
        main_question_count=0,
        current_main_question_follow_ups=0,
    )


def _analysis():
    return validate_resume_analysis(
        {
            "background_summary": "候选人有项目交付经验",
            "key_projects": ["Mock Interview"],
            "technical_stack": ["React"],
            "follow_up_topics": ["项目职责"],
        }
    )


# --- 增量 JSON 提取器单测 ---


def test_extractor_single_chunk_kind_and_message():
    ex = _StreamingMessageExtractor()
    delta = ex.feed('{"kind":"follow_up","message":"你好"}')
    assert ex.kind_value == "follow_up"
    assert ex.message_value == "你好"
    assert delta == "你好"


def test_extractor_message_field_appears_before_kind():
    ex = _StreamingMessageExtractor()
    d1 = ex.feed('{"message":"你好",')
    assert ex.kind_value is None
    assert ex.message_value == "你好"
    assert d1 == "你好"
    d2 = ex.feed('"kind":"follow_up"}')
    assert ex.kind_value == "follow_up"
    assert d2 == ""  # message 未增长


def test_extractor_message_split_across_chunks():
    ex = _StreamingMessageExtractor()
    assert ex.feed('{"kind":"follow_up","message":"ab') == "ab"
    assert ex.feed("cd") == "cd"
    assert ex.feed('ef"}') == "ef"
    assert ex.message_value == "abcdef"


def test_extractor_kind_value_split_across_chunks():
    ex = _StreamingMessageExtractor()
    assert ex.feed('{"kind":"follo') == ""
    assert ex.kind_value is None
    ex.feed('w_up","message":"x"}')
    assert ex.kind_value == "follow_up"
    assert ex.message_value == "x"


def test_extractor_decodes_escapes():
    ex = _StreamingMessageExtractor()
    ex.feed('{"kind":"follow_up","message":"a\\"b\\n\\tc"}')
    assert ex.message_value == 'a"b\n\tc'


def test_extractor_unicode_escape_across_chunks():
    ex = _StreamingMessageExtractor()
    assert ex.feed('{"kind":"follow_up","message":"\\u4f60') == "你"
    assert ex.feed('\\u597d"}') == "好"
    assert ex.message_value == "你好"


def test_extractor_message_with_colons_commas_braces():
    ex = _StreamingMessageExtractor()
    ex.feed('{"kind":"follow_up","message":"a:b,c{d}e"}')
    assert ex.message_value == "a:b,c{d}e"


def test_extractor_nested_json_inside_message():
    ex = _StreamingMessageExtractor()
    ex.feed('{"kind":"follow_up","message":"{\\"x\\":1}"}')
    assert ex.message_value == '{"x":1}'


def test_extractor_ignores_unrelated_fields():
    ex = _StreamingMessageExtractor()
    ex.feed('{"foo":"bar","kind":"follow_up","message":"hi"}')
    assert ex.kind_value == "follow_up"
    assert ex.message_value == "hi"


def test_extractor_not_fooled_by_kind_inside_message():
    ex = _StreamingMessageExtractor()
    ex.feed('{"kind":"follow_up","message":"the kind is strong"}')
    assert ex.kind_value == "follow_up"
    assert ex.message_value == "the kind is strong"


def test_extractor_tolerates_whitespace():
    ex = _StreamingMessageExtractor()
    ex.feed('{ "kind" : "follow_up" , "message" : "x" }')
    assert ex.kind_value == "follow_up"
    assert ex.message_value == "x"


def test_extractor_missing_message_returns_empty():
    ex = _StreamingMessageExtractor()
    ex.feed('{"kind":"follow_up"}')
    assert ex.kind_value == "follow_up"
    assert ex.message_value == ""


def test_extractor_single_quoted_non_json_yields_nothing():
    ex = _StreamingMessageExtractor()
    ex.feed("{'kind':'follow_up','message':'x'}")
    assert ex.kind_value is None
    assert ex.message_value == ""


def test_extractor_full_text_accumulates_raw():
    ex = _StreamingMessageExtractor()
    ex.feed('{"kind":"f')
    ex.feed('ollow_up"}')
    assert ex.full_text() == '{"kind":"follow_up"}'


# --- FakeAIProvider 流式契约 ---


def test_stream_emits_meta_then_deltas_then_final():
    provider = _provider("fake://success")
    chunks = list(
        provider.stream_next_interviewer_action(
            session=_session(), analysis=_analysis(), target_role="前端", starting=True
        )
    )
    kinds = [chunk.kind for chunk in chunks]
    assert kinds[0] == "meta"
    assert kinds[-1] == "final"
    assert all(kind == "delta" for kind in kinds[1:-1])

    assert chunks[0].action_kind == "main_question"
    final_action = chunks[-1].action
    assert final_action is not None
    assert final_action.kind == "main_question"

    streamed_text = "".join(chunk.text for chunk in chunks if chunk.kind == "delta")
    assert streamed_text == final_action.message


def test_stream_slow_still_completes():
    provider = _provider("fake://stream-slow")
    chunks = list(
        provider.stream_next_interviewer_action(
            session=_session(), analysis=_analysis(), target_role="前端", starting=True
        )
    )
    final_action = chunks[-1].action
    assert final_action is not None
    assert final_action.kind == "main_question"


def test_stream_error_raises_after_first_delta():
    provider = _provider("fake://stream-error")
    gen = provider.stream_next_interviewer_action(
        session=_session(), analysis=_analysis(), target_role="", starting=True
    )
    first = next(gen)
    assert isinstance(first, InterviewerActionChunk)
    assert first.kind == "delta"
    with pytest.raises(AIProviderRequestError):
        next(gen)
