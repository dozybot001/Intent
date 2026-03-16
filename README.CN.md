[English](README.md) | 简体中文

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

Intent 以 CLI 形式提供这层历史，并提供给人和 agent 都可读取的结构化入口。

这意味着 Intent 不是“多一份说明文档”，而是把这些高层语义变成：

- 人容易理解的工作流
- 开发者容易集成的接口
- agent 能稳定读取和操作的对象

## 为什么不直接用 issue / ADR / commit message

现有工具当然有价值，但它们没有把“采纳历史”本身做成稳定对象。

| 方式 | 擅长什么 | 不足在哪里 |
| --- | --- | --- |
| commit message | 解释一次代码提交 | 不稳定回答“当前 intent 是什么”“试过哪些候选”“最终采纳了什么” |
| issue / PR | 承载讨论和上下文 | 信息容易分散，对 agent 缺少稳定对象边界和固定读取入口 |
| ADR / docs | 沉淀长期决策 | 对高频 `start -> snap -> adopt` 过重，不适合作为每次候选采纳的默认路径 |
| Intent | 记录语义对象与采纳历史 | 重点在本地 CLI 闭环和结构化读取入口 |

## 核心闭环

Intent 先把最重要的 3 个动作做成正式对象：

- `start`：开始处理一个问题
- `snap`：保存一个候选结果
- `adopt`：正式采纳一个候选结果

也就是这条最小路径：

`问题 -> 候选 -> 采纳`

这条路径同时面向人和 agent。

## 为什么它对 agent 重要

对 agent 来说，Intent 提供的是结构化上下文，而不是只依赖 prose：

- 稳定的对象边界
- 明确的当前状态
- 可预测的下一步动作
- 结构化、可消费的输出

Intent 将意图、候选和采纳作为正式对象暴露出来。

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

这条路径表达三件事：

- Git 还在正常管理代码
- Intent 额外记录了这次工作的语义历史
- `itt log` 比 commit history 更接近“这次到底采纳了什么决策”

## 本地体验

```bash
git clone https://github.com/dozybot001/Intent.git
cd Intent
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
itt --help
```

如果你只是想直接跑仓库里的版本，也可以用 `./itt --help`。

## 验证方式

```bash
./scripts/check.sh
```

如果你想分步骤执行，也可以用：

```bash
python3 -m unittest discover -s tests -v
./scripts/smoke.sh
./scripts/demo_log.sh
./scripts/demo_agent.sh
```

## 首页先记住这 6 个命令

```bash
itt init
itt start
itt status
itt snap
itt adopt
itt log
```

如果你是开发者或 agent 集成方，可以先看这两个入口：

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

Intent 的接口分成两层：

- 对用户：`start -> snap -> adopt`
- 对开发者：本地对象层与 CLI contract
- 对 agent：固定对象、固定状态和固定 JSON 入口

## 当前阶段

项目还在早期阶段，当前重点不是铺开大而全的能力，而是先把本地最小闭环做稳。

当前优先级是：

- `.intent/` 本地对象层
- `init -> start -> snap -> adopt -> log`
- 基础 read-side 命令，以及 `run` / `decision`
- `status --json` / `inspect --json` 这类 agent-friendly contract
- 让同一套语义既适合人使用，也适合 agent 使用

## 文档

README 只保留总览，更完整的说明在 `docs/`：

- [变更记录](CHANGELOG.CN.md)
- [文档索引](docs/CN/README.md)
- [术语表](docs/CN/glossary.md)
- [愿景与问题定义](docs/CN/vision.md)
- [CLI 统一设计文档](docs/CN/cli.md)
- [Demo](docs/CN/demo.md)
- [发布基线](docs/CN/release.md)
- [路线图](docs/CN/roadmap.md)
- [文档国际化规范](docs/CN/i18n.md)

更多背景见：[愿景与问题定义](docs/CN/vision.md)。
