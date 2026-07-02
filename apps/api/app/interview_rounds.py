from __future__ import annotations

from dataclasses import dataclass


# 轮次 kind 常量。single_round 作为单轮面试的占位 kind，不在 ROUND_TEMPLATES 中，
# 因此 get_round_template("single_round") 返回 None —— AI prompt 不会注入轮次段落。
ROUND_KIND_PEER = "peer_technical"
ROUND_KIND_SENIOR = "senior_technical"
ROUND_KIND_MANAGER = "manager_comprehensive"
ROUND_KIND_HR = "hr"
ROUND_KIND_SINGLE = "single_round"

# 多轮面试默认轮次顺序：同事技术面 → 资深技术面 → 主管综合面；HR 面可选并置于最后。
MULTI_ROUND_ORDER = (ROUND_KIND_PEER, ROUND_KIND_SENIOR, ROUND_KIND_MANAGER)

# 视为“该轮已处理、可进入下一轮”的终态。进行中态（in_progress / awaiting_review）
# 不在其中，由调用方在更上层拦截（同一 interview 不允许同时存在多个进行中轮次）。
HANDLED_ROUND_STATUSES = ("ended", "abandoned")


@dataclass(frozen=True)
class InterviewRoundTemplate:
    kind: str
    title: str
    focus: str


# focus 文案会原样注入 AI prompt 与前端展示，必须与 issue #9 验收标准逐字一致。
# packages/core 的 defaultRoundTemplates 需保持字字相同，前端测试断言会守住这一点。
ROUND_TEMPLATES: dict[str, InterviewRoundTemplate] = {
    ROUND_KIND_PEER: InterviewRoundTemplate(
        kind=ROUND_KIND_PEER,
        title="同事技术面",
        focus="基础技术、简历真实性、项目细节和协作可行性",
    ),
    ROUND_KIND_SENIOR: InterviewRoundTemplate(
        kind=ROUND_KIND_SENIOR,
        title="资深技术面",
        focus="技术深度、方案取舍、复杂问题分析、边界条件和排障能力",
    ),
    ROUND_KIND_MANAGER: InterviewRoundTemplate(
        kind=ROUND_KIND_MANAGER,
        title="主管综合面",
        focus="岗位匹配、沟通协作、业务理解、成长性和高层次技术判断",
    ),
    ROUND_KIND_HR: InterviewRoundTemplate(
        kind=ROUND_KIND_HR,
        title="HR 面",
        focus="求职动机、稳定性、薪资期望、入职时间和职业规划",
    ),
}


def plan_rounds(interview_mode: str, include_hr: bool) -> list[InterviewRoundTemplate]:
    """按面试模式规划默认轮次。单轮面试返回空列表（调用方按 single_round 行为处理）。"""

    if interview_mode != "multi_round":
        return []

    ordered_kinds = [*MULTI_ROUND_ORDER, *(("hr",) if include_hr else ())]
    return [ROUND_TEMPLATES[kind] for kind in ordered_kinds]


def get_round_template(round_kind: str) -> InterviewRoundTemplate | None:
    """取轮次模板。single_round 与未知 kind 返回 None，调用方据此跳过 prompt 注入。"""

    return ROUND_TEMPLATES.get(round_kind)


def decide_next_round_kind(
    planned: list[InterviewRoundTemplate],
    existing: list[dict[str, object]],
) -> str | None:
    """根据已存在的 session 状态，决定多轮面试下一个待启动的轮次 kind。

    existing 形如 [{"round_kind": "peer_technical", "status": "ended"}, ...]。
    规则：按 planned 顺序，返回首个“无 session 或 session 已 ended/abandoned”的 kind；
    进行中态（in_progress / awaiting_review）视为未处理，仍返回该 kind（由上层拦截并发）；
    全部已处理返回 None。
    """

    status_by_kind = {str(item["round_kind"]): str(item["status"]) for item in existing}

    for template in planned:
        status = status_by_kind.get(template.kind)
        if status is None:
            return template.kind
        if status in HANDLED_ROUND_STATUSES:
            continue
        return template.kind

    return None
