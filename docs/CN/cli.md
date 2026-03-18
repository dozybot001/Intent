# Intent CLI 设计文档

[English](../EN/cli.md) | 中文

Schema version: **1.0**

Intent CLI 改为对象中心的 agent-first CLI。系统只建模三类对象：**intent**、**snap**、**decision**。

设计原则：

- `decision` 是最高层对象，表示沉淀下来的长期决策，可挂载多个 intent
- `intent` 是 agent 从用户 query 中识别出的意图，可挂载多个 decision 和 snap
- `snap` 是一次与 agent 交互的快照，记录 query、agent 做了什么的简单摘要，以及用户反馈
- schema version 是 workspace 级配置，只保留在 `config.json`
- 所有对象统一保留 `id`、`object`、`created_at`、`title`、`status`
- 所有对象移除 `updated_at`
- 新建 `decision` 时，自动挂载所有 `active` intent
- 新建 `intent` 时，自动挂载所有 `active` decision
- 不再假设“同一时间只能有一个 active intent”

## 1. 对象模型

### 1.1 共享字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 对象 ID，如 `intent-001` |
| `object` | string | 对象类型：`intent`、`snap`、`decision` |
| `created_at` | string | ISO 8601 UTC |
| `title` | string | 对象标题 |
| `status` | string | 对象状态，枚举因类型而异 |

### 1.2 Intent

Intent 表示用户想解决的事情。它来自 agent 对用户 query 的意图识别，而不是用户“手动开启一个任务”

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| 共享字段 | - | 见上表 |
| `source_query` | string | 触发该 intent 创建的原始用户 query |
| `rationale` | string | 为什么要追这个目标；用户 query 中有解释性语句时写入，否则留空 |
| `decision_ids` | string[] | 关联的 decision ID 列表，保留历史关系 |
| `snap_ids` | string[] | 当前挂载的 snap ID 列表 |

Intent 状态：

- `active`：当前仍然成立并持续推进
- `suspend`：暂时挂起，不参与新 decision 的自动挂载
- `done`：该意图已经完成

### 1.3 Snap

Snap 表示一次形式完整的用户-agent 交互快照。它隶属于一个 intent，用来记录这次交互输入了什么、agent 做了什么、用户怎么反馈。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| 共享字段 | - | 见上表 |
| `intent_id` | string | 所属 intent ID |
| `query` | string | 本次交互的原始用户 query |
| `rationale` | string | 为什么选择这个方案；用户 query 中有解释性语句时写入，否则留空 |
| `summary` | string | 简单摘要，说明这次 agent 干了什么；不保存详细操作日志 |
| `feedback` | string | 用户反馈；若用户切换到别的主题，则保留空字符串 `""` |

`summary` 是摘要字段，不是逐步执行日志，不要求保存完整命令、文件级操作明细或终端输出。

Snap 状态：

- `active`：这条交互记录当前有效
- `reverted`：该次执行后续被明确回退

### 1.4 Decision

Decision 表示沉淀下来的长期决策，是最高层对象，可跨多个 intent 持续生效。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| 共享字段 | - | 见上表 |
| `rationale` | string | 为什么形成这个长期决策 |
| `intent_ids` | string[] | 关联的 intent ID 列表，保留历史关系 |

Decision 状态：

- `active`：当前生效，并自动挂载到新 intent
- `deprecated`：该决策已被废弃，保留历史但不再自动挂载到新 intent

## 2. 对象关系规则

所有挂载关系都必须双向落盘。

- `decision ↔ intent` 关系变更时，必须同时更新 `decision.intent_ids` 和 `intent.decision_ids`
- `intent ↔ snap` 关系变更时，必须同时更新 `snap.intent_id` 和 `intent.snap_ids`
- 对象文件本身是唯一事实源，不额外维护独立状态索引文件
- `decision ↔ intent` 关系默认保留历史；`decision deprecated` 不回收既有关联，只停止后续自动挂载

### 2.1 Decision → Intent

- 一个 decision 可以挂载多个 intent
- 一个 intent 也可以同时挂载多个 decision
- 创建 decision 时，系统自动把所有 `active` intent 加入该 decision 的 `intent_ids`
- 创建 intent 时，系统自动把所有 `active` decision 加入该 intent 的 `decision_ids`
- 将 suspend 的 intent 重新激活为 `active` 时，应补挂当前所有 `active` decision
- 手动补挂关系时，也必须同时更新两侧对象

