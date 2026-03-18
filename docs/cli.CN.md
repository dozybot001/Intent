[English](cli.md) | 简体中文

# Intent CLI 设计文档

Schema version: **0.3**

Intent CLI 是一个构建在 Git 之上的语义历史工具。它记录你在解决什么问题、做了什么、为什么——使用三种对象：**intent**、**snap** 和 **decision**。

核心闭环：`init → start → snap → done`

## 1. 对象模型

### Intent

一个 intent 代表一个工作单元——通常是一个问题或任务。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 如 `intent-001` |
| `object` | string | 固定为 `"intent"` |
| `schema_version` | string | `"0.3"` |
| `created_at` | string | ISO 8601 UTC |
| `updated_at` | string | ISO 8601 UTC |
| `title` | string | 在解决什么问题 |
| `status` | string | `open`、`suspended` 或 `done` |
| `decision_ids` | string[] | 关联的 decision ID 列表 |

### Snap

一个 snap 记录 intent 内的一个步骤——做了什么以及为什么。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 如 `snap-001` |
| `object` | string | 固定为 `"snap"` |
| `schema_version` | string | `"0.3"` |
| `created_at` | string | ISO 8601 UTC |
| `updated_at` | string | ISO 8601 UTC |
| `title` | string | 做了什么 |
| `rationale` | string | 为什么（通过 `-m` 提供） |
| `status` | string | `active` 或 `reverted` |
| `intent_id` | string | 所属 intent ID |
| `git` | object | snap 时的 Git 上下文 |

**Snap 状态语义：**

- `active` — `snap` 时的默认状态，表示这个步骤当前生效
- `reverted` — 曾经 active，后通过 `revert` 回退

### Decision

一个 decision 记录跨 intent 的架构或策略决定——为什么选择某个方向。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 如 `decision-001` |
| `object` | string | 固定为 `"decision"` |
| `schema_version` | string | `"0.3"` |
| `created_at` | string | ISO 8601 UTC |
| `updated_at` | string | ISO 8601 UTC |
| `title` | string | 决定的标题 |
| `rationale` | string | 为什么做出这个决定 |
| `status` | string | `active` 或 `deprecated` |
| `intent_ids` | string[] | 关联的 intent ID 列表 |
| `created_from_intent_id` | string | 创建时所在的 intent ID |

## 2. 状态机

### Workspace 状态

从当前状态推导，存储在 `state.json`：

| 状态 | 含义 |
| --- | --- |
| `idle` | 没有 active intent |
| `active` | 有一个 open intent |

### Intent 生命周期

```
open → done
open → suspended → open → done
```

`start` 创建时为 `open`，`done` 关闭时变为 `done`。open 的 intent 可以通过 `suspend` 暂停，之后用 `resume` 恢复。

## 3. 存储结构

```
.intent/
  config.json           # {"schema_version": "0.3"}
  state.json            # workspace 状态
  intents/
    intent-001.json
  snaps/
    snap-001.json
  decisions/
    decision-001.json
```

### state.json

```json
{
  "schema_version": "0.3",
  "active_intent_id": null,
  "workspace_status": "idle",
  "updated_at": "2026-03-17T10:00:00Z"
}
```

## 4. 命令

所有命令输出 JSON。没有人类可读文本模式，不需要 `--json` flag。

### version

```
itt version
```

### init

在当前 Git 仓库中初始化 Intent。创建 `.intent/` 目录及子目录。

```
itt init
```

若 `.intent/` 已存在或不在 Git worktree 中则失败。

### start

创建并激活一个新 intent。同一时间只能有一个 open intent。

```
itt start "Fix the login timeout bug"
```

若已有 open intent 则失败，需先 `itt done` 或 `itt suspend`。

### snap

对 active intent 记录一个 snap。默认状态为 `active`。

```
itt snap "Increase timeout to 30s" -m "Default 5s was too short for slow networks"
```

### revert

回退 active intent 中最近一个 active snap。

```
itt revert
itt revert -m "Approach caused regression in tests"
```

将 snap 状态从 `active` 改为 `reverted`。若无 active snap 则失败。

### suspend

暂停 active intent。workspace 变为 `idle`，可以 start 新的 intent 或 resume 其他已暂停的 intent。

```
itt suspend
```

若无 active intent 则失败。

### resume

