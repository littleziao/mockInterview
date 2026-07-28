import { describe, expect, it } from "vitest";

import type { InterviewReview, TranscriptMessage } from "../App";
import {
  buildFullInterviewReviewMarkdown,
  buildInterviewHandoffMarkdown,
  groupTranscriptByMainQuestion,
  markdownList,
  sanitizeMarkdownFilename,
} from "./interviewReviewMarkdown";

function makeReview(overrides: Partial<InterviewReview> = {}): InterviewReview {
  return {
    overallEvaluation: "整体能说明项目背景，但结果指标不足。",
    highlights: ["能说明自己负责的模块"],
    mainIssues: ["结果指标偏少"],
    questionReviews: ["第 1 题：覆盖背景，但缺少量化结果。"],
    improvedExpressionExamples: ["可以按 STAR 顺序说明项目贡献。"],
    sampleAnswers: ["示范性回答：这是一种可参考表达。"],
    knowledgeReferences: ["结构化输出校验"],
    learningFramework: ["先补齐项目指标"],
    nextPracticeSuggestions: ["下一次重点练习项目深挖。"],
    abilityScores: [
      { dimension: "专业知识准确性", score: 3, rationale: "概念基本准确。" },
      { dimension: "项目经验表达", score: 4, rationale: "项目表达较清楚。" },
      { dimension: "问题分析能力", score: 3, rationale: "拆解过程还可加强。" },
      { dimension: "技术深度", score: 3, rationale: "底层机制展开不足。" },
      { dimension: "沟通结构化", score: 4, rationale: "表达有主线。" },
      { dimension: "岗位匹配度", score: 4, rationale: "经历和岗位较匹配。" },
    ],
    ...overrides,
  };
}

function makeTranscript(): TranscriptMessage[] {
  return [
    { role: "interviewer", content: "介绍一下你负责的模块。", kind: "main_question", mainQuestionIndex: 0 },
    { role: "candidate", content: "我负责简历分析模块。", kind: "", mainQuestionIndex: 0 },
    { role: "interviewer", content: "你是如何校验 AI 输出的？", kind: "follow_up", mainQuestionIndex: 0 },
    { role: "candidate", content: "用结构化 schema 做校验。", kind: "", mainQuestionIndex: 0 },
    { role: "interviewer", content: "再聊聊另一个项目。", kind: "main_question", mainQuestionIndex: 1 },
    { role: "candidate", content: "我做了一个工具链。", kind: "", mainQuestionIndex: 1 },
    { role: "interviewer", content: "本场面试信息已经足够。", kind: "end_interview", mainQuestionIndex: 1 },
  ];
}

const baseMeta = {
  recordId: 1,
  interviewId: 7,
  completedAt: "2026-07-28 09:00:00",
  targetRole: "AI 大数据开发工程师",
  modeLabel: "单轮面试",
  styleLabel: "学习梳理面",
  roundTitle: "技术面",
};

describe("interviewReviewMarkdown", () => {
  it("交接摘要包含标题与面试信息", () => {
    const md = buildInterviewHandoffMarkdown({ review: makeReview(), transcript: makeTranscript(), meta: baseMeta });
    expect(md).toContain("# 模拟面试交接");
    expect(md).toContain("面试记录 ID：1");
    expect(md).toContain("面试时间：2026-07-28 09:00:00");
    expect(md).toContain("目标岗位：AI 大数据开发工程师");
    expect(md).toContain("面试模式：单轮面试");
  });

  it("交接摘要包含候选人原始回答", () => {
    const md = buildInterviewHandoffMarkdown({ review: makeReview(), transcript: makeTranscript(), meta: baseMeta });
    expect(md).toContain("我负责简历分析模块。");
    expect(md).toContain("候选人");
  });

  it("追问归入正确的主问题分组，end_interview 不独立成组", () => {
    const groups = groupTranscriptByMainQuestion(makeTranscript());
    expect(groups).toHaveLength(2);
    expect(groups[0].messages.map((m) => m.content)).toContain("你是如何校验 AI 输出的？");
    expect(groups[0].messages.map((m) => m.kind)).toContain("follow_up");
    expect(groups.flatMap((g) => g.messages).some((m) => m.kind === "end_interview")).toBe(false);
  });

  it("输出六维能力评分", () => {
    const md = buildFullInterviewReviewMarkdown({ review: makeReview(), transcript: makeTranscript(), meta: baseMeta });
    expect(md).toContain("专业知识准确性：3/5");
    expect(md).toContain("项目经验表达：4/5");
    expect(md).toContain("岗位匹配度：4/5");
  });

  it("缺少 jdMatchAnalysis 时不会报错或输出该段", () => {
    const md = buildFullInterviewReviewMarkdown({
      review: makeReview({ jdMatchAnalysis: undefined }),
      transcript: [],
      meta: baseMeta,
    });
    expect(md).not.toContain("JD 匹配分析");
  });

  it("缺失可选字段时不出现 undefined / null / [object Object]", () => {
    const sparse = makeReview({
      highlights: [],
      mainIssues: [],
      abilityScores: [],
      overallEvaluation: "",
      jdMatchAnalysis: null,
    });
    const md = buildFullInterviewReviewMarkdown({
      review: sparse,
      transcript: [],
      meta: { targetRole: "", modeLabel: "" },
    });
    expect(md).not.toContain("undefined");
    expect(md).not.toContain("null");
    expect(md).not.toContain("[object Object]");
  });

  it("完整 Markdown 包含逐题点评与参考答案", () => {
    const md = buildFullInterviewReviewMarkdown({ review: makeReview(), transcript: makeTranscript(), meta: baseMeta });
    expect(md).toContain("第 1 题：覆盖背景，但缺少量化结果。");
    expect(md).toContain("示范性回答：这是一种可参考表达。");
    expect(md).toContain("完整问答记录");
  });

  it("文件名非法字符被替换，空串给默认名", () => {
    expect(sanitizeMarkdownFilename('a/b:c*d?e"f<g>h|i')).toBe("a_b_c_d_e_f_g_h_i");
    expect(sanitizeMarkdownFilename("   ")).toBe("模拟面试复盘");
  });

  it("transcript 为空时输出友好占位", () => {
    const handoff = buildInterviewHandoffMarkdown({ review: makeReview(), transcript: [], meta: baseMeta });
    expect(handoff).toContain("暂无对话记录");
    const full = buildFullInterviewReviewMarkdown({ review: makeReview(), transcript: [], meta: baseMeta });
    expect(full).toContain("暂无对话记录");
  });

  it("多个主问题的分组顺序正确", () => {
    const groups = groupTranscriptByMainQuestion(makeTranscript());
    expect(groups[0].title).toBe("第 1 个主问题");
    expect(groups[1].title).toBe("第 2 个主问题");
    expect(groups[0].messages[0].content).toBe("介绍一下你负责的模块。");
    expect(groups[1].messages[0].content).toBe("再聊聊另一个项目。");
  });

  it("markdownList 空数组使用 fallback", () => {
    expect(markdownList([])).toBe("- 暂无");
    expect(markdownList(["a", "b"])).toBe("- a\n- b");
  });
});
