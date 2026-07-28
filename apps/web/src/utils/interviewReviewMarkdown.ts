import type { InterviewReview, TranscriptMessage } from "../App";

/** 导出 Markdown 时需要的面试元信息(字段尽量可选,缺失给默认值)。 */
export type InterviewReviewMeta = {
  recordId?: number;
  interviewId?: number;
  completedAt?: string;
  targetRole?: string;
  modeLabel?: string;
  styleLabel?: string;
  roundTitle?: string;
  projectName?: string;
};

export type InterviewReviewMarkdownInput = {
  review: InterviewReview;
  transcript: TranscriptMessage[];
  meta: InterviewReviewMeta;
};

export type TranscriptQuestionGroup = {
  title: string;
  messages: TranscriptMessage[];
};

/** 把字符串数组渲染成 Markdown 列表;空数组或缺失给出 fallback,绝不输出 undefined/null。 */
export function markdownList(items: ReadonlyArray<string> | null | undefined, fallback = "暂无"): string {
  const safe = (items ?? [])
    .map((item) => (item == null ? "" : String(item)))
    .filter((item) => item.trim() !== "");
  return safe.length ? safe.map((item) => `- ${item}`).join("\n") : `- ${fallback}`;
}

/** 面试官消息类型 → Markdown 标注(按类型判断,不依赖页面文案)。 */
function interviewerKindLabel(kind: string): string {
  switch (kind) {
    case "main_question":
      return "主问题";
    case "follow_up":
      return "追问";
    case "clarify":
      return "澄清";
    case "end_interview":
      return "结束";
    default:
      return "补充";
  }
}

/**
 * 按主问题分组 transcript:
 * - interviewer + main_question 开启新分组;
 * - 其后的 candidate / follow_up / clarify 归入当前分组;
 * - end_interview 不独立成组(收尾说明由 builder 单独处理);
 * - 若开头不是主问题,也会建一个默认分组收纳;
 * - 空数组返回 []。
 */
export function groupTranscriptByMainQuestion(transcript: ReadonlyArray<TranscriptMessage>): TranscriptQuestionGroup[] {
  const groups: TranscriptQuestionGroup[] = [];
  let current: TranscriptQuestionGroup | null = null;
  for (const message of transcript) {
    if (message.role === "interviewer" && message.kind === "end_interview") {
      continue;
    }
    if (message.role === "interviewer" && message.kind === "main_question") {
      current = { title: `第 ${groups.length + 1} 个主问题`, messages: [message] };
      groups.push(current);
      continue;
    }
    if (!current) {
      current = { title: `第 ${groups.length + 1} 个主问题`, messages: [] };
      groups.push(current);
    }
    current.messages.push(message);
  }
  return groups;
}

