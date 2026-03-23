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
| **Intent** | 一个可恢复的目标。`query` = 用户原话，`why` = 上下文（有则填，无则 `""`）。 | `active` → `suspend` ↔ `active` → `done`（终态） |
| **Snap** | intent 下的语义快照：`what` / `why` / `next` / `query`。 | 不可变；通过新建 snap 修正 |
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

### 2. 自由工作

专注于用户的请求。**不要**在工作过程中主动创建 intent 或 snap——不需要每个 query 都判断"要不要记录"。语义记录在用户要求时进行。

### 3. 被要求时记录

当用户让你记录（如"记录一下"、"let's record what we did"、或明确表示目标已达成），回顾工作并创建：

1. **一个 intent** — 概括这次交互的目标
2. **若干 snap** — 每个里程碑或有意义的工作块一个，记录 what/why/next
3. **`itt intent done`** — 如果目标已完全解决

```bash
itt intent create "实现了认证重试逻辑" \
  --query "修复登录超时问题" \
  --why "慢网络用户会被踢出登录"
itt snap create "API 客户端增加指数退避重试" \
  --why "上游间歇性 503 导致级联失败" \
  --next "监控面板需要增加重试指标"
itt snap create "更新登录流程的错误处理" \
  --why "旧处理器静默吞掉了重试错误"
itt intent done
```

Snap 字段：
- `WHAT`：简洁的行动描述，便于扫读
- `--query`：触发此工作的用户查询（选填）
- `--why`：选择这个方案的原因（选填；有需要保存的推理时填写）
- `--next`：剩余工作、方向、阻塞项（选填）
- `--intent`：仅在多个 intent 同时 active 时需要（单个时 CLI 自动推断）

### 4. 记录 decision

**未经用户确认，绝不创建 decision。**

| 路径 | 触发条件 | 动作 |
|------|---------|------|
| 显式 | 用户说 `decision-[文本]` 或 `决定-[文本]` | 直接创建 |
| 发现 | 你发现了一个长期约束 | 问用户："要不要把这个记录为 decision？" → 确认后才创建 |

如果用户的新请求与 active decision 冲突，明确指出并询问是否废弃。

### 5. 上下文切换

```bash
itt intent suspend intent-001            # 暂停当前工作
itt intent create "紧急修复" --query "..."  # 处理插入任务
# ... 工作 ...
itt intent done intent-002               # 完成修复
itt intent activate intent-001           # 恢复；active decision 自动同步
```

### 6. 目标完成

`itt intent done` —— 终态。同一问题再次出现时创建新 intent。

### 备选：Snap–Query 模式

对于跨多个 session 的长期目标，可以改为实时记录：识别到目标时创建 intent，每个有意义的 query 后创建 snap。更自动但噪声更多。默认推荐上面的 Intent–Session 模式。

## 关键规则

- **不要主动记录** —— 等用户要求；语义记录由用户发起，和 git commit 一样
- **Decision 必须用户确认** —— 绝不凭自己判断单独创建
- **完成的 intent 必须 `done`** —— 残留的 stale intent 会污染 inspect 并自动挂载到无关 decision
- **Snap 记录推理，不记录操作** —— 记 why 和 next，不记 diff 和命令日志
- **一个 intent 对应一个目标，不是一个步骤** —— "迁移认证到 JWT"，而不是"添加 JWT token 生成"
- **Decision 清理** —— 当 active decision 超过 20 条时，提醒用户："当前有 N 条 active decision，要做一轮清理吗？" 确认后审查所有 active decision，提议合并同主题的，用户确认后废弃原条目

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
| `itt decision create WHAT [--query Q] [--why W] [--origin LABEL]` | 新建 decision（自动挂载 active intent；`origin` 从环境自动填充） |
| `itt decision deprecate ID [--reason TEXT]` | `active` → `deprecated`（终态）；`--reason` 记录原因 |

### Hub

| 命令 | 功能 |
|------|------|
| `itt hub start [--port PORT] [--no-open]` | 启动 IntHub Local（任意目录可用） |
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
