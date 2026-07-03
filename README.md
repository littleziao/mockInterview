# Mock Interview

私人使用的 AI 模拟面试本地 Web 应用。第一版采用 React + TypeScript + Vite 前端、Python + FastAPI 后端和本地 SQLite 数据库。

## 本地开发

### 依赖

- Node.js 20+
- uv
- Python 3.13（由 uv 自动下载与管理）

安装前端依赖：

```powershell
npm install
```

后端依赖使用 uv 在项目根 `.venv` 中管理。首次运行如果还没有依赖，可执行：

```powershell
uv venv --python 3.13
uv pip install -r apps/api/requirements.txt
```

### 一键启动前后端

```powershell
npm run dev:all
```

使用 concurrently 同时启动前端（5173）与后端（8000），日志以 `[web]`/`[api]` 前缀区分，Ctrl+C 一次关闭两边。

### 启动前端

```powershell
npm run dev
```

默认地址：`http://localhost:5173`。

### 启动后端

```powershell
npm run dev:api
```

默认地址：`http://localhost:8000`。

健康检查：

```powershell
Invoke-RestMethod http://localhost:8000/health
```

### 数据库

后端默认使用 `data/mock_interview.sqlite3`。启动时会自动创建数据目录并执行最小初始化，当前包含 `schema_migrations` 表，为后续 Repository 层迁移提供落点。

可通过环境变量覆盖数据库路径：

```powershell
$env:MOCK_INTERVIEW_DB_PATH="D:\tmp\mock_interview.sqlite3"
npm run dev:api
```

### 测试与质量检查

运行全部检查：

```powershell
npm run lint
npm test
```

只运行后端测试：

```powershell
npm run test:api
```

只运行前端测试：

```powershell
npm run test:web
```

前端类型检查：

```powershell
npm run typecheck
```

## 目录结构

```text
apps/
  api/      FastAPI 后端，本地 SQLite 初始化与后端测试
  web/      React + TypeScript + Vite 前端应用壳
packages/
  core/     可复用面试领域类型与默认配置，避免核心逻辑绑定 Web UI
docs/
  adr/      架构决策记录
  prd/      产品需求文档
```
