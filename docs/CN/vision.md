# Intent 的愿景

中文 | [English](../EN/vision.md)

## 1. 核心判断

```mermaid
flowchart LR
  subgraph traditional["古法编程"]
    direction TB
    H1["人"]
    C1["代码"]
    H1 -->|"Git"| C1
  end
  subgraph agent["Agent 驱动开发"]
    direction TB
    H2["人"]
    AG["Agent"]
    C2["代码"]
    H2 -."❌ 无语义历史".-> AG
    AG -->|"Git"| C2
  end
  subgraph withintent["有 Intent 的 Agent"]
    direction TB
    H3["人"]
    AG2["Agent"]
    C3["代码"]
    H3 -->|"Intent"| AG2
    AG2 -->|"Git"| C3
  end
  traditional ~~~ agent ~~~ withintent
```

Git 仍然是代码世界的基础设施，这一点没有变。

变化的是软件开发的工作方式：

- 人越来越多通过 agent 间接塑造代码
- 实现过程越来越像“提出目标、推进结果、持续修正、沉淀决策”
- 开发过程稳定地产生出更高层的语义节点，例如当前意图、语义检查点、长期决策、修正与续做

因此，新的问题不是“怎么替代 Git”，而是：

**如何在 Git 之上，为人和 agent 的协作补上一层 semantic history。**

Intent 的定位就是这一层。

## 2. 现在真正缺的不是信息，而是稳定对象边界

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
- 可以回忆，但没有统一边界
- 对人还能凑合，对 agent 不够可靠

这会导致一个很实际的问题：我们能看到代码怎么变了，却很难稳定回答下面这些问题。

- 当前到底在解决什么问题
- 最近一次交互实际推进了什么
- 用户对这次推进给了什么反馈
- 哪些长期决策仍然有效
- 为什么当前会沿着这条路径继续推进

Intent 要解决的不是“记录更多信息”，而是：

**把这些高层语义提升为第一类对象。**

## 3. 为什么现有工具组合不够

`Git + PR + issue + docs + chat` 当然有用，但它们并没有把这层语义历史建成一个统一系统。

主要问题有四个：

- 语义是分散表达的，不是正式建模的
- 语义节点边界不稳定，很难引用、比较和回溯
- 对 agent 来说，缺少稳定入口和可查询上下文
- “推进、修正、沉淀决策”仍然散落在不同媒介里

在传统开发里，中心动作更像“写代码”。

在 agent-driven development 里，越来越关键的动作其实是：

- 提出目标
- 推进实现
- 持续修正
- 记录交互反馈
- 沉淀长期有效的决策

也就是说，开发过程的重心正在从“写”转向“引导、衔接与沉淀”。

## 4. Intent 补的是哪一层

Intent 不替代 Git。它补的是 Git 天然没有被设计去承载的那层历史。

```mermaid
flowchart TB
  Hub["IntHub — 协作层"]
  Intent["Intent — 语义历史层"]
  Git["Git — 代码历史层"]
  Hub <--> Intent <--> Git
```

| 层 | 负责什么 | 典型内容 |
| --- | --- | --- |
| Git | code history | commit、branch、diff |
| Intent | semantic history | 当前意图、语义检查点、长期决策、修正与续做 |
| 协作层 | 远端组织与协作 | timeline、共享视图、协作上下文 |

因此可以把 Intent 理解成：

**构建在 Git 之上的 semantic history layer。**

一句话说就是：

**Git 记录代码变化，Intent 记录语义历史。**

## 5. 项目边界

Intent 当前不打算做这些事：

- 替代 Git 的版本控制能力
- 替代 issue、PR 或 docs 系统
- 保存全部原始对话和全部中间过程
- 成为“记录一切”的重型过程平台
- 把远端协作当成第一优先级前提

Intent 的边界很明确：

**只记录那些值得被正式跟踪、链接、纠偏和复用的语义节点。**

## 6. 为什么这在 agent 时代更迫切

```mermaid
sequenceDiagram
  participant H as 人
  participant A as Agent A
  participant I as Intent
  participant B as Agent B

  H->>A: “修复登录超时”
  A->>I: intent create + snap（summary）
  A-->>H: 今天到这里

  Note over A,B: session 结束，上下文丢失

  H->>B: “接着上次继续”
  B->>I: itt inspect
  I-->>B: active intents、decisions、latest snap
  B->>B: 读 summary → 知道做了什么、还差什么
  B->>I: snap（继续推进）
```

在传统开发里，语义在程序员脑中。在 agent 时代，session 会中断、agent 会切换、上下文会丢失。Intent 让这个交接变成结构化的，而不是口头的。

## 7. 判断这件事是否成立

Intent 是否成立，不取决于它记录了多少东西，而取决于它是否真的降低了协作中的语义损耗。

更具体地说：

- 新 session 需要重新补推上下文的次数是否更少
- 人类是否更容易看懂当前在解决什么、最近推进了什么、为什么这么推进
- 被中断的工作是否更容易续做
- 长期决策是否更容易被稳定继承，而不是埋没在聊天或记忆里

如果这些收益不成立，那么无论 schema 多漂亮、命令多完整，Intent 都不成立。

## 8. 一句话定义

Intent 是一个面向 agent-driven software development 的 Git-compatible semantic history layer，主打产品形成历史记录与跨 session / agent 的工作恢复。

## 9. 总结

Intent 关注的不是 Git 的版本控制能力，而是 Git 之外的语义历史：

- 产品、工作流或设计方向是如何逐步形成的
- 后续 session 或其他 agent 如何在不丢失语义上下文的前提下继续工作
- 最近一次交互推进了什么
- 用户对这些推进给了什么反馈
- 哪些长期决策仍然有效
- 当前路径是如何形成的，以及后续修正应如何理解
