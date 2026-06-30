# 采用 FastAPI、SQLite 和轻量 AI Provider 层

第一版是本地 Web 应用，需要快速验证简历驱动的连续对话式模拟面试、复盘反馈、评分雷达图和长期趋势分析。我们采用 React + TypeScript + Vite 构建前端，Python + FastAPI 构建本地后端，SQLite 保存本地面试记录，并通过自研轻量 AI Provider 层支持用户自定义模型服务；第一版不引入 LangChain，以降低抽象复杂度、调试成本和供应商绑定风险。

## Considered Options

- Node.js + Fastify：前后端同为 TypeScript，但后续简历解析、文本分析、评分统计等 AI 辅助能力不如 Python 生态顺手。
- LangChain：适合复杂工具调用、RAG、agent 编排和多模型路由；第一版只需要 prompt 编排、结构化输出和 provider 抽象，直接引入会增加不必要复杂度。

## Consequences

- 后端运行依赖 Python/Miniconda 环境。
- AI 调用必须集中在后端 Provider 层，前端和未来微信小程序不得直接持有模型 API Key。
- 关键 AI 输出必须由后端进行结构化 JSON 校验，避免前端直接解析不稳定的自由文本。
- 核心面试逻辑应避免绑定 Web UI，以便第二阶段微信小程序复用。
