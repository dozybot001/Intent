# Intent 文档索引

`docs/` 只做一件事：把 Intent 的文档拆成清楚的几层，每层只回答一类问题。

## 文档结构

| 文档 | 主要回答 | 不负责 |
| --- | --- | --- |
| [术语表](glossary.md) | 这些核心名词分别是什么意思 | 产品论证、命令设计、实现细节 |
| [愿景与问题定义](vision.md) | 为什么 agent 时代需要 Intent | 具体命令语法、JSON schema |
| [CLI 设计说明](cli-design.md) | Intent CLI 应该如何组织和使用 | 底层字段和返回结构冻结 |
| [实现约束](cli-contract.md) | 首版实现必须遵守什么 | 再次解释项目为什么存在 |

## 推荐阅读路径

- 第一次了解项目：先看 [术语表](glossary.md)，再看 [愿景与问题定义](vision.md)
- 想讨论命令和交互：继续看 [CLI 设计说明](cli-design.md)
- 准备开始实现或做集成：直接看 [实现约束](cli-contract.md)，需要时回看设计说明

## 当前 Source Of Truth

- 问题定义、长期方向：以 [愿景与问题定义](vision.md) 为准
- 命令语义、对象曝光顺序、交互原则：以 [CLI 设计说明](cli-design.md) 为准
- schema、状态机、JSON contract、错误模型：以 [实现约束](cli-contract.md) 为准

如果不同文档出现细节冲突，按这条规则理解：

- 产品语义和用户路径，优先看设计说明
- 实现字段和机器可读 contract，优先看实现约束

## 当前最该关注的内容

- `init -> start -> snap -> adopt -> log`
- `.intent/` 本地对象层
- `status --json` / `inspect --json`
- Git linkage、错误模型、幂等语义

## 说明

- 根目录 [README.md](../README.md) 面向首次进入仓库的人，只保留总览
- `docs/` 里的文档会尽量减少重复叙事；共用术语统一收敛到 [术语表](glossary.md)
