# Intent CLI

> 一个构建在 Git 之上的 semantic history layer，用来记录当前想解决什么问题、形成过哪些候选结果，以及最终正式采纳了什么、为什么采纳。

Intent 不是 Git 的替代品。
它补的是 Git 天然不擅长承载的那一层高阶语义历史。

一句话概括：

> **Git 管代码变化，Intent 管采纳历史。**

## 为什么是 Intent

在 agent-driven development 里，真正重要的信息并不稀缺，而是分散。

- 问题目标可能在 issue 里
- 候选方案可能在对话、草稿或临时提交里
- 最终选择和取舍理由可能只留在某次讨论中

这些信息可以阅读，但通常不是稳定对象，也不容易被持续追踪、比较、采纳或让 agent 可靠调用。

Intent 想解决的是这个问题：

- 把高层语义从零散说明，变成正式对象
- 把“生成过什么”推进到“最终采纳了什么”
- 在 Git 之上补一层可追溯的 semantic history

## 核心工作流

首页只需要先理解 3 个动作：

- `start`：开始处理一个问题
- `snap`：保存一个候选结果
- `adopt`：正式采纳一个候选结果

对应的最小闭环是：

```bash
itt init
itt start "Reduce onboarding confusion"
itt snap "Landing page candidate B"
git add .
git commit -m "refine onboarding landing layout"
itt adopt -m "Adopt progressive disclosure layout"
itt log
```

如果只看首屏，建议先记住这 6 个命令：

```bash
itt init
itt start
itt status
itt snap
itt adopt
itt log
```

## 这个项目不做什么

Intent 不打算：

- 替代 Git 的版本控制
- 替代 issue、PR 或 docs 系统
- 成为“什么都记录”的日志归档工具
- 在第一阶段就扩展成完整远端平台

第一阶段更关心的是先把本地 semantic workflow 做成立。

## 文档导航

更完整的说明已经拆到 `docs/`，README 只保留总览。
建议先从 [文档索引](docs/README.md) 进入。

- [文档索引](docs/README.md)：推荐入口，包含阅读顺序、文档定位与当前参考优先级
- [产品愿景](docs/intent_vision_notes_v_3_cn.md)：为什么 agent 时代需要 semantic history，以及 Intent 解决的核心问题
- [CLI 设计文档](docs/intent_cli_design_spec_v_0_4_cn.md)：产品定位、对象模型、命令设计、主路径与交互原则
- [实现约束文档](docs/intent_cli_implementation_contract_v_0.md)：本地目录结构、schema、状态机、JSON contract、错误模型与实现边界

推荐阅读顺序：

1. 先看愿景文档，理解项目为什么存在
2. 再看设计文档，理解 CLI 怎么组织
3. 最后看实现约束，理解首版应该冻结什么

## 项目状态

项目目前仍处于早期阶段，重点不是扩展功能面，而是尽快冻结首版的最小闭环与 contract。

当前仓库也仍以产品定义与实现约束收敛为主，尚未发布正式安装包或稳定可用版本。

当前更优先稳定的是：

- `.intent/` 本地对象层
- `state.json` 与状态流转
- `intent / checkpoint / adoption` 的基础 schema
- `status --json` / `inspect --json` 等机器可读 contract
- `init -> start -> snap -> adopt -> log` 这条最小路径

## 贡献

如果你对以下方向感兴趣，欢迎通过 Issue、Discussion 或 PR 参与：

- CLI 命令命名与交互体验收敛
- 对象 schema 与状态机设计审查
- `status --json` / `inspect --json` 等 contract 设计
- 错误模型、幂等语义与 non-interactive 行为
- Git linkage policy 与最小工作流验证

## 项目方向

Intent 的长期方向不是替代 Git，而是补全 agent 时代的软件历史表达方式：

- 代码怎么变，由 Git 负责
- 为什么这样演化、最后采纳了什么，由 Intent 负责

未来结构会更清晰地分成三层：

- **Intent CLI**：本地 semantic history 操作层
- **Skill / agent workflow**：agent 执行与集成层
- **IntHub**：远端组织、协作与展示层
