# Intent CLI 实现约束 v0.1

用途：作为 [CLI 设计说明](cli-design.md) 的实现层补充文档。本文只定义首版必须冻结的 contract、schema、状态机和行为规则。

## 这篇文档回答什么

- `.intent/` 应该如何落地
- 首版对象、状态和 JSON contract 应该长什么样
- 核心写命令、错误模型、幂等语义和 non-interactive policy 应如何定义

## 这篇文档不回答什么

- 为什么需要 Intent
- 首页命令为什么这么设计
- 更长期的平台路线

## 与其他文档的边界

- 问题定义以 [愿景与问题定义](vision.md) 为准
- 命令语义和对象曝光顺序以 [CLI 设计说明](cli-design.md) 为准
- 共用术语以 [术语表](glossary.md) 为准

## 1. 首版范围

### 1.1 必须覆盖的命令

- `itt init`
- `itt start`
- `itt status`
- `itt snap`
- `itt adopt`
- `itt log`
- `itt inspect`
- `itt checkpoint select`
- `itt revert`

### 1.2 首版核心对象

- `intent`
- `checkpoint`
- `adoption`
- `state`

### 1.3 可延后对象

- `run`
- `decision`

要求：

- 目录可以先保留
- `inspect --json` 可返回 `null` 或空列表
- 不能影响 `init -> start -> snap -> adopt -> log` 这条最小闭环

## 2. 实现优先级

- 先保证 semantic history 闭环成立
- 先冻结 contract，再优化输出文案
- human path 允许 implicit default
- machine path 必须依赖显式对象和稳定 JSON

## 3. 本地目录结构

首版目录固定为：

```text
.intent/
  config.json
  state.json
  intents/
  checkpoints/
  adoptions/
  runs/
  decisions/
```

### 3.1 目录职责

| 路径 | 职责 |
| --- | --- |
| `.intent/config.json` | 仓库级配置，不保存运行态上下文 |
| `.intent/state.json` | 当前 workspace 的活动状态和默认对象引用 |
| `.intent/intents/` | intent 对象文件 |
| `.intent/checkpoints/` | checkpoint 对象文件 |
| `.intent/adoptions/` | adoption 对象文件 |
| `.intent/runs/` | run 对象文件；首版可为空 |
| `.intent/decisions/` | decision 对象文件；首版可为空 |

### 3.2 文件组织原则

- 一个对象对应一个 JSON 文件
- 文件名默认等于对象 id，例如 `intent-001.json`
- 不使用单一大数据库文件
- 首版不依赖 sqlite
- 文件内容必须可读、可 Git 跟踪、可被其他工具消费

## 4. 命名与 ID 规则

### 4.1 ID 前缀

| 对象 | 前缀示例 |
| --- | --- |
| intent | `intent-001` |
| checkpoint | `cp-001` |
| adoption | `adopt-001` |
| run | `run-001` |
| decision | `decision-001` |

### 4.2 生成规则

- 首版使用单仓库内单调递增序号
- 每类对象独立递增
- 删除对象后不复用旧 id
- 输出必须稳定，不能在不同执行间改写已分配 id

### 4.3 显示名与标题分离

- 机器标识使用 `id`
- 面向人展示时同时显示 `title`

示例：

```text
intent-003  Reduce onboarding confusion
cp-012      Landing page candidate B
```

## 5. 通用对象 schema

所有对象必须至少包含这些字段：

```json
{
  "id": "...",
  "object": "intent|checkpoint|adoption|run|decision",
  "schema_version": "0.1",
  "created_at": "2026-03-15T14:00:00Z",
  "updated_at": "2026-03-15T14:00:00Z",
  "title": "...",
  "summary": "...",
  "status": "...",
  "intent_id": "intent-001",
  "run_id": null,
  "git": {
    "branch": "main",
    "head": "a91c3d2",
    "working_tree": "clean",
    "linkage_quality": "stable_commit"
  },
  "metadata": {}
}
```

### 5.1 字段说明

| 字段 | 说明 |
| --- | --- |
| `id` | 对象唯一标识 |
| `object` | 对象类型字符串，不允许省略 |
| `schema_version` | 对象 schema 版本；首版固定为 `0.1` |
| `created_at` / `updated_at` | RFC3339 UTC 时间戳 |
| `title` | 面向人的短标题 |
| `summary` | 可选摘要；首版允许为空字符串 |
| `status` | 枚举值，不允许自由文本 |
| `intent_id` | 除 intent 自身外，其余对象必须指向所属 intent |
| `run_id` | 首版可为 `null` |
| `git` | Git 关联上下文 |
| `metadata` | 扩展字段；首版核心逻辑不得依赖 |

