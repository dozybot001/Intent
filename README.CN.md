[English](README.md) | 简体中文

# Intent

> Git 记录代码变化，Intent 记录你做了什么以及为什么。

Intent 是一个构建在 Git 之上的语义历史层，面向 agent 驱动的软件开发。它记录：

- 当前在解决什么问题
- 做了哪些步骤
- 关键选择背后的理由是什么

它不替代 Git，它补的是 Git 天然没有被设计去承载的那层历史。

## 30 秒理解

在 agent 驱动的开发里，代码可以生成得很快，但背后的推理过程往往散落在对话、issue 和草稿中。

Git 擅长回答"代码怎么变了"，但不擅长回答"当时的目标是什么，为什么选了这条路"。

Intent 把这些高层语义提升为第一类对象，让 agent 能稳定读取和操作。

## 核心闭环

```
start → snap → done
```

- `start`：开始处理一个问题
- `snap`：记录一个步骤，可附带理由
- `done`：工作完成，关闭 intent

## 对象模型

Intent 有两种对象类型：

| 对象 | 状态 | 用途 |
| --- | --- | --- |
| Intent | `open` → `done` | 当前在处理的问题或目标 |
| Checkpoint | `adopted`、`candidate`、`reverted` | 一次记录的步骤——语义历史的基本单元 |

默认情况下，`snap` 创建的 checkpoint 状态为 adopted。需要真正比较方案时，使用 `--candidate`。

## 最小示例

```bash
itt init
itt start "Reduce onboarding confusion"
itt snap "Simplify landing page" -m "Progressive disclosure approach"
git add . && git commit -m "refine onboarding layout"
itt done
```

所有命令输出 JSON。Intent 为 agent 消费而设计。

## 为什么不直接用 issue / ADR / commit message

| 方式 | 擅长什么 | 不足在哪里 |
| --- | --- | --- |
| commit message | 解释一次代码提交 | 不能回答"当前目标是什么""经历了哪些步骤" |
| issue / PR | 承载讨论和上下文 | 信息容易分散，对 agent 缺少稳定对象边界 |
| ADR / docs | 沉淀长期决策 | 对高频步骤记录过重 |
| Intent | 记录语义步骤与理由 | 当前重点在本地 CLI 闭环 |

## 安装

给贡献者：

```bash
git clone https://github.com/dozybot001/Intent.git
cd Intent
python3 -m venv .venv && . .venv/bin/activate
pip install -e .
```

给普通用户：

```bash
curl -fsSL https://raw.githubusercontent.com/dozybot001/Intent/main/setup/install.sh | bash
```

这条 bootstrap 命令会在 `~/.intent/repo` 保留一份 checkout，把 `itt` 暴露到 `~/.intent/bin/itt`，并对检测到的 agent 运行 `itt setup`。

## 命令

| 命令 | 用途 |
| --- | --- |
| `itt init` | 在 Git 仓库中初始化 Intent |
| `itt start <title>` | 创建并激活一个 intent |
| `itt snap <title> [-m rationale]` | 记录一个 checkpoint（默认 adopted） |
| `itt snap <title> --candidate` | 记录为候选，用于比较 |
| `itt adopt [checkpoint_id]` | 采纳一个候选 checkpoint |
| `itt revert` | 回退最近一个已采纳的 checkpoint |
| `itt done [intent_id]` | 关闭当前 active intent |
| `itt inspect` | 机器可读的 workspace 快照（JSON） |
| `itt list <intent\|checkpoint>` | 列出对象 |
| `itt show <id>` | 按 ID 查看单个对象 |
| `itt setup [agent]` | 安装 agent 集成 |
| `itt doctor` | 验证 agent 配置状态 |

## Agent 协议

Intent 主要面向 agent。一个 agent 应该：

- 在开始实质工作前运行 `itt inspect` 了解当前状态
- 开始有意义的工作时启动一个 intent
- 用 `itt snap` 记录步骤和理由
- 工作完成时运行 `itt done`
- 对于琐碎的问题或微小编辑，跳过记录

## 验证

```bash
./scripts/check.sh
```

或者分步骤执行：

```bash
python3 -m unittest discover -s tests -v
./scripts/smoke.sh
./scripts/demo_agent.sh
```

## Intent 不是什么

- 不是 Git 的替代品
- 不是 issue、PR 或 docs 系统的替代品
- 不是"什么都记录"的日志归档工具

Intent 只记录值得追踪的语义步骤及其理由。

## 仓库结构

```text
Intent/
|-- README.md
|-- README.CN.md
|-- skills/
|   `-- intent-cli/
|-- setup/
|-- src/
|   `-- intent_cli/
|-- docs/
|-- scripts/
|-- tests/
`-- .intent/
```

## 文档

- [变更记录](CHANGELOG.CN.md)
- [文档索引](docs/CN/README.md)
- [术语表](docs/CN/glossary.md)
- [愿景与问题定义](docs/CN/vision.md)
- [CLI 设计文档](docs/CN/cli.md)
- [分发与集成设计](docs/CN/distribution.md)
- [首个 Agent 试用反馈实录](docs/CN/feedback.md)
- [Demo](docs/CN/demo.md)
- [发布基线](docs/CN/release.md)
- [发展战略](docs/CN/strategy.md)
- [路线图](docs/CN/roadmap.md)
- [文档国际化规范](docs/CN/i18n.md)
