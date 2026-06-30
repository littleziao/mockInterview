# Domain docs

本文件说明工程技能在探索代码库前，应该如何读取本仓库的领域文档。

## 探索前先读取

- 根目录的 `CONTEXT.md`。
- 根目录的 `docs/adr/`。

如果这些文件暂时不存在，继续执行任务即可，不需要因为缺失而中断。`/domain-modeling`、`/grill-with-docs` 和 `/improve-codebase-architecture` 可以在后续真正沉淀术语或架构决策时再创建它们。

## 文件结构

本仓库使用 single-context 布局：

```text
/
├── CONTEXT.md
├── docs/adr/
│   ├── 0001-example-decision.md
│   └── 0002-example-decision.md
└── src/
```

## 使用领域词汇

当输出 issue 标题、重构建议、问题假设、测试名称等内容时，优先使用 `CONTEXT.md` 中定义的项目领域词汇。

如果需要表达的概念还没有出现在 `CONTEXT.md` 中，说明可能存在领域语言缺口。可以在合适时机通过 `/domain-modeling` 补充。

## 标出 ADR 冲突

如果某个建议或实现会违背已有 ADR，需要明确指出冲突点，而不是静默覆盖既有决策。
