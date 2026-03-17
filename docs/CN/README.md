[English](../EN/README.md) | 简体中文

# Intent 文档索引

`docs/` 只做一件事：把 Intent 的文档拆成清楚的几层，每层只回答一类问题。

## 文档结构

| 文档 | 主要回答 | 不负责 |
| --- | --- | --- |
| [术语表](glossary.md) | 这些核心名词分别是什么意思 | 项目背景、命令设计 |
| [愿景与问题定义](vision.md) | 为什么 agent 时代需要 Intent | 具体命令语法、JSON schema |
| [CLI 设计文档](cli.md) | CLI 的命令、对象模型与 JSON contract | 更长期的平台问题 |
| [分发与集成设计](distribution.md) | Intent CLI 与 agent 集成应该如何分发 | CLI contract 细节 |
| [首个 Agent 试用反馈](feedback.md) | 第一个真实 agent 使用者觉得哪里有帮助、哪里卡手 | CLI contract 定义 |
| [Demo](demo.md) | 如何快速试用 Intent | CLI contract 定义 |
| [发布基线](release.md) | release 前至少需要检查什么 | CLI contract 细节 |
| [发展战略](strategy.md) | Intent 如何成为新范式 | 当前 CLI 细节 |
| [路线图](roadmap.md) | v0.2 简化之后接下来做什么 | 当前 CLI contract 定义 |
| [文档国际化规范](i18n.md) | 中英文文档如何组织 | CLI contract 细节 |

## 推荐阅读路径

- 第一次了解项目：先看 [术语表](glossary.md)，再看 [愿景与问题定义](vision.md)
- 想快速看一个可运行示例：看 [Demo](demo.md)
- 想了解 CLI：看 [CLI 设计文档](cli.md)
- 想看真实 agent 使用的产品反馈：看 [首个 Agent 试用反馈](feedback.md)
- 想做一次 release 检查：看 [发布基线](release.md)
- 想了解长期方向：看 [发展战略](strategy.md)
- 想讨论优先级：看 [路线图](roadmap.md)

## 当前 Source Of Truth

- 问题定义、长期方向：以 [愿景与问题定义](vision.md) 为准
- CLI 命令语义、对象模型、JSON contract、错误模型：以 [CLI 设计文档](cli.md) 为准
- 简化后的优先级：以 [路线图](roadmap.md) 为准

如果不同文档出现 CLI 细节冲突，请同步修正 EN/CN 两份文档。

## 当前最该关注的内容

- `init → start → snap → done`
- 2 对象模型：intent 和 checkpoint
- `inspect` 作为主要的机器可读入口
- JSON-only 输出
- 固定 bootstrap 路径：`~/.intent/repo` 加 `~/.intent/bin/itt`

## 说明

- 根目录 [README](../../README.md) 是英文 GitHub 入口，[README.CN.md](../../README.CN.md) 是中文版本
- `docs/` 里的文档会尽量减少重复叙事；共用术语统一收敛到 [术语表](glossary.md)
- 当前安装旅程的 source of truth 是 [分发与集成设计](distribution.md)