/** 清理文件名非法字符 \ / : * ? " < > |,空白合并,空串给默认名。 */
export function sanitizeMarkdownFilename(name: string): string {
  const cleaned = (name ?? "")
    .replace(/[\\/:*?"<>|]/g, "_")
    .replace(/\s+/g, " ")
    .trim();
  return cleaned || "模拟面试复盘";
}

function metaInfoBlock(meta: InterviewReviewMeta): string {
  const lines: string[] = ["## 面试信息", ""];
  lines.push(`- 面试记录 ID：${meta.recordId ?? meta.interviewId ?? "未知"}`);
  lines.push(`- 面试时间：${meta.completedAt || "未记录"}`);
  lines.push(`- 目标岗位：${meta.targetRole || "未填写"}`);
  if (meta.projectName) {
    lines.push(`- 项目或简历名称：${meta.projectName}`);
  }
  lines.push(`- 面试模式：${meta.modeLabel || "未填写"}`);
  lines.push(`- 面试风格：${meta.styleLabel || "未填写"}`);
  if (meta.roundTitle) {
    lines.push(`- 面试轮次：${meta.roundTitle}`);
  }
  return lines.join("\n");
}

/** 交接摘要:适合粘贴到下一个 ChatGPT 会话,包含原始问答,不含冗长示范答案。 */
export function buildInterviewHandoffMarkdown({ review, transcript, meta }: InterviewReviewMarkdownInput): string {
  const blocks: string[] = [];
  blocks.push("# 模拟面试交接", "");
  blocks.push(metaInfoBlock(meta), "");

  blocks.push("## 总体评价", review.overallEvaluation || "暂无", "");

  const scores = review.abilityScores ?? [];
  blocks.push(
    "## 能力评分",
    scores.length
      ? scores.map((score) => `- ${score.dimension}：${score.score}/5`).join("\n")
      : "- 暂无评分",
    ""
  );

  blocks.push("## 主要亮点", markdownList(review.highlights), "");
  blocks.push("## 主要问题", markdownList(review.mainIssues), "");

  const groups = groupTranscriptByMainQuestion(transcript);
  const qaLines: string[] = ["## 原始问答", ""];
  if (groups.length === 0) {
    qaLines.push("- 暂无对话记录", "");
  } else {
    groups.forEach((group) => {
      qaLines.push(`### ${group.title}`, "");
      group.messages.forEach((message) => {
        const heading = message.role === "interviewer" ? "面试官" : "候选人";
        qaLines.push(`#### ${heading}`, message.content || "(无内容)", "");
      });
    });
  }
  blocks.push(qaLines.join("\n"));

  const reviews = review.questionReviews ?? [];
  const summaryLines: string[] = ["## 逐题评价摘要", ""];
  if (reviews.length === 0) {
    summaryLines.push("- 暂无逐题评价", "");
  } else {
    reviews.forEach((reviewText, index) => {
      summaryLines.push(`### 问题 ${index + 1}`);
      summaryLines.push(`- 评价：${reviewText || "暂无"}`);
      const improve = review.improvedExpressionExamples?.[index];
      if (improve) {
        summaryLines.push(`- 改进方向：${improve}`);
      }
      summaryLines.push("");
    });
  }
  blocks.push(summaryLines.join("\n"));

  const knowledgeLines: string[] = ["## 建议补充的知识点", ""];
  knowledgeLines.push(markdownList(review.knowledgeReferences, "暂无"));
  if ((review.learningFramework ?? []).length) {
    knowledgeLines.push("", markdownList(review.learningFramework, "暂无"));
  }
  knowledgeLines.push("");
  blocks.push(knowledgeLines.join("\n"));

  blocks.push("## 下一轮建议", markdownList(review.nextPracticeSuggestions, "暂无"), "");

  blocks.push(
    "## 给后续 ChatGPT 的任务",
    "",
    "请根据以上原始问答和复盘：",
    "",
    "1. 区分知识缺口、项目细节缺口和表达问题；",
    "2. 判断 AI 复盘是否存在不准确或套话；",
    "3. 按优先级给出本轮需要补充的内容；",
    "4. 每次只安排一个可在两小时内完成的学习主题；",
    "5. 学习完成后给出下一轮 Mock Interview 的复测范围。",
    ""
  );

  return blocks.join("\n");
}

/** 完整复盘 Markdown:信息尽量完整,适合 Obsidian 归档,必须保留候选人原始回答。 */
export function buildFullInterviewReviewMarkdown({ review, transcript, meta }: InterviewReviewMarkdownInput): string {
  const blocks: string[] = [];
  blocks.push("# 模拟面试复盘", "");
  blocks.push(metaInfoBlock(meta), "");

  blocks.push("## 总体评价", review.overallEvaluation || "暂无", "");

  const scores = review.abilityScores ?? [];
  blocks.push(
    "## 六维能力评分",
    scores.length
      ? scores.map((score) => `- ${score.dimension}：${score.score}/5，${score.rationale || ""}`.trim()).join("\n")
      : "- 暂无评分",
    ""
  );

  blocks.push("## 亮点", markdownList(review.highlights), "");
  blocks.push("## 主要问题", markdownList(review.mainIssues), "");
  blocks.push("## 逐题点评", markdownList(review.questionReviews), "");
  blocks.push("## 可改进表达示例", markdownList(review.improvedExpressionExamples), "");
  blocks.push("## 示范性参考答案", markdownList(review.sampleAnswers), "");
  blocks.push("## 知识点参考", markdownList(review.knowledgeReferences), "");
  blocks.push("## 学习框架", markdownList(review.learningFramework), "");
  blocks.push("## 下一次练习建议", markdownList(review.nextPracticeSuggestions), "");

  if (review.jdMatchAnalysis) {
    blocks.push(
      "## JD 匹配分析",
      "",
      "### 匹配证据",
      markdownList(review.jdMatchAnalysis.matchingEvidence),
      "",
      "### 暴露的岗位缺口",
      markdownList(review.jdMatchAnalysis.roleGaps),
      "",
      "### 项目表达如何更贴 JD",
      markdownList(review.jdMatchAnalysis.projectExpressionImprovements),
      "",
      "### 下轮优先补齐的 JD 要求",
      markdownList(review.jdMatchAnalysis.nextPracticeJdPriorities),
      ""
    );
  }

  const groups = groupTranscriptByMainQuestion(transcript);
  const transcriptLines: string[] = ["## 完整问答记录", ""];
  if (groups.length === 0) {
    transcriptLines.push("- 暂无对话记录", "");
  } else {
    groups.forEach((group) => {
      transcriptLines.push(`### ${group.title}`, "");
      group.messages.forEach((message) => {
        const speaker =
          message.role === "interviewer"
            ? `面试官（${interviewerKindLabel(message.kind)}）`
            : "候选人";
        transcriptLines.push(`- **${speaker}**：${message.content || "(无内容)"}`);
      });
      transcriptLines.push("");
    });
  }
  const endMessage = transcript.find(
    (message) => message.role === "interviewer" && message.kind === "end_interview"
  );
  if (endMessage) {
    transcriptLines.push("### 面试结束", "", `- **面试官**：${endMessage.content || "(无内容)"}`, "");
  }
  blocks.push(transcriptLines.join("\n"));

  return blocks.join("\n");
}
