export type InterviewMode = "single_round" | "multi_round";

export type InterviewStyle = "learning" | "pressure";

export type InterviewRoundKind =
  | "peer_technical"
  | "senior_technical"
  | "manager_comprehensive"
  | "hr";

export interface InterviewRoundTemplate {
  kind: InterviewRoundKind;
  title: string;
  focus: string;
}

export const defaultRoundTemplates: InterviewRoundTemplate[] = [
  {
    kind: "peer_technical",
    title: "同事技术面",
    focus: "基础技术、简历真实性、项目细节和协作可行性"
  },
  {
    kind: "senior_technical",
    title: "资深技术面",
    focus: "技术深度、方案取舍、复杂问题分析、边界条件和排障能力"
  },
  {
    kind: "manager_comprehensive",
    title: "主管综合面",
    focus: "岗位匹配、沟通协作、业务理解、成长性和高层次技术判断"
  }
];

// HR 面是多轮面试的可选轮次，默认不包含，故单独导出，由调用方按用户选择拼接。
export const hrRoundTemplate: InterviewRoundTemplate = {
  kind: "hr",
  title: "HR 面",
  focus: "求职动机、稳定性、薪资期望、入职时间和职业规划"
};

// 多轮面试默认轮次顺序：同事技术面 → 资深技术面 → 主管综合面；HR 面可选并置于最后。
export const MULTI_ROUND_ORDER: InterviewRoundKind[] = [
  "peer_technical",
  "senior_technical",
  "manager_comprehensive"
];

// focus 文案需与后端 apps/api/app/interview_rounds.py 的 ROUND_TEMPLATES 逐字一致。
export function roundTemplatesForMode(
  mode: InterviewMode,
  includeHr: boolean
): InterviewRoundTemplate[] {
  if (mode !== "multi_round") {
    return [];
  }
  return includeHr ? [...defaultRoundTemplates, hrRoundTemplate] : defaultRoundTemplates;
}

export const defaultInterviewConfig = {
  mainQuestionCount: 6,
  maxFollowUpsPerQuestion: 2,
  mode: "single_round" satisfies InterviewMode,
  style: "learning" satisfies InterviewStyle
};

export const capabilityModel = [
  "专业知识准确性",
  "项目经验表达",
  "问题分析能力",
  "技术深度",
  "沟通结构化",
  "岗位匹配度"
] as const;

