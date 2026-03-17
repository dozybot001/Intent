[English](../EN/README.md) | 简体中文

# Intent 文档索引

`docs/` 只做一件事：把 Intent 的文档拆成清楚的几层，每层只回答一类问题。

## 文档结构

| 文档 | 主要回答 | 不负责 |
| --- | --- | --- |
| [术语表](glossary.md) | 这些核心名词分别是什么意思 | 项目背景、命令设计、实现细节 |
| [愿景与问题定义](vision.md) | 为什么 agent 时代需要 Intent | 具体命令语法、JSON schema |
| [CLI 统一设计文档](cli.md) | Intent CLI 的项目边界、命令语义与实现 contract | 更长期的平台问题 |
| [分发与集成设计](distribution.md) | Intent CLI 与 agent 集成应该如何分发和安装 | CLI contract 细节、各平台实现细枝末节 |
| [项目结构说明](structure.md) | 当前仓库结构是什么样、各路径分别负责什么 | CLI contract 细节、release 策略 |
| [首个 Agent 试用反馈](feedback.md) | 第一个真实 agent 使用者觉得哪里有帮助、哪里卡手 | CLI contract 定义、最终产品决策 |
| [Demo](demo.md) | 如何快速复现 `itt log` 与 `git log` 的对比 | CLI contract 定义、长期路线 |
| [发布基线](release.md) | 阶段性 release 前至少需要检查什么 | CLI contract 细节、长期路线 |
| [路线图](roadmap.md) | `v0.1.0` 之后接下来最值得做什么 | 当前 CLI contract 定义 |
| [文档国际化规范](i18n.md) | 中英文文档如何组织与维护 | CLI contract 细节、实现路线 |

## 推荐阅读路径

- 第一次了解项目：先看 [术语表](glossary.md)，再看 [愿景与问题定义](vision.md)
- 想快速看一个可运行示例：看 [Demo](demo.md)
- 想在动手之前先看懂仓库布局：看 [项目结构说明](structure.md)
- 想看一次真实 agent 使用后的产品反馈：看 [首个 Agent 试用反馈](feedback.md)
- 想讨论一步安装与多平台 agent 启用：看 [分发与集成设计](distribution.md)
- 想做一次阶段性 release 检查：看 [发布基线](release.md)
- 想讨论中英文文档如何组织：看 [文档国际化规范](i18n.md)
- 想讨论命令、交互或准备实现：直接看 [CLI 统一设计文档](cli.md)
- 想讨论 `v0.1.0` 之后的实现优先级：看 [路线图](roadmap.md)

## 当前 Source Of Truth

- 问题定义、长期方向：以 [愿景与问题定义](vision.md) 为准
- CLI 的命令语义、对象曝光顺序、状态机、JSON contract、错误模型：以 [CLI 统一设计文档](cli.md) 为准
- `v0.1.0` 之后的优先级和下一阶段方向：以 [路线图](roadmap.md) 为准
- 首次 dogfooding 得到的真实使用反馈：看 [首个 Agent 试用反馈](feedback.md)

如果不同文档出现 CLI 细节冲突，请同步修正 EN/CN 两份文档。

## 当前最该关注的内容

- `init -> start -> snap -> adopt -> log`
- `.intent/` 本地对象层
- `status --json` / `inspect --json`
- Git linkage、错误模型、幂等语义
- 固定 bootstrap 路径：`~/.intent/repo` 加 `~/.intent/bin/itt`

## 说明

- 根目录 [README](../../README.md) 是英文 GitHub 入口，[README.CN.md](../../README.CN.md) 是中文版本
- `docs/` 里的文档会尽量减少重复叙事；共用术语统一收敛到 [术语表](glossary.md)
- 当前安装旅程的 source of truth 是 [分发与集成设计](distribution.md)
