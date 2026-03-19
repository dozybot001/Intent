# Intent CLI

中文 | [English](README.md)

为 agent 驱动的开发提供语义历史。记录**你做了什么**以及**为什么**。

Intent CLI 让 AI agent 能够跨会话地追踪目标、交互和决策。当对话结束时，agent 将理解持久化为三个简单对象，存储在代码仓库中。

## 为什么

Git 记录代码怎么变的。但它不记录**你为什么走这条路**、途中做了什么决策、上次停在哪里。

今天这些上下文散落在聊天记录、PR 讨论和你的脑子里。勉强能用——直到会话结束、agent 失忆、或者队友接手时一头雾水。

Intent 把这些视为缺失的一层：**语义历史**。不是更多文档，不是更好的 commit message，而是一组正式的对象来捕获目标、交互和决策，让它们不会随上下文一起消失。

> 变化很简单：开发正在从"写代码"转向"引导 agent、沉淀决策"。历史层应该反映这一点。

## 三个对象，一张图

| 对象 | 记录什么 |
|---|---|
| **Intent** | agent 从用户 query 中识别出的目标 |
| **Snap** | 一次 agent 交互 — query、摘要、反馈 |
| **Decision** | 跨多个 intent 持续生效的长期决策 |

对象自动关联：创建 intent 时挂载所有 active decision；创建 decision 时挂载所有 active intent。关系始终双向且只增不减。

### Decision 如何创建

Decision 需要人类参与，有两条路径：

- **显式指定**：在 query 中写 `decision-[内容]` 或 `决定-[内容]`，agent 直接创建。例如："决定-所有 API 返回 envelope 格式"
- **Agent 提议**：agent 在对话中发现潜在的长期约束，向你确认后再创建

## 安装

```bash
# 克隆仓库
git clone https://github.com/dozybot001/Intent.git

# 安装 CLI（推荐 pipx）
pipx install intent-cli-python

# 或使用 pip
pip install intent-cli-python
```

需要 Python 3.9+ 和 Git。

### IntHub 分发边界

`pipx install intent-cli-python` 只安装 CLI。

当前仓库是 `Intent` 和 `IntHub` 的总项目仓库，但分发边界比仓库边界更窄：

- PyPI 只分发 `itt` CLI
- IntHub Web 是独立的静态前端，适合通过 GitHub Pages 托管
- IntHub API 是独立服务，不属于 PyPI 包的一部分

如果你是在这个源码仓库里直接运行 IntHub，当前本地入口是：

```bash
python -m apps.inthub_api --db-path .inthub/inthub.db
python -m apps.inthub_web --api-base-url http://127.0.0.1:8000
```

之后在本地 Intent workspace 中执行 `itt hub login`、`itt hub link`、`itt hub sync`，就能把数据推到只读 IntHub 项目视图里。

### 版本与发布

`Intent` 现在是 umbrella project / monorepo，不再维护一个统一的项目版本号。

发布版本只属于具体 deliverable：

- CLI 的版本以 `pyproject.toml` 中的 PyPI 包版本为准，Git tag 使用 `cli-v2.0.0` 这种形式
- IntHub 未来单独发布时，使用自己的版本轨道和 `hub-v0.1.0` 这种 tag

历史上的裸 tag，例如 `v1.3.0`，作为既有历史保留；新的发布一律使用带 deliverable 前缀的 tag。

### 通过 skills.sh 安装 skill

```bash
npx skills add dozybot001/Intent -g
```

这会把 `intent-cli` 安装到你的全局 skill 库中，可供 Codex、Claude Code 等支持的 agent 使用。

> **提示：** `itt` 是一个全新的工具，当前模型的训练数据中从未出现过它。对话过程中 agent 可能会忘记调用。遇到这种情况，简单提醒一句"用 itt 记录一下"就够了。
>
> 这并不是徒增负担——每一条记录都是**语义资产**。后续平台 **IntHub** 将把这些资产转化为可检索、可共享的项目知识。

## 快速上手

```bash
# 在任意 git 仓库中初始化
itt init

# Agent 从用户 query 中识别出新意图
itt intent create "修复登录超时问题" \
  --query "为什么登录 5 秒就超时了？"

# 记录 agent 做了什么
itt snap create "将超时提升到 30s" \
  --intent intent-001 \
  --query "慢网络下登录仍然超时" \
  --summary "更新了超时配置并运行了登录测试"

# 沉淀一条长期决策
itt decision create "超时时间必须可配置" \
  --rationale "不同部署环境的延迟各不相同"

# 查看完整的对象图
itt inspect
```

## 命令

### 全局

| 命令 | 说明 |
|---|---|
| `itt version` | 打印版本 |
| `itt init` | 在当前 git 仓库初始化 `.intent/` |
| `itt inspect` | 显示实时对象图快照 |
| `itt doctor` | 校验对象图中的断链引用和非法状态 |

### Intent

| 命令 | 说明 |
|---|---|
| `itt intent create TITLE --query Q` | 创建新 intent |
| `itt intent list [--status S] [--decision ID]` | 列出 intent |
| `itt intent show ID` | 查看 intent 详情 |
| `itt intent activate ID` | 恢复挂起的 intent |
| `itt intent suspend ID` | 挂起 active intent |
| `itt intent done ID` | 标记 intent 为完成 |

### Snap

| 命令 | 说明 |
|---|---|
| `itt snap create TITLE --intent ID` | 记录一次交互快照 |
| `itt snap list [--intent ID] [--status S]` | 列出 snap |
| `itt snap show ID` | 查看 snap 详情 |
| `itt snap feedback ID TEXT` | 设置或覆盖反馈 |
| `itt snap revert ID` | 标记 snap 为已回退 |

### Decision

| 命令 | 说明 |
|---|---|
| `itt decision create TITLE --rationale R` | 创建长期决策 |
| `itt decision list [--status S] [--intent ID]` | 列出 decision |
| `itt decision show ID` | 查看 decision 详情 |
| `itt decision deprecate ID` | 废弃一条 decision |
| `itt decision attach ID --intent ID` | 手动补挂 decision 与 intent 的关系 |

## 设计原则

- **Agent-first**：为 AI agent 调用而设计，而非手动输入
- **Append-only 历史**：内容字段创建后不可变；通过新 snap 修正，而非篡改旧记录
- **关系只增不减**：没有 detach — 改用 deprecate
- **全量 JSON 输出**：默认机器可读
- **零依赖**：纯 Python，仅使用标准库

## 存储结构

所有数据存储在 git 仓库根目录的 `.intent/` 中：

```
.intent/
  config.json
  intents/
    intent-001.json
  snaps/
    snap-001.json
  decisions/
    decision-001.json
```

`.intent/` 是本地语义工作区元数据，不应进入 Git 历史，且应始终由 `.gitignore` 忽略。

## 文档

- [愿景](docs/CN/vision.md) — 为什么需要语义历史。**如果你对这个项目感兴趣，强烈建议从这里开始。**
- [CLI 设计文档](docs/CN/cli.md) — 对象模型、命令、JSON 契约
- [路线图](docs/CN/roadmap.md) — 阶段规划
- [IntHub MVP 设计文档](docs/CN/inthub-mvp.md) — 首期远端协作层范围
- [IntHub 同步契约（首版）](docs/CN/inthub-sync-contract.md) — 首版同步、身份与接口契约

## 许可证

MIT
