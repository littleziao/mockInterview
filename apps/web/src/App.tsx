import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertCircle,
  BookOpenText,
  CheckCircle2,
  ClipboardList,
  History,
  Home,
  KeyRound,
  MessageSquareText,
  Plus,
  Radar,
  Save,
  Settings,
  Sparkles,
  Trash2,
  Wifi
} from "lucide-react";

import {
  capabilityModel,
  defaultInterviewConfig,
  defaultRoundTemplates
} from "@mock-interview/core";

const resumePreview = [
  "## 项目经历",
  "- 本地 AI 工具：设计 Provider 层与 SQLite Repository",
  "- 前端工程：React + TypeScript 工作台体验",
  "- 后端工程：FastAPI 服务与结构化 JSON 校验"
].join("\n");

const navItems = [
  { id: "home", label: "首页", icon: Home },
  { id: "new", label: "新建面试", icon: ClipboardList },
  { id: "history", label: "历史与趋势", icon: Radar },
  { id: "settings", label: "设置", icon: Settings }
] as const;

type ViewId = (typeof navItems)[number]["id"];
type ConnectionStatus = "idle" | "success" | "failure" | "missing";

type AIProviderConfig = {
  id: string;
  name: string;
  baseUrl: string;
  model: string;
  hasApiKey: boolean;
  isConfigured: boolean;
};

type AIProviderSettings = {
  activeProviderId: string;
  providers: AIProviderConfig[];
};

type EditableAIProviderConfig = AIProviderConfig & {
  apiKey: string;
};

type AIProviderTestResult = {
  status: ConnectionStatus;
  message: string;
};

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

function createDraftProvider(index = 1): EditableAIProviderConfig {
  return {
    id: `provider-${Date.now()}-${index}`,
    name: `模型供应商 ${index}`,
    baseUrl: "",
    apiKey: "",
    model: "",
    hasApiKey: false,
    isConfigured: false
  };
}

function Navigation({
  activeView,
  onViewChange
}: {
  activeView: ViewId;
  onViewChange: (view: ViewId) => void;
}) {
  return (
    <aside className="sidebar" aria-label="主导航">
      <div className="brand">
        <div className="brandMark" aria-hidden="true">
          <MessageSquareText size={20} />
        </div>
        <div>
          <strong>Mock Interview</strong>
          <span>本地模拟面试</span>
        </div>
      </div>

      <nav className="navList">
        {navItems.map((item) => (
          <button
            className={item.id === activeView ? "navItem active" : "navItem"}
            key={item.label}
            onClick={() => onViewChange(item.id)}
            type="button"
          >
            <item.icon size={18} aria-hidden="true" />
            <span>{item.label}</span>
          </button>
        ))}
      </nav>
    </aside>
  );
}

function StatusMessage({ result }: { result: AIProviderTestResult | null }) {
  if (!result) {
    return (
      <div className="connectionState idle">
        <AlertCircle size={18} aria-hidden="true" />
        <span>尚未测试连接</span>
      </div>
    );
  }

  const Icon = result.status === "success" ? CheckCircle2 : AlertCircle;

  return (
    <div className={`connectionState ${result.status}`}>
      <Icon size={18} aria-hidden="true" />
      <span>{result.message}</span>
    </div>
  );
}

