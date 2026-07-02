import { render, screen, waitFor, within } from "@testing-library/react";
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
        { role: "candidate", content: "我负责 FastAPI 和 SQLite。", kind: "", mainQuestionIndex: 0 }
      ],
      review: {
        overallEvaluation: "后端复盘：接口边界清楚，排障细节还可以加强。",
        highlights: ["能讲清 API 职责"],
        mainIssues: ["异常路径说明不足"],
        questionReviews: ["第 1 题：API 边界清楚。"],
        improvedExpressionExamples: ["补充错误处理与观测方式。"],
        sampleAnswers: ["示范性回答：先讲接口契约，再讲异常处理。"],
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

describe("App", () => {
  beforeEach(() => {
    interviewAnswerCount = 0;
    inProgressSessionsMock = [];
    roundsProgressMock = [];
    sessionRoundKindMock = "peer_technical";
    sessionRoundTitleMock = "同事技术面";
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

        if (url.includes("/history") && !init) {
          if (url.includes("target_role=%E5%89%8D%E7%AB%AF%E5%B7%A5%E7%A8%8B%E5%B8%88")) {
            return Response.json({
              ...historyPayloadMock,
              records: historyPayloadMock.records.filter((record) => record.targetRole === "前端工程师"),
              trends: historyPayloadMock.trends.map((trend) => ({
                ...trend,
                averageScore: trend.points[0]?.score ?? 0,
                points: trend.points.filter((point) => point.historyRecordId === 1)
              }))
            });
          }
          return Response.json(historyPayloadMock);
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
          return Response.json({
            id: 7,
            resumeMarkdown: body.resumeMarkdown,
            targetRole: body.targetRole,
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
    expect(screen.getByText("我的回答：我负责历史与趋势页。")).toBeInTheDocument();
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
    expect(screen.queryByLabelText("目标岗位")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "手动结束" }));
    expect(await screen.findByText("面试已结束，请确认是否生成复盘。")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "提交回答" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "生成复盘" }));

    expect(await screen.findByRole("heading", { name: "面试复盘" })).toBeInTheDocument();
    expect(screen.getByText("整体能说明项目背景，但技术取舍和结果指标还可以加强。")).toBeInTheDocument();
    expect(screen.getByLabelText("六维能力评分雷达图")).toHaveTextContent("专业知识准确性");
    expect(screen.getByLabelText("六维能力评分雷达图")).toHaveTextContent("4/5");
    expect(screen.getByText("示范性回答：这是一种可参考表达，不是唯一标准答案。")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "导出 Markdown" }));

    expect(URL.createObjectURL).toHaveBeenCalledWith(expect.any(Blob));
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:mock-review");
  });

  it("回退修改目标岗位后显式失效已生成的简历分析", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "解析简历" }));
    expect(await screen.findByRole("heading", { name: "简历解析与配置" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "返回修改简历" }));
    await user.clear(screen.getByLabelText("目标岗位"));
    await user.type(screen.getByLabelText("目标岗位"), "后端工程师");

    expect(screen.getByText("简历或目标岗位已修改，需要重新解析简历")).toBeInTheDocument();

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
});
