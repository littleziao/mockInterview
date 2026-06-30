import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

describe("App", () => {
  beforeEach(() => {
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
});