function SettingsPage() {
  const [providers, setProviders] = useState<EditableAIProviderConfig[]>([createDraftProvider()]);
  const [activeProviderId, setActiveProviderId] = useState(providers[0].id);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [status, setStatus] = useState<AIProviderTestResult | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadSettings() {
      try {
        const response = await fetch(`${apiBaseUrl}/settings/ai-provider`);
        if (!response.ok) {
          throw new Error("读取 AI 配置失败");
        }
        const settings = (await response.json()) as AIProviderSettings;
        if (isMounted) {
          const loadedProviders =
            settings.providers.length > 0
              ? settings.providers.map((provider) => ({ ...provider, apiKey: "" }))
              : [createDraftProvider()];
          const nextActiveProviderId = settings.activeProviderId || loadedProviders[0].id;
          setProviders(loadedProviders);
          setActiveProviderId(nextActiveProviderId);
          setStatus(
            loadedProviders.some((provider) => provider.id === nextActiveProviderId && provider.isConfigured)
              ? { status: "idle", message: "配置已保存，可测试连接" }
              : { status: "missing", message: "请先保存供应商名称、baseUrl、apiKey 和 model" }
          );
        }
      } catch (error) {
        if (isMounted) {
          setStatus({
            status: "failure",
            message: error instanceof Error ? error.message : "读取 AI 配置失败"
          });
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadSettings();

    return () => {
      isMounted = false;
    };
  }, []);

  const activeProvider = useMemo(
    () => providers.find((provider) => provider.id === activeProviderId) ?? providers[0],
    [activeProviderId, providers]
  );

  const apiKeyPlaceholder = activeProvider?.hasApiKey ? "已保存密钥；重新输入会覆盖" : "输入本地私有 API Key";

  function updateActiveProvider(patch: Partial<EditableAIProviderConfig>) {
    setProviders((currentProviders) =>
      currentProviders.map((provider) => (provider.id === activeProvider.id ? { ...provider, ...patch } : provider))
    );
  }

  function addProvider() {
    const provider = createDraftProvider(providers.length + 1);
    setProviders((currentProviders) => [...currentProviders, provider]);
    setActiveProviderId(provider.id);
    setStatus({ status: "missing", message: "请填写并保存新的模型供应商" });
  }

  function removeActiveProvider() {
    if (providers.length === 1) {
      const provider = createDraftProvider();
      setProviders([provider]);
      setActiveProviderId(provider.id);
      setStatus({ status: "missing", message: "请至少配置一个模型供应商" });
      return;
    }

    const remainingProviders = providers.filter((provider) => provider.id !== activeProvider.id);
    setProviders(remainingProviders);
    setActiveProviderId(remainingProviders[0].id);
    setStatus({ status: "idle", message: "供应商已移除，保存后生效" });
  }

  async function saveSettings() {
    setIsSaving(true);
    try {
      const response = await fetch(`${apiBaseUrl}/settings/ai-provider`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          activeProviderId,
          providers: providers.map((provider) => ({
            id: provider.id,
            name: provider.name,
            baseUrl: provider.baseUrl,
            apiKey: provider.apiKey,
            model: provider.model
          }))
        })
      });
      if (!response.ok) {
        throw new Error("保存 AI 配置失败");
      }
      const settings = (await response.json()) as AIProviderSettings;
      setProviders(settings.providers.map((provider) => ({ ...provider, apiKey: "" })));
      setActiveProviderId(settings.activeProviderId);
      setStatus({
        status: settings.providers.some((provider) => provider.id === settings.activeProviderId && provider.isConfigured)
          ? "idle"
          : "missing",
        message: settings.providers.some((provider) => provider.id === settings.activeProviderId && provider.isConfigured)
          ? "配置已保存，可测试连接"
          : "请先保存供应商名称、baseUrl、apiKey 和 model"
      });
    } catch (error) {
      setStatus({
        status: "failure",
        message: error instanceof Error ? error.message : "保存 AI 配置失败"
      });
    } finally {
      setIsSaving(false);
    }
  }

  async function testConnection() {
    setIsTesting(true);
    try {
      const response = await fetch(`${apiBaseUrl}/settings/ai-provider/test`, {
        method: "POST"
      });
      if (!response.ok) {
        throw new Error("测试 AI Provider 连接失败");
      }
      setStatus((await response.json()) as AIProviderTestResult);
    } catch (error) {
      setStatus({
        status: "failure",
        message: error instanceof Error ? error.message : "测试 AI Provider 连接失败"
      });
    } finally {
      setIsTesting(false);
    }
  }

  return (
    <section className="panel settingsPanel" aria-labelledby="settings-title">
      <div className="sectionHeader">
        <div>
          <h2 id="settings-title">AI Provider 设置</h2>
          <p>配置本地私有模型服务，密钥只保存到后端本机配置文件。</p>
        </div>
        <StatusMessage result={status} />
      </div>

      <div className="providerSettingsLayout">
        <div className="providerList" aria-label="模型供应商列表">
          {providers.map((provider) => (
            <button
              className={provider.id === activeProvider.id ? "providerItem active" : "providerItem"}
              key={provider.id}
              onClick={() => {
                setActiveProviderId(provider.id);
                setStatus({ status: "idle", message: "已切换供应商，保存后生效" });
              }}
              type="button"
            >
              <span>{provider.name || "未命名供应商"}</span>
              <small>{provider.model || "未配置模型"}</small>
            </button>
          ))}
          <button className="secondaryButton providerAddButton" onClick={addProvider} type="button">
            <Plus size={16} aria-hidden="true" />
            新增供应商
          </button>
        </div>

        <div className="settingsGrid">
          <label>
            <span>供应商名称</span>
            <input
              disabled={isLoading}
              onChange={(event) => updateActiveProvider({ name: event.target.value })}
              placeholder="OpenAI、DeepSeek、备用网关"
              value={activeProvider.name}
            />
          </label>

          <label>
            <span>Base URL</span>
            <input
              disabled={isLoading}
              onChange={(event) => updateActiveProvider({ baseUrl: event.target.value })}
              placeholder="https://api.openai.com/v1 或 fake://success"
              value={activeProvider.baseUrl}
            />
          </label>

          <label>
            <span>API Key</span>
            <input
              disabled={isLoading}
              onChange={(event) => updateActiveProvider({ apiKey: event.target.value })}
              placeholder={apiKeyPlaceholder}
              type="password"
              value={activeProvider.apiKey}
            />
          </label>

          <label>
            <span>Model</span>
            <input
              disabled={isLoading}
              onChange={(event) => updateActiveProvider({ model: event.target.value })}
              placeholder="gpt-4.1-mini"
              value={activeProvider.model}
            />
          </label>
        </div>
      </div>

      <div className="settingsActions">
        <button className="primaryButton" disabled={isLoading || isSaving} onClick={saveSettings} type="button">
          <Save size={16} aria-hidden="true" />
          {isSaving ? "保存中" : "保存配置"}
        </button>
        <button className="secondaryButton" disabled={isLoading || isTesting} onClick={testConnection} type="button">
          <Wifi size={16} aria-hidden="true" />
          {isTesting ? "测试中" : "测试连接"}
        </button>
        <button className="dangerButton" disabled={isLoading} onClick={removeActiveProvider} type="button">
          <Trash2 size={16} aria-hidden="true" />
          删除当前供应商
        </button>
      </div>

      <div className="privateConfigNote">
        <KeyRound size={18} aria-hidden="true" />
        <span>前端只保存表单状态；面试流程中的模型调用会从后端 Provider 层发起。</span>
      </div>
    </section>
  );
}

