[English](cli.EN.md) | 简体中文

# Intent CLI 设计文档

Schema version: **0.2**

Intent CLI 是一个构建在 Git 之上的语义历史工具。它记录你在解决什么问题、做了什么、为什么——使用两种对象：**intent** 和 **snap**。

核心闭环：`init → start → snap → done`

## 1. 对象模型

### Intent

一个 intent 代表一个工作单元——通常是一个问题或任务。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 如 `intent-001` |
| `object` | string | 固定为 `"intent"` |
| `schema_version` | string | `"0.2"` |
| `created_at` | string | ISO 8601 UTC |
| `updated_at` | string | ISO 8601 UTC |
| `title` | string | 在解决什么问题 |
| `status` | string | `open` 或 `done` |

### Snap

一个 snap 记录 intent 内的一个步骤——做了什么以及为什么。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 如 `snap-001` |
| `object` | string | 固定为 `"snap"` |
| `schema_version` | string | `"0.2"` |
| `created_at` | string | ISO 8601 UTC |
| `updated_at` | string | ISO 8601 UTC |
| `title` | string | 做了什么 |
| `rationale` | string | 为什么（通过 `-m` 提供） |
| `status` | string | `adopted`、`candidate` 或 `reverted` |
| `intent_id` | string | 所属 intent ID |
| `git` | object | snap 时的 Git 上下文 |

**Snap 状态语义：**

- `adopted` — `snap` 时的默认状态，表示这个步骤被接受
- `candidate` — 通过 `snap --candidate` 创建，等待显式 `adopt`
- `reverted` — 曾经 adopted，后通过 `revert` 回退

## 2. 状态机

### Workspace 状态

从当前状态推导，存储在 `state.json`：

| 状态 | 含义 |
| --- | --- |
| `idle` | 没有 active intent |
| `active` | 有一个 open intent |
| `conflict` | 存在多个 candidate snap |

### Intent 生命周期

```
open → done
```

`start` 创建时为 `open`，`done` 关闭时变为 `done`。

## 3. 存储结构

```
.intent/
  config.json           # {"schema_version": "0.2"}
  state.json            # workspace 状态
  intents/
    intent-001.json
  snaps/
    snap-001.json
```

### state.json

```json
{
  "schema_version": "0.2",
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

若已有 open intent 则失败，需先 `itt done`。

### snap

对 active intent 记录一个 snap。默认状态为 `adopted`。

```
itt snap "Increase timeout to 30s" -m "Default 5s was too short for slow networks"
```

使用 `--candidate` 记录但不 adopt——适用于比较备选方案：

```
itt snap "Try connection pooling" --candidate
```

### adopt

采纳一个 candidate snap。如果只有一个 candidate，不需要指定 ID。

```
itt adopt
itt adopt snap-003
itt adopt snap-003 -m "Pooling approach benchmarked 2x faster"
```

若无 candidate 或存在多个 candidate 但未指定 ID 则失败（错误中会列出 candidate 列表）。

### revert

回退 active intent 中最近一个 adopted snap。

```
itt revert
itt revert -m "Approach caused regression in tests"
```

将 snap 状态从 `adopted` 改为 `reverted`。若无 adopted snap 则失败。

### done

关闭 active intent（或按 ID 指定关闭）。

```
itt done
itt done intent-001
```

将 intent 状态设为 `done`，清空 `active_intent_id`，workspace 状态变为 `idle`。

### inspect

机器可读的 workspace 快照。以单个 JSON 对象返回当前状态。

```
itt inspect
```

```json
{
  "ok": true,
  "schema_version": "0.2",
  "workspace_status": "active",
  "intent": { "id": "intent-001", "title": "Fix the login timeout bug", "status": "open" },
  "latest_snap": { "id": "snap-002", "title": "Increase timeout to 30s", "status": "adopted", "rationale": "Default 5s was too short" },
  "candidate_snaps": [],
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

没有 active intent 时，`intent`、`latest_snap` 为 `null`，`candidate_snaps` 为 `[]`，`suggested_next_action` 推荐 `itt start`。

### list

列出指定类型的所有对象，按创建时间倒序。

```
itt list intent
itt list snap
```

### show

按 ID 查看单个对象。类型从 ID 前缀推断（`intent-` 或 `snap-`）。

```
itt show intent-001
itt show snap-003
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

ID 零填充至 3 位，按类型自动递增。