## 6. 对象级 contract

### 6.1 Intent

```json
{
  "id": "intent-001",
  "object": "intent",
  "schema_version": "0.1",
  "created_at": "2026-03-15T14:00:00Z",
  "updated_at": "2026-03-15T14:00:00Z",
  "title": "Reduce onboarding confusion",
  "summary": "Improve first-run understanding and reduce drop-off.",
  "status": "active",
  "parent_intent_id": null,
  "tags": [],
  "latest_checkpoint_id": "cp-003",
  "latest_adoption_id": "adopt-002",
  "metadata": {}
}
```

`status` 枚举：

- `active`
- `paused`
- `completed`
- `archived`

约束：

- `itt start` 创建的新 intent 默认 `active`
- `state.active_intent_id` 必须切换到它
- 首版默认同一时刻只有一个 active intent 作为 workspace current context

### 6.2 Checkpoint

```json
{
  "id": "cp-001",
  "object": "checkpoint",
  "schema_version": "0.1",
  "created_at": "2026-03-15T14:10:00Z",
  "updated_at": "2026-03-15T14:10:00Z",
  "title": "Landing page candidate B",
  "summary": "Progressive disclosure layout with shorter hero copy.",
  "status": "candidate",
  "intent_id": "intent-001",
  "run_id": null,
  "ordinal": 1,
  "selected": true,
  "adopted": false,
  "adopted_by": null,
  "git": {
    "branch": "main",
    "head": "a91c3d2",
    "working_tree": "dirty",
    "linkage_quality": "working_tree_context"
  },
  "metadata": {}
}
```

`status` 枚举：

- `candidate`
- `adopted`
- `superseded`
- `reverted`

约束：

- `itt snap` 创建时默认 `candidate`
- 新 checkpoint 自动成为 `state.current_checkpoint_id`
- 同一 intent 下允许多个 `candidate`
- 仅 `selected=true` 的 checkpoint 可作为 human default current checkpoint
- adoption 完成后，对应 checkpoint 的 `adopted=true`，`adopted_by=<adoption_id>`

### 6.3 Adoption

```json
{
  "id": "adopt-001",
  "object": "adoption",
  "schema_version": "0.1",
  "created_at": "2026-03-15T14:20:00Z",
  "updated_at": "2026-03-15T14:20:00Z",
  "title": "Adopt progressive disclosure layout",
  "summary": "Choose candidate B as the official direction for onboarding.",
  "status": "active",
  "intent_id": "intent-001",
  "checkpoint_id": "cp-001",
  "rationale": "Lower cognitive load and clearer first action.",
  "reverts_adoption_id": null,
  "git": {
    "branch": "main",
    "head": "a91c3d2",
    "working_tree": "clean",
    "linkage_quality": "stable_commit"
  },
  "metadata": {}
}
```

`status` 枚举：

- `active`
- `reverted`

约束：

- 一个 checkpoint 首版默认最多只能有一个 active adoption
- `itt revert` 首版固定复用 adoption object，不引入单独的 revert object
- revert record 继续使用同一 schema，`reverts_adoption_id` 必须指向被回退 adoption
- revert record 复用原 adoption 的 `intent_id` 与 `checkpoint_id`
- 新创建的 revert record `status=active`；被回退 adoption 标记为 `reverted`
- adoption 不直接修改 Git，只记录 Git 关联状态

revert record 示例：

```json
{
  "id": "adopt-002",
  "object": "adoption",
  "schema_version": "0.1",
  "created_at": "2026-03-15T14:30:00Z",
  "updated_at": "2026-03-15T14:30:00Z",
  "title": "Revert progressive disclosure layout",
  "summary": "Revert the previously adopted onboarding direction.",
  "status": "active",
  "intent_id": "intent-001",
  "checkpoint_id": "cp-001",
  "rationale": "Testing showed higher confusion than expected.",
  "reverts_adoption_id": "adopt-001",
  "git": {
    "branch": "main",
    "head": "b02d441",
    "working_tree": "clean",
    "linkage_quality": "stable_commit"
  },
  "metadata": {}
}
```

## 7. `state.json` contract

首版 `state.json` 至少包含：