function SetupPanel() {
  return (
    <section className="panel setupPanel" aria-labelledby="setup-title">
      <div className="sectionHeader">
        <div>
          <h2 id="setup-title">新建面试</h2>
          <p>粘贴 Markdown 简历，确认分析后进入连续对话式模拟面试。</p>
        </div>
        <button className="primaryButton" type="button">
          <Sparkles size={16} aria-hidden="true" />
          生成简历分析
        </button>
      </div>

      <div className="workspaceGrid">
        <label className="resumeEditor">
          <span>Markdown 简历</span>
          <textarea defaultValue={resumePreview} rows={12} />
        </label>

        <div className="setupControls">
          <label>
            <span>目标岗位</span>
            <input defaultValue="前端工程师" />
          </label>

          <fieldset>
            <legend>面试模式</legend>
            <div className="segmented">
              <button className="selected" type="button">
                单轮面试
              </button>
              <button type="button">多轮面试</button>
            </div>
          </fieldset>

          <fieldset>
            <legend>面试风格</legend>
            <div className="segmented">
              <button className="selected" type="button">
                学习梳理面
              </button>
              <button type="button">压力面</button>
            </div>
          </fieldset>

          <div className="configNote">
            <CheckCircle2 size={18} aria-hidden="true" />
            <div>
              <strong>{defaultInterviewConfig.mainQuestionCount} 个主问题</strong>
              <span>每题最多 {defaultInterviewConfig.maxFollowUpsPerQuestion} 次追问</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function RoundsPanel() {
  return (
    <section className="panel" aria-labelledby="rounds-title">
      <div className="sectionHeader compact">
        <div>
          <h2 id="rounds-title">默认轮次模板</h2>
          <p>核心面试配置来自可复用领域包，后续小程序版本可复用。</p>
        </div>
      </div>
      <div className="roundList">
        {defaultRoundTemplates.map((round) => (
          <article className="roundItem" key={round.kind}>
            <BookOpenText size={18} aria-hidden="true" />
            <div>
              <h3>{round.title}</h3>
              <p>{round.focus}</p>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function RightRail() {
  return (
    <aside className="rightRail" aria-label="状态与历史">
      <section className="panel healthPanel">
        <div className="healthStatus">
          <Activity size={18} aria-hidden="true" />
          <div>
            <strong>后端健康检查</strong>
            <span>FastAPI / SQLite 就绪</span>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="railTitle">
          <History size={18} aria-hidden="true" />
          <h2>最近记录</h2>
        </div>
        <div className="emptyState">暂无完成面试，完成后将在这里展示趋势。</div>
      </section>

      <section className="panel">
        <div className="railTitle">
          <Radar size={18} aria-hidden="true" />
          <h2>能力模型</h2>
        </div>
        <ul className="capabilityList">
          {capabilityModel.map((capability) => (
            <li key={capability}>{capability}</li>
          ))}
        </ul>
      </section>
    </aside>
  );
}

export function App() {
  const [activeView, setActiveView] = useState<ViewId>("home");

  return (
    <div className="appShell">
      <Navigation activeView={activeView} onViewChange={setActiveView} />

      <main className="mainContent">
        <header className="topBar">
          <div>
            <h1>AI 模拟面试工作台</h1>
            <p>本地保存简历、面试记录、复盘与长期趋势。</p>
          </div>
          <div className="statusPill">
            <CheckCircle2 size={16} aria-hidden="true" />
            无登录本地使用
          </div>
        </header>

        {activeView === "settings" ? (
          <SettingsPage />
        ) : (
          <>
            <SetupPanel />
            <RoundsPanel />
          </>
        )}
      </main>

      <RightRail />
    </div>
  );
}
