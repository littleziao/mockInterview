import {
  Activity,
  BookOpenText,
  CheckCircle2,
  ClipboardList,
  History,
  Home,
  MessageSquareText,
  Radar,
  Settings,
  Sparkles
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
  { label: "首页", icon: Home, active: true },
  { label: "新建面试", icon: ClipboardList, active: false },
  { label: "历史与趋势", icon: Radar, active: false },
  { label: "设置", icon: Settings, active: false }
];

function Navigation() {
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
            className={item.active ? "navItem active" : "navItem"}
            key={item.label}
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
  return (
    <div className="appShell">
      <Navigation />

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

        <SetupPanel />
        <RoundsPanel />
      </main>

      <RightRail />
    </div>
  );
}