```json
{
  "schema_version": "0.1",
  "mode": "human",
  "active_intent_id": "intent-001",
  "active_run_id": null,
  "current_checkpoint_id": "cp-001",
  "last_adoption_id": "adopt-001",
  "workspace_status": "candidate_ready",
  "updated_at": "2026-03-15T14:20:00Z"
}
```

### 7.1 字段说明

| 字段 | 说明 |
| --- | --- |
| `mode` | `human` / `agent` / `ci` |
| `active_intent_id` | 当前默认 intent |
| `active_run_id` | 当前 run；首版可为 `null` |
| `current_checkpoint_id` | 当前默认 checkpoint |
| `last_adoption_id` | 最近一次 adoption |
| `workspace_status` | 当前 workspace 聚合状态 |
| `updated_at` | 最近刷新时间 |

### 7.2 `workspace_status` 枚举

- `idle`
- `blocked_no_active_intent`
- `intent_active`
- `candidate_ready`
- `adoption_recorded`
- `conflict_multiple_candidates`

### 7.3 推导规则

| 状态 | 触发条件 |
| --- | --- |
| `idle` | 尚未创建任何 intent，或 state 尚未初始化完整 |
| `blocked_no_active_intent` | 当前无 `active_intent_id` |
| `intent_active` | 有 active intent，但没有 current checkpoint |
| `candidate_ready` | 有 current checkpoint，且它尚未被 adoption，适合作为推荐采纳对象 |
| `adoption_recorded` | 最近一次动作是 adoption 或 revert record，且当前没有更高优先级冲突 |
| `conflict_multiple_candidates` | 存在多个未采纳 candidate，且没有唯一 `selected=true` 的 current checkpoint |

### 7.4 更新原则

- 每次成功写命令后必须刷新 `updated_at`
- `state.json` 是当前快照，不是历史记录
- 历史事件必须由对象文件承载，不能只存在于 state 中

## 8. 核心写命令行为规则

### 8.1 `itt init`

- 创建 `.intent/`
- 创建必要子目录
- 创建 `config.json`
- 创建 `state.json`
- 若已存在，默认不覆盖，返回可识别错误

### 8.2 `itt start <title>`

- 创建新的 intent object
- 设置为 `active_intent_id`
- 将 `current_checkpoint_id` 置空
- `workspace_status=intent_active`

### 8.3 `itt snap <title>`

- 要求存在 `active_intent_id`
- 创建 checkpoint object
- 自动成为 `current_checkpoint_id`
- 默认 `selected=true`
- 若原 current checkpoint 存在，则旧 checkpoint 应变为 `selected=false`
- `workspace_status=candidate_ready`

### 8.4 `itt checkpoint select <id>`

- 要求 checkpoint 存在且属于 active intent
- 将目标 checkpoint `selected=true`
- 其他同 intent checkpoint `selected=false`
- 更新 `current_checkpoint_id`

### 8.5 `itt adopt`

- 默认采用 `current_checkpoint_id`
- 若无 current checkpoint，返回 `STATE_CONFLICT`
- 若存在多个 candidate 且当前对象不明确，返回 `STATE_CONFLICT`
- 成功后创建 adoption object
- 更新 checkpoint adoption 字段
- 更新 `last_adoption_id`
- `workspace_status=adoption_recorded`

### 8.6 `itt revert`

- 默认回退最近一条 active adoption
- 若无 active adoption，返回 object/state 错误
- 创建一条新的 adoption object 作为 revert record，引用 `reverts_adoption_id`
- 新 revert record 继承目标 adoption 的 `intent_id` 与 `checkpoint_id`
- 新 revert record `status=active`
- 被回退 adoption 标记为 `reverted`
- 更新 `last_adoption_id`
- `workspace_status=adoption_recorded`
- checkpoint 状态保持历史事实，不自动恢复为 `candidate`

## 9. Surface 与 Canonical 映射

| Surface CLI | Canonical 语义 |
| --- | --- |
| `itt start` | `itt intent create --activate` |
| `itt snap` | `itt checkpoint create --select` |
| `itt adopt` | `itt adoption create` |
| `itt revert` | `itt adoption revert` |

实现建议：

- 内部逻辑优先围绕 canonical action handler 组织
- Surface CLI 只做参数预填和 UX 包装
- JSON 返回结构围绕 canonical object 设计

## 10. Git linkage contract

### 10.1 必须记录的 Git 字段

```json
{
  "git": {
    "branch": "main",
    "head": "a91c3d2",
    "working_tree": "clean|dirty|no_repo|unknown",
    "linkage_quality": "stable_commit|working_tree_context|explicit_ref|none"
  }
}
```

