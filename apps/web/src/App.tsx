import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertCircle,
  BarChart3,
  BookOpenText,
  CheckCircle2,
  CircleStop,
  ClipboardList,
  Download,
  Eye,
  FileUp,
  History,
  Home,
  KeyRound,
  MessageSquareText,
  MessagesSquare,
  Plus,
  Radar,
  Save,
  Send,
  Settings,
  Sparkles,
  TrendingUp,
  Trash2,
  Wifi
} from "lucide-react";

import {
  capabilityModel,
  defaultInterviewConfig,
  defaultRoundTemplates,
  roundTemplatesForMode
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

type ResumeAnalysis = {
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

type ResumeAnalysisRecord = {
  id: number;
  targetRole: string;
  summary: string;
  keyProjects: string[];
  technicalStack: string[];
  followUpTopics: string[];
  createdAt: string;
  lastUsedAt: string;
  useCount: number;
};

type ResumeAnalysisRecordsPayload = {
  records: ResumeAnalysisRecord[];
};

type InterviewSessionStyle = "study" | "pressure";
type InterviewMode = "single_round" | "multi_round";
type NewInterviewStep = "upload" | "analysis" | "interview" | "review";

type TranscriptMessage = {
  role: "interviewer" | "candidate";
  content: string;
  kind: "" | "main_question" | "follow_up" | "clarify" | "end_interview";
  mainQuestionIndex: number;
};

type InterviewSession = {
  id: number;
  interviewId: number;
  style: InterviewSessionStyle;
  status: "in_progress" | "awaiting_review" | "ended" | "abandoned";
  mainQuestionCount: number;
  currentMainQuestionFollowUps: number;
  mainQuestionLimit: number;
  followUpLimit: number;
  roundKind?: string;
  roundTitle?: string;
  roundFocus?: string;
  transcript: TranscriptMessage[];
  review?: InterviewReview | null;
  reviewError?: string;
};

type ResumeableSession = {
  id: number;
  interviewId: number;
  style: InterviewSessionStyle;
  status: "in_progress";
  mainQuestionCount: number;
  currentMainQuestionFollowUps: number;
  mainQuestionLimit: number;
  followUpLimit: number;
  roundKind?: string;
  roundTitle?: string;
  roundFocus?: string;
  targetRole: string;
  interviewMode: InterviewMode;
};

type RoundProgress = {
  kind: string;
  title: string;
  focus: string;
  status: "pending" | "in_progress" | "awaiting_review" | "completed" | "abandoned";
  sessionId?: number | null;
};

type ResumedInterview = {
  id: number;
  resumeMarkdown: string;
  targetRole: string;
  interviewMode: InterviewMode;
  includeHrRound?: boolean;
  analysis: ResumeAnalysis;
};

type ResumeContext = {
  session: InterviewSession;
  interview: ResumedInterview;
};

type AbilityScore = {
  dimension: string;
  score: number;
  rationale: string;
};

type InterviewReview = {
  overallEvaluation: string;
  highlights: string[];
  mainIssues: string[];
  questionReviews: string[];
  improvedExpressionExamples: string[];
  sampleAnswers: string[];
  knowledgeReferences: string[];
  learningFramework: string[];
  nextPracticeSuggestions: string[];
  abilityScores: AbilityScore[];
};

type HistoryRecord = {
  id: number;
  interviewId: number;
  sessionId: number;
  targetRole: string;
  interviewMode: InterviewMode;
  style: InterviewSessionStyle;
  roundKind: string;
  roundTitle: string;
  completedAt: string;
  review: InterviewReview;
  transcript: TranscriptMessage[];
};

type ReviewQuestionSegment = {
  title: string;
  messages: TranscriptMessage[];
  questionReview?: string;
  sampleAnswer?: string;
};

type TrendPoint = {
  historyRecordId: number;
  completedAt: string;
  score: number;
};

type TrendDimension = {
  dimension: string;
  averageScore: number;
  points: TrendPoint[];
};

type HistoryPayload = {
  records: HistoryRecord[];
  targetRoles: string[];
  trends: TrendDimension[];
};

type RouteId = "home" | "new-upload" | "new-analysis" | "new-interview" | "review" | "history" | "settings";

const interviewStyleOptions: { value: InterviewSessionStyle; label: string }[] = [
  { value: "study", label: "学习梳理面" },
  { value: "pressure", label: "压力面" }
];

const interviewModeOptions: { value: InterviewMode; label: string }[] = [
  { value: "single_round", label: "单轮面试" },
  { value: "multi_round", label: "多轮面试" }
];

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

function routeFromHash(hash: string): RouteId {
  switch (hash.replace(/^#/, "")) {
    case "/new/resume":
      return "new-upload";
    case "/new/analysis":
      return "new-analysis";
    case "/new/interview":
      return "new-interview";
    case "/review":
      return "review";
    case "/history":
      return "history";
    case "/settings":
      return "settings";
    default:
      return "home";
  }
}

function hashForRoute(route: RouteId) {
  switch (route) {
    case "new-upload":
      return "#/new/resume";
    case "new-analysis":
      return "#/new/analysis";
    case "new-interview":
      return "#/new/interview";
    case "review":
      return "#/review";
    case "history":
      return "#/history";
    case "settings":
      return "#/settings";
    default:
      return "#/";
  }
}

function routeForStep(step: NewInterviewStep): RouteId {
  if (step === "analysis") {
    return "new-analysis";
  }
  if (step === "interview") {
    return "new-interview";
  }
  if (step === "review") {
    return "review";
  }
  return "new-upload";
}

function viewForRoute(route: RouteId): ViewId {
  switch (route) {
    case "settings":
      return "settings";
    case "history":
      return "history";
    case "home":
      return "home";
    default:
      return "new";
  }
}

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

function linesToList(value: string) {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function listToLines(value: string[]) {
  return value.join("\n");
}

function readFileAsText(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(typeof reader.result === "string" ? reader.result : "");
    reader.onerror = () => reject(new Error("导入失败：无法读取文件"));
    reader.readAsText(file);
  });
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

function NewInterviewFlow({
  hasInProgressInterview,
  onAbandonActiveInterview,
  onResumeAnalysisCreated,
  onNavigateStep,
  resumeContext,
  step
}: {
  hasInProgressInterview: boolean;
  onAbandonActiveInterview: (sessionId: number) => Promise<void> | void;
  onResumeAnalysisCreated: () => Promise<void> | void;
  onNavigateStep: (step: NewInterviewStep) => void;
  resumeContext: ResumeContext | null;
  step: NewInterviewStep;
}) {
  const [resumeMarkdown, setResumeMarkdown] = useState(resumePreview);
  const [targetRole, setTargetRole] = useState("前端工程师");
  const [analysis, setAnalysis] = useState<ResumeAnalysis | null>(null);
  const [lastImportedFileName, setLastImportedFileName] = useState("");
  const [fileError, setFileError] = useState("");
  const [workflowMessage, setWorkflowMessage] = useState("");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isSavingInterview, setIsSavingInterview] = useState(false);
  const [interviewMode, setInterviewMode] = useState<InterviewMode>("single_round");
  const [interviewStyle, setInterviewStyle] = useState<InterviewSessionStyle>("study");
  const [includeHrRound, setIncludeHrRound] = useState(false);
  const [roundsProgress, setRoundsProgress] = useState<RoundProgress[]>([]);
  const [isStartingNextRound, setIsStartingNextRound] = useState(false);
  const [nextRoundError, setNextRoundError] = useState("");
  const [savedInterviewId, setSavedInterviewId] = useState<number | null>(null);
  const [session, setSession] = useState<InterviewSession | null>(null);
  const [answerDraft, setAnswerDraft] = useState("");
  const [interviewError, setInterviewError] = useState("");
  // 用户提交后、服务端回复前的乐观回答；非 null 期间对话区追加该回答与「正在思考」气泡。
  const [pendingAnswer, setPendingAnswer] = useState<string | null>(null);

  const [isSubmittingAnswer, setIsSubmittingAnswer] = useState(false);
  const [isEndingSession, setIsEndingSession] = useState(false);
  const [isGeneratingReview, setIsGeneratingReview] = useState(false);

  // 从后端恢复未完成面试时，把进行中会话与简历分析灌入流程状态。
  useEffect(() => {
    if (!resumeContext) {
      return;
    }
    setResumeMarkdown(resumeContext.interview.resumeMarkdown);
    setTargetRole(resumeContext.interview.targetRole);
    setAnalysis(resumeContext.interview.analysis);
    setInterviewMode(resumeContext.interview.interviewMode);
    setIncludeHrRound(resumeContext.interview.includeHrRound ?? false);
    setInterviewStyle(resumeContext.session.style);
    setSavedInterviewId(resumeContext.interview.id);
    setSession(resumeContext.session);
    setAnswerDraft("");
    setInterviewError("");
    setNextRoundError("");
    setWorkflowMessage("已恢复未完成的面试，可继续作答");
  }, [resumeContext]);

  function applySessionUpdate(nextSession: InterviewSession) {
    setSession(nextSession);
    if (nextSession.status === "ended" && nextSession.review) {
      setWorkflowMessage("复盘已生成，可查看学习建议并导出 Markdown");
      onNavigateStep("review");
    } else if (nextSession.status === "awaiting_review") {
      setWorkflowMessage("面试已结束，请确认是否生成复盘");
    }
  }

  function invalidateGeneratedState(message = "简历或目标岗位已修改，需要重新解析简历") {
    if (analysis || savedInterviewId !== null || session) {
      setAnalysis(null);
      setSavedInterviewId(null);
      setSession(null);
      setAnswerDraft("");
      setWorkflowMessage(message);
    }
  }

  function updateResumeMarkdown(value: string) {
    setResumeMarkdown(value);
    invalidateGeneratedState();
  }

  function updateTargetRole(value: string) {
    setTargetRole(value);
    invalidateGeneratedState();
  }

  async function importMarkdownFile(file: File | undefined) {
    if (!file) {
      return;
    }

    const normalizedName = file.name.toLowerCase();
    if (!normalizedName.endsWith(".md") && !normalizedName.endsWith(".markdown")) {
      setFileError("只支持导入 .md 或 .markdown 文件");
      return;
    }

    try {
      const content = await readFileAsText(file);
      if (!content.trim()) {
        setFileError("导入失败：文件内容为空");
        return;
      }

      setResumeMarkdown(content);
      invalidateGeneratedState("Markdown 简历已导入，需要重新解析简历");
      setLastImportedFileName(file.name);
      setFileError("");
      setWorkflowMessage("Markdown 简历已导入，请确认内容后手动生成分析");
    } catch (error) {
      setFileError(error instanceof Error ? error.message : "导入失败：无法读取文件");
    }
  }

  async function generateAnalysis() {
    if (!resumeMarkdown.trim()) {
      setWorkflowMessage("Markdown 简历不能为空");
      return;
    }

    setIsAnalyzing(true);
    setWorkflowMessage("");
    try {
      const response = await fetch(`${apiBaseUrl}/resume-analyses/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          resumeMarkdown,
          targetRole
        })
      });
      if (!response.ok) {
        const detail = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(detail?.detail ?? "生成简历分析失败");
      }
      setAnalysis((await response.json()) as ResumeAnalysis);
      await onResumeAnalysisCreated();
      setSavedInterviewId(null);
      setSession(null);
      setAnswerDraft("");
      setWorkflowMessage("简历分析已生成，可继续编辑并确认配置");
      onNavigateStep("analysis");
    } catch (error) {
      setWorkflowMessage(error instanceof Error ? error.message : "生成简历分析失败");
    } finally {
      setIsAnalyzing(false);
    }
  }

  async function confirmAndStartInterview() {
    if (hasInProgressInterview) {
      setWorkflowMessage("已有未完成的面试，请先在首页继续或放弃后再开始新面试");
      return;
    }
    if (!analysis) {
      setWorkflowMessage("请先生成简历分析");
      return;
    }

    setIsSavingInterview(true);
    setWorkflowMessage("");
    try {
      let interviewId = savedInterviewId;
      if (interviewId === null) {
        const response = await fetch(`${apiBaseUrl}/interviews`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            resumeMarkdown,
            targetRole,
            interviewMode,
            includeHrRound: interviewMode === "multi_round" ? includeHrRound : false,
            analysis: {
              background_summary: analysis.backgroundSummary,
              key_projects: analysis.keyProjects,
              technical_stack: analysis.technicalStack,
              follow_up_topics: analysis.followUpTopics,
              risk_points: analysis.riskPoints,
              unclear_points: analysis.unclearPoints,
              target_role_notes: analysis.targetRoleNotes,
              focus_topics: analysis.focusTopics,
              low_priority_follow_up_topics: analysis.lowPriorityFollowUpTopics
            }
          })
        });
        if (!response.ok) {
          const detail = (await response.json().catch(() => null)) as { detail?: string } | null;
          throw new Error(detail?.detail ?? "保存面试记录失败");
        }
        const savedInterview = (await response.json()) as { id: number };
        interviewId = savedInterview.id;
        setSavedInterviewId(interviewId);
      }
      const sessionResponse = await fetch(`${apiBaseUrl}/interviews/${interviewId}/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ style: interviewStyle })
      });
      if (!sessionResponse.ok) {
        const detail = (await sessionResponse.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(detail?.detail ?? "启动面试失败");
      }
      setSession((await sessionResponse.json()) as InterviewSession);
      setWorkflowMessage(`配置已确认，面试记录 #${interviewId} 已开始`);
      onNavigateStep("interview");
    } catch (error) {
      setWorkflowMessage(error instanceof Error ? error.message : "保存面试记录或启动面试失败");
    } finally {
      setIsSavingInterview(false);
    }
  }

  async function submitAnswer() {
    if (!session || session.status !== "in_progress") {
      return;
    }

    const answer = answerDraft.trim();
    if (!answer) {
      setInterviewError("回答内容不能为空");
      return;
    }

    // 乐观渲染：用户回答立即进入对话区并显示「面试官正在思考」气泡，
    // 随后等待服务端返回包含这条回答与下一题的权威 transcript 做整体替换。
    setPendingAnswer(answer);
    setAnswerDraft("");
    setIsSubmittingAnswer(true);
    setInterviewError("");
    try {
      const response = await fetch(`${apiBaseUrl}/interview-sessions/${session.id}/answers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answer })
      });
      if (!response.ok) {
        const detail = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(detail?.detail ?? "提交回答失败");
      }
      applySessionUpdate((await response.json()) as InterviewSession);
    } catch (error) {
      // 提交失败：回滚乐观消息，把回答内容还给输入框，方便用户改后重发。
      setAnswerDraft(answer);
      setInterviewError(error instanceof Error ? error.message : "提交回答失败");
    } finally {
      setPendingAnswer(null);
      setIsSubmittingAnswer(false);
    }
  }

  async function endInterview() {
    if (!session) {
      return;
    }

    setIsEndingSession(true);
    setInterviewError("");
    try {
      const response = await fetch(`${apiBaseUrl}/interview-sessions/${session.id}/end`, {
        method: "POST"
      });
      if (!response.ok) {
        const detail = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(detail?.detail ?? "结束面试失败");
      }
      const nextSession = (await response.json()) as InterviewSession;
      applySessionUpdate(nextSession);
      if (!nextSession.review) {
        setWorkflowMessage("面试已结束，请确认是否生成复盘");
      }
    } catch (error) {
      setInterviewError(error instanceof Error ? error.message : "结束面试失败");
    } finally {
      setIsEndingSession(false);
    }
  }

  async function generateReview() {
    if (!session || session.status !== "awaiting_review") {
      return;
    }

    setIsGeneratingReview(true);
    setInterviewError("");
    try {
      const response = await fetch(`${apiBaseUrl}/interview-sessions/${session.id}/review`, {
        method: "POST"
      });
      if (!response.ok) {
        const detail = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(detail?.detail ?? "生成复盘失败");
      }
      applySessionUpdate((await response.json()) as InterviewSession);
    } catch (error) {
      setInterviewError(error instanceof Error ? error.message : "生成复盘失败");
    } finally {
      setIsGeneratingReview(false);
    }
  }

  // 多轮面试：当前轮复盘完成后，拉取轮次进度，用于在复盘页展示「进入下一轮」入口。
  useEffect(() => {
    if (session?.status !== "ended") {
      return;
    }
    if (interviewMode !== "multi_round" || savedInterviewId === null) {
      return;
    }
    let mounted = true;
    async function loadRounds() {
      try {
        const response = await fetch(`${apiBaseUrl}/interviews/${savedInterviewId}/rounds`);
        if (!response.ok) {
          return;
        }
        const rounds = (await response.json()) as RoundProgress[];
        if (mounted) {
          setRoundsProgress(rounds);
        }
      } catch {
        // 进度加载失败不阻塞复盘展示。
      }
    }
    void loadRounds();
    return () => {
      mounted = false;
    };
  }, [session?.status, interviewMode, savedInterviewId]);

  const nextRound = useMemo(
    () => roundsProgress.find((round) => round.status === "pending") ?? null,
    [roundsProgress]
  );
  const multiRoundCompleted =
    interviewMode === "multi_round" && roundsProgress.length > 0 && nextRound === null;

  async function startNextRound() {
    if (savedInterviewId === null) {
      return;
    }
    setIsStartingNextRound(true);
    setNextRoundError("");
    try {
      const response = await fetch(`${apiBaseUrl}/interviews/${savedInterviewId}/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ style: interviewStyle })
      });
      if (!response.ok) {
        const detail = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(detail?.detail ?? "进入下一轮失败");
      }
      const nextSession = (await response.json()) as InterviewSession;
      setSession(nextSession);
      setRoundsProgress([]);
      setAnswerDraft("");
      setWorkflowMessage(`已进入${nextSession.roundTitle ?? "下一轮"}，可继续作答`);
      onNavigateStep("interview");
    } catch (error) {
      setNextRoundError(error instanceof Error ? error.message : "进入下一轮失败");
    } finally {
      setIsStartingNextRound(false);
    }
  }

  function updateAnalysis(patch: Partial<ResumeAnalysis>) {
    setSavedInterviewId(null);
    setSession(null);
    setAnalysis((currentAnalysis) => (currentAnalysis ? { ...currentAnalysis, ...patch } : currentAnalysis));
  }

  async function abandonStartedInterview() {
    if (!session) {
      return;
    }
    const sessionId = session.id;
    try {
      await onAbandonActiveInterview(sessionId);
    } catch (error) {
      setInterviewError(error instanceof Error ? error.message : "放弃面试失败");
      return;
    }
    setSession(null);
    setSavedInterviewId(null);
    setAnswerDraft("");
    setInterviewError("");
    setWorkflowMessage("当前会话已放弃；如需继续，请重新确认配置并开始面试");
    onNavigateStep("analysis");
  }

  if (step === "analysis" && !analysis) {
    return (
      <section className="panel setupPanel" aria-labelledby="setup-guard-title">
        <div className="emptyRouteState">
          <AlertCircle size={22} aria-hidden="true" />
          <div>
            <h2 id="setup-guard-title">需要先解析简历</h2>
            <p>简历解析与配置页依赖第一步的 Markdown 简历和目标岗位。</p>
          </div>
          <button className="primaryButton" onClick={() => onNavigateStep("upload")} type="button">
            返回上传简历
          </button>
        </div>
      </section>
    );
  }

  if (step === "interview" && !session && !resumeContext) {
    return (
      <section className="panel setupPanel" aria-labelledby="interview-guard-title">
        <div className="emptyRouteState">
          <AlertCircle size={22} aria-hidden="true" />
          <div>
            <h2 id="interview-guard-title">面试尚未开始</h2>
            <p>开始面试页需要已确认的简历分析和进行中的面试会话。</p>
          </div>
          <button
            className="primaryButton"
            onClick={() => onNavigateStep(analysis ? "analysis" : "upload")}
            type="button"
          >
            回到前置步骤
          </button>
        </div>
      </section>
    );
  }

  if (step === "review" && (!session || session.status !== "ended" || !session.review)) {
    return (
      <section className="panel setupPanel" aria-labelledby="review-guard-title">
        <div className="emptyRouteState">
          <AlertCircle size={22} aria-hidden="true" />
          <div>
            <h2 id="review-guard-title">暂无可查看的复盘</h2>
            <p>复盘页需要已结束的面试和已生成的结构化复盘内容。</p>
          </div>
          <button className="primaryButton" onClick={() => onNavigateStep(session ? "interview" : "upload")} type="button">
            回到面试流程
          </button>
        </div>
      </section>
    );
  }

  if (step === "upload") {
    return (
    <section className="panel setupPanel" aria-labelledby="setup-title">
      <div className="sectionHeader">
        <div>
          <h2 id="setup-title">上传简历</h2>
          <p>输入或导入 Markdown 简历，并填写可选目标岗位。</p>
        </div>
        <button className="primaryButton" disabled={isAnalyzing} onClick={generateAnalysis} type="button">
          <Sparkles size={16} aria-hidden="true" />
          {isAnalyzing ? "分析中" : "解析简历"}
        </button>
      </div>

      <div className="workspaceGrid">
        <label className="resumeEditor">
          <span>Markdown 简历</span>
          <textarea onChange={(event) => updateResumeMarkdown(event.target.value)} rows={12} value={resumeMarkdown} />
        </label>

        <div className="setupControls">
          <label className="fileImportControl">
            <span>导入 Markdown 简历</span>
            <input
              accept=".md,.markdown"
              onChange={(event) => {
                void importMarkdownFile(event.target.files?.[0]);
                event.currentTarget.value = "";
              }}
              type="file"
            />
          </label>
          <div className={fileError ? "importState failure" : "importState"}>
            <FileUp size={16} aria-hidden="true" />
            <span>{fileError || (lastImportedFileName ? `最近导入：${lastImportedFileName}` : "尚未导入文件")}</span>
          </div>

          <label>
            <span>目标岗位</span>
            <input onChange={(event) => updateTargetRole(event.target.value)} value={targetRole} />
          </label>
        </div>
      </div>

      {workflowMessage ? <div className="workflowMessage">{workflowMessage}</div> : null}
    </section>
    );
  }

  if (step === "analysis" && analysis) {
    return (
      <section className="panel setupPanel" aria-labelledby="analysis-title">
        <div className="analysisEditor" aria-label="简历分析确认">
          <div className="analysisEditorHeader">
            <div>
              <h2 id="analysis-title">简历解析与配置</h2>
              <p>编辑 AI 对简历的理解，并选择本次面试的组织方式。</p>
            </div>
            <div className="stepActions">
              <button className="secondaryButton" onClick={() => onNavigateStep("upload")} type="button">
                返回修改简历
              </button>
              <button
                className="primaryButton"
                disabled={isSavingInterview}
                onClick={confirmAndStartInterview}
                type="button"
              >
                <MessagesSquare size={16} aria-hidden="true" />
                {isSavingInterview ? "启动中" : "确认配置并开始面试"}
              </button>
            </div>
          </div>

          <div className="configurationGrid">
            <fieldset>
              <legend>面试模式</legend>
              <div className="segmented">
                {interviewModeOptions.map((option) => (
                  <button
                    className={option.value === interviewMode ? "selected" : ""}
                    disabled={Boolean(session)}
                    key={option.value}
                    onClick={() => setInterviewMode(option.value)}
                    type="button"
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </fieldset>

            <fieldset>
              <legend>面试风格</legend>
              <div className="segmented">
                {interviewStyleOptions.map((option) => (
                  <button
                    className={option.value === interviewStyle ? "selected" : ""}
                    disabled={Boolean(session)}
                    key={option.value}
                    onClick={() => setInterviewStyle(option.value)}
                    type="button"
                  >
                    {option.label}
                  </button>
                ))}
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

          {interviewMode === "multi_round" ? (
            <div className="multiRoundConfig">
              <label className="hrToggle">
                <input
                  checked={includeHrRound}
                  disabled={Boolean(session)}
                  onChange={(event) => setIncludeHrRound(event.target.checked)}
                  type="checkbox"
                />
                <span>加入 HR 面</span>
                <small>在主管综合面后追加 HR 面，考察求职动机、稳定性与职业规划</small>
              </label>
              <ul className="roundPreview" aria-label="多轮面试轮次预览">
                {roundTemplatesForMode(interviewMode, includeHrRound).map((round) => (
                  <li key={round.kind}>
                    <strong>{round.title}</strong>
                    <span>{round.focus}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {workflowMessage ? <div className="workflowMessage">{workflowMessage}</div> : null}

          <div className="analysisGrid">
            <label>
              <span>背景摘要</span>
              <textarea
                onChange={(event) => updateAnalysis({ backgroundSummary: event.target.value })}
                rows={4}
                value={analysis.backgroundSummary}
              />
            </label>
            <label>
              <span>关键项目</span>
              <textarea
                onChange={(event) => updateAnalysis({ keyProjects: linesToList(event.target.value) })}
                rows={4}
                value={listToLines(analysis.keyProjects)}
              />
            </label>
            <label>
              <span>技术栈</span>
              <textarea
                onChange={(event) => updateAnalysis({ technicalStack: linesToList(event.target.value) })}
                rows={4}
                value={listToLines(analysis.technicalStack)}
              />
            </label>
            <label>
              <span>可能追问点</span>
              <textarea
                onChange={(event) => updateAnalysis({ followUpTopics: linesToList(event.target.value) })}
                rows={4}
                value={listToLines(analysis.followUpTopics)}
              />
            </label>
            <label>
              <span>风险点</span>
              <textarea
                onChange={(event) => updateAnalysis({ riskPoints: linesToList(event.target.value) })}
                rows={4}
                value={listToLines(analysis.riskPoints)}
              />
            </label>
            <label>
              <span>表达不清之处</span>
              <textarea
                onChange={(event) => updateAnalysis({ unclearPoints: linesToList(event.target.value) })}
                rows={4}
                value={listToLines(analysis.unclearPoints)}
              />
            </label>
            <label>
              <span>目标岗位补充说明</span>
              <textarea
                onChange={(event) => updateAnalysis({ targetRoleNotes: event.target.value })}
                rows={4}
                value={analysis.targetRoleNotes}
              />
            </label>
            <label>
              <span>希望重点练习的内容</span>
              <textarea
                onChange={(event) => updateAnalysis({ focusTopics: linesToList(event.target.value) })}
                rows={4}
                value={listToLines(analysis.focusTopics)}
              />
            </label>
            <label>
              <span>不希望重点追问的内容</span>
              <textarea
                onChange={(event) => updateAnalysis({ lowPriorityFollowUpTopics: linesToList(event.target.value) })}
                rows={4}
                value={listToLines(analysis.lowPriorityFollowUpTopics)}
              />
            </label>
         </div>
       </div>
      </section>
    );
  }

  if (step === "review" && session?.review) {
    return (
      <ReviewPage
        isStartingNextRound={isStartingNextRound}
        modeLabel={interviewModeOptions.find((option) => option.value === interviewMode)?.label ?? "单轮面试"}
        multiRoundCompleted={multiRoundCompleted}
        nextRound={nextRound}
        nextRoundError={nextRoundError}
        onBackToInterview={() => onNavigateStep("interview")}
        onStartNextRound={startNextRound}
        review={session.review}
        session={session}
        styleLabel={interviewStyleOptions.find((option) => option.value === interviewStyle)?.label ?? "学习梳理面"}
        targetRole={targetRole}
      />
    );
  }

  return session ? (
    <section className="panel setupPanel" aria-labelledby="interview-title">
      <div className="sectionHeader">
        <div>
          <h2 id="interview-title">开始面试</h2>
          <p>当前页面只聚焦问题、文字回答和手动结束。</p>
        </div>
        <button className="dangerButton" onClick={abandonStartedInterview} type="button">
          <Trash2 size={16} aria-hidden="true" />
          放弃并重新开始
        </button>
      </div>

      <div className="readonlySummary" aria-label="面试配置摘要">
        <div>
          <span>目标岗位</span>
          <strong>{targetRole || "由简历推断"}</strong>
        </div>
        <div>
          <span>面试模式</span>
          <strong>{interviewModeOptions.find((option) => option.value === interviewMode)?.label}</strong>
        </div>
        <div>
          <span>面试风格</span>
          <strong>{interviewStyleOptions.find((option) => option.value === interviewStyle)?.label}</strong>
        </div>
        {interviewMode === "multi_round" && session.roundTitle ? (
          <div>
            <span>当前轮次</span>
            <strong>{session.roundTitle}</strong>
          </div>
        ) : null}
        <div>
          <span>进度</span>
          <strong>
            第 {Math.max(session.mainQuestionCount, 0)} / {session.mainQuestionLimit} 个主问题
          </strong>
        </div>
      </div>

      {workflowMessage ? <div className="workflowMessage">{workflowMessage}</div> : null}

        <InterviewConversation
          answerDraft={answerDraft}
          interviewError={interviewError}
          isEndingSession={isEndingSession}
          isGeneratingReview={isGeneratingReview}
          isSubmittingAnswer={isSubmittingAnswer}
          onAnswerChange={setAnswerDraft}
          onEnd={endInterview}
          onGenerateReview={generateReview}
          onSubmit={submitAnswer}
          pendingAnswer={pendingAnswer}
          session={session}
        />
    </section>
  ) : null;
}

function markdownList(items: string[]) {
  return items.length ? items.map((item) => `- ${item}`).join("\n") : "- 暂无";
}

function buildReviewQuestionSegments(transcript: TranscriptMessage[], review: InterviewReview) {
  const segments: ReviewQuestionSegment[] = [];
  let currentSegment: ReviewQuestionSegment | null = null;

  transcript.forEach((message) => {
    if (message.kind === "end_interview") {
      return;
    }

    if (message.role === "interviewer" && message.kind === "main_question") {
      currentSegment = {
        title: `第 ${segments.length + 1} 个主问题`,
        messages: [message],
        questionReview: review.questionReviews[segments.length],
        sampleAnswer: review.sampleAnswers[segments.length]
      };
      segments.push(currentSegment);
      return;
    }

    if (!currentSegment) {
      currentSegment = {
        title: `第 ${segments.length + 1} 个主问题`,
        messages: [],
        questionReview: review.questionReviews[segments.length],
        sampleAnswer: review.sampleAnswers[segments.length]
      };
      segments.push(currentSegment);
    }

    currentSegment.messages.push(message);
  });

  return {
    segments,
    supplementalQuestionReviews: review.questionReviews.slice(segments.length),
    supplementalSampleAnswers: review.sampleAnswers.slice(segments.length)
  };
}

function markdownReviewConversation(transcript: TranscriptMessage[], review: InterviewReview) {
  const { segments, supplementalQuestionReviews, supplementalSampleAnswers } = buildReviewQuestionSegments(
    transcript,
    review
  );

  const segmentMarkdown = segments.map((segment) => {
    const messages = segment.messages
      .map((message) => {
        const speaker = message.role === "interviewer" ? `面试官（${transcriptKindLabel(message.kind)}）` : "我的回答";
        return `- **${speaker}**：${message.content}`;
      })
      .join("\n");

    return [
      `### ${segment.title}`,
      messages || "- 暂无对话记录",
      segment.questionReview ? `\n**逐题点评**：${segment.questionReview}` : "",
      segment.sampleAnswer ? `\n**参考答案**：${segment.sampleAnswer}` : ""
    ]
      .filter(Boolean)
      .join("\n");
  });

  if (supplementalQuestionReviews.length) {
    segmentMarkdown.push(["### 补充逐题点评", markdownList(supplementalQuestionReviews)].join("\n"));
  }

  if (supplementalSampleAnswers.length) {
    segmentMarkdown.push(["### 补充参考答案", markdownList(supplementalSampleAnswers)].join("\n"));
  }

  return segmentMarkdown.length ? segmentMarkdown.join("\n\n") : "- 暂无对话记录";
}

function buildReviewMarkdown({
  modeLabel,
  review,
  session,
  styleLabel,
  targetRole
}: {
  modeLabel: string;
  review: InterviewReview;
  session: InterviewSession;
  styleLabel: string;
  targetRole: string;
}) {
  return [
    "# 模拟面试复盘",
    "",
    `- 目标岗位：${targetRole || "由简历推断"}`,
    `- 面试模式：${modeLabel}`,
    `- 面试风格：${styleLabel}`,
    "",
    "## 总体评价",
    review.overallEvaluation,
    "",
    "## 亮点",
    markdownList(review.highlights),
    "",
    "## 主要问题",
    markdownList(review.mainIssues),
    "",
    "## 可改进表达示例",
    markdownList(review.improvedExpressionExamples),
    "",
    "## 知识点参考",
    markdownList(review.knowledgeReferences),
    "",
    "## 学习框架",
    markdownList(review.learningFramework),
    "",
    "## 下一次练习建议",
    markdownList(review.nextPracticeSuggestions),
    "",
    "## 六维能力评分",
    review.abilityScores.map((score) => `- ${score.dimension}：${score.score}/5，${score.rationale}`).join("\n"),
    "",
    "## 逐题对话复盘",
    markdownReviewConversation(session.transcript, review),
    ""
  ].join("\n");
}

function downloadReviewMarkdown(markdown: string) {
  const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `mock-interview-review-${new Date().toISOString().slice(0, 10)}.md`;
  link.click();
  URL.revokeObjectURL(url);
}

function formatCompletedAt(value: string) {
  if (!value) {
    return "时间未知";
  }
  const normalized = value.includes("T") ? value : value.replace(" ", "T");
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function HistoryPage() {
  const [history, setHistory] = useState<HistoryPayload>({
    records: [],
    targetRoles: [],
    trends: []
  });
  const [selectedTargetRole, setSelectedTargetRole] = useState("");
  const [selectedRecordId, setSelectedRecordId] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isDeleting, setIsDeleting] = useState(false);
  const [pendingDeleteRecord, setPendingDeleteRecord] = useState<HistoryRecord | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;

    async function loadHistory() {
      setIsLoading(true);
      setError("");
      try {
        const query = selectedTargetRole ? `?target_role=${encodeURIComponent(selectedTargetRole)}` : "";
        const response = await fetch(`${apiBaseUrl}/history${query}`);
        if (!response.ok) {
          throw new Error("读取历史与趋势失败");
        }
        const payload = (await response.json()) as HistoryPayload;
        if (mounted) {
          setHistory(payload);
          setSelectedRecordId((current) => {
            if (payload.records.some((record) => record.id === current)) {
              return current;
            }
            return payload.records[0]?.id ?? null;
          });
        }
      } catch (loadError) {
        if (mounted) {
          setError(loadError instanceof Error ? loadError.message : "读取历史与趋势失败");
        }
      } finally {
        if (mounted) {
          setIsLoading(false);
        }
      }
    }

    void loadHistory();
    return () => {
      mounted = false;
    };
  }, [selectedTargetRole, reloadToken]);

  const selectedRecord = history.records.find((record) => record.id === selectedRecordId) ?? history.records[0];
  const filteredLabel = selectedTargetRole || "全部岗位";

  async function deletePendingRecord() {
    if (!pendingDeleteRecord) {
      return;
    }
    setIsDeleting(true);
    setError("");
    try {
      const response = await fetch(`${apiBaseUrl}/history/${pendingDeleteRecord.id}`, {
        method: "DELETE"
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail || "删除已完成面试记录失败");
      }
      setPendingDeleteRecord(null);
      setReloadToken((current) => current + 1);
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "删除已完成面试记录失败");
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <section className="panel historyPage" aria-labelledby="history-title">
      <div className="sectionHeader">
        <div>
          <h2 id="history-title">历史与趋势</h2>
          <p>只统计已完成并生成复盘的本地面试记录。</p>
        </div>
        <div className="historyFilter" aria-label="目标岗位筛选">
          <button
            className={selectedTargetRole ? "secondaryButton" : "primaryButton"}
            onClick={() => setSelectedTargetRole("")}
            type="button"
          >
            <BarChart3 size={16} aria-hidden="true" />
            全部岗位
          </button>
          {history.targetRoles.map((role) => (
            <button
              className={selectedTargetRole === role ? "primaryButton" : "secondaryButton"}
              key={role}
              onClick={() => setSelectedTargetRole(role)}
              type="button"
            >
              {role}
            </button>
          ))}
        </div>
      </div>

      {error ? <div className="workflowMessage failure">{error}</div> : null}
      {isLoading ? <div className="workflowMessage">正在读取历史记录</div> : null}

      {!isLoading && history.records.length === 0 ? (
        <div className="emptyState historyEmpty">暂无完成面试，生成复盘后会出现在这里。</div>
      ) : null}

      {history.records.length > 0 ? (
        <>
          <div className="historyStats" aria-label="历史统计">
            <div>
              <span>当前范围</span>
              <strong>{filteredLabel}</strong>
            </div>
            <div>
              <span>完成记录</span>
              <strong>{history.records.length}</strong>
            </div>
            <div>
              <span>最高均分维度</span>
              <strong>
                {history.trends
                  .slice()
                  .sort((a, b) => b.averageScore - a.averageScore)[0]?.dimension ?? "暂无"}
              </strong>
            </div>
          </div>

          <div className="historyLayout">
            <section className="historyList" aria-labelledby="history-list-title">
              <h3 id="history-list-title">完成记录</h3>
              <ul aria-label="已完成面试记录列表">
                {history.records.map((record) => {
                  const modeLabel =
                    interviewModeOptions.find((option) => option.value === record.interviewMode)?.label ?? "单轮面试";
                  const styleLabel =
                    interviewStyleOptions.find((option) => option.value === record.style)?.label ?? "学习梳理面";
                  return (
                    <li className={record.id === selectedRecord?.id ? "historyItem active" : "historyItem"} key={record.id}>
                      <div>
                        <strong>{record.targetRole || "由简历推断"}</strong>
                        <span>
                          {formatCompletedAt(record.completedAt)} · {modeLabel} · {styleLabel}
                          {record.roundTitle ? ` · ${record.roundTitle}` : ""}
                        </span>
                      </div>
                      <div className="historyItemActions">
                        <button className="secondaryButton" onClick={() => setSelectedRecordId(record.id)} type="button">
                          <Eye size={16} aria-hidden="true" />
                          查看复盘
                        </button>
                        <button
                          aria-label={`删除${record.targetRole || "由简历推断"}完成记录`}
                          className="dangerButton"
                          disabled={isDeleting}
                          onClick={() => setPendingDeleteRecord(record)}
                          type="button"
                        >
                          <Trash2 size={16} aria-hidden="true" />
                          删除
                        </button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </section>

            <section className="trendPanel" aria-labelledby="trend-title">
              <div className="trendHeading">
                <TrendingUp size={18} aria-hidden="true" />
                <h3 id="trend-title">六维长期趋势</h3>
              </div>
              <div className="trendRows" aria-label="六维能力趋势">
                {history.trends.map((trend) => (
                  <div className="trendRow" key={trend.dimension}>
                    <div>
                      <strong>{trend.dimension}</strong>
                      <span>平均 {trend.averageScore.toFixed(1)} / 5</span>
                    </div>
                    <div className="trendDots" aria-label={`${trend.dimension} 趋势分数`}>
                      {trend.points.map((point) => (
                        <span
                          className="trendDot"
                          key={`${trend.dimension}-${point.historyRecordId}`}
                          title={`${formatCompletedAt(point.completedAt)}：${point.score}/5`}
                        >
                          {point.score}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </div>

          {selectedRecord ? (
            <section className="historyReview" aria-labelledby="history-review-title">
              <div className="sectionHeader compact">
                <div>
                  <h3 id="history-review-title">历史复盘详情</h3>
                  <p>{selectedRecord.review.overallEvaluation}</p>
                </div>
              </div>
              <div className="reviewOverview">
                <section className="reviewSummary" aria-labelledby="history-review-summary">
                  <h3 id="history-review-summary">总体评价</h3>
                  <p>{selectedRecord.review.overallEvaluation}</p>
                </section>
                <AbilityRadar scores={selectedRecord.review.abilityScores} />
              </div>
              <ReviewConversationSection review={selectedRecord.review} transcript={selectedRecord.transcript} />
              <div className="reviewGrid" aria-label="跨题总结复盘">
                <ReviewSection items={selectedRecord.review.highlights} title="亮点" />
                <ReviewSection items={selectedRecord.review.mainIssues} title="主要问题" />
                <ReviewSection items={selectedRecord.review.improvedExpressionExamples} title="可改进表达示例" />
                <ReviewSection items={selectedRecord.review.knowledgeReferences} title="知识点参考" />
                <ReviewSection items={selectedRecord.review.learningFramework} title="学习框架" />
                <ReviewSection items={selectedRecord.review.nextPracticeSuggestions} title="下一次练习建议" />
              </div>
            </section>
          ) : null}
        </>
      ) : null}

      {pendingDeleteRecord ? (
        <div className="dialogBackdrop" role="presentation">
          <div
            aria-labelledby="delete-history-title"
            aria-modal="true"
            className="confirmDialog"
            role="dialog"
          >
            <div>
              <h3 id="delete-history-title">删除已完成面试记录</h3>
              <p>
                确认后会删除这次面试的对话、复盘和能力评分，并从长期趋势中移除。
                不会删除简历分析记录，也不会删除同一多轮面试下的其他轮次。
              </p>
            </div>
            <div className="dialogActions">
              <button
                className="secondaryButton"
                disabled={isDeleting}
                onClick={() => setPendingDeleteRecord(null)}
                type="button"
              >
                取消
              </button>
              <button className="dangerButton" disabled={isDeleting} onClick={deletePendingRecord} type="button">
                <Trash2 size={16} aria-hidden="true" />
                确认删除
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function AbilityRadar({ scores }: { scores: AbilityScore[] }) {
  const center = 120;
  const maxRadius = 88;
  const vertices = scores.map((score, index) => {
    const angle = (Math.PI * 2 * index) / scores.length - Math.PI / 2;
    const radius = (Math.max(0, Math.min(5, score.score)) / 5) * maxRadius;
    return `${center + Math.cos(angle) * radius},${center + Math.sin(angle) * radius}`;
  });

  return (
    <div className="radarChart" aria-label="六维能力评分雷达图">
      <svg viewBox="0 0 240 240" role="img" aria-label="基于已保存能力评分绘制的雷达图">
        {[1, 2, 3, 4, 5].map((level) => {
          const radius = (level / 5) * maxRadius;
          const points = scores.map((_, index) => {
            const angle = (Math.PI * 2 * index) / scores.length - Math.PI / 2;
            return `${center + Math.cos(angle) * radius},${center + Math.sin(angle) * radius}`;
          });
          return <polygon className="radarGrid" key={level} points={points.join(" ")} />;
        })}
        {scores.map((_, index) => {
          const angle = (Math.PI * 2 * index) / scores.length - Math.PI / 2;
          return (
            <line
              className="radarAxis"
              key={index}
              x1={center}
              x2={center + Math.cos(angle) * maxRadius}
              y1={center}
              y2={center + Math.sin(angle) * maxRadius}
            />
          );
        })}
        <polygon className="radarArea" points={vertices.join(" ")} />
      </svg>
      <ul className="radarLegend">
        {scores.map((score) => (
          <li key={score.dimension}>
            <span>{score.dimension}</span>
            <strong>{score.score}/5</strong>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ReviewSection({ title, items }: { title: string; items: string[] }) {
  return (
    <section className="reviewBlock" aria-labelledby={`review-${title}`}>
      <h3 id={`review-${title}`}>{title}</h3>
      <ul>
        {items.map((item, index) => (
          <li key={`${title}-${index}`}>{item}</li>
        ))}
      </ul>
    </section>
  );
}

function ReviewConversationSection({
  review,
  transcript
}: {
  review: InterviewReview;
  transcript: TranscriptMessage[];
}) {
  const { segments, supplementalQuestionReviews, supplementalSampleAnswers } = buildReviewQuestionSegments(
    transcript,
    review
  );

  return (
    <section className="reviewConversationSection" aria-label="逐题对话复盘">
      <div className="reviewConversationHeader">
        <div>
          <h3>逐题对话复盘</h3>
          <p>面试对话按主问题分段，逐题点评和参考答案只在对应对话段展示。</p>
        </div>
      </div>
      <div className="reviewQuestionList">
        {segments.map((segment) => (
          <article className="reviewQuestionSegment" key={segment.title}>
            <div className="reviewQuestionTitle">
              <h4>{segment.title}</h4>
            </div>
            <ol className="reviewDialogue" aria-label={`${segment.title} 对话`}>
              {segment.messages.map((message, index) => {
                const isInterviewer = message.role === "interviewer";
                return (
                  <li className={isInterviewer ? "reviewDialogueItem interviewer" : "reviewDialogueItem candidate"} key={`${segment.title}-${index}`}>
                    <span className="reviewDialogueMeta">
                      {isInterviewer ? "面试官" : "我的回答"}
                      {isInterviewer ? ` · ${transcriptKindLabel(message.kind)}` : ""}
                    </span>
                    <p>{message.content}</p>
                  </li>
                );
              })}
            </ol>
            {segment.questionReview ? (
              <div className="reviewInlineBlock">
                <strong>逐题点评</strong>
                <p>{segment.questionReview}</p>
              </div>
            ) : null}
            {segment.sampleAnswer ? (
              <div className="reviewInlineBlock">
                <strong>参考答案</strong>
                <p>{segment.sampleAnswer}</p>
              </div>
            ) : null}
          </article>
        ))}
      </div>
      {supplementalQuestionReviews.length ? (
        <ReviewSection items={supplementalQuestionReviews} title="补充逐题点评" />
      ) : null}
      {supplementalSampleAnswers.length ? (
        <ReviewSection items={supplementalSampleAnswers} title="补充参考答案" />
      ) : null}
    </section>
  );
}

function ReviewPage({
  isStartingNextRound,
  modeLabel,
  multiRoundCompleted,
  nextRound,
  nextRoundError,
  onBackToInterview,
  onStartNextRound,
  review,
  session,
  styleLabel,
  targetRole
}: {
  isStartingNextRound: boolean;
  modeLabel: string;
  multiRoundCompleted: boolean;
  nextRound: RoundProgress | null;
  nextRoundError: string;
  onBackToInterview: () => void;
  onStartNextRound: () => void;
  review: InterviewReview;
  session: InterviewSession;
  styleLabel: string;
  targetRole: string;
}) {
  const markdown = buildReviewMarkdown({ modeLabel, review, session, styleLabel, targetRole });
  const showRoundNavigation = Boolean(nextRound) || multiRoundCompleted;

  return (
    <section className="panel setupPanel reviewPage" aria-labelledby="review-title">
      <div className="sectionHeader">
        <div>
          <h2 id="review-title">面试复盘</h2>
          <p>教练视角的复盘、学习材料和六维能力评分。</p>
        </div>
        <div className="stepActions">
          <button className="secondaryButton" onClick={onBackToInterview} type="button">
            <MessagesSquare size={16} aria-hidden="true" />
            查看对话
          </button>
          <button className="primaryButton" onClick={() => downloadReviewMarkdown(markdown)} type="button">
            <Download size={16} aria-hidden="true" />
            导出 Markdown
          </button>
        </div>
      </div>

      {showRoundNavigation ? (
        <div className="nextRoundBanner" aria-label="多轮面试进度">
          {nextRound ? (
            <>
              <div>
                <strong>下一轮：{nextRound.title}</strong>
                <span>{nextRound.focus}</span>
              </div>
              <button
                className="primaryButton"
                disabled={isStartingNextRound}
                onClick={onStartNextRound}
                type="button"
              >
                <MessagesSquare size={16} aria-hidden="true" />
                {isStartingNextRound ? "进入中" : `进入下一轮：${nextRound.title}`}
              </button>
            </>
          ) : (
            <div>
              <CheckCircle2 size={18} aria-hidden="true" />
              <span>全部轮次已完成，可回到首页或新建面试继续练习。</span>
            </div>
          )}
          {nextRoundError ? (
            <div className="workflowMessage failure">{nextRoundError}</div>
          ) : null}
        </div>
      ) : null}

      <div className="readonlySummary" aria-label="复盘配置摘要">
        <div>
          <span>目标岗位</span>
          <strong>{targetRole || "由简历推断"}</strong>
        </div>
        <div>
          <span>面试模式</span>
          <strong>{modeLabel}</strong>
        </div>
        <div>
          <span>面试风格</span>
          <strong>{styleLabel}</strong>
        </div>
        {session.roundTitle ? (
          <div>
            <span>当前轮次</span>
            <strong>{session.roundTitle}</strong>
          </div>
        ) : null}
        <div>
          <span>主问题</span>
          <strong>
            {session.mainQuestionCount} / {session.mainQuestionLimit}
          </strong>
        </div>
      </div>

      <div className="reviewOverview">
        <section className="reviewSummary" aria-labelledby="review-summary-title">
          <h3 id="review-summary-title">总体评价</h3>
          <p>{review.overallEvaluation}</p>
        </section>
        <AbilityRadar scores={review.abilityScores} />
      </div>

      <ReviewConversationSection review={review} transcript={session.transcript} />

      <div className="reviewGrid" aria-label="跨题总结复盘">
        <ReviewSection items={review.highlights} title="亮点" />
        <ReviewSection items={review.mainIssues} title="主要问题" />
        <ReviewSection items={review.improvedExpressionExamples} title="可改进表达示例" />
        <ReviewSection items={review.knowledgeReferences} title="知识点参考" />
        <ReviewSection items={review.learningFramework} title="学习框架" />
        <ReviewSection items={review.nextPracticeSuggestions} title="下一次练习建议" />
      </div>
    </section>
  );
}

function transcriptKindLabel(kind: TranscriptMessage["kind"]) {
  if (kind === "main_question") {
    return "主问题";
  }
  if (kind === "follow_up") {
    return "追问";
  }
  if (kind === "clarify") {
    return "澄清";
  }
  if (kind === "end_interview") {
    return "收尾";
  }
  return "提问";
}

function InterviewConversation({
  answerDraft,
  interviewError,
  isEndingSession,
  isGeneratingReview,
  isSubmittingAnswer,
  onAnswerChange,
  onEnd,
  onGenerateReview,
  onSubmit,
  pendingAnswer,
  session
}: {
  answerDraft: string;
  interviewError: string;
  isEndingSession: boolean;
  isGeneratingReview: boolean;
  isSubmittingAnswer: boolean;
  onAnswerChange: (value: string) => void;
  onEnd: () => void;
  onGenerateReview: () => void;
  onSubmit: () => void;
  pendingAnswer: string | null;
  session: InterviewSession;
}) {
  const styleLabel = session.style === "pressure" ? "压力面" : "学习梳理面";
  const awaitingReview = session.status === "awaiting_review";
  const conversationClosed = session.status !== "in_progress";
  const latestInterviewerIndex = (() => {
    for (let index = session.transcript.length - 1; index >= 0; index -= 1) {
      if (session.transcript[index].role === "interviewer") {
        return index;
      }
    }
    return -1;
  })();
  const totalMainQuestions = Math.max(session.mainQuestionCount, 0);

  return (
    <div className="interviewConversation" aria-label="面试对话">
      <div className="conversationHeader">
        <div className="conversationHeading">
          <MessagesSquare size={20} aria-hidden="true" />
          <div>
            <h3>面试对话</h3>
            <p>
              {styleLabel} · 第 {totalMainQuestions} / {session.mainQuestionLimit} 个主问题
            </p>
          </div>
        </div>
        <button className="dangerButton" disabled={conversationClosed || isEndingSession} onClick={onEnd} type="button">
          <CircleStop size={16} aria-hidden="true" />
          {isEndingSession ? "结束中" : "手动结束"}
        </button>
      </div>

      <ol className="transcript" aria-label="面试对话记录">
        {session.transcript.map((message, index) => {
          const isInterviewer = message.role === "interviewer";
          const isCurrent = isInterviewer && index === latestInterviewerIndex && !conversationClosed;
          return (
            <li
              className={isInterviewer ? "transcriptItem interviewer" : "transcriptItem candidate"}
              key={index}
            >
              <div className="transcriptMeta">
                <span className="roleTag">{isInterviewer ? "面试官" : "我的回答"}</span>
                {isInterviewer ? <span className="kindTag">{transcriptKindLabel(message.kind)}</span> : null}
              </div>
              <div className={isCurrent ? "transcriptBubble current" : "transcriptBubble"}>
                {message.content}
              </div>
            </li>
          );
        })}
        {pendingAnswer ? (
          <>
            <li className="transcriptItem candidate" key="optimistic-candidate">
              <div className="transcriptMeta">
                <span className="roleTag">我的回答</span>
              </div>
              <div className="transcriptBubble">{pendingAnswer}</div>
            </li>
            <li className="transcriptItem interviewer" key="optimistic-thinking">
              <div className="transcriptMeta">
                <span className="roleTag">面试官</span>
              </div>
              <div className="transcriptBubble thinkingBubble">
                <span className="thinkingLabel">正在思考</span>
                <span className="thinkingDots" aria-hidden="true">
                  <span />
                  <span />
                  <span />
                </span>
              </div>
            </li>
          </>
        ) : null}
      </ol>

      {conversationClosed ? (
        <div className="conversationFooter">
          <div className="endedState">
            {awaitingReview ? "面试已结束，请确认是否生成复盘。" : "面试已结束，完整对话上下文已保留。"}
          </div>
          {awaitingReview ? (
            <button className="primaryButton" disabled={isGeneratingReview} onClick={onGenerateReview} type="button">
              <Sparkles size={16} aria-hidden="true" />
              {isGeneratingReview ? "生成中" : "生成复盘"}
            </button>
          ) : null}
          {session.reviewError ? (
            <div className="workflowMessage failure">复盘生成失败：{session.reviewError}</div>
          ) : null}
        </div>
      ) : (
        <div className="conversationFooter">
          <label className="answerEditor">
            <span>文字回答</span>
            <textarea
              onChange={(event) => onAnswerChange(event.target.value)}
              placeholder="用文字回答当前问题，第一版不支持语音"
              rows={4}
              value={answerDraft}
            />
          </label>
          <button className="primaryButton" disabled={isSubmittingAnswer} onClick={onSubmit} type="button">
            <Send size={16} aria-hidden="true" />
            {isSubmittingAnswer ? "提交中" : "提交回答"}
          </button>
        </div>
      )}

      {interviewError ? <div className="workflowMessage failure">{interviewError}</div> : null}
    </div>
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

function ResumableInterviews({
  onAbandon,
  onResume,
  sessions
}: {
  onAbandon: (sessionId: number) => Promise<void> | void;
  onResume: (sessionId: number, interviewId: number) => Promise<void> | void;
  sessions: ResumeableSession[];
}) {
  if (sessions.length === 0) {
    return null;
  }

  async function handleAbandon(onAbandon: (sessionId: number) => Promise<void> | void, sessionId: number) {
    try {
      await onAbandon(sessionId);
    } catch {
      // 错误已由 onAbandon 内部上报到首页错误条。
    }
  }

  return (
    <section className="panel homeResumePanel" aria-labelledby="resume-title">
      <div className="sectionHeader">
        <div>
          <h2 id="resume-title">未完成的面试</h2>
          <p>继续之前未完成的模拟面试，或放弃后重新开始。</p>
        </div>
      </div>
      <ul className="resumeList" aria-label="进行中面试列表">
        {sessions.map((session) => {
          const modeLabel =
            interviewModeOptions.find((option) => option.value === session.interviewMode)?.label ?? "单轮面试";
          const styleLabel =
            interviewStyleOptions.find((option) => option.value === session.style)?.label ?? "学习梳理面";
          return (
            <li className="resumeItem" key={session.id}>
              <div className="resumeSummary">
                <strong>目标岗位：{session.targetRole || "由简历推断"}</strong>
                <span>
                  {modeLabel} · {styleLabel}
                  {session.roundTitle ? ` · ${session.roundTitle}` : ""}
                  {" · 第 "}
                  {Math.max(session.mainQuestionCount, 0)} / {session.mainQuestionLimit} 个主问题
                </span>
              </div>
              <div className="resumeActions">
                <button
                  className="primaryButton"
                  onClick={() => void onResume(session.id, session.interviewId)}
                  type="button"
                >
                  继续面试
                </button>
                <button
                  className="dangerButton"
                  onClick={() => void handleAbandon(onAbandon, session.id)}
                  type="button"
                >
                  放弃
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function ResumeAnalysisHistory({ records }: { records: ResumeAnalysisRecord[] }) {
  return (
    <section className="panel homeResumeAnalysisPanel" aria-labelledby="resume-analysis-history-title">
      <div className="sectionHeader">
        <div>
          <h2 id="resume-analysis-history-title">简历分析历史</h2>
          <p>成功解析过的 Markdown 简历会保存在这里，便于确认和辨认。</p>
        </div>
      </div>

      {records.length === 0 ? (
        <div className="emptyState">暂无简历分析记录，解析成功后会出现在这里。</div>
      ) : (
        <ul className="resumeAnalysisList" aria-label="简历分析历史列表">
          {records.map((record) => (
            <li className="resumeAnalysisItem" key={record.id}>
              <div className="resumeAnalysisItemHeader">
                <strong>{record.targetRole || "由简历推断"}</strong>
                <span>创建 {formatCompletedAt(record.createdAt)}</span>
              </div>
              <p>{record.summary}</p>
              <div className="resumeAnalysisMeta">
                <span>使用 {record.useCount} 次</span>
                <span>最后使用 {formatCompletedAt(record.lastUsedAt)}</span>
              </div>
              <div className="resumeAnalysisTags" aria-label={`简历分析记录 ${record.id} 摘要`}>
                {record.keyProjects.slice(0, 2).map((project) => (
                  <span key={`project-${record.id}-${project}`}>{project}</span>
                ))}
                {record.technicalStack.length > 0 ? (
                  <span>{record.technicalStack.slice(0, 3).join(" / ")}</span>
                ) : null}
                {record.followUpTopics.slice(0, 1).map((topic) => (
                  <span key={`topic-${record.id}-${topic}`}>{topic}</span>
                ))}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function App() {
  const [route, setRoute] = useState<RouteId>(() => routeFromHash(window.location.hash));
  const [inProgressSessions, setInProgressSessions] = useState<ResumeableSession[]>([]);
  const [resumeAnalysisRecords, setResumeAnalysisRecords] = useState<ResumeAnalysisRecord[]>([]);
  const [resumeContext, setResumeContext] = useState<ResumeContext | null>(null);
  const [resumeError, setResumeError] = useState("");

  useEffect(() => {
    function syncRouteFromHash() {
      setRoute(routeFromHash(window.location.hash));
    }

    window.addEventListener("hashchange", syncRouteFromHash);
    return () => window.removeEventListener("hashchange", syncRouteFromHash);
  }, []);

  async function loadResumeAnalysisRecords() {
    try {
      const response = await fetch(`${apiBaseUrl}/resume-analysis-records`);
      if (!response.ok) {
        return;
      }
      const payload = (await response.json()) as ResumeAnalysisRecordsPayload;
      setResumeAnalysisRecords(payload.records);
    } catch {
      // 简历分析历史加载失败不阻塞首页和新建面试主流程。
    }
  }

  useEffect(() => {
    void loadResumeAnalysisRecords();
  }, []);

  useEffect(() => {
    let mounted = true;

    async function loadInProgress() {
      try {
        const response = await fetch(`${apiBaseUrl}/interview-sessions/in-progress`);
        if (!response.ok) {
          return;
        }
        const sessions = (await response.json()) as ResumeableSession[];
        if (mounted) {
          setInProgressSessions(sessions);
        }
      } catch {
        // 进行中面试加载失败时不阻塞主流程，首页仍可新建面试。
      }
    }

    void loadInProgress();
    return () => {
      mounted = false;
    };
  }, []);

  function navigate(routeId: RouteId) {
    const nextHash = hashForRoute(routeId);
    if (window.location.hash === nextHash) {
      setRoute(routeId);
      return;
    }
    window.location.hash = nextHash;
  }

  async function resumeInterview(sessionId: number, interviewId: number) {
    setResumeError("");
    try {
      const [sessionResponse, interviewResponse] = await Promise.all([
        fetch(`${apiBaseUrl}/interview-sessions/${sessionId}`),
        fetch(`${apiBaseUrl}/interviews/${interviewId}`)
      ]);
      if (!sessionResponse.ok || !interviewResponse.ok) {
        throw new Error("恢复面试失败");
      }
      const session = (await sessionResponse.json()) as InterviewSession;
      const interview = (await interviewResponse.json()) as ResumedInterview;
      setResumeContext({ interview, session });
      navigate("new-interview");
    } catch (error) {
      setResumeError(error instanceof Error ? error.message : "恢复面试失败");
    }
  }

  async function abandonInterview(sessionId: number) {
    setResumeError("");
    try {
      const response = await fetch(`${apiBaseUrl}/interview-sessions/${sessionId}/abandon`, {
        method: "POST"
      });
      if (!response.ok) {
        throw new Error("放弃面试失败");
      }
      setInProgressSessions((current) => current.filter((session) => session.id !== sessionId));
      setResumeContext((current) => (current && current.session.id === sessionId ? null : current));
    } catch (error) {
      setResumeError(error instanceof Error ? error.message : "放弃面试失败");
      throw error;
    }
  }

  const activeView = viewForRoute(route);
  const newInterviewStep: NewInterviewStep =
    route === "new-analysis"
      ? "analysis"
      : route === "new-interview"
        ? "interview"
        : route === "review"
          ? "review"
          : "upload";

  return (
    <div className="appShell">
      <Navigation
        activeView={activeView}
        onViewChange={(view) => navigate(view === "new" ? "new-upload" : view)}
      />

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

        {route === "settings" ? (
          <SettingsPage />
        ) : route === "history" ? (
          <HistoryPage />
        ) : (
          <>
            {route === "home" ? (
              <>
                <ResumableInterviews
                  onAbandon={abandonInterview}
                  onResume={resumeInterview}
                  sessions={inProgressSessions}
                />
                <ResumeAnalysisHistory records={resumeAnalysisRecords} />
              </>
            ) : null}
            {resumeError && route === "home" ? (
              <div className="workflowMessage failure">{resumeError}</div>
            ) : null}
            <NewInterviewFlow
              hasInProgressInterview={inProgressSessions.length > 0}
              onAbandonActiveInterview={abandonInterview}
              onResumeAnalysisCreated={loadResumeAnalysisRecords}
              onNavigateStep={(step) => navigate(routeForStep(step))}
              resumeContext={resumeContext}
              step={newInterviewStep}
            />
            {route !== "new-interview" && route !== "review" ? <RoundsPanel /> : null}
          </>
        )}
      </main>

      <RightRail />
    </div>
  );
}
