# Issue tracker：GitHub

本仓库的 Issues 和 PRD 存放在 GitHub Issues。所有相关操作默认使用 `gh` CLI。

## 约定

- 创建 issue：`gh issue create --title "..." --body "..."`
- 读取 issue：`gh issue view <number> --comments`
- 列出 issue：`gh issue list --state open --json number,title,body,labels,comments`
- 评论 issue：`gh issue comment <number> --body "..."`
- 添加或移除标签：`gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- 关闭 issue：`gh issue close <number> --comment "..."`

在已关联 GitHub 远程仓库后，`gh` 会根据当前仓库的 `git remote` 自动推断目标仓库。

## PR 是否作为 triage 入口

外部 PR 不作为 triage 入口。

这是一个私人项目，`/triage` 只处理 GitHub Issues，不把 PR 当作需求或任务来源。

## 当技能要求“发布到 issue tracker”

创建一个 GitHub Issue。

## 当技能要求“读取相关 ticket”

运行 `gh issue view <number> --comments`。
