[English](../EN/vision.md) | 简体中文

# Intent 愿景与问题定义

## 核心判断

Git 仍然是代码世界的基础设施，这一点没有变。

变化的是软件开发的工作方式：

- 人越来越多通过 agent 间接塑造代码
- 实现过程越来越像"提出目标、生成候选、选择结果"
- 开发过程的重心正在从"写代码"转向"记录为什么"

新的问题不是"怎么替代 Git"，而是：

**如何在 Git 之上，为 agent 驱动的开发补上一层语义历史。**

Intent 的定位就是这一层。

## 缺的不是信息，而是对象

高层语义信息并不稀缺，它通常散落在 commit message、issue、PR discussion、docs、团队聊天和 agent 对话中。

问题不是"信息不存在"，而是它们通常：

- 可以阅读，但不稳定
- 可以讨论，但难以持续追踪
- 对人还能凑合，对 agent 不够可靠

我们能看到代码怎么变了，却很难稳定回答：

- 当前在解决什么问题
- 做了哪些步骤，为什么
- 关键选择背后的理由是什么

Intent 把这些高层语义提升为第一类对象。

## 为什么现有工具组合不够

`Git + PR + issue + docs + chat` 当然有用，但它们没有把语义历史建成统一系统：

- 语义是分散表达的，不是正式建模的
- 语义节点边界不稳定，很难引用和回溯
- 对 agent 来说，缺少稳定 ID、明确状态和结构化入口

## Intent 补的是哪一层

| 层 | 负责什么 | 典型对象 |
| --- | --- | --- |
| Git | code history | commit、branch、diff |
| Intent | semantic history | intent、checkpoint |
| IntHub | 远端组织与协作 | 后续 |

**Git 记录代码变化，Intent 记录你做了什么以及为什么。**

## 项目边界

Intent 不打算做这些事：

- 替代 Git 的版本控制能力
- 替代 issue、PR 或 docs 系统
- 保存全部原始对话和全部中间过程
- 成为"记录一切"的重型过程平台

Intent 的边界：**只记录值得追踪的语义步骤及其理由。**

## 一句话定义

Intent is a Git-compatible semantic history layer for agent-driven software development.
