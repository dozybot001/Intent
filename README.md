# Intent

> Git 记录代码变化，Intent 记录采纳历史。
> Intent 同时面向人和 agent。

Intent 是一个构建在 Git 之上的新层，用来记录软件开发里更高层的信息：

- 现在想解决什么问题
- 试过哪些候选方案
- 最后正式采纳了什么
- 为什么采纳它

它不替代 Git。  
它补的是 Git 通常不会清楚保存的那部分历史。

如果用一句更技术的话说，Intent 是一个面向 agent 时代的 Git-compatible semantic history layer。当前第一步先以 `Intent CLI` 的形式落地。

## 30 秒理解

在 agent-driven development 里，代码可以生成得很快，但决策过程往往是散的：

- 目标在 issue 里
- 候选方案在对话或草稿里
- 最终选择和理由在某次讨论里

Git 很擅长回答“代码怎么变了”，但不擅长回答“我们最后决定了什么”。

Intent 想补上的，就是这层历史。

更重要的是，这层历史不能只对人类可读，也必须对 agent 友好。

新范式如果只靠人读长文档来理解，就很难传播。
如果用户越来越通过 AI 获取信息、调用工具和完成工作，那么 Intent 这一层从第一天起就必须是 AI-friendly 的。

这意味着 Intent 不只是“多一份说明文档”，而是要把这些高层语义变成：

- 人容易理解的工作流
- 开发者容易集成的接口
- agent 能稳定读取和操作的对象

## 核心闭环

Intent 先把最重要的 3 个动作做成正式对象：

- `start`：开始处理一个问题
- `snap`：保存一个候选结果
- `adopt`：正式采纳一个候选结果

也就是这条最小路径：

`问题 -> 候选 -> 采纳`

这条路径既是给人记的，也是给 agent 用的。

## 为什么它对 agent 重要

Intent 不只是帮助人回忆过去，也是在给 agent 提供稳定上下文。

对 agent 来说，最重要的不是更多 prose，而是：

- 稳定的对象边界
- 明确的当前状态
- 可预测的下一步动作
- 结构化、可消费的输出

所以 Intent 的目标不是“让 agent 猜测你的意图”，而是让意图、候选和采纳本身成为正式对象。

## 最小示例

```bash
itt init
itt start "Reduce onboarding confusion"
itt snap "Landing page candidate B"
git add .
git commit -m "refine onboarding landing layout"
itt adopt -m "Adopt progressive disclosure layout"
itt log
```

跑完这条路径后，用户应该立刻理解三件事：

- Git 还在正常管理代码
- Intent 额外记录了这次工作的语义历史
- `itt log` 比 commit history 更接近“这次到底采纳了什么决策”

## 首页先记住这 6 个命令

```bash
itt init
itt start
itt status
itt snap
itt adopt
itt log
```

如果你是开发者或 agent 集成方，首版还应该特别关注这两个入口：

```bash
itt status --json
itt inspect --json
```

## Intent 不是什么

- 不是 Git 的替代品
- 不是 issue、PR 或 docs 系统的替代品
- 不是“什么都记录”的日志归档工具

Intent 只关心那些值得被正式追踪的语义节点，例如意图、候选、采纳、撤销与决策。

## Human-Friendly, Agent-Friendly

Intent 首页的设计原则很简单：

- 对用户：先让人秒懂 `start -> snap -> adopt`
- 对开发者：提供稳定、清晰、可实现的本地 contract
- 对 agent：提供固定对象、固定状态和固定 JSON 入口

如果这三件事不能同时成立，Intent 就很难成为新范式。

## 当前阶段

项目还在早期阶段，当前重点不是铺开大而全的能力，而是先把本地最小闭环做稳。

当前优先级是：

- `.intent/` 本地对象层
- `init -> start -> snap -> adopt -> log`
- `status --json` / `inspect --json` 这类 agent-friendly contract
- 让同一套语义既适合人使用，也适合 agent 使用

## 文档

README 只保留总览，更完整的说明在 `docs/`：

- [文档索引](docs/README.md)
- [术语表](docs/glossary.md)
- [愿景与问题定义](docs/vision.md)
- [CLI 统一设计文档](docs/cli.md)

强烈推荐阅读：[愿景与问题定义](docs/vision.md)。
