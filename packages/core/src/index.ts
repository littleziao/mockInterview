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
    focus: "基础技术、项目真实性和一起完成工作的能力"
  },
  {
    kind: "senior_technical",
    title: "资深技术面",
    focus: "技术深度、方案取舍、边界条件和排障能力"
  },
  {
    kind: "manager_comprehensive",
    title: "主管综合面",
    focus: "岗位匹配、沟通协作、业务理解和高层次技术判断"
  }
];

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

