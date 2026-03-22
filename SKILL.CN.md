---
name: intent-cli
description: 用结构化语义历史（.intent/）追踪你在做什么、为什么做——目标、决策和工作状态，跨 agent session 持久化。
---

# Intent — 语义历史

本仓库使用 Intent（`.intent/`）追踪你在做什么、为什么做。
安装：`git clone https://github.com/dozybot001/Intent.git && cd Intent && pip install .`

`itt` 命令的输出均为 JSON——解析它，不要猜测。`argparse` 的帮助文本不是 JSON。

## 对象

| 对象 | 定义 | 状态 |
|------|------|------|
| **Intent** | 从用户查询中识别出的可恢复目标。`query` = 用户原话，`why` = 上下文（有则填，无则 `""`）。 | `active` → `suspend` ↔ `active` → `done`（终态） |
| **Snap** | intent 下的语义快照：`what` / `why` / `next` / `query`。将 session 结束后会丢失的推理过程外化保存。 | 不可变；通过新建 snap 修正 |
| **Decision** | 超越单个 intent 的长期约束。**判断标准：**未来一个不相关的 intent 仍需遵守它？是 → decision。否 → 写进 snap。 | `active` → `deprecated`（终态） |

- 关系是**双向的**、**只增不删的**：创建 intent 自动挂载所有 active decision；创建 decision 自动挂载所有 active intent。双方同步更新。
- 对象创建后**不可变**。发现错误时通过新建 snap 修正。

## 工作流

### 1. Session 开始

**每个 session 必须以 `itt inspect` 开始。** 没有例外。

1. 从每个 active intent 的 `latest_snap` 继续工作。不要让用户重复解释。
2. 遵守 `active_decisions`——它们是现行约束。
3. 检查 `suspended`——相关则提及或重新激活。
4. 如有 `warnings`，运行 `itt doctor`。
5. 全部为空 → 全新工作区。

### 2. 识别 intent

**这是你的职责，不是用户的。**

| 情况 | 动作 |
|------|------|
| 简单事实性问题，无后续工作 | 直接回答，不创建对象 |
| 属于已有 active intent | 在该 intent 下创建 snap |
| 与 suspended intent 相关 | 激活它，然后创建 snap |
| 新目标，不在任何 active intent 范围内 | 创建 intent，然后创建 snap |

创建前做**恢复测试**：下一个 agent session 需要这个目标边界来恢复工作吗？不需要 → 跳过。

如果你即将开始有意义的工作，但没有 active intent 能解释这个目标，先创建 intent。

### 3. 创建 snap

| 类别 | 时机 | 动作 |
|------|------|------|
| 不需要 snap | 简单问答——没有需要持久化的推理 | 跳过 |
| 有代码变更的 snap | 代码已修改；Git 记录了 diff，snap 记录 why | `itt snap create` |
| 无代码变更的 snap | 调查得出结论、方向已确定、非代码工作产出了可执行结论 | `itt snap create` |

Snap 字段：
- `WHAT`：简洁的行动描述，便于扫读
- `--query`：触发此 snap 的用户查询
- `--why`：选择这个方案的原因（选填；有需要保存的推理时填写）
- `--next`：剩余工作、方向、阻塞项（可选）
- `--intent`：仅在多个 intent 同时 active 时需要（单个时 CLI 自动推断；有歧义时返回 `MULTIPLE_ACTIVE_INTENTS` 及候选列表）

### 4. 记录 decision

**未经用户确认，绝不创建 decision。**

| 路径 | 触发条件 | 动作 |
|------|---------|------|
| 显式 | 用户说 `decision-[文本]` 或 `决定-[文本]` | 直接创建 |
| 发现 | 你发现了一个长期约束 | 问用户："要不要把这个记录为 decision？" → 确认后才创建 |

如果用户的新请求与 active decision 冲突，明确指出并询问是否废弃。废弃 decision 但没有替代会留下空白——询问新方向是否也应记录为 decision。

### 5. 上下文切换

```bash
itt intent suspend intent-001            # 暂停当前工作
itt intent create "紧急修复" --query "..."  # 处理插入任务
# ... 工作 ...
itt intent done intent-002               # 完成修复
itt intent activate intent-001           # 恢复；active decision 自动同步
```

### 6. 目标完成

`itt intent done` —— 用户确认目标已解决，或最后一个 snap 的 `next` 为空时使用。终态；同一问题再次出现时创建新 intent。

## 关键规则

