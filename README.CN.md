[English](README.md) | 简体中文

# Intent

> Git 记录代码变化，Intent 记录为什么。

## 问题

在 agent 驱动的开发中，代码生成得很快，但背后的推理过程在 session 之间消失了。Git 能告诉你代码*怎么*变了——但不能告诉你当时在解决什么问题、试过什么方案、为什么选了这条路。

在人类时代，这些上下文靠记忆和对话维持。在 agent 时代，每个新 session 都从零开始。没有持久的"为什么"。

## 方案

Intent 在你的仓库中添加一个 `.intent/` 目录——结构化的元数据，在代码历史旁边记录语义历史。

```
.git/    ← 代码怎么变的
.intent/ ← 做了什么以及为什么
```

任何 agent 平台都可以读取 `.intent/`。它是一个协议，不只是一个工具。

## 核心闭环

```
start → snap → done
```

- `start` — 开始处理一个问题
- `snap` — 记录一个步骤和理由
- `done` — 完成后关闭

两种对象：**intent**（目标）和 **checkpoint**（步骤）。所有输出都是 JSON。

## 示例

```bash
itt init
itt start "修复登录超时"
itt snap "将超时增加到 30s" -m "5s 对慢网络太短"
git add . && git commit -m "fix timeout"
itt done
```

## 发展方向

1. **Agent 记忆层** — agent 启动时读取 `.intent/`，立刻知道上次发生了什么
2. **语义交换协议** — `.intent/` 成为 agent 平台之间传递上下文的标准方式
3. **网络效应** — 当足够多的仓库包含 `.intent/`，新工具涌现：intent 感知的代码审查、决策考古、语义仪表盘

## 安装

```bash
curl -fsSL https://raw.githubusercontent.com/dozybot001/Intent/main/setup/install.sh | bash
```

贡献者：

```bash
git clone https://github.com/dozybot001/Intent.git && cd Intent
python3 -m venv .venv && . .venv/bin/activate && pip install -e .
```

## 命令

| 命令 | 用途 |
| --- | --- |
| `itt init` | 在 Git 仓库中初始化 `.intent/` |
| `itt start <title>` | 打开一个 intent |
| `itt snap <title> [-m why]` | 记录一个 checkpoint |
| `itt done` | 关闭当前 intent |
| `itt inspect` | 机器可读的 workspace 快照 |
| `itt list <intent\|checkpoint>` | 列出对象 |
| `itt show <id>` | 查看单个对象 |
| `itt adopt [id]` | 采纳一个候选 checkpoint |
| `itt revert` | 回退最近的 checkpoint |

## 文档

- [CLI 设计](docs/CN/cli.md) — 对象、命令、JSON 输出契约