### 2.2 Intent → Snap

- 一个 intent 可以挂载多个 snap
- 一个 snap 只能属于一个 intent
- 创建 snap 时必须明确指定 `intent_id`
- 创建 snap 时必须同时写入 `snap.intent_id` 与对应 `intent.snap_ids`
- 只有 `active` intent 可以继续挂载新 snap

## 3. 状态模型

Intent CLI 不再维护单一的 workspace active intent 状态，而是维护对象集合。

### 3.1 公共状态名

- `active`：对象当前有效

### 3.2 类型专属状态

- intent：`suspend`、`done`
- snap：`reverted`
- decision：`deprecated`

### 3.3 合法状态转换

状态转换只允许以下路径，其余均返回 `STATE_CONFLICT`：

**Intent：**

- `active` → `suspend`（挂起）
- `active` → `done`（完成）
- `suspend` → `active`（恢复，触发补挂 active decision）

`done` 是终态，不可回退。如需重新推进同一问题，应创建新 intent。

**Snap：**

- `active` → `reverted`（回退）

`reverted` 是终态，不可回退。

**Decision：**

- `active` → `deprecated`（废弃）

`deprecated` 是终态，不可回退。如需恢复同一决策，应创建新 decision 并说明原因。

## 4. 存储结构

```text
.intent/
  config.json
  intents/
    intent-001.json
  snaps/
    snap-001.json
  decisions/
    decision-001.json
```

### 4.1 config.json

```json
{
  "schema_version": "1.0"
}
```

## 5. 命令设计

所有命令输出 JSON。CLI 改为对象子命令风格，不再使用 `start`、`resume`、`decide` 这类分散动词作为核心入口。

### 5.1 全局命令

#### version

```bash
itt version
```

#### init

在当前 Git 仓库中初始化 `.intent/` 目录。

```bash
itt init
```

#### inspect

输出当前对象图快照，而不是单个 active intent 视角。`inspect` 通过扫描对象文件实时计算当前结果。

`recent_snaps` 返回全局最近 10 条 snap（按 `created_at` 降序），不限 intent 归属和状态。

```bash
itt inspect
```

示例：

```json
{
  "ok": true,
  "schema_version": "1.0",
  "active_intents": [
    {
      "id": "intent-001",
      "title": "Fix the login timeout bug",
      "status": "active",
      "decision_ids": ["decision-001"],
      "latest_snap_id": "snap-002"
    }
  ],
  "suspend_intents": [],
  "active_decisions": [
    {
      "id": "decision-001",
      "title": "Timeout must stay configurable",
      "status": "active",
      "intent_ids": ["intent-001", "intent-003"]
    }
  ],
  "recent_snaps": [
    {
      "id": "snap-002",
      "title": "Raise timeout to 30s",
      "intent_id": "intent-001",
      "status": "active",
      "summary": "Updated timeout config and ran the login test",
      "feedback": ""
    }
  ],
  "warnings": []
}
```

### 5.2 Intent 命令

#### create

创建一个新的 intent。通常由 agent 在识别出用户 query 中的新意图后调用。

```bash
itt intent create "Fix the login timeout bug" \
  --query "why does login timeout after 5s?" \
  --rationale "users on slow networks get logged out mid-session"
```

行为：

- 新对象状态为 `active`
- 自动挂载全部 `active` decision
- 新增挂载关系必须双向落盘到 intent 与 decision

#### list

```bash
itt intent list
itt intent list --status active
itt intent list --status suspend
itt intent list --status done
```

#### show

```bash
itt intent show intent-001
```

#### activate

把一个 `suspend` intent 重新变为 `active`。

```bash
itt intent activate intent-001
```

行为：

- 将当前所有 `active` decision 补挂到该 intent
- 新增挂载关系必须双向落盘到 intent 与 decision

#### suspend

```bash
itt intent suspend intent-001
```

#### done

```bash
itt intent done intent-001
```

### 5.3 Snap 命令

#### create

在指定 intent 下记录一次交互快照。

```bash
itt snap create "Raise timeout to 30s" \
  --intent intent-001 \
  --query "login timeout still fails on slow networks" \
  --rationale "30s covers 99th-percentile latency without hurting UX" \
  --summary "updated timeout config and ran the login test" \
  --feedback "works in staging"
```