- **识别 intent 是你的职责** —— 用户不会说"创建一个 intent"；你从他们的查询中识别目标
- **Decision 必须用户确认** —— 绝不凭自己判断单独创建
- **完成的 intent 必须 `done`** —— 残留的 stale intent 会污染 inspect 并自动挂载到无关 decision
- **Snap 记录推理，不记录操作** —— 记 why 和 next，不记 diff 和命令日志
- **一个 intent 对应一个目标，不是一个步骤** —— "迁移认证到 JWT"，而不是"添加 JWT token 生成"
- **简单问答不需要 intent** —— 琐碎问题、工作流熟悉、元讨论不需要追踪

## 命令参考

### 全局

| 命令 | 功能 |
|------|------|
| `itt init` | 在当前 git 仓库创建 `.intent/` |
| `itt inspect` | 恢复优先的视图 —— **每个 session 从这里开始** |
| `itt doctor` | 验证对象图的结构和链接 |
| `itt version` | 打印版本 |

### Intent

| 命令 | 功能 |
|------|------|
| `itt intent create WHAT --query Q [--why W] [--origin LABEL]` | 新建 intent（自动挂载 active decision；`origin` 从环境自动填充） |
| `itt intent activate [ID]` | `suspend` → `active`（同步 active decision；唯一 suspended 时自动推断） |
| `itt intent suspend [ID]` | `active` → `suspend`（唯一 active 时自动推断） |
| `itt intent done [ID]` | `active` → `done`（终态；唯一 active 时自动推断） |

### Snap

| 命令 | 功能 |
|------|------|
| `itt snap create WHAT [--query Q] [--why W] [--next N] [--origin LABEL]` | 语义快照。自动挂载到 active intent；多个时用 `--intent ID` 指定。 |

### Decision

| 命令 | 功能 |
|------|------|
| `itt decision create WHAT [--query Q] --why W [--origin LABEL]` | 新建 decision（自动挂载 active intent；`origin` 从环境自动填充） |
| `itt decision deprecate ID [--reason TEXT]` | `active` → `deprecated`（终态）；`--reason` 记录原因 |

### Hub

| 命令 | 功能 |
|------|------|
| `itt hub start [--port PORT] [--no-open]` | 从 Intent 仓库目录启动 IntHub Local |
| `itt hub link [--project-name NAME] [--api-base-url URL] [--token TOKEN]` | 将当前工作区链接到 IntHub 项目 |
| `itt hub sync [--api-base-url URL] [--token TOKEN] [--dry-run]` | 将本地语义历史 + Git 上下文推送到 IntHub |

Hub **不替代**本地命令。先在本地记录，再同步。

## JSON 输出合约

**成功：**
```json
{"ok": true, "action": "snap.create", "result": {...}, "warnings": []}
```

`action` 取值：`intent.create`、`intent.activate`、`intent.suspend`、`intent.done`、`snap.create`、`decision.create`、`decision.deprecate`、`version`、`init`、`doctor`、`hub.start`、`hub.link`、`hub.sync`。

**`inspect`** 格式不同：顶层 `ok`、`active_intents`、`active_decisions`、`suspended`、`warnings`（无 `action`/`result` 包装）。

**错误：**
```json
{"ok": false, "error": {"code": "ERROR_CODE", "message": "...", "suggested_fix": "itt ..."}}
```

有 `suggested_fix` 时，照做。

错误码：`NOT_INITIALIZED`、`ALREADY_EXISTS`、`GIT_STATE_INVALID`、`STATE_CONFLICT`、`OBJECT_NOT_FOUND`、`INVALID_INPUT`、`NO_ACTIVE_INTENT`、`MULTIPLE_ACTIVE_INTENTS`、`NO_SUSPENDED_INTENT`、`MULTIPLE_SUSPENDED_INTENTS`、`HUB_NOT_CONFIGURED`、`NOT_LINKED`、`PROVIDER_UNSUPPORTED`、`NETWORK_ERROR`、`SERVER_ERROR`。

**`doctor`：**`result.healthy`（bool）+ `result.issues[]`，issue 码：`MISSING_REFERENCE`、`BROKEN_LINK`、`INVALID_STATUS`、`OBJECT_TYPE_MISMATCH`。

## 存储

```
.intent/
  hub.json                 # IntHub 访问配置 + 工作区绑定
  intents/intent-001.json
  snaps/snap-001.json
  decisions/decision-001.json
```

ID 为零填充 3 位，按类型自增。
