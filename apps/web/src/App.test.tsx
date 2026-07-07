import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

let interviewAnswerCount = 0;

type InProgressMockSession = {
  id: number;
  interviewId: number;
  style: string;
  status: string;
  mainQuestionCount: number;
  currentMainQuestionFollowUps: number;
  mainQuestionLimit: number;
  followUpLimit: number;
  targetRole: string;
  interviewMode: string;
};

let inProgressSessionsMock: InProgressMockSession[] = [];

type MockRoundProgress = {
  kind: string;
  title: string;
  focus: string;
  status: string;
  sessionId?: number | null;
};

let roundsProgressMock: MockRoundProgress[] = [];
let sessionRoundKindMock = "peer_technical";
let sessionRoundTitleMock = "同事技术面";
let resumeAnalysisRecordsMock: {
  id: number;
  targetRole: string;
  targetJobDescription?: string;
  hasTargetJobDescription?: boolean;
  summary: string;
  resumeMarkdown: string;
  analysis: {
    backgroundSummary: string;
    keyProjects: string[];
    technicalStack: string[];
    followUpTopics: string[];
    riskPoints: string[];
    unclearPoints: string[];
    targetRoleNotes: string;
    focusTopics: string[];
    lowPriorityFollowUpTopics: string[];
  };
  keyProjects: string[];
  technicalStack: string[];
  followUpTopics: string[];
  createdAt: string;
  lastUsedAt: string;
  useCount: number;
}[] = [];

// 默认 fetch mock 对 /answers 同步返回。乐观渲染需要验证「fetch 已发出但响应未到达」的中间态，
// 因此允许单个测试注入自定义处理器（例如挂起响应或返回失败状态）。
let answersHandlerOverride: ((init?: RequestInit) => Promise<Response> | Response) | null = null;

const historyPayloadMock = {
  targetRoles: ["前端工程师", "后端工程师"],
  records: [
    {
      id: 2,
      interviewId: 8,
      sessionId: 32,
      targetRole: "后端工程师",
      interviewMode: "single_round",
      style: "pressure",
      roundKind: "single_round",
      roundTitle: "",
      completedAt: "2026-07-02 10:30:00",
      transcript: [
        { role: "interviewer", content: "请介绍 API 设计。", kind: "main_question", mainQuestionIndex: 0 },
        { role: "candidate", content: "我负责 FastAPI 和 SQLite。", kind: "", mainQuestionIndex: 0 },
        { role: "interviewer", content: "异常路径怎么处理？", kind: "follow_up", mainQuestionIndex: 0 },
        { role: "candidate", content: "我会区分校验错误和 Provider 错误。", kind: "", mainQuestionIndex: 0 }
      ],
      review: {
        overallEvaluation: "后端复盘：接口边界清楚，排障细节还可以加强。",
        highlights: ["能讲清 API 职责"],
        mainIssues: ["异常路径说明不足"],
        questionReviews: ["第 1 题：API 边界清楚。", "补充点评：后续可以单独练习错误观测。"],
        improvedExpressionExamples: ["补充错误处理与观测方式。"],
        sampleAnswers: ["示范性回答：先讲接口契约，再讲异常处理。", "补充参考：也可以按状态码分类说明。"],
        knowledgeReferences: ["FastAPI 依赖注入"],
        learningFramework: ["整理 Repository 查询"],
        nextPracticeSuggestions: ["下一次重点练习排障表达。"],
        abilityScores: [
          { dimension: "专业知识准确性", score: 5, rationale: "概念准确。" },
          { dimension: "项目经验表达", score: 4, rationale: "项目表达清楚。" },
          { dimension: "问题分析能力", score: 4, rationale: "拆解合理。" },
          { dimension: "技术深度", score: 4, rationale: "有一定深度。" },
          { dimension: "沟通结构化", score: 3, rationale: "结构可加强。" },
          { dimension: "岗位匹配度", score: 5, rationale: "匹配岗位。" }
        ]
      }
    },
    {
      id: 1,
      interviewId: 7,
      sessionId: 31,
      targetRole: "前端工程师",
      interviewMode: "multi_round",
      style: "study",
      roundKind: "peer_technical",
      roundTitle: "同事技术面",
      completedAt: "2026-07-01 09:00:00",
      transcript: [
        { role: "interviewer", content: "请介绍前端工作台。", kind: "main_question", mainQuestionIndex: 0 },
        { role: "candidate", content: "我负责历史与趋势页。", kind: "", mainQuestionIndex: 0 }
      ],
      review: {
        overallEvaluation: "前端复盘：能说明页面结构，但趋势数据解释还可以更完整。",
        highlights: ["能结合真实页面回答"],
        mainIssues: ["趋势解释略少"],
        questionReviews: ["第 1 题：页面结构说明清楚。"],
        improvedExpressionExamples: ["先讲用户目标，再讲数据来源。"],
        sampleAnswers: ["示范性回答：历史页只统计已完成复盘的记录。"],
        knowledgeReferences: ["React 状态同步"],
        learningFramework: ["整理趋势维度"],
        nextPracticeSuggestions: ["下一次重点练习数据可视化表达。"],
        abilityScores: [
          { dimension: "专业知识准确性", score: 3, rationale: "概念基本准确。" },
          { dimension: "项目经验表达", score: 4, rationale: "项目表达较清楚。" },
          { dimension: "问题分析能力", score: 3, rationale: "拆解过程可加强。" },
          { dimension: "技术深度", score: 3, rationale: "技术深度可加强。" },
          { dimension: "沟通结构化", score: 4, rationale: "表达有结构。" },
          { dimension: "岗位匹配度", score: 4, rationale: "匹配岗位。" }
        ]
      }
    }
  ],
  trends: [
    {
      dimension: "专业知识准确性",
      averageScore: 4,
      points: [
        { historyRecordId: 1, completedAt: "2026-07-01 09:00:00", score: 3 },
        { historyRecordId: 2, completedAt: "2026-07-02 10:30:00", score: 5 }
      ]
    },
    { dimension: "项目经验表达", averageScore: 4, points: [{ historyRecordId: 1, completedAt: "2026-07-01 09:00:00", score: 4 }] },
    { dimension: "问题分析能力", averageScore: 3.5, points: [{ historyRecordId: 1, completedAt: "2026-07-01 09:00:00", score: 3 }] },
    { dimension: "技术深度", averageScore: 3.5, points: [{ historyRecordId: 1, completedAt: "2026-07-01 09:00:00", score: 3 }] },
    { dimension: "沟通结构化", averageScore: 3.5, points: [{ historyRecordId: 1, completedAt: "2026-07-01 09:00:00", score: 4 }] },
    { dimension: "岗位匹配度", averageScore: 4.5, points: [{ historyRecordId: 1, completedAt: "2026-07-01 09:00:00", score: 4 }] }
  ]
};

let deletedHistoryRecordIds: number[] = [];
let deletedResumeAnalysisRecordIds: number[] = [];

