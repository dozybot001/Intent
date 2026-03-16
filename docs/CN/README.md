[English](../EN/README.md) | 简体中文

# Intent 文档索引

`docs/` 只做一件事：把 Intent 的文档拆成清楚的几层，每层只回答一类问题。

仓库当前正在进行中英文迁移。GitHub 默认先展示英文 README，核心文档以 EN/CN 成对提供。

## 文档结构

| 文档 | 主要回答 | 不负责 | 当前语言状态 |
| --- | --- | --- | --- |
| [术语表](glossary.md) | 这些核心名词分别是什么意思 | 项目背景、命令设计、实现细节 | EN/CN 双语可用 |
| [愿景与问题定义](vision.md) | 为什么 agent 时代需要 Intent | 具体命令语法、JSON schema | EN/CN 双语可用 |
| [CLI 统一设计文档](cli.md) | Intent CLI 的项目边界、命令语义与实现 contract | 更长期的平台问题 | EN/CN 双语可用 |
| [Demo](demo.md) | 如何快速复现 `itt log` 与 `git log` 的对比 | CLI contract 定义、长期路线 | EN/CN 双语可用 |
| [路线图](roadmap.md) | CLI 初版之后接下来最值得做什么 | 当前 CLI contract 定义 | EN/CN 双语可用 |
| [文档国际化方案](i18n.md) | 中英双轨文档如何组织与迁移 | CLI contract 细节、实现路线 | EN/CN 双语可用 |

## 推荐阅读路径

- 第一次了解项目：先看 [术语表](glossary.md)，再看 [愿景与问题定义](vision.md)
- 想快速看一个可运行示例：看 [Demo](demo.md)
- 想讨论中英文文档如何组织：看 [文档国际化方案](i18n.md)
- 想讨论命令、交互或准备实现：直接看 [CLI 统一设计文档](cli.md)
- 想讨论下一阶段实现优先级：看 [路线图](roadmap.md)

## 当前 Source Of Truth

- 问题定义、长期方向：以 [愿景与问题定义](vision.md) 为准
- CLI 的命令语义、对象曝光顺序、状态机、JSON contract、错误模型：以 [CLI 统一设计文档](cli.md) 为准
- 实现优先级和下一阶段计划：以 [路线图](roadmap.md) 为准

如果不同文档出现 CLI 细节冲突，请同步修正 EN/CN 两份文档。

## 当前最该关注的内容

- `init -> start -> snap -> adopt -> log`
- `.intent/` 本地对象层
- `status --json` / `inspect --json`
- Git linkage、错误模型、幂等语义

## 说明

- 根目录 [README](../../README.md) 是英文 GitHub 入口，[README.CN.md](../../README.CN.md) 是中文版本
- `docs/` 里的文档会尽量减少重复叙事；共用术语统一收敛到 [术语表](glossary.md)
