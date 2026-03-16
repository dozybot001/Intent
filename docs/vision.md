# Intent 愿景与问题定义 v4

## 这篇文档回答什么

- 为什么 agent 时代需要一层新的 semantic history
- Intent 补的是哪一层，而不是替代什么
- Intent CLI、Skill 与 IntHub 各自处在什么位置
- 当前应该如何判断这件事是否成立

## 这篇文档不回答什么

- 具体命令应该怎么设计
- JSON schema、状态机和 exit code
- 首版实现细节

## 与其他文档的边界

- 术语定义以 [术语表](glossary.md) 为准
- CLI 命令语义、状态机与机器可读 contract 以 [CLI 统一设计文档](cli.md) 为准

## 1. 核心判断

Git 仍然是代码世界的基础设施，这一点没有变。

变化的是软件开发的工作方式：

- 人越来越多通过 agent 间接塑造代码
- 实现过程越来越像“提出目标、生成候选、选择结果”
- 开发过程稳定地产生出更高层的对象，例如 `intent`、`checkpoint`、`adoption`、`decision`

因此，新的问题不是“怎么替代 Git”，而是：

**如何在 Git 之上，为人和 agent 的协作补上一层 semantic history。**

Intent 的定位就是这一层。

## 2. 现在真正缺的不是信息，而是对象

高层语义信息今天并不稀缺。它通常散落在：

- commit message
- issue
- PR discussion
- docs
- 团队聊天
- agent conversation
- 临时笔记和口头共识

问题不是“这些信息不存在”，而是它们通常：

- 可以阅读，但不稳定
- 可以讨论，但难以持续追踪
- 可以回忆，但没有统一对象边界
- 对人还能凑合，对 agent 不够可靠

这会导致一个很实际的问题：我们能看到代码怎么变了，却很难稳定回答下面这些问题。

- 当前到底在解决什么问题
- 出现过哪些候选结果
- 最后正式采纳了哪一个
- 为什么是这个，而不是那个

Intent 要解决的不是“记录更多信息”，而是：

**把这些高层语义提升为第一类对象。**

## 3. 为什么现有工具组合不够

`Git + PR + issue + docs + chat` 当然有用，但它们并没有把“采纳历史”建成一个统一系统。

主要问题有四个：

- 语义是分散表达的，不是正式建模的
- 语义节点边界不稳定，很难引用、比较和回溯
- 对 agent 来说，缺少稳定 id、状态机和结构化入口
- “采纳”没有成为系统中心动作

在传统开发里，中心动作更像“写代码”。

在 agent-driven development 里，越来越关键的动作其实是：

- 提出目标
- 生成候选
- 比较候选
- 正式采纳
- 必要时撤销
- 沉淀长期有效的决策

也就是说，开发过程的重心正在从“写”转向“选”。

## 4. Intent 补的是哪一层

Intent 不替代 Git。它补的是 Git 天然没有被设计去承载的那层历史。

| 层 | 负责什么 | 典型对象 |
| --- | --- | --- |
| Git | code history | commit、branch、diff |
| Intent | semantic history | intent、checkpoint、adoption、decision |
| IntHub | 远端组织与协作 | timeline、共享、协作视图 |

因此可以把 Intent 理解成：

**构建在 Git 之上的 intention and adoption layer。**

一句话说就是：

**Git 记录代码变化，Intent 记录采纳历史。**

## 5. 产品边界

Intent 当前不打算做这些事：

- 替代 Git 的版本控制能力
- 替代 issue、PR 或 docs 系统
- 保存全部原始对话和全部中间过程
- 成为“记录一切”的重型过程平台
- 在第一阶段先做成完整远端平台

Intent 的边界很明确：

**只记录那些值得被正式追踪、比较、采纳、撤销和复用的语义节点。**

## 6. 为什么这是 agent 时代更强烈的需求

在传统开发里，很多高层语义虽然没有被正式建模，但至少还在程序员脑中，或者散落在日常协作材料里。

在 agent 时代，情况变了：

- 大量实现由 agent 承担
- 人更像 reviewer、selector、director
- 用户与 agent 的 query、修正、采纳和撤销，本身开始成为开发过程的一部分

这意味着，系统不能只记录“代码如何变化”，还要能记录“为什么最终选择了这条路径”。

对 agent 来说，这层能力尤其重要，因为它需要的是：

- 稳定的对象 id
- 明确的状态
- 可查询的上下文
- 可执行的语义动作

## 7. 为什么第一步必须先做 CLI

Intent 的第一阶段不是平台，而是本地 CLI。

原因很简单：

- 先证明最小闭环能跑通
- 先冻结本地对象层和行为 contract
- 先让 agent、IDE、automation 有稳定入口
- 先用真实 workflow 建立信任，而不是靠长文案

如果本地这层不成立，后面的远端协作、可视化历史和平台化表达都会漂浮。

## 8. 现在如何判断 Intent 是否成立

Intent 当前还不是一个已经自证价值的产品，更像一个正在被验证的本地 semantic layer。

因此，现阶段最重要的不是继续扩张叙事，而是回答三个更硬的问题：

- `start -> snap -> adopt` 是否真的顺手
- `itt log` 是否真的比 `git log` 更接近采纳历史
- `itt inspect --json` 是否真的能让 agent 少猜当前状态

这三个问题可以先通过两个 demo 来证明：

- human demo：同一轮工作里，`itt log` 比 commit history 更清楚地回答“最终采纳了什么”
- agent demo：agent 先读 `itt inspect --json`，再执行正确下一步动作，而不是从 issue、聊天和文档里拼状态

如果这两个 demo 还没有成立，那么 Intent 更应该继续打磨本地闭环，而不是提前扩到平台层。

## 9. 长期结构

Intent 的长期结构可以分成三层：

| 层 | 角色 | 当前优先级 |
| --- | --- | --- |
| Intent CLI | 本地 semantic history 操作层 | 最高 |
| Skill / agent workflow | 教会 agent 何时、如何使用 `itt` | 次高 |
| IntHub | 远端组织、展示与协作层 | 更后 |

这里的关键顺序不是技术实现顺序，而是产品成立顺序：

**先把本地 semantic layer 做成立，再让远端协作层自然长出来。**

这也意味着 IntHub 目前只是一个更后续的组织与协作层，不应该在本地 contract 还未被证明前占据设计中心。

## 10. 一句话定义

### 中文

Intent 是一个构建在 Git 之上的高层语义版本层，用来记录 agent 时代软件开发中的意图、候选、采纳与决策历史。

### English

Intent is a Git-compatible semantic history layer for agent-driven software development.

## 11. 结论

Intent 不是在和 Git 竞争“谁来管理代码版本”。

Intent 解决的是另一个问题：

当开发越来越由人和 agent 协作完成时，系统应该如何正式记录“我们到底采纳了什么”。