恢复一个暂停的 intent。如果只有一个 suspended intent，不需要指定 ID。恢复时会自动补挂 suspend 期间新建的 decision。

```
itt resume
itt resume intent-001
```

若已有 active intent 则失败，若存在多个 suspended intent 但未指定 ID 则失败（错误中会列出列表）。

### done

关闭 active intent（或按 ID 指定关闭）。

```
itt done
itt done intent-001
```

将 intent 状态设为 `done`，清空 `active_intent_id`，workspace 状态变为 `idle`。

### decide

对 active intent 创建一个 decision。记录一个架构或策略决定，并关联到当前 intent。

```
itt decide "Use connection pooling for DB access" -m "Benchmarks show 2x throughput improvement"
```

### deprecate

废弃一个 decision。将 decision 状态从 `active` 改为 `deprecated`。

```
itt deprecate decision-001
itt deprecate decision-001 -m "Switched to serverless architecture"
```

### inspect

机器可读的 workspace 快照。以单个 JSON 对象返回当前状态。

```
itt inspect
```

```json
{
  "ok": true,
  "schema_version": "0.3",
  "workspace_status": "active",
  "intent": { "id": "intent-001", "title": "Fix the login timeout bug", "status": "open", "decision_ids": ["decision-001"] },
  "latest_snap": { "id": "snap-002", "title": "Increase timeout to 30s", "status": "active", "rationale": "Default 5s was too short" },
  "active_decisions": [],
  "suspended_intents": [],
  "suggested_next_action": {
    "command": "itt snap 'Describe the step'",
    "reason": "Intent is active."
  },
  "git": {
    "branch": "fix/login-timeout",
    "head": "a1b2c3d",
    "working_tree": "dirty"
  },
  "warnings": ["Git working tree is dirty; recording working tree context."]
}
```

没有 active intent 时，`intent`、`latest_snap` 为 `null`，`active_decisions` 和 `suspended_intents` 为 `[]`，`suggested_next_action` 推荐 `itt start`（若有 suspended intent 则推荐 `itt resume`）。

### list

列出指定类型的所有对象，按创建时间倒序。

```
itt list intent
itt list snap
itt list decision
```

### show

按 ID 查看单个对象。类型从 ID 前缀推断（`intent-`、`snap-` 或 `decision-`）。

```
itt show intent-001
itt show snap-003
itt show decision-001
```

## 5. JSON 输出 contract

### 成功

```json
{
  "ok": true,
  "action": "<command-name>",
  "result": { ... },
  "warnings": []
}
```

例外：`inspect` 返回扁平结构，顶层 `"ok": true`，不带 `action`/`result` 包装。

### 错误

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

`suggested_fix` 仅在适用时出现。

## 6. Exit code

| Code | 含义 |
| --- | --- |
| `0` | 成功 |
| `1` | 通用失败 |
| `2` | 无效输入 |
| `3` | 状态冲突 |
| `4` | 对象未找到 |

## 7. Error code

| Code | 触发场景 |
| --- | --- |
| `NOT_INITIALIZED` | `.intent/` 不存在 |
| `ALREADY_EXISTS` | `.intent/` 已存在时执行 `init` |
| `GIT_STATE_INVALID` | 不在 Git worktree 中 |
| `STATE_CONFLICT` | intent 已 open、snap 不是 candidate 等 |
| `OBJECT_NOT_FOUND` | ID 找不到对应对象 |
| `INVALID_INPUT` | 参数错误或 flag 冲突 |

## 8. Git 上下文

每个 snap 在创建时记录 Git 上下文：

```json
{
  "branch": "main",
  "head": "a1b2c3d",
  "working_tree": "clean",
  "linkage_quality": "stable_commit"
}
```

| `linkage_quality` | 含义 |
| --- | --- |
| `stable_commit` | clean tree，HEAD 可解析 |
| `working_tree_context` | dirty tree 或 HEAD 不可解析 |
| `explicit_ref` | 用户提供的 ref 已解析 |

`inspect` 在顶层返回 git 上下文的子集（`branch`、`head`、`working_tree`）。

## 9. ID 格式

- Intent：`intent-001`、`intent-002`、...
- Snap：`snap-001`、`snap-002`、...
- Decision：`decision-001`、`decision-002`、...

ID 零填充至 3 位，按类型自动递增。
