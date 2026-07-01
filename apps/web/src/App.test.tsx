import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

let interviewAnswerCount = 0;

describe("App", () => {
  beforeEach(() => {
    interviewAnswerCount = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);

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
              }
            ]
          });
        }

        return Response.json({}, { status: 404 });
      })
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the local mock interview shell", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "AI 模拟面试工作台" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "新建面试" })).toBeInTheDocument();
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

  it("imports Markdown resume, edits generated analysis, and confirms interview", async () => {
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

    await user.click(screen.getByRole("button", { name: "生成简历分析" }));

    const backgroundSummary = await screen.findByDisplayValue("候选人具备前端工程经验");
    await user.clear(backgroundSummary);
    await user.type(backgroundSummary, "用户编辑后的背景摘要");

    const lowPriority = screen.getByLabelText("不希望重点追问的内容");
    await user.clear(lowPriority);
    await user.type(lowPriority, "弱相关外包经历");
    await user.click(screen.getByRole("button", { name: "确认并保存" }));

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
    expect(await screen.findByText("简历分析已确认并保存为面试记录 #7")).toBeInTheDocument();
  });
});
