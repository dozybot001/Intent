# Intent

> Git 记录代码变化，Intent 记录采纳历史。

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

## 核心闭环

Intent 先把最重要的 3 个动作做成正式对象：

- `start`：开始处理一个问题
- `snap`：保存一个候选结果
- `adopt`：正式采纳一个候选结果

也就是这条最小路径：

`问题 -> 候选 -> 采纳`

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

## Intent 不是什么

- 不是 Git 的替代品
- 不是 issue、PR 或 docs 系统的替代品
- 不是“什么都记录”的日志归档工具

Intent 只关心那些值得被正式追踪的语义节点，例如意图、候选、采纳、撤销与决策。

## 当前阶段

项目还在早期阶段，当前重点不是铺开大而全的能力，而是先把本地最小闭环做稳。

当前优先级是：

- `.intent/` 本地对象层
- `init -> start -> snap -> adopt -> log`
- `status --json` / `inspect --json` 这类 agent-friendly contract

## 文档

README 只保留总览，更完整的说明在 `docs/`：

- [文档索引](docs/README.md)
- [术语表](docs/glossary.md)
- [愿景与问题定义](docs/vision.md)
- [CLI 设计说明](docs/cli-design.md)
- [实现约束](docs/cli-contract.md)