行为：

- 新对象状态默认为 `active`
- 同时写入 `snap.intent_id` 与目标 intent 的 `snap_ids`
- `--feedback` 可省略，默认为 `""`；若本轮执行后用户没有给出反馈并切换到其他主题，保持默认值

#### list

```bash
itt snap list
itt snap list --intent intent-001
itt snap list --status active
```

#### show

```bash
itt snap show snap-001
```

#### feedback

补录或覆盖用户反馈。每条 snap 只保留最新一次反馈值。

```bash
itt snap feedback snap-001 "timeout issue is fixed"
```

#### revert

把一次执行标记为 `reverted`。

```bash
itt snap revert snap-001
```

### 5.4 Decision 命令

#### create

创建一个新的长期 decision。

```bash
itt decision create "Timeout must stay configurable" \
  --rationale "Different deployments have different latency envelopes"
```

行为：

- 新对象状态为 `active`
- 自动挂载全部 `active` intent
- 新增挂载关系必须双向落盘到 decision 与 intent

#### list

```bash
itt decision list
itt decision list --status active
itt decision list --status deprecated
```

#### show

```bash
itt decision show decision-001
```

#### deprecate

```bash
itt decision deprecate decision-001
```

行为：

- 将 decision 状态改为 `deprecated`
- 保留已有 `decision.intent_ids` 与对应 `intent.decision_ids`
- `deprecated` decision 不再自动挂载到新 intent

#### attach

手动给 decision 补挂一个 intent，用于补录历史关系。

```bash
itt decision attach decision-001 --intent intent-002
```

行为：

- 必须同时更新 `decision.intent_ids` 与 `intent.decision_ids`

## 6. JSON 输出约定

### 6.1 成功

除 `inspect` 外，成功响应统一为：

```json
{
  "ok": true,
  "action": "<command-name>",
  "result": { ... },
  "warnings": []
}
```

### 6.2 错误

```json
{
  "ok": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable explanation.",
    "details": {},
    "suggested_fix": "itt ..."
  }
}
```

### 6.3 Warnings

`warnings` 是字符串数组，用于传达非阻塞性提示。可能的场景：

- 创建 intent 时没有任何 `active` decision 可挂载
- 创建 decision 时没有任何 `active` intent 可挂载
- `inspect` 发现存在孤立 snap（其 `intent_id` 指向的 intent 文件缺失）
- 对象文件中出现未识别的字段（前向兼容提示）

warnings 不影响 `ok: true`，仅供调用方参考。

## 7. Error code

| Code | 触发场景 |
| --- | --- |
| `NOT_INITIALIZED` | `.intent/` 不存在 |
| `ALREADY_EXISTS` | `.intent/` 已存在时执行 `init` |
| `GIT_STATE_INVALID` | 不在 Git worktree 中 |
| `STATE_CONFLICT` | 状态变更不合法，如对 `done` intent 再执行 `activate` |
| `OBJECT_NOT_FOUND` | ID 找不到对应对象 |
| `INVALID_INPUT` | 参数错误、缺少对象 ID、缺少 `--intent` 等 |

## 8. ID 格式

- Intent：`intent-001`、`intent-002`、...
- Snap：`snap-001`、`snap-002`、...
- Decision：`decision-001`、`decision-002`、...

ID 零填充至 3 位，按类型自动递增。新 ID = 当前该类型最大编号 + 1，已删除的编号不复用。

## 9. 设计约束

### 9.1 对象不可变

对象创建后，内容字段（title、summary、rationale、source_query 等）不提供 update 命令。

这是有意为之：语义历史应当是 append-only 的记录。如果标题或摘要写错了，正确做法是在后续 snap 中修正，而不是篡改历史。唯一允许事后变更的字段是 `snap.feedback`（通过 `snap feedback` 命令覆盖写入），因为反馈天然是延迟产生的。

### 9.2 关系只增不减

`decision attach` 用于补挂关系，但不提供 `detach` 命令。

关系记录的是"这个 decision 曾经/正在影响这个 intent"的事实，移除关系等于抹掉历史。如果一个 decision 不再适用，应当 `deprecate` 它——已有关联保留，只是停止后续自动挂载。

### 9.3 `snap feedback` 是覆盖语义

`snap feedback` 对 `feedback` 字段执行整体覆盖，不是追加。每条 snap 只保留最新一次反馈。