### 10.2 `linkage_quality` 取值

- `stable_commit`：当前 HEAD 可解析为稳定提交
- `working_tree_context`：只记录当前工作区上下文，未绑定稳定 commit
- `explicit_ref`：通过 `--link-git <hash|HEAD>` 显式指定
- `none`：不在 Git 仓库中，或 Git 不可用

### 10.3 行为规则

checkpoint：

- 允许在 dirty working tree 上创建
- 不要求必须有 commit
- 若有 HEAD，记录 HEAD；若无，则记录 `null` 并给出 warning

adoption：

- 默认尽量绑定当前 HEAD
- dirty working tree 允许继续，但必须给出 warning 或质量降级
- strict mode 下可要求 clean tree + stable commit，否则失败

### 10.4 strict mode

首版建议支持：

```json
{
  "git": {
    "strict_adoption": false
  }
}
```

当 `strict_adoption=true` 时：

- `itt adopt` 要求当前处于 Git repo
- 要求 HEAD 可解析
- 要求 working tree 为 clean

## 11. 读命令 JSON contract

### 11.1 `itt status --json`

```json
{
  "ok": true,
  "object": "status",
  "schema_version": "0.1",
  "active_intent": {
    "id": "intent-001",
    "title": "Reduce onboarding confusion",
    "status": "active"
  },
  "current_checkpoint": {
    "id": "cp-001",
    "title": "Landing page candidate B",
    "status": "candidate"
  },
  "latest_adoption": {
    "id": "adopt-001",
    "title": "Adopt progressive disclosure layout",
    "status": "active"
  },
  "workspace_status": "candidate_ready",
  "git": {
    "branch": "main",
    "head": "a91c3d2",
    "working_tree": "clean"
  },
  "next_action": {
    "command": "itt adopt -m \"Adopt candidate\"",
    "reason": "Current checkpoint is ready for adoption."
  },
  "warnings": []
}
```

### 11.2 `itt inspect --json`

```json
{
  "ok": true,
  "object": "inspect",
  "schema_version": "0.1",
  "mode": "human",
  "state": {
    "active_intent_id": "intent-001",
    "active_run_id": null,
    "current_checkpoint_id": "cp-001",
    "last_adoption_id": "adopt-001",
    "workspace_status": "candidate_ready"
  },
  "active_intent": {
    "id": "intent-001",
    "title": "Reduce onboarding confusion",
    "status": "active"
  },
  "current_checkpoint": {
    "id": "cp-001",
    "title": "Landing page candidate B",
    "status": "candidate",
    "adopted": false
  },
  "latest_adoption": {
    "id": "adopt-001",
    "title": "Adopt progressive disclosure layout",
    "status": "active"
  },
  "pending_items": [
    {
      "type": "candidate",
      "id": "cp-001",
      "reason": "Ready for adoption"
    }
  ],
  "suggested_next_actions": [
    {
      "command": "itt adopt --checkpoint cp-001 -m \"Adopt candidate\"",
      "reason": "Checkpoint is current and not yet adopted"
    }
  ],
  "git": {
    "branch": "main",
    "head": "a91c3d2",
    "working_tree": "clean"
  },
  "warnings": []
}
```

### 11.3 稳定性要求

- 顶层字段必须固定
- 缺失对象时返回 `null`
- 列表为空时返回 `[]`
- 所有枚举值必须文档化

## 12. 写命令 JSON contract

所有写命令支持 `--json`，并返回统一结构：

```json
{
  "ok": true,
  "object": "checkpoint",
  "action": "create",
  "id": "cp-001",
  "state_changed": true,
  "result": {},
  "next_action": {
    "command": "itt adopt -m \"...\"",
    "reason": "Checkpoint created and selected"
  },
  "warnings": []
}
```

### 12.1 最低要求字段

- `ok`
- `object`
- `action`
- `id`
- `state_changed`
- `result`
- `warnings`

### 12.2 `--id-only`

支持机器调用场景：

```text
cp-001
```

要求：

- 仅输出对象 id
- 不附带说明文本
- 错误时仍走 stderr / 非零 exit code

## 13. 错误模型与 exit code

### 13.1 exit code

| code | 含义 |
| --- | --- |
| `0` | success |
| `1` | general failure |
| `2` | invalid input |
| `3` | state conflict |
| `4` | object not found |

### 13.2 JSON 错误格式

