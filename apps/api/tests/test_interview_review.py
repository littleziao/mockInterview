from apps.api.app.interview_review import (
    ABILITY_DIMENSIONS,
    validate_interview_review,
)


def _full_review() -> dict:
    return {
        "overall_evaluation": "本次回答能覆盖项目背景，但关键指标还可以加强。",
        "highlights": ["能说明自己负责的模块"],
        "main_issues": ["结果指标偏少"],
        "question_reviews": ["第 1 个主问题：回答覆盖背景。"],
        "improved_expression_examples": ["按 背景-行动-结果 说明贡献。"],
        "sample_answers": ["示范性回答：一种可参考表达。"],
        "knowledge_references": ["结构化输出校验"],
        "learning_framework": ["补齐项目指标"],
        "next_practice_suggestions": ["重点练习项目深挖。"],
        "ability_scores": [
            {"dimension": dimension, "score": 3, "rationale": "基于本次表现。"}
            for dimension in ABILITY_DIMENSIONS
        ],
    }


def test_review_accepts_empty_list_fields() -> None:
    """列表字段允许为空：AI 返回稀疏结构时不再整体校验失败。"""
    data = _full_review()
    for key in ("highlights", "knowledge_references", "learning_framework", "sample_answers"):
        data[key] = []

    review = validate_interview_review(data)

    assert review.highlights == []
    assert review.knowledge_references == []
    assert review.learning_framework == []
    assert review.sample_answers == []


def test_review_fills_missing_and_mismatched_ability_dimensions() -> None:
    """缺失或维度名写错的维度补默认值，保证永远恰好 6 个、顺序对齐。"""
    data = _full_review()
    data["ability_scores"] = [
        {"dimension": "专业知识准确性", "score": 4, "rationale": "概念准确。"},
        {"dimension": "项目经验", "score": 3, "rationale": "不会命中（正确名是“项目经验表达”）。"},
        {"dimension": "技术深度", "score": 5, "rationale": "底层展开充分。"},
    ]

    review = validate_interview_review(data)

    assert [score.dimension for score in review.ability_scores] == list(ABILITY_DIMENSIONS)
    assert len(review.ability_scores) == len(ABILITY_DIMENSIONS)
    # 命中的维度保留 AI 给的原值。
    hit = next(score for score in review.ability_scores if score.dimension == "技术深度")
    assert hit.score == 5
    # 缺失的维度补默认 score=3。
    filled = next(score for score in review.ability_scores if score.dimension == "项目经验表达")
    assert filled.score == 3


def test_review_accepts_no_ability_scores() -> None:
    """整段 ability_scores 缺失时，全部六个维度补默认值。"""
    data = _full_review()
    data["ability_scores"] = []

    review = validate_interview_review(data)

    assert [score.dimension for score in review.ability_scores] == list(ABILITY_DIMENSIONS)
    assert all(score.score == 3 for score in review.ability_scores)
