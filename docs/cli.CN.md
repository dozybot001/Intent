[English](cli.md) | 简体中文

# Intent CLI 设计文档

Schema version: **0.2**

Intent CLI 是一个构建在 Git 之上的语义历史工具。它记录你在解决什么问题、做了什么、为什么——使用两种对象：**intent** 和 **checkpoint**。

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

### Checkpoint

一个 checkpoint 记录 intent 内的一个步骤——做了什么以及为什么。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 如 `cp-001` |
| `object` | string | 固定为 `"checkpoint"` |
| `schema_version` | string | `"0.2"` |
| `created_at` | string | ISO 8601 UTC |
| `updated_at` | string | ISO 8601 UTC |
| `title` | string | 做了什么 |
| `rationale` | string | 为什么（通过 `-m` 提供） |
| `status` | string | `adopted`、`candidate` 或 `reverted` |
| `intent_id` | string | 所属 intent ID |
| `git` | object | snap 时的 Git 上下文 |

**Checkpoint 状态语义：**

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
| `conflict` | 存在多个 candidate checkpoint |

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
  checkpoints/
    cp-001.json
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

对 active intent 记录一个 checkpoint。默认状态为 `adopted`。

```
itt snap "Increase timeout to 30s" -m "Default 5s was too short for slow networks"
```

使用 `--candidate` 记录但不 adopt——适用于比较备选方案：

```
itt snap "Try connection pooling" --candidate
```

### adopt

采纳一个 candidate checkpoint。如果只有一个 candidate，不需要指定 ID。

```
itt adopt
itt adopt cp-003
itt adopt cp-003 -m "Pooling approach benchmarked 2x faster"
```

若无 candidate 或存在多个 candidate 但未指定 ID 则失败（错误中会列出 candidate 列表）。

### revert

回退 active intent 中最近一个 adopted checkpoint。

```
itt revert
itt revert -m "Approach caused regression in tests"
```

将 checkpoint 状态从 `adopted` 改为 `reverted`。若无 adopted checkpoint 则失败。

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
  "latest_checkpoint": { "id": "cp-002", "title": "Increase timeout to 30s", "status": "adopted" },
  "candidate_checkpoints": [],
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

没有 active intent 时，`intent`、`latest_checkpoint` 为 `null`，`candidate_checkpoints` 为 `[]`，`suggested_next_action` 推荐 `itt start`。

### list

列出指定类型的所有对象，按创建时间倒序。

```
itt list intent
itt list checkpoint
```

### show

按 ID 查看单个对象。类型从 ID 前缀推断（`intent-` 或 `cp-`）。

```
itt show intent-001
itt show cp-003
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
| `STATE_CONFLICT` | intent 已 open、checkpoint 不是 candidate 等 |
| `OBJECT_NOT_FOUND` | ID 找不到对应对象 |
| `INVALID_INPUT` | 参数错误或 flag 冲突 |

## 8. Git 上下文

每个 checkpoint 在创建时记录 Git 上下文：

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
- Checkpoint：`cp-001`、`cp-002`、...

ID 零填充至 3 位，按类型自动递增。

## 10. Agent 协议

一个 agent 应该：

1. 运行 `itt inspect` 了解当前状态
2. 开始有意义的工作时启动 intent
3. 用 `itt snap` 记录步骤和理由
4. 工作完成时运行 `itt done`
5. 对于琐碎问题或微小编辑，跳过记录

克制规则：

- 若现有 open intent 仍匹配当前工作，优先继续沿用
- 只在工作方向真正转变时才新建 intent
- 理由应在对未来有参考价值时记录