// 服务端对一次回答的权威响应：transcript 同时包含用户刚提交的回答与面试官的新消息。
// 乐观渲染测试用它作为「整体替换」的目标数据。
function buildAnswerResponse(answer: string) {
  return {
    id: 31,
    interviewId: 7,
    style: "study",
    status: "in_progress",
    mainQuestionCount: 1,
    currentMainQuestionFollowUps: 1,
    mainQuestionLimit: 6,
    followUpLimit: 2,
    transcript: [
      { role: "interviewer", content: "先做个自我介绍吧。", kind: "main_question", mainQuestionIndex: 0 },
      { role: "candidate", content: answer, kind: "", mainQuestionIndex: 0 },
      {
        role: "interviewer",
        content: "你提到 SQLite Repository，能说说它解决了什么问题吗？",
        kind: "follow_up",
        mainQuestionIndex: 0
      }
    ]
  };
}

describe("App", () => {
  beforeEach(() => {
    interviewAnswerCount = 0;
    inProgressSessionsMock = [];
    roundsProgressMock = [];
    sessionRoundKindMock = "peer_technical";
    sessionRoundTitleMock = "同事技术面";
    resumeAnalysisRecordsMock = [];
    answersHandlerOverride = null;
    deletedHistoryRecordIds = [];
    deletedResumeAnalysisRecordIds = [];
    window.location.hash = "#/";
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: vi.fn(() => "blob:mock-review")
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      value: vi.fn()
    });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);

        if (url.endsWith("/interview-sessions/in-progress") && !init) {
          return Response.json(inProgressSessionsMock);
        }

        if (url.endsWith("/resume-analysis-records") && !init) {
          return Response.json({
            records: resumeAnalysisRecordsMock.filter(
              (record) => !deletedResumeAnalysisRecordIds.includes(record.id)
            )
          });
        }

        if (url.match(/\/resume-analysis-records\/\d+$/) && !init) {
          const recordId = Number(url.split("/").at(-1));
          if (deletedResumeAnalysisRecordIds.includes(recordId)) {
            return Response.json({}, { status: 404 });
          }
          const record = resumeAnalysisRecordsMock.find((item) => item.id === recordId);
          if (!record) {
            return Response.json({}, { status: 404 });
          }
          return Response.json(record);
        }

        if (url.match(/\/resume-analysis-records\/\d+$/) && init?.method === "DELETE") {
          const deletedRecordId = Number(url.split("/").at(-1));
          deletedResumeAnalysisRecordIds.push(deletedRecordId);
          return new Response(null, { status: 204 });
        }

        if (url.match(/\/history\/\d+$/) && init?.method === "DELETE") {
          const deletedRecordId = Number(url.split("/").at(-1));
          deletedHistoryRecordIds.push(deletedRecordId);
          return new Response(null, { status: 204 });
        }

        if (url.includes("/history") && !init) {
          const visibleRecords = historyPayloadMock.records.filter(
            (record) => !deletedHistoryRecordIds.includes(record.id)
          );
          const visibleRecordIds = new Set(visibleRecords.map((record) => record.id));
          const visibleTrends = historyPayloadMock.trends.map((trend) => {
            const points = trend.points.filter((point) => visibleRecordIds.has(point.historyRecordId));
            return {
              ...trend,
              points,
              averageScore: points.length
                ? points.reduce((total, point) => total + point.score, 0) / points.length
                : 0
            };
          });

          if (url.includes("target_role=%E5%89%8D%E7%AB%AF%E5%B7%A5%E7%A8%8B%E5%B8%88")) {
            const frontendRecords = visibleRecords.filter((record) => record.targetRole === "前端工程师");
            const frontendRecordIds = new Set(frontendRecords.map((record) => record.id));
            return Response.json({
              ...historyPayloadMock,
              records: frontendRecords,
              trends: visibleTrends.map((trend) => {
                const points = trend.points.filter((point) => frontendRecordIds.has(point.historyRecordId));
                return {
                  ...trend,
                  points,
                  averageScore: points.length
                    ? points.reduce((total, point) => total + point.score, 0) / points.length
                    : 0
                };
              })
            });
          }
          return Response.json({
            ...historyPayloadMock,
            records: visibleRecords,
            trends: visibleTrends
          });
        }

        if (url.endsWith("/settings/ai-provider") && !init) {
          return Response.json({
            activeProviderId: "primary",
            providers: [
              {
                id: "primary",
                name: "主供应商",
                baseUrl: "fake://success",
                model: "mock-model",
                hasApiKey: true,
                isConfigured: true
              },
              {
                id: "backup",
                name: "备用供应商",
                baseUrl: "fake://failure",
                model: "backup-model",
                hasApiKey: true,
                isConfigured: true
              }
            ]
          });
        }

        if (url.endsWith("/settings/ai-provider") && init?.method === "PUT") {
          const body = JSON.parse(String(init.body));
          return Response.json({
            activeProviderId: body.activeProviderId,
            providers: body.providers.map((provider: { id: string; name: string; baseUrl: string; model: string }) => ({
              id: provider.id,
              name: provider.name,
              baseUrl: provider.baseUrl,
              model: provider.model,
              hasApiKey: true,
              isConfigured: true
            }))
          });
        }

        if (url.endsWith("/settings/ai-provider/test")) {
          return Response.json({
            status: "success",
            message: "AI Provider 连接测试成功"
          });
        }

        if (url.endsWith("/resume-analyses/generate")) {
          const body = JSON.parse(String(init?.body ?? "{}"));
          resumeAnalysisRecordsMock = [
            {
              id: resumeAnalysisRecordsMock.length + 1,
              targetRole: body.targetRole,
              targetJobDescription: body.targetJobDescription ?? "",
              hasTargetJobDescription: Boolean(body.targetJobDescription?.trim()),
              summary: "候选人具备前端工程经验",
              resumeMarkdown: body.resumeMarkdown,
              analysis: {
                backgroundSummary: "候选人具备前端工程经验",
                keyProjects: ["Mock Interview"],
                technicalStack: ["React", "FastAPI"],
                followUpTopics: ["项目职责", "技术取舍"],
                riskPoints: ["项目指标不清晰"],
                unclearPoints: ["上线规模未说明"],
                targetRoleNotes: "偏前端岗位",
                focusTopics: ["项目表达"],
                lowPriorityFollowUpTopics: ["弱相关运营经历"]
              },
              keyProjects: ["Mock Interview"],
              technicalStack: ["React", "FastAPI"],
              followUpTopics: ["项目职责", "技术取舍"],
              createdAt: "2026-07-03 10:15:00",
              lastUsedAt: "2026-07-03 10:15:00",
              useCount: 0
            },
            ...resumeAnalysisRecordsMock
          ];
          return Response.json({
            backgroundSummary: "候选人具备前端工程经验",
            keyProjects: ["Mock Interview"],
            technicalStack: ["React", "FastAPI"],
            followUpTopics: ["项目职责", "技术取舍"],
            riskPoints: ["项目指标不清晰"],
            unclearPoints: ["上线规模未说明"],
            targetRoleNotes: "偏前端岗位",
            focusTopics: ["项目表达"],
            lowPriorityFollowUpTopics: ["弱相关运营经历"]
          });
        }

        if (url.endsWith("/interviews") && init?.method === "POST") {
          const body = JSON.parse(String(init.body));
          if (body.sourceResumeAnalysisRecordId) {
            resumeAnalysisRecordsMock = resumeAnalysisRecordsMock.map((record) =>
              record.id === body.sourceResumeAnalysisRecordId
                ? {
                    ...record,
                    targetRole: body.targetRole,
                    targetJobDescription: body.targetJobDescription ?? "",
                    hasTargetJobDescription: Boolean(body.targetJobDescription?.trim()),
                    summary: body.analysis.background_summary,
                    resumeMarkdown: body.resumeMarkdown,
                    analysis: {
                      backgroundSummary: body.analysis.background_summary,
                      keyProjects: body.analysis.key_projects,
                      technicalStack: body.analysis.technical_stack,
                      followUpTopics: body.analysis.follow_up_topics,
                      riskPoints: body.analysis.risk_points,
                      unclearPoints: body.analysis.unclear_points,
                      targetRoleNotes: body.analysis.target_role_notes,
                      focusTopics: body.analysis.focus_topics,
                      lowPriorityFollowUpTopics: body.analysis.low_priority_follow_up_topics
                    },
                    keyProjects: body.analysis.key_projects,
                    technicalStack: body.analysis.technical_stack,
                    followUpTopics: body.analysis.follow_up_topics,
                    useCount: record.useCount + 1,
                    lastUsedAt: "2026-07-03 11:00:00"
                  }
                : record
            );
          }
          return Response.json({
            id: 7,
            resumeMarkdown: body.resumeMarkdown,
            targetRole: body.targetRole,
            targetJobDescription: body.targetJobDescription ?? "",
            interviewMode: body.interviewMode,
            includeHrRound: body.includeHrRound,
            sourceResumeAnalysisRecordId: body.sourceResumeAnalysisRecordId ?? null,
            analysis: body.analysis
          });
        }

        if (url.match(/\/interviews\/\d+\/sessions$/) && init?.method === "POST") {
          return Response.json({
            id: 31,
            interviewId: 7,
            style: "study",
            status: "in_progress",
            mainQuestionCount: 1,
            currentMainQuestionFollowUps: 0,
            mainQuestionLimit: 6,
            followUpLimit: 2,
            roundKind: sessionRoundKindMock,
            roundTitle: sessionRoundTitleMock,
            roundFocus: "基础技术、简历真实性、项目细节和协作可行性",
            transcript: [
              {
                role: "interviewer",
                content: "先做个自我介绍吧。",
                kind: "main_question",
                mainQuestionIndex: 0
              }
            ]
          });
        }

        if (url.match(/\/interviews\/\d+\/rounds$/) && !init) {
          return Response.json(roundsProgressMock);
        }

        if (url.match(/\/interview-sessions\/\d+\/answers$/) && init?.method === "POST") {
          if (answersHandlerOverride) {
            return Promise.resolve(answersHandlerOverride(init));
          }
          interviewAnswerCount += 1;
          return Response.json({
            id: 31,
            interviewId: 7,
            style: "study",
            status: "in_progress",
            mainQuestionCount: 1,
            currentMainQuestionFollowUps: 1,
            mainQuestionLimit: 6,
            followUpLimit: 2,
            transcript: [
              {
                role: "interviewer",
                content: "先做个自我介绍吧。",
                kind: "main_question",
                mainQuestionIndex: 0
              },
              {
                role: "candidate",
                content: JSON.parse(String(init.body)).answer,
                kind: "",
                mainQuestionIndex: 0
              },
              {
                role: "interviewer",
                content:
                  interviewAnswerCount === 1
                    ? "你提到 SQLite Repository，能说说它解决了什么问题吗？"
                    : "好的，我们换个方向。",
                kind: interviewAnswerCount === 1 ? "follow_up" : "clarify",
                mainQuestionIndex: 0
              }
            ]
          });
        }

        if (url.match(/\/interview-sessions\/\d+\/end$/) && init?.method === "POST") {
          return Response.json({
            id: 31,
            interviewId: 7,
            style: "study",
            status: "awaiting_review",
            mainQuestionCount: 1,
            currentMainQuestionFollowUps: 1,
            mainQuestionLimit: 6,
            followUpLimit: 2,
            transcript: [
              {
                role: "interviewer",
                content: "先做个自我介绍吧。",
                kind: "main_question",
                mainQuestionIndex: 0
              },
              {
                role: "candidate",
                content: "我负责简历分析和 AI Provider 接入。",
                kind: "",
                mainQuestionIndex: 0
              }
            ]
          });
        }

        if (url.match(/\/interview-sessions\/\d+\/review$/) && init?.method === "POST") {
          return Response.json({
            id: 31,
            interviewId: 7,
            style: "study",
            status: "ended",
            mainQuestionCount: 1,
            currentMainQuestionFollowUps: 1,
            mainQuestionLimit: 6,
            followUpLimit: 2,
            transcript: [
              {
                role: "interviewer",
                content: "先做个自我介绍吧。",
                kind: "main_question",
                mainQuestionIndex: 0
              },
              {
                role: "candidate",
                content: "我负责简历分析和 AI Provider 接入。",
                kind: "",
                mainQuestionIndex: 0
              }
            ],
            review: {
              overallEvaluation: "整体能说明项目背景，但技术取舍和结果指标还可以加强。",
              highlights: ["能基于真实项目经历回答问题"],
              mainIssues: ["项目结果指标还不够明确"],
              questionReviews: ["第 1 个主问题：回答覆盖背景，但缺少量化结果。"],
              improvedExpressionExamples: ["可以按 背景-行动-结果 的顺序说明项目贡献。"],
              sampleAnswers: ["示范性回答：这是一种可参考表达，不是唯一标准答案。"],
              knowledgeReferences: ["结构化输出校验"],
              learningFramework: ["整理项目指标", "练习技术取舍表达"],
              nextPracticeSuggestions: ["下一次重点练习项目深挖。"],
              abilityScores: [
                { dimension: "专业知识准确性", score: 3, rationale: "概念基本准确。" },
                { dimension: "项目经验表达", score: 4, rationale: "项目表达较清楚。" },
                { dimension: "问题分析能力", score: 3, rationale: "拆解过程还可加强。" },
                { dimension: "技术深度", score: 3, rationale: "底层机制展开不足。" },
                { dimension: "沟通结构化", score: 4, rationale: "表达有主线。" },
                { dimension: "岗位匹配度", score: 4, rationale: "经历和岗位较匹配。" }
              ]
            }
          });
        }

        if (url.match(/\/interview-sessions\/\d+\/abandon$/) && init?.method === "POST") {
          return Response.json({
            id: 31,
            interviewId: 7,
            style: "study",
            status: "abandoned",
            mainQuestionCount: 2,
            currentMainQuestionFollowUps: 1,
            mainQuestionLimit: 6,
            followUpLimit: 2,
            transcript: [
              { role: "interviewer", content: "继续上次的回答吧。", kind: "main_question", mainQuestionIndex: 0 },
              { role: "candidate", content: "我之前负责简历分析。", kind: "", mainQuestionIndex: 0 }
            ]
          });
        }

        if (url.match(/\/interview-sessions\/\d+$/) && !init) {
          return Response.json({
            id: 31,
            interviewId: 7,
            style: "study",
            status: "in_progress",
            mainQuestionCount: 2,
            currentMainQuestionFollowUps: 1,
            mainQuestionLimit: 6,
            followUpLimit: 2,
            transcript: [
              { role: "interviewer", content: "继续上次的回答吧。", kind: "main_question", mainQuestionIndex: 0 },
              { role: "candidate", content: "我之前负责简历分析。", kind: "", mainQuestionIndex: 0 }
            ]
          });
        }

        if (url.match(/\/interviews\/\d+$/) && !init) {
          return Response.json({
            id: 7,
            resumeMarkdown: "# 恢复的简历",
            targetRole: "前端工程师",
            targetJobDescription: "",
            interviewMode: "single_round",
            analysis: {
              backgroundSummary: "恢复的背景摘要",
              keyProjects: ["Mock Interview"],
              technicalStack: ["React"],
              followUpTopics: ["项目职责"],
              riskPoints: [],
              unclearPoints: [],
              targetRoleNotes: "",
              focusTopics: [],
              lowPriorityFollowUpTopics: []
            }
          });
        }

        return Response.json({}, { status: 404 });
      })
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    window.location.hash = "#/";
  });

  it("renders the local mock interview shell", async () => {
    render(<App />);

    // 等待首页进行中面试列表加载完成，避免异步状态更新落在 act 之外。
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "AI 模拟面试工作台" })).toBeInTheDocument();
    });
    expect(screen.getByRole("heading", { name: "上传简历" })).toBeInTheDocument();
    expect(screen.getByText("FastAPI / SQLite 就绪")).toBeInTheDocument();
  });

  it("switches, saves, and tests multiple AI provider settings from the settings page", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "设置" }));

    expect(screen.getByRole("heading", { name: "AI Provider 设置" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /主供应商/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /备用供应商/ })).toBeInTheDocument();
    expect(await screen.findByDisplayValue("fake://success")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("已保存密钥；重新输入会覆盖")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /备用供应商/ }));
    expect(screen.getByDisplayValue("fake://failure")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "新增供应商" }));
    expect(screen.getByDisplayValue("模型供应商 3")).toBeInTheDocument();

    await user.type(screen.getByLabelText("API Key"), "secret-key");
    await user.click(screen.getByRole("button", { name: "保存配置" }));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        "http://127.0.0.1:8000/settings/ai-provider",
        expect.objectContaining({ method: "PUT" })
      );
    });

    await user.click(screen.getByRole("button", { name: "测试连接" }));

    const successMessage = await screen.findByText("AI Provider 连接测试成功");
    expect(successMessage).toBeInTheDocument();
    expect(successMessage.closest(".connectionState")).toHaveClass("success");
  });

  it("展示历史记录、按目标岗位筛选并打开复盘趋势", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "历史与趋势" }));

    expect(await screen.findByRole("heading", { name: "历史与趋势" })).toBeInTheDocument();
    expect(screen.getByLabelText("历史统计")).toHaveTextContent("完成记录");
    expect(screen.getByLabelText("历史统计")).toHaveTextContent("2");
    expect(screen.getByLabelText("已完成面试记录列表")).toHaveTextContent("后端工程师");
    expect(screen.getByLabelText("六维能力趋势")).toHaveTextContent("专业知识准确性");
    expect(screen.getByLabelText("六维能力趋势")).toHaveTextContent("平均 4.0 / 5");
    expect(screen.getAllByText("后端复盘：接口边界清楚，排障细节还可以加强。").length).toBeGreaterThan(0);
    const backendConversationReview = screen.getByLabelText("逐题对话复盘");
    expect(backendConversationReview).toHaveTextContent("第 1 个主问题");
    expect(backendConversationReview).toHaveTextContent("请介绍 API 设计。");
    expect(backendConversationReview).toHaveTextContent("异常路径怎么处理？");
    expect(backendConversationReview).toHaveTextContent("我会区分校验错误和 Provider 错误。");
    expect(backendConversationReview).toHaveTextContent("第 1 题：API 边界清楚。");
    expect(backendConversationReview).toHaveTextContent("示范性回答：先讲接口契约，再讲异常处理。");
    expect(backendConversationReview).toHaveTextContent("补充点评：后续可以单独练习错误观测。");
    expect(backendConversationReview).toHaveTextContent("补充参考：也可以按状态码分类说明。");
    const backendSummaryReview = screen.getByLabelText("跨题总结复盘");
    expect(backendSummaryReview).toHaveTextContent("能讲清 API 职责");
    expect(backendSummaryReview).not.toHaveTextContent("第 1 题：API 边界清楚。");
    expect(backendSummaryReview).not.toHaveTextContent("示范性回答：先讲接口契约，再讲异常处理。");

    await user.click(screen.getByRole("button", { name: "前端工程师" }));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        "http://127.0.0.1:8000/history?target_role=%E5%89%8D%E7%AB%AF%E5%B7%A5%E7%A8%8B%E5%B8%88"
      );
    });
    await waitFor(() => {
      expect(screen.getAllByText("前端复盘：能说明页面结构，但趋势数据解释还可以更完整。").length).toBeGreaterThan(0);
    });
    expect(screen.getByLabelText("已完成面试记录列表")).not.toHaveTextContent("后端工程师");
    expect(screen.getByLabelText("逐题对话复盘")).toHaveTextContent("请介绍前端工作台。");
    expect(screen.getByLabelText("逐题对话复盘")).toHaveTextContent("我负责历史与趋势页。");
  });

  it("在历史与趋势页二次确认后删除完成记录并刷新列表、详情和趋势", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "历史与趋势" }));

    expect(await screen.findByRole("heading", { name: "历史与趋势" })).toBeInTheDocument();
    expect(screen.getByLabelText("已完成面试记录列表")).toHaveTextContent("后端工程师");
    expect(screen.getByLabelText("历史统计")).toHaveTextContent("2");
    expect(screen.getByLabelText("六维能力趋势")).toHaveTextContent("平均 4.0 / 5");
    expect(screen.getByLabelText("历史复盘详情")).toHaveTextContent("后端复盘：接口边界清楚，排障细节还可以加强。");

    await user.click(screen.getByRole("button", { name: "删除后端工程师完成记录" }));

    const dialog = await screen.findByRole("dialog", { name: "删除已完成面试记录" });
    expect(dialog).toHaveTextContent("会删除这次面试的对话、复盘和能力评分，并从长期趋势中移除");
    await user.click(within(dialog).getByRole("button", { name: "确认删除" }));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        "http://127.0.0.1:8000/history/2",
        expect.objectContaining({ method: "DELETE" })
      );
    });
    await waitFor(() => {
      expect(screen.getByLabelText("已完成面试记录列表")).not.toHaveTextContent("后端工程师");
    });
    expect(screen.getByLabelText("历史统计")).toHaveTextContent("1");
    expect(screen.queryByText("后端复盘：接口边界清楚，排障细节还可以加强。")).not.toBeInTheDocument();
    expect(screen.getByLabelText("历史复盘详情")).toHaveTextContent("前端复盘：能说明页面结构");
    expect(screen.getByLabelText("六维能力趋势")).toHaveTextContent("平均 3.0 / 5");
  });

  it("覆盖新建面试流程三步主路径、可编辑简历分析和只读面试配置摘要", async () => {
    const user = userEvent.setup();
    render(<App />);

    const resumeInput = screen.getByLabelText("Markdown 简历");
    const fileInput = screen.getByLabelText("导入 Markdown 简历");
    const file = new File(["# 李四\n\n## 项目\n- 简历分析流程"], "resume.md", { type: "text/markdown" });

    await user.upload(fileInput, file);

    await waitFor(() => {
      expect(resumeInput).toHaveValue("# 李四\n\n## 项目\n- 简历分析流程");
    });
    expect(screen.getByText("最近导入：resume.md")).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalledWith(
      "http://127.0.0.1:8000/resume-analyses/generate",
      expect.anything()
    );

    await user.click(screen.getByRole("button", { name: "解析简历" }));

    expect(await screen.findByRole("heading", { name: "简历解析与配置" })).toBeInTheDocument();
    const backgroundSummary = await screen.findByDisplayValue("候选人具备前端工程经验");
    await user.clear(backgroundSummary);
    await user.type(backgroundSummary, "用户编辑后的背景摘要");

    const lowPriority = screen.getByLabelText("不希望重点追问的内容");
    await user.clear(lowPriority);
    await user.type(lowPriority, "弱相关外包经历");
    await user.click(screen.getByRole("button", { name: "多轮面试" }));
    await user.click(screen.getByRole("button", { name: "压力面" }));
    await user.click(screen.getByRole("button", { name: "确认配置并开始面试" }));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        "http://127.0.0.1:8000/interviews",
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining("用户编辑后的背景摘要")
        })
      );
    });
    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/interviews",
      expect.objectContaining({
        body: expect.stringContaining("low_priority_follow_up_topics")
      })
    );
    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/interviews",
      expect.objectContaining({
        body: expect.stringContaining('"interviewMode":"multi_round"')
      })
    );
    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/interviews/7/sessions",
      expect.objectContaining({
        method: "POST",
        body: expect.stringContaining("pressure")
      })
    );
    expect(await screen.findByRole("heading", { name: "开始面试" })).toBeInTheDocument();
    expect(screen.getByLabelText("面试配置摘要")).toHaveTextContent("前端工程师");
    expect(screen.getByLabelText("面试配置摘要")).toHaveTextContent("多轮面试");
    expect(screen.getByLabelText("面试配置摘要")).toHaveTextContent("压力面");
    expect(screen.getByText("先做个自我介绍吧。")).toBeInTheDocument();
    expect(screen.queryByText("示范性回答：这是一种可参考表达，不是唯一标准答案。")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("目标岗位")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "手动结束" }));
    expect(await screen.findByText("面试已结束，请确认是否生成复盘。")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "提交回答" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "生成复盘" }));

    expect(await screen.findByRole("heading", { name: "面试复盘" })).toBeInTheDocument();
    expect(screen.getByText("整体能说明项目背景，但技术取舍和结果指标还可以加强。")).toBeInTheDocument();
    expect(screen.getByLabelText("六维能力评分雷达图")).toHaveTextContent("专业知识准确性");
    expect(screen.getByLabelText("六维能力评分雷达图")).toHaveTextContent("4/5");
    const reviewConversation = screen.getByLabelText("逐题对话复盘");
    expect(reviewConversation).toHaveTextContent("先做个自我介绍吧。");
    expect(reviewConversation).toHaveTextContent("我负责简历分析和 AI Provider 接入。");
    expect(reviewConversation).toHaveTextContent("第 1 个主问题：回答覆盖背景，但缺少量化结果。");
    expect(reviewConversation).toHaveTextContent("示范性回答：这是一种可参考表达，不是唯一标准答案。");
    expect(screen.getByLabelText("跨题总结复盘")).not.toHaveTextContent("示范性回答：这是一种可参考表达，不是唯一标准答案。");

    await user.click(screen.getByRole("button", { name: "导出 Markdown" }));

    expect(URL.createObjectURL).toHaveBeenCalledWith(expect.any(Blob));
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:mock-review");
  });

  it("上传页可粘贴目标岗位 JD 并在解析和开始面试时透传", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.type(
      screen.getByLabelText(/目标岗位 JD/),
      "职责：负责 React 工作台体验；要求：TypeScript、接口协作。"
    );
    expect(screen.getByText("37 / 8000")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "解析简历" }));

    expect(await screen.findByRole("heading", { name: "简历解析与配置" })).toBeInTheDocument();
    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        "http://127.0.0.1:8000/resume-analyses/generate",
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining('"targetJobDescription":"职责：负责 React 工作台体验；要求：TypeScript、接口协作。"')
        })
      );
    });

    await user.click(screen.getByRole("button", { name: "确认配置并开始面试" }));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        "http://127.0.0.1:8000/interviews",
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining('"targetJobDescription":"职责：负责 React 工作台体验；要求：TypeScript、接口协作。"')
        })
      );
    });
  });

  it("目标岗位 JD 超过 8000 字符时前端拦截解析并提示", async () => {
    const user = userEvent.setup();
    render(<App />);

    fireEvent.change(screen.getByLabelText(/目标岗位 JD/), { target: { value: "前".repeat(8001) } });
    await user.click(screen.getByRole("button", { name: "解析简历" }));

    expect(screen.getByText("目标岗位 JD 不能超过 8000 字符")).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalledWith(
      "http://127.0.0.1:8000/resume-analyses/generate",
      expect.anything()
    );
  });

  it("解析成功后在简历库可看到简历分析历史列表", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "解析简历" }));
    expect(await screen.findByRole("heading", { name: "简历解析与配置" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "简历库" }));

    const historyList = await screen.findByLabelText("简历分析历史列表");
    expect(historyList).toHaveTextContent("前端工程师");
    expect(historyList).toHaveTextContent("候选人具备前端工程经验");
    expect(historyList).toHaveTextContent("使用 0 次");
    expect(historyList).toHaveTextContent("Mock Interview");
    expect(historyList).toHaveTextContent("React / FastAPI");
  });

  it("可从简历库进入确认页，编辑后再开始面试", async () => {
    resumeAnalysisRecordsMock = [
      {
        id: 42,
        targetRole: "前端工程师",
        targetJobDescription: "历史 JD：负责 React 平台体验。",
        hasTargetJobDescription: true,
        summary: "历史背景摘要",
        resumeMarkdown: "# 历史简历\n\n- 历史项目",
        analysis: {
          backgroundSummary: "历史背景摘要",
          keyProjects: ["历史项目"],
          technicalStack: ["React"],
          followUpTopics: ["历史追问"],
          riskPoints: ["历史风险"],
          unclearPoints: [],
          targetRoleNotes: "历史岗位说明",
          focusTopics: ["历史重点"],
          lowPriorityFollowUpTopics: ["历史低优先级"]
        },
        keyProjects: ["历史项目"],
        technicalStack: ["React"],
        followUpTopics: ["历史追问"],
        createdAt: "2026-07-03 09:00:00",
        lastUsedAt: "2026-07-03 09:00:00",
        useCount: 0
      }
    ];
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "简历库" }));
    const historyList = await screen.findByLabelText("简历分析历史列表");
    await user.click(within(historyList).getByRole("button", { name: "用于面试" }));

    expect(await screen.findByRole("heading", { name: "简历解析与配置" })).toBeInTheDocument();
    expect(screen.getByDisplayValue("历史背景摘要")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith("http://127.0.0.1:8000/resume-analysis-records/42");
    expect(fetch).not.toHaveBeenCalledWith(
      "http://127.0.0.1:8000/interviews/7/sessions",
      expect.objectContaining({ method: "POST" })
    );

    const backgroundSummary = screen.getByDisplayValue("历史背景摘要");
    await user.clear(backgroundSummary);
    await user.type(backgroundSummary, "确认页编辑后的背景摘要");
    await user.click(screen.getByRole("button", { name: "多轮面试" }));
    await user.click(screen.getByRole("button", { name: "确认配置并开始面试" }));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        "http://127.0.0.1:8000/interviews",
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining('"sourceResumeAnalysisRecordId":42')
        })
      );
    });
    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/interviews",
      expect.objectContaining({
        body: expect.stringContaining("确认页编辑后的背景摘要")
      })
    );
    expect(await screen.findByRole("heading", { name: "开始面试" })).toBeInTheDocument();
    expect(screen.getByText("先做个自我介绍吧。")).toBeInTheDocument();
  });

  it("可在简历库展开详情查看完整 Markdown 简历和结构化分析", async () => {
    resumeAnalysisRecordsMock = [
      {
        id: 42,
        targetRole: "前端工程师",
        targetJobDescription: "历史 JD：负责 React 平台体验。",
        hasTargetJobDescription: true,
        summary: "历史背景摘要",
        resumeMarkdown: "# 历史简历\n\n## 项目经历\n- 历史项目",
        analysis: {
          backgroundSummary: "完整背景摘要",
          keyProjects: ["历史项目"],
          technicalStack: ["React", "TypeScript"],
          followUpTopics: ["历史追问"],
          riskPoints: ["历史风险"],
          unclearPoints: ["历史不清"],
          targetRoleNotes: "历史岗位说明",
          focusTopics: ["历史重点"],
          lowPriorityFollowUpTopics: ["历史低优先级"]
        },
        keyProjects: ["历史项目"],
        technicalStack: ["React", "TypeScript"],
        followUpTopics: ["历史追问"],
        createdAt: "2026-07-03 09:00:00",
        lastUsedAt: "2026-07-03 09:00:00",
        useCount: 0
      }
    ];
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "简历库" }));
    const historyList = await screen.findByLabelText("简历分析历史列表");
    expect(historyList).toHaveTextContent("含目标岗位 JD");
    await user.click(within(historyList).getByRole("button", { name: "查看详情" }));

    const detail = await screen.findByLabelText("简历分析记录详情");
    expect(detail).toHaveTextContent("# 历史简历");
    expect(detail).toHaveTextContent("完整目标岗位 JD");
    expect(detail).toHaveTextContent("历史 JD：负责 React 平台体验。");
    expect(detail).toHaveTextContent("完整背景摘要");
    expect(detail).toHaveTextContent("历史项目");
    expect(detail).toHaveTextContent("React");
    expect(detail).toHaveTextContent("历史风险");
    expect(detail).toHaveTextContent("历史低优先级");
    expect(fetch).toHaveBeenCalledWith("http://127.0.0.1:8000/resume-analysis-records/42");

    await user.click(screen.getByRole("button", { name: "收起详情" }));
    expect(screen.queryByLabelText("简历分析记录详情")).not.toBeInTheDocument();
  });

  it("从简历库复用记录时预填目标岗位 JD", async () => {
    resumeAnalysisRecordsMock = [
      {
        id: 42,
        targetRole: "前端工程师",
        targetJobDescription: "历史 JD：负责 React 平台体验。",
        hasTargetJobDescription: true,
        summary: "历史背景摘要",
        resumeMarkdown: "# 历史简历\n\n- 历史项目",
        analysis: {
          backgroundSummary: "历史背景摘要",
          keyProjects: ["历史项目"],
          technicalStack: ["React"],
          followUpTopics: ["历史追问"],
          riskPoints: [],
          unclearPoints: [],
          targetRoleNotes: "历史岗位说明",
          focusTopics: [],
          lowPriorityFollowUpTopics: []
        },
        keyProjects: ["历史项目"],
        technicalStack: ["React"],
        followUpTopics: ["历史追问"],
        createdAt: "2026-07-03 09:00:00",
        lastUsedAt: "2026-07-03 09:00:00",
        useCount: 0
      }
    ];
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "简历库" }));
    const historyList = await screen.findByLabelText("简历分析历史列表");
    await user.click(within(historyList).getByRole("button", { name: "用于面试" }));
    expect(await screen.findByRole("heading", { name: "简历解析与配置" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "返回修改简历" }));

    expect(screen.getByLabelText(/目标岗位 JD/)).toHaveValue("历史 JD：负责 React 平台体验。");
  });

  it("删除简历分析记录经二次确认后从列表移除且不影响历史面试", async () => {
    resumeAnalysisRecordsMock = [
      {
        id: 42,
        targetRole: "前端工程师",
        summary: "历史背景摘要",
        resumeMarkdown: "# 历史简历\n\n- 历史项目",
        analysis: {
          backgroundSummary: "历史背景摘要",
          keyProjects: ["历史项目"],
          technicalStack: ["React"],
          followUpTopics: ["历史追问"],
          riskPoints: [],
          unclearPoints: [],
          targetRoleNotes: "",
          focusTopics: [],
          lowPriorityFollowUpTopics: []
        },
        keyProjects: ["历史项目"],
        technicalStack: ["React"],
        followUpTopics: ["历史追问"],
        createdAt: "2026-07-03 09:00:00",
        lastUsedAt: "2026-07-03 09:00:00",
        useCount: 0
      }
    ];
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "简历库" }));
    const historyList = await screen.findByLabelText("简历分析历史列表");
    await user.click(within(historyList).getByRole("button", { name: "删除前端工程师简历分析记录" }));

    const dialog = await screen.findByRole("dialog", { name: "删除简历分析记录" });
    expect(dialog).toHaveTextContent("不会影响已开始或已完成的面试");
    await user.click(within(dialog).getByRole("button", { name: "确认删除" }));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        "http://127.0.0.1:8000/resume-analysis-records/42",
        expect.objectContaining({ method: "DELETE" })
      );
    });
    await waitFor(() => {
      expect(screen.getByText("暂无简历分析记录，解析成功后会出现在这里。")).toBeInTheDocument();
    });

    // 删除简历分析记录不影响历史与趋势页的面试记录。
    await user.click(screen.getByRole("button", { name: "历史与趋势" }));
    expect(await screen.findByLabelText("已完成面试记录列表")).toHaveTextContent("后端工程师");
  });

  it("上传页可选择历史简历分析并进入确认页", async () => {
    resumeAnalysisRecordsMock = [
      {
        id: 43,
        targetRole: "后端工程师",
        summary: "后端历史摘要",
        resumeMarkdown: "# 后端简历",
        analysis: {
          backgroundSummary: "后端历史摘要",
          keyProjects: ["API 项目"],
          technicalStack: ["FastAPI"],
          followUpTopics: ["接口设计"],
          riskPoints: [],
          unclearPoints: [],
          targetRoleNotes: "",
          focusTopics: [],
          lowPriorityFollowUpTopics: []
        },
        keyProjects: ["API 项目"],
        technicalStack: ["FastAPI"],
        followUpTopics: ["接口设计"],
        createdAt: "2026-07-03 09:10:00",
        lastUsedAt: "2026-07-03 09:10:00",
        useCount: 1
      }
    ];
    const user = userEvent.setup();
    render(<App />);

    const reuseBox = await screen.findByLabelText("从历史简历开始");
    await user.click(within(reuseBox).getByRole("button", { name: "后端工程师" }));

    expect(await screen.findByRole("heading", { name: "简历解析与配置" })).toBeInTheDocument();
    expect(screen.getByDisplayValue("后端历史摘要")).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalledWith(
      "http://127.0.0.1:8000/interviews/7/sessions",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("回退修改目标岗位后显式失效已生成的简历分析", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "解析简历" }));
    expect(await screen.findByRole("heading", { name: "简历解析与配置" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "返回修改简历" }));
    await user.clear(screen.getByLabelText("目标岗位"));
    await user.type(screen.getByLabelText("目标岗位"), "后端工程师");

    expect(screen.getByText("简历、目标岗位或目标岗位 JD 已修改，需要重新解析简历")).toBeInTheDocument();

    window.history.back();
    expect(await screen.findByRole("heading", { name: "需要先解析简历" })).toBeInTheDocument();
  });

  it("回退修改目标岗位 JD 后显式失效已生成的简历分析", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "解析简历" }));
    expect(await screen.findByRole("heading", { name: "简历解析与配置" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "返回修改简历" }));
    await user.type(screen.getByLabelText(/目标岗位 JD/), "新增 JD 要求");

    expect(screen.getByText("简历、目标岗位或目标岗位 JD 已修改，需要重新解析简历")).toBeInTheDocument();

    window.history.back();
    expect(await screen.findByRole("heading", { name: "需要先解析简历" })).toBeInTheDocument();
  });

  it("缺少新建面试上下文时守卫后续步骤路由", async () => {
    window.location.hash = "#/new/interview";
    render(<App />);

    expect(await screen.findByRole("heading", { name: "面试尚未开始" })).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "回到前置步骤" }));

    expect(await screen.findByRole("heading", { name: "上传简历" })).toBeInTheDocument();
  });

  it("首页检测到进行中面试时展示恢复入口与进度摘要", async () => {
    inProgressSessionsMock = [
      {
        id: 31,
        interviewId: 7,
        style: "study",
        status: "in_progress",
        mainQuestionCount: 2,
        currentMainQuestionFollowUps: 1,
        mainQuestionLimit: 6,
        followUpLimit: 2,
        targetRole: "前端工程师",
        interviewMode: "single_round"
      }
    ];
    render(<App />);

    expect(await screen.findByRole("heading", { name: "未完成的面试" })).toBeInTheDocument();
    expect(screen.getByText(/目标岗位：前端工程师/)).toBeInTheDocument();
    expect(screen.getByText(/第 2 \/ 6 个主问题/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "继续面试" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "放弃" })).toBeInTheDocument();
  });

  it("在首页放弃进行中面试后调用 abandon 接口并移除卡片", async () => {
    const user = userEvent.setup();
    inProgressSessionsMock = [
      {
        id: 31,
        interviewId: 7,
        style: "study",
        status: "in_progress",
        mainQuestionCount: 2,
        currentMainQuestionFollowUps: 1,
        mainQuestionLimit: 6,
        followUpLimit: 2,
        targetRole: "前端工程师",
        interviewMode: "single_round"
      }
    ];
    render(<App />);

    await screen.findByRole("heading", { name: "未完成的面试" });
    await user.click(screen.getByRole("button", { name: "放弃" }));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        "http://127.0.0.1:8000/interview-sessions/31/abandon",
        expect.objectContaining({ method: "POST" })
      );
    });
    await waitFor(() => {
      expect(screen.queryByRole("heading", { name: "未完成的面试" })).not.toBeInTheDocument();
    });
  });

  it("继续进行中面试时拉取会话与简历并恢复到面试页", async () => {
    const user = userEvent.setup();
    inProgressSessionsMock = [
      {
        id: 31,
        interviewId: 7,
        style: "study",
        status: "in_progress",
        mainQuestionCount: 2,
        currentMainQuestionFollowUps: 1,
        mainQuestionLimit: 6,
        followUpLimit: 2,
        targetRole: "前端工程师",
        interviewMode: "single_round"
      }
    ];
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "继续面试" }));

    expect(await screen.findByRole("heading", { name: "开始面试" })).toBeInTheDocument();
    expect(screen.getByText("继续上次的回答吧。")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith("http://127.0.0.1:8000/interview-sessions/31");
    expect(fetch).toHaveBeenCalledWith("http://127.0.0.1:8000/interviews/7");
  });

  it("存在进行中面试时禁止新建并提示先去首页处理", async () => {
    const user = userEvent.setup();
    inProgressSessionsMock = [
      {
        id: 31,
        interviewId: 7,
        style: "study",
        status: "in_progress",
        mainQuestionCount: 1,
        currentMainQuestionFollowUps: 0,
        mainQuestionLimit: 6,
        followUpLimit: 2,
        targetRole: "前端工程师",
        interviewMode: "single_round"
      }
    ];
    render(<App />);
    await screen.findByRole("heading", { name: "未完成的面试" });

    await user.click(screen.getByRole("button", { name: "解析简历" }));
    expect(await screen.findByRole("heading", { name: "简历解析与配置" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "确认配置并开始面试" }));

    expect(await screen.findByText("已有未完成的面试，请先在首页继续或放弃后再开始新面试")).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalledWith(
      "http://127.0.0.1:8000/interviews",
      expect.objectContaining({ method: "POST" })
    );
  });

  async function runMultiRoundToInterview(user: ReturnType<typeof userEvent.setup>) {
    await user.click(screen.getByRole("button", { name: "解析简历" }));
    await screen.findByRole("heading", { name: "简历解析与配置" });
    await user.click(screen.getByRole("button", { name: "多轮面试" }));
    await user.click(screen.getByRole("button", { name: "确认配置并开始面试" }));
    await screen.findByRole("heading", { name: "开始面试" });
  }

  it("选择多轮时展示 HR 面复选框、轮次预览并透传 includeHrRound", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "解析简历" }));
    await screen.findByRole("heading", { name: "简历解析与配置" });

    await user.click(screen.getByRole("button", { name: "多轮面试" }));
    const hrCheckbox = await screen.findByRole("checkbox", { name: /加入 HR 面/ });
    const preview = screen.getByLabelText("多轮面试轮次预览");
    expect(preview.querySelectorAll("li")).toHaveLength(3);
    expect(within(preview).queryByText("HR 面")).not.toBeInTheDocument();

    await user.click(hrCheckbox);
    const items = preview.querySelectorAll("li");
    expect(items).toHaveLength(4);
    expect(within(preview).getByText("HR 面")).toBeInTheDocument();
    // focus 文案需与后端 apps/api/app/interview_rounds.py 逐字一致，此处守住前端镜像不漂移。
    expect(within(preview).getByText("基础技术、简历真实性、项目细节和协作可行性")).toBeInTheDocument();
    expect(within(preview).getByText("求职动机、稳定性、薪资期望、入职时间和职业规划")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "确认配置并开始面试" }));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        "http://127.0.0.1:8000/interviews",
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining('"includeHrRound":true')
        })
      );
    });
    expect(await screen.findByLabelText("面试配置摘要")).toHaveTextContent("同事技术面");
  });

  it("多轮复盘后存在待进行轮次时展示进入下一轮入口并触发推进", async () => {
    roundsProgressMock = [
      { kind: "peer_technical", title: "同事技术面", focus: "同事焦点", status: "completed", sessionId: 31 },
      { kind: "senior_technical", title: "资深技术面", focus: "资深焦点", status: "pending" },
      { kind: "manager_comprehensive", title: "主管综合面", focus: "主管焦点", status: "pending" }
    ];
    const user = userEvent.setup();
    render(<App />);

    await runMultiRoundToInterview(user);
    await user.click(screen.getByRole("button", { name: "手动结束" }));
    await screen.findByText("面试已结束，请确认是否生成复盘。");
    await user.click(screen.getByRole("button", { name: "生成复盘" }));

    expect(await screen.findByRole("heading", { name: "面试复盘" })).toBeInTheDocument();
    expect(await screen.findByText("下一轮：资深技术面")).toBeInTheDocument();
    const nextButton = screen.getByRole("button", { name: /进入下一轮/ });
    expect(nextButton).toBeInTheDocument();

    await user.click(nextButton);
    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        "http://127.0.0.1:8000/interviews/7/sessions",
        expect.objectContaining({ method: "POST" })
      );
    });
    expect(await screen.findByRole("heading", { name: "开始面试" })).toBeInTheDocument();
  });

  it("多轮全部轮次完成时复盘页提示全部完成", async () => {
    roundsProgressMock = [
      { kind: "peer_technical", title: "同事技术面", focus: "", status: "completed" },
      { kind: "senior_technical", title: "资深技术面", focus: "", status: "completed" },
      { kind: "manager_comprehensive", title: "主管综合面", focus: "", status: "completed" }
    ];
    const user = userEvent.setup();
    render(<App />);

    await runMultiRoundToInterview(user);
    await user.click(screen.getByRole("button", { name: "手动结束" }));
    await user.click(await screen.findByRole("button", { name: "生成复盘" }));

    expect(await screen.findByText(/全部轮次已完成/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /进入下一轮/ })).not.toBeInTheDocument();
  });

  it("提交回答后用户回答与思考气泡立即出现，先于服务端回复", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "解析简历" }));
    await screen.findByRole("heading", { name: "简历解析与配置" });
    await user.click(screen.getByRole("button", { name: "确认配置并开始面试" }));
    await screen.findByRole("heading", { name: "开始面试" });

    // 让服务端响应挂起：用受控的 Promise，测试期间永不 resolve，
    // 以便断言「fetch 已发出但响应未到达」的乐观渲染中间态。
    let releaseServer!: () => void;
    answersHandlerOverride = () =>
      new Promise<Response>((resolve) => {
        releaseServer = () => resolve(Response.json(buildAnswerResponse("我负责简历分析与 Provider 接入")));
      });

    // 查询限定在对话记录区域内，避免误匹配回答输入框里的同名文本。
    const transcript = screen.getByLabelText("面试对话记录");

    await user.type(screen.getByLabelText("文字回答"), "我负责简历分析与 Provider 接入");
    await user.click(screen.getByRole("button", { name: "提交回答" }));

    // 乐观渲染：用户回答立即进入对话记录，面试官「正在思考」气泡同时出现，
    // 而服务端响应尚未到达（面试官的真实追问还未出现）。
    await waitFor(() => {
      expect(within(transcript).getByText("我负责简历分析与 Provider 接入")).toBeInTheDocument();
    });
    expect(within(transcript).getByText(/正在思考/)).toBeInTheDocument();
    expect(within(transcript).queryByText("你提到 SQLite Repository，能说说它解决了什么问题吗？")).not.toBeInTheDocument();

    releaseServer();
  });

  it("服务端回复到达后用权威 transcript 整体替换乐观消息与思考气泡", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "解析简历" }));
    await screen.findByRole("heading", { name: "简历解析与配置" });
    await user.click(screen.getByRole("button", { name: "确认配置并开始面试" }));
    await screen.findByRole("heading", { name: "开始面试" });

    let releaseServer!: () => void;
    answersHandlerOverride = () =>
      new Promise<Response>((resolve) => {
        releaseServer = () => resolve(Response.json(buildAnswerResponse("我负责简历分析与 Provider 接入")));
      });

    const transcript = screen.getByLabelText("面试对话记录");

    await user.type(screen.getByLabelText("文字回答"), "我负责简历分析与 Provider 接入");
    await user.click(screen.getByRole("button", { name: "提交回答" }));

    // 先确认进入乐观中间态（思考气泡存在）。
    await waitFor(() => {
      expect(within(transcript).getByText(/正在思考/)).toBeInTheDocument();
    });

    // 服务端权威响应到达。
    releaseServer();

    // 整体替换：思考气泡消失，真实追问出现；用户回答保留且只出现一次（不与乐观消息重复）。
    await waitFor(() => {
      expect(within(transcript).queryByText(/正在思考/)).not.toBeInTheDocument();
    });
    expect(within(transcript).getByText("你提到 SQLite Repository，能说说它解决了什么问题吗？")).toBeInTheDocument();
    expect(within(transcript).getAllByText("我负责简历分析与 Provider 接入")).toHaveLength(1);
  });

  it("提交失败时回滚乐观消息、恢复回答草稿并显示错误", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "解析简历" }));
    await screen.findByRole("heading", { name: "简历解析与配置" });
    await user.click(screen.getByRole("button", { name: "确认配置并开始面试" }));
    await screen.findByRole("heading", { name: "开始面试" });

    // 服务端返回失败，模拟网络或校验错误。
    answersHandlerOverride = () => Response.json({ detail: "服务端校验失败" }, { status: 500 });

    const transcript = screen.getByLabelText("面试对话记录");
    const answerInput = screen.getByLabelText("文字回答");

    await user.type(answerInput, "我负责简历分析与 Provider 接入");
    await user.click(screen.getByRole("button", { name: "提交回答" }));

    // 乐观消息与思考气泡回滚：对话记录回到初始状态（只剩面试官开场问题）。
    await waitFor(() => {
      expect(within(transcript).queryByText(/正在思考/)).not.toBeInTheDocument();
    });
    expect(within(transcript).queryByText("我负责简历分析与 Provider 接入")).not.toBeInTheDocument();
    // 回答草稿恢复、错误提示可见，方便用户改后重发。
    expect(answerInput).toHaveValue("我负责简历分析与 Provider 接入");
    expect(screen.getByText("服务端校验失败")).toBeInTheDocument();
  });
});