```json
{
  "ok": false,
  "error": {
    "code": "STATE_CONFLICT",
    "message": "Multiple candidate checkpoints exist and no current checkpoint is selected.",
    "details": {
      "intent_id": "intent-001",
      "candidate_count": 2
    },
    "suggested_fix": "Run `itt checkpoint select <id>` or pass `--checkpoint <id>` explicitly."
  }
}
```

### 13.3 推荐 error code

- `GENERAL_FAILURE`
- `INVALID_INPUT`
- `STATE_CONFLICT`
- `OBJECT_NOT_FOUND`
- `ALREADY_EXISTS`
- `NOT_INITIALIZED`
- `GIT_STATE_INVALID`

### 13.4 典型错误场景

| 场景 | exit code | error code |
| --- | --- | --- |
| 已初始化仓库重复执行 `itt init` | `1` | `ALREADY_EXISTS` |
| 无 active intent 时执行 `itt snap` | `3` | `STATE_CONFLICT` |
| checkpoint id 不存在 | `4` | `OBJECT_NOT_FOUND` |
| 参数缺失或非法 flag | `2` | `INVALID_INPUT` |

## 14. 幂等与 non-interactive

### 14.1 幂等语义

`itt start`

- 默认非幂等
- 每次执行创建新 intent

`itt snap`

- 默认非幂等
- 每次执行创建新 checkpoint

`itt adopt`

- 必须支持 `--if-not-adopted`
- 若目标 checkpoint 已存在 active adoption，推荐返回 success-like no-op 结构

示例：

```json
{
  "ok": true,
  "object": "adoption",
  "action": "create",
  "id": "adopt-001",
  "state_changed": false,
  "noop": true,
  "reason": "Checkpoint already adopted",
  "warnings": []
}
```

`itt init`

- 首版建议默认非幂等
- 若目录已存在则失败

### 14.2 non-interactive policy

核心写命令建议支持：

- `--json`
- `--id-only`
- `--yes`
- `--no-interactive`

规则：

- 不允许进入选择器、prompt 或确认问答
- 遇到状态不明确时直接失败
- 必须返回稳定错误对象

多个 candidate 并存但无唯一 current checkpoint 时：

- human 模式可提示下一步
- non-interactive 模式必须直接报 `STATE_CONFLICT`

## 15. 首版测试矩阵

- 初始化：`itt init` 首次成功、重复失败、目录结构正确
- start：创建 intent 成功，`active_intent_id` 更新，`workspace_status=intent_active`
- snap：创建 checkpoint 成功，自动 selected，旧 selected 取消，`current_checkpoint_id` 更新
- adopt：默认采纳 current checkpoint 成功，checkpoint 与 adoption 正确关联，`last_adoption_id` 更新
- revert：创建新的 revert record，原 adoption 标记为 `reverted`，`last_adoption_id` 更新
- conflict：无 active intent 时 `snap` 失败；无 current checkpoint 时 `adopt` 失败；多 candidate 且默认对象不清晰时 `adopt` 失败
- inspect/status：`status --json` 和 `inspect --json` 顶层字段稳定；缺失对象返回 `null`
- git linkage：clean repo 记录 HEAD；dirty tree 质量降级；strict mode 下 dirty tree adopt 失败

## 16. 建议实现顺序

### Phase 1

- `.intent/` 初始化
- id 生成器
- JSON 文件读写
- `state.json` 读写与 `workspace_status` 推导

### Phase 2

- `itt start`
- `itt snap`
- `itt adopt`

### Phase 3

- `itt status`
- `itt log`
- `itt inspect --json`

### Phase 4

- exit code
- `--json`
- `--id-only`
- `--no-interactive`
- `--if-not-adopted`

### Phase 5

- `itt checkpoint select`
- `itt revert`
- strict mode

## 17. 开工前冻结项

- `.intent/` 目录名
- `state.json` 文件名
- 对象类型名：`intent` / `checkpoint` / `adoption` / `run` / `decision`
- ID 前缀：`intent` / `cp` / `adopt` / `run` / `decision`
- `workspace_status` 枚举
- `linkage_quality` 枚举
- `status --json` 顶层字段
- `inspect --json` 顶层字段
- exit code `0/1/2/3/4`
- `STATE_CONFLICT` / `OBJECT_NOT_FOUND` 等错误码字符串

## 18. 一句话结论

首版最该冻结的不是更大的叙事，而是本地对象层、状态机、JSON contract 和错误模型。
