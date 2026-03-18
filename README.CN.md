[English](https://github.com/dozybot001/Intent/blob/main/README.md) | 简体中文

# Intent

> Git 记录代码变化，Intent 记录采纳历史。

## 问题

软件开发的重心正在从"写"转向"选"。Agent 生成候选方案，人来 review、比较、采纳。但工具没有跟上——Git 记录代码怎么变的，却不记录在解决什么问题、有过哪些备选、为什么选了这条路。

每个新 agent session 从零开始。推理过程、被否决的候选、做到一半的工作——全部消失。

## 缺失的环节

高层语义信息并不稀缺——它散落在 commit message、PR、文档、聊天和 agent 对话中。问题在于它们都不是**第一类对象**：可以阅读但难以稳定追踪，可以讨论但无法比较，可以回忆但 agent 无法可靠查询。

三类信息总是丢失：

**目标连续性。** Commit 是孤立的快照。没有结构把五个 commit 关联到同一个任务，或者说明"我们在试图解决什么"。

**决策理由。** 为什么选 JWT 而不是 cookie？为什么过期时间是 15 分钟？这些决策存在于某个 Slack 消息、某条 PR 评论中——但它们不是 agent 能定位和推理的对象。

**工作状态。** `git status` 可以是 clean 的，但任务只完成了一半。下一个 session 没有任何信号表明工作被中断、接下来该做什么。

## 方案

Intent 在仓库中添加 `.intent/` 目录——把目标、决策和采纳记录提升为第一类、机器可读的对象，与代码历史并存。

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
pipx install intent-cli-python
itt init
itt start "修复登录超时"
itt snap "将超时增加到 30s" -m "5s 对慢网络太短"
git add . && git commit -m "fix timeout"
itt done
```

## 为什么不直接用……

| 方案 | 擅长什么 | 缺什么 |
| --- | --- | --- |
| **Git commit message** | 记录每个 commit 改了什么 | 无法跨 commit 关联目标；rationale 是事后补的；没有进行中状态 |
| **CLAUDE.md / .cursorrules** | 给 agent 项目级指令 | 静态的——不跟踪活跃任务、决策或进度；需要手动维护 |
| **TODO 注释** | 在代码中标记未完成的工作 | 散落在各文件；没有生命周期；没有理由；agent 必须 grep 然后猜优先级 |
| **Notion / Linear / Jira** | 面向人类的丰富项目跟踪 | 在仓库之外；agent 需要 API 集成才能读取；对于独立/agent 工作流来说过重 |
| **Agent 记忆**（如 Claude Code memory） | 跨 session 保存用户偏好 | 绑定单一平台；不随代码版本化；无法在不同 agent 或队友之间共享 |
| **临时上下文文件**（如 `context.md`） | 快速、零工具上手 | 没有 schema——每个项目自己发明格式；没有生命周期管理；悄悄过期 |

**Intent 填补的是一个具体的缝隙**：结构化、版本化、任务粒度的上下文，*住在仓库里*，跨任何 agent 平台工作。

- **结构化** — JSON 对象，定义了 schema，不是 agent 需要猜的自由文本
- **任务粒度** — intent 有生命周期（`open → done`）；snap 是有序步骤，不是一堆笔记
- **版本化** — `.intent/` 和代码一起 commit；`git blame` 也能用在你的决策上
- **平台无关** — 任何能读 JSON 的 agent 都能用；没有供应商锁定
- **极简** — 两种对象（intent、snap），一个 CLI，零依赖；给工作流加几秒，不是几分钟

最接近的替代方案是手写一个 `context.md`。Intent 用一致性换灵活性：一个 agent 可以直接依赖的 schema，不需要每个项目单独写 prompt 来解析。

## 发展方向

Intent 是一个协议，不只是工具。长期结构分三层：

| 层 | 角色 | 状态 |
| --- | --- | --- |
| **Intent CLI** | 本地 semantic history——对象、生命周期、查询 | 当前重点 |
| **Skill / Agent workflow** | 教会 agent 何时、如何维护 `.intent/` | 正在 dogfooding |
| **IntHub** | 远端协作、共享时间线、仪表盘 | 更后续 |

核心判断：先做好本地语义层，再扩展远端协作。如果 `.intent/` 成为 agent 工作流的自然组成部分，新工具会自然涌现——intent 感知的代码审查、决策考古、跨 session 连续性。

## 安装

**用户：**

```bash
pipx install intent-cli-python
```

**配置你的 agent：** 安装 Intent skill，让 agent 了解工作流：

```bash
npx skills add dozybot001/Intent
```

**贡献者：**

```bash
git clone https://github.com/dozybot001/Intent.git
cd Intent
python3 ./itt   # 开发入口，无需安装
```

## 命令

| 命令 | 用途 |
| --- | --- |
| `itt init` | 初始化 `.intent/` |
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
- [吃自己的狗粮](https://github.com/dozybot001/Intent/blob/main/docs/dogfooding.CN.md) — 用 Intent 开发 Intent 的真实记录
