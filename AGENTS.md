# 全局规则

## 基本规则

- 永远使用中文回复。
- 不得回滚用户改动，除非用户明确要求。
- 不得执行破坏性操作，除非用户明确授权。

## Agent 协作规则

- 允许在任务适合并行拆分时使用子代理。
- 对于代码修改、文档重整、代码审查、批量分析等任务，可以自行判断是否使用子代理。
- 子代理不得执行破坏性操作，不得回滚用户改动。

## Git 提交规范

提交信息使用 Conventional Commits，确保日志可读、便于生成变更记录。

### 必要性澄清

- 未经允许禁止创建新分支

### 提交粒度

- 单次提交只做一类变更（功能/修复/文档）。
- 提交前先整理改动，避免混入无关格式化或临时调试。
- 每个提交应可构建、可运行，方便回滚。
- 大改动拆分为多个可审查的小提交。

### 提交信息格式

```text
<type>[(scope)]: <summary>

[body]

[footer]
```

- type 建议：feat、fix、docs、refactor、test、chore、build（其他场景按需）。
- scope 使用模块/目录（如 app、data、scripts），无明确范围可省略。
- summary 使用中文、动词开头，长度不超过 50 字，不加句号。
- 需要时在正文补充动机、影响或迁移方式。

### 提交类型

| 类型          | 说明                             |
| ------------- | -------------------------------- |
| `🎉 init`     | 项目初始化                       |
| `✨ feat`     | 新功能                           |
| `🐞 fix`      | 错误修复                         |
| `📃 docs`     | 文档变更                         |
| `🌈 style`    | 代码格式化（不影响代码逻辑）     |
| `🦄 refactor` | 代码重构（不新增功能或修复错误） |
| `🎈 perf`     | 性能优化                         |
| `🧪 test`     | 测试相关                         |
| `🔧 build`    | 构建系统或外部依赖               |
| `🐎 ci`       | CI 配置相关                      |
| `🐳 chore`    | 构建过程或辅助工具的变动         |
| `↩ revert`   | 撤销提交                         |

### 破坏性变更

- 在 type 后添加 `!`，或在正文写明 `BREAKING CHANGE: ...`。
- 明确写出受影响范围与升级指引。

### 提交流程

- `git status` 确认改动范围。
- `git add <files>` 仅添加相关文件。
- `npm run lint` 通过后再提交。
- `git commit -m "..."` 完成提交。
- `git push` 后发起 PR（如需）。

## Agent skills

### Issue tracker

本私人项目的 Issues 和 PRD 存放在 GitHub Issues；外部 PR 不作为 triage 入口。详见 `docs/agents/issue-tracker.md`。

### Triage labels

使用默认的 Matt Pocock triage 标签词表：`needs-triage`、`needs-info`、`ready-for-agent`、`ready-for-human`、`wontfix`。详见 `docs/agents/triage-labels.md`。

### Domain docs

本仓库使用 single-context 领域文档布局：根目录 `CONTEXT.md` 加 `docs/adr/`。详见 `docs/agents/domain.md`。