from __future__ import annotations

from apps.api.app.interview_rounds import (
    MULTI_ROUND_ORDER,
    ROUND_KIND_HR,
    ROUND_KIND_MANAGER,
    ROUND_KIND_PEER,
    ROUND_KIND_SENIOR,
    ROUND_KIND_SINGLE,
    ROUND_TEMPLATES,
    InterviewRoundTemplate,
    decide_next_round_kind,
    get_round_template,
    plan_rounds,
)


def test_plan_rounds_multi_round_default_returns_three_in_order() -> None:
    rounds = plan_rounds("multi_round", include_hr=False)

    assert [template.kind for template in rounds] == list(MULTI_ROUND_ORDER)
    assert [template.kind for template in rounds] == [
        ROUND_KIND_PEER,
        ROUND_KIND_SENIOR,
        ROUND_KIND_MANAGER,
    ]


def test_plan_rounds_multi_round_with_hr_appends_hr_last() -> None:
    rounds = plan_rounds("multi_round", include_hr=True)

    assert [template.kind for template in rounds] == [
        ROUND_KIND_PEER,
        ROUND_KIND_SENIOR,
        ROUND_KIND_MANAGER,
        ROUND_KIND_HR,
    ]
    assert rounds[-1].title == "HR 面"


def test_plan_rounds_single_round_returns_empty() -> None:
    assert plan_rounds("single_round", include_hr=False) == []
    assert plan_rounds("single_round", include_hr=True) == []


def test_plan_rounds_unknown_mode_returns_empty() -> None:
    assert plan_rounds("unexpected", include_hr=True) == []


def test_round_templates_focus_text_matches_issue_spec_verbatim() -> None:
    # focus 文案会原样注入 AI prompt 与前端展示，必须与 issue #9 验收标准逐字一致。
    assert ROUND_TEMPLATES[ROUND_KIND_PEER].focus == "基础技术、简历真实性、项目细节和协作可行性"
    assert ROUND_TEMPLATES[ROUND_KIND_SENIOR].focus == "技术深度、方案取舍、复杂问题分析、边界条件和排障能力"
    assert (
        ROUND_TEMPLATES[ROUND_KIND_MANAGER].focus
        == "岗位匹配、沟通协作、业务理解、成长性和高层次技术判断"
    )
    assert ROUND_TEMPLATES[ROUND_KIND_HR].focus == "求职动机、稳定性、薪资期望、入职时间和职业规划"


def test_round_templates_carry_title_and_kind() -> None:
    for kind, template in ROUND_TEMPLATES.items():
        assert template.kind == kind
        assert template.title
        assert template.focus


def test_get_round_template_returns_none_for_single_round() -> None:
    assert get_round_template(ROUND_KIND_SINGLE) is None
    assert get_round_template("unknown") is None
    assert get_round_template(ROUND_KIND_PEER) is ROUND_TEMPLATES[ROUND_KIND_PEER]


def _existing(round_kinds_with_status):
    return [{"round_kind": kind, "status": status} for kind, status in round_kinds_with_status]


def test_decide_next_round_kind_returns_first_pending_when_no_existing() -> None:
    planned = plan_rounds("multi_round", include_hr=False)
    assert decide_next_round_kind(planned, existing=[]) == ROUND_KIND_PEER


def test_decide_next_round_kind_skips_ended_and_abandoned() -> None:
    planned = plan_rounds("multi_round", include_hr=False)
    existing = _existing(
        [(ROUND_KIND_PEER, "ended"), (ROUND_KIND_SENIOR, "abandoned")]
    )
    assert decide_next_round_kind(planned, existing=existing) == ROUND_KIND_MANAGER


def test_decide_next_round_kind_returns_none_when_all_done() -> None:
    planned = plan_rounds("multi_round", include_hr=True)
    existing = _existing(
        [
            (ROUND_KIND_PEER, "ended"),
            (ROUND_KIND_SENIOR, "ended"),
            (ROUND_KIND_MANAGER, "ended"),
            (ROUND_KIND_HR, "abandoned"),
        ]
    )
    assert decide_next_round_kind(planned, existing=existing) is None


def test_decide_next_round_kind_treats_in_progress_as_not_yet_handled() -> None:
    planned = plan_rounds("multi_round", include_hr=False)
    existing = _existing([(ROUND_KIND_PEER, "awaiting_review")])
    # peer 尚未结束，下一轮仍应停留在 peer，调用方在更上层用 409 拦截。
    assert decide_next_round_kind(planned, existing=existing) == ROUND_KIND_PEER


def test_decide_next_round_kind_empty_planned_returns_none() -> None:
    assert decide_next_round_kind(planned=[], existing=[]) is None
