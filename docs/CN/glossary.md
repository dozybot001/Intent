[English](../EN/glossary.md) | 简体中文

# Intent 术语表

这份文档只做术语对齐。它不解释项目愿景，也不定义实现 contract。

## 核心句

Git 记录代码变化，Intent 记录你做了什么以及为什么。

## 术语

- `semantic history`：意图、步骤与理由的历史，而不是代码 diff 的历史
- `intent`：当前想解决的问题或目标
- `checkpoint`：一次记录的步骤，可附带理由——语义历史的基本单元
- `inspect`：主要的机器可读接口；以 JSON 返回完整的 workspace 状态
- `rationale`：checkpoint 背后的理由，通过 `-m` 记录

## 对象模型

Intent 有两种对象类型：

- **Intent**：`open` → `done`
- **Checkpoint**：`adopted`（默认）、`candidate` 或 `reverted`

## 核心闭环

`问题 → 步骤 → 完成`

对应到命令层就是：

`start → snap → done`

## Intent 不是什么

- 不是 Git 的替代品
- 不是 issue、PR 或 docs 系统的替代品
- 不是"记录一切"的日志归档工具
