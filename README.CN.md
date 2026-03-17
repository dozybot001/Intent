[English](https://github.com/dozybot001/Intent/blob/main/README.md) | 简体中文

# Intent

> Git 记录代码变化，Intent 记录为什么。

## 问题

Agent 驱动的开发中，代码生成很快，但推理过程在 session 之间消失。每个新 session 从零开始——agent 不知道在解决什么问题、试过什么方案、为什么选了这条路。

## 缺失的环节

Git 记录了*什么*变了。Commit message 和代码注释提供了一些上下文。但三类信息总是丢失：

**目标连续性。** Commit 是孤立的快照。没有结构把五个 commit 关联到同一个任务，或者说明"我们在试图解决什么"。

**决策理由。** 为什么选 JWT 而不是 cookie？为什么过期时间是 15 分钟？这些很少出现在 commit message 里——即使有，也是非结构化文本，agent 需要猜测和推断。

**工作状态。** `git status` 可以是 clean 的，但任务只完成了一半。下一个 session 没有任何信号表明工作被中断、接下来该做什么。

## 方案

Intent 在仓库中添加 `.intent/` 目录——结构化、机器可读的元数据，在代码历史旁记录语义历史。

```
.git/    ← 代码怎么变的
.intent/ ← 在做什么、为什么
```

两种对象：**intent**（目标）和 **snap**（步骤及理由）。全部 JSON。任何 agent 平台都可以读取。

### 有什么不同

**没有 `.intent/`** — 新 session 开始。Agent 读 `git log` 和源码，了解代码*现在*是什么样，但不知道 JWT 迁移是因为合规要求（可能改回 cookie），不知道 refresh token 是故意没写完的，看不出还有未完成的工作。它问：*"你想让我做什么？"*

**有 `.intent/`** — 新 session 开始。Agent 运行 `itt inspect`，看到 active intent（"将认证迁移到 JWT"）、最后一个 snap（"添加 refresh token——未完成"）、以及理由（"token rotation 未做，安全优先级"）。它说：*"我来实现 token rotation。"*

差别：10 秒读结构化元数据，vs 几分钟重新解释上下文。

## 核心闭环

```
start → snap → done
```

- `start` — 打开一个 intent（在解决什么问题）
- `snap` — 记录一个 snap（做了什么、为什么）
- `done` — 完成后关闭

## 示例

```bash
itt init
itt start "修复登录超时"
itt snap "将超时增加到 30s" -m "5s 对慢网络太短"
git add . && git commit -m "fix timeout"
itt done
```

## 发展方向

`.intent/` 是一个协议，不只是工具。

1. **Agent 记忆** — agent 启动时读取 `.intent/`，秒级恢复上次 session 的上下文
2. **上下文交换** — `.intent/` 成为 agent 平台之间传递工作上下文的标准方式
3. **网络效应** — 当足够多的仓库包含 `.intent/`，新工具涌现：intent 感知的代码审查、决策考古、语义仪表盘

## 安装

```bash
pip install git-intent
```

或从源码安装：

```bash
git clone https://github.com/dozybot001/Intent.git && cd Intent
pip install -e .
```

## 命令

| 命令 | 用途 |
| --- | --- |
| `itt init` | 在 Git 仓库中初始化 `.intent/` |
| `itt start <title>` | 打开一个 intent |
| `itt snap <title> [-m why]` | 记录一个 snap |
| `itt done` | 关闭当前 intent |
| `itt inspect` | 机器可读的 workspace 快照 |
| `itt list <intent\|snap>` | 列出对象 |
| `itt show <id>` | 查看单个对象 |
| `itt suspend` | 暂停当前 intent |
| `itt resume [id]` | 恢复一个暂停的 intent |
| `itt adopt [id]` | 采纳一个候选 snap |
| `itt revert` | 回退最近的 snap |

## 文档

- [CLI 设计](https://github.com/dozybot001/Intent/blob/main/docs/cli.CN.md) — 对象、命令、JSON 输出契约
- [Agent 集成](https://github.com/dozybot001/Intent/blob/main/docs/agent-integration.md) — Claude Code、Cursor、AGENTS.md 接入片段
- [吃自己的狗粮](https://github.com/dozybot001/Intent/blob/main/docs/dogfooding.CN.md) — 用 Intent 开发 Intent 的真实记录
