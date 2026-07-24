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

## 部署

推荐用 Docker Compose 一键部署。镜像内多阶段构建前端并交由后端 FastAPI 托管，**一个容器、一个端口、一个地址**，`data/` 目录挂载持久化。

### 前提

本机已安装 Docker（含 compose v2）。验证：

```powershell
docker compose version
```

### 启动

在项目根目录执行：

```powershell
docker compose up --build
```

首次会构建镜像（装前端依赖、构建前端、装后端依赖），后续启动直接用缓存，秒级起。

启动后浏览器打开 **`http://localhost:8000`**（前端与 API 同源）。

健康检查：

```powershell
curl http://localhost:8000/health
```

### 数据持久化

- 数据库：`data/mock_interview.sqlite3`
- AI Provider 配置：`data/ai-provider.json`

两者通过 `./data` 卷挂载，容器重建或升级后数据保留。AI 模型密钥等私有配置只存在本机 `data/` 下，不进镜像、不进仓库、不上云。

> AI Provider 在应用内「设置页」配置（baseUrl / apiKey / model），首次使用前先配置。

### 更新代码后重新部署

```powershell
git pull
docker compose up --build
```

### 停止

```powershell
docker compose down        # 停止并移除容器，data/ 保留
```

### 配置项

| 配置 | 方式 | 默认 | 说明 |
| --- | --- | --- | --- |
| 监听端口 | `compose.yml` 的 `ports` | `8000:8000` | 改左侧宿主端口 |
| 数据目录 | `compose.yml` 的 `volumes` | `./data:/app/data` | 改为 named volume 或自定义路径 |
| 数据库路径 | `MOCK_INTERVIEW_DB_PATH` 环境变量 | `data/mock_interview.sqlite3` | 一般无需改 |
| AI 配置路径 | `MOCK_INTERVIEW_AI_CONFIG_PATH` 环境变量 | `data/ai-provider.json` | 一般无需改 |
| 局域网访问 | `Dockerfile` 的 uvicorn `--host` 已为 `0.0.0.0` | — | 仅宿主映射的端口可访问，自行评估暴露风险 |

### 不用 Docker 的本地部署

若不想用 Docker，等价做法是手动构建前端 + 启动后端（后端会自动托管 `apps/web/dist`）：

```powershell
npm install
npm run build
uv pip install -r apps/api/requirements.txt
uv run uvicorn apps.api.app.main:app --host 127.0.0.1 --port 8000
```

打开 `http://localhost:8000`。

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
