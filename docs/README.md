# Intent 文档索引

`docs/` 只做一件事：把 Intent 的文档拆成清楚的几层，每层只回答一类问题。

## 文档结构

| 文档 | 主要回答 | 不负责 |
| --- | --- | --- |
| [术语表](glossary.md) | 这些核心名词分别是什么意思 | 产品论证、命令设计、实现细节 |
| [愿景与问题定义](vision.md) | 为什么 agent 时代需要 Intent | 具体命令语法、JSON schema |
| [CLI 统一设计文档](cli.md) | Intent CLI 的产品边界、命令语义与实现 contract | 更长期的平台问题 |

## 推荐阅读路径

- 第一次了解项目：先看 [术语表](glossary.md)，再看 [愿景与问题定义](vision.md)
- 想讨论命令、交互或准备实现：直接看 [CLI 统一设计文档](cli.md)

## 当前 Source Of Truth

- 问题定义、长期方向：以 [愿景与问题定义](vision.md) 为准
- CLI 的命令语义、对象曝光顺序、状态机、JSON contract、错误模型：以 [CLI 统一设计文档](cli.md) 为准

如果不同文档出现细节冲突，按这条规则理解：

- CLI 相关内容统一以 [CLI 统一设计文档](cli.md) 为准

## 当前最该关注的内容

- `init -> start -> snap -> adopt -> log`
- `.intent/` 本地对象层
- `status --json` / `inspect --json`
- Git linkage、错误模型、幂等语义

## 说明

- 根目录 [README.md](../README.md) 面向首次进入仓库的人，只保留总览
- `docs/` 里的文档会尽量减少重复叙事；共用术语统一收敛到 [术语表](glossary.md)
