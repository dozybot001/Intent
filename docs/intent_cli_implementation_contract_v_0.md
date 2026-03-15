# Intent CLI Implementation Contract v0.1

用途：作为《Intent CLI Design Spec v0.4》的实现约束补充文档。本文档不重复愿景叙事，重点定义 **首版实现必须冻结的 contract、schema、状态机与行为规则**，以减少开发过程中反复回头。

## 导读

**本文回答什么**

- 首版实现必须冻结哪些 schema、状态机和行为规则
- `.intent/`、`state.json` 和对象字段应该如何落地
- JSON contract、错误模型、幂等语义和 non-interactive policy 应如何定义

**适合谁读**

- 正在实现 CLI 的开发者
- 需要对接 agent、Skill 或 IDE integration 的人
- 想核对首版边界和机器可读 contract 的人

**与其他文档关系**

- 这篇文档负责实现层 contract，不重复展开愿景叙事
- 产品定位、命令语义和用户主路径以 [Intent CLI Design Spec v0.4](intent_cli_design_spec_v_0_4_cn.md) 为主
- 如果你想先理解项目要解决什么问题，建议先读 [Intent 愿景笔记 v3](intent_vision_notes_v_3_cn.md)

---

## 1. 文档目标

本文件用于补足目前 design spec 中尚未完全落死、但一旦进入实现就容易反复修改的部分。

本文档的目标不是扩大产品范围，而是把 v0.1 / v0.2 开工阶段最需要稳定下来的约束明确下来，包括：

- 本地存储目录与文件职责
- 通用对象 schema 与对象级字段约束
- `state.json` 的状态含义与状态转移规则
- Surface CLI 与 Canonical CLI 的映射原则
- `status --json` / `inspect --json` 的稳定返回 contract
- 写命令返回结构
- exit code / error code / non-interactive 行为
- 幂等语义
- Git linkage policy 的实现细节
- 最小测试矩阵

本文档优先服务以下目标：

1. 让 CLI 首版实现时不再依赖“临场决定”
2. 让 agent / Skill / IDE 集成拥有稳定契约
3. 让后续远端平台与 IntHub 演化建立在稳定本地对象层之上

---

## 2. 版本边界

### 2.1 本文档覆盖的首版范围

本文档默认约束以下首版能力：

- `itt init`
- `itt start`
- `itt status`
- `itt snap`
- `itt adopt`
- `itt log`
- `itt inspect`
- `itt checkpoint select`
- `itt revert`（可先实现为 adoption revert 的 surface）

以及以下核心对象：

- intent
- checkpoint
- adoption
- state

### 2.2 首版可弱化或延后实现的对象

以下对象允许在首版中仅保留目录或接口位，不要求能力完整：

- run
- decision

要求是：

- schema version 中允许这些对象未启用；
- `inspect --json` 可返回 `null` 或空列表；
- 命令帮助中可标注为 planned / experimental；
- 不得影响最小闭环：`init → start → snap → adopt → log`。

---

## 3. 实现优先原则

### 3.1 首先保证 semantic history 闭环成立

首版最重要的不是对象数量，而是证明以下闭环可用：

1. 开始一个 intent
2. 形成一个 checkpoint
3. 正式采纳一个 checkpoint
4. 能在 log 中清楚看到 semantic history

### 3.2 首先保证 contract 稳定，而不是输出花哨

CLI 输出文本可以后续优化，但以下 contract 必须尽早冻结：

- 文件路径
- JSON schema
- 状态字段命名
- exit code
- 错误对象格式
- `inspect --json` 顶层字段

### 3.3 人类高频路径允许 implicit default

Human UX 中允许：

- `snap` 自动成为 current checkpoint
- `adopt` 默认采纳 current checkpoint
- `start` 自动切换 active intent

### 3.4 机器调用必须以显式对象和稳定 JSON 为准

Agent / automation / IDE 不应依赖模糊默认值作为强契约。

推荐原则：

- 读状态先走 `itt inspect --json`
- 执行动作尽量显式传对象 id
- 写后再次 `inspect --json` 验证状态变化

---

## 4. 本地目录结构与职责

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

### 4.1 目录职责

#### `config.json`

保存仓库级配置，不存放运行态上下文。

#### `state.json`

保存当前 workspace 的活动状态与默认对象引用。

#### `intents/`

存放 intent 对象文件。

#### `checkpoints/`

存放 checkpoint 对象文件。

#### `adoptions/`

存放 adoption 对象文件。

#### `runs/` / `decisions/`

首版可以创建目录但不要求完整使用。

### 4.2 文件组织原则

- 一个对象对应一个 JSON 文件
- 文件名默认等于对象 id，例如 `intent-001.json`
- 不使用单一大数据库文件
- 不依赖 sqlite 作为首版基础设施
- 文件内容必须可手动阅读、可 Git 跟踪、可被其他工具消费

---

## 5. 命名与 ID 规则

### 5.1 对象 ID 前缀

首版固定使用：

- intent：`intent-001`
- checkpoint：`cp-001`
- adoption：`adopt-001`
- run：`run-001`
- decision：`decision-001`

### 5.2 ID 生成规则

首版建议使用 **单仓库内单调递增序号**，而不是 UUID。

原因：

- 便于人类阅读与引用
- 便于 demo 与文档展示
- 便于 shell、日志与终端输出

约束：

- 每类对象独立递增
- 删除对象不会复用旧 id
- 通过扫描目录或计数索引生成均可，但输出上必须稳定

### 5.3 显示名与标题分离

对象的机器标识是 `id`，对人展示时可同时显示 `title`。

例如：

```text
intent-003  Reduce onboarding confusion
cp-012      Landing page candidate B
```

---

## 6. 通用对象 schema

所有对象必须包含以下通用字段：

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

### 6.1 通用字段说明

#### `id`

对象唯一标识。

#### `object`

对象类型字符串，不允许省略。

#### `schema_version`

对象自身 schema 版本。首版统一为 `0.1`。

#### `created_at` / `updated_at`

RFC3339 UTC 时间戳。

#### `title`

面向人类的短标题。建议一行内读懂。

#### `summary`

可选摘要。首版允许为空字符串。

#### `status`

对象内部状态。必须为可枚举值，不允许自由文本。

#### `intent_id`

除 intent 本身外，其余对象必须指向所属 intent。

#### `run_id`

首版可为 `null`。

#### `git`

存储 Git 关联上下文。见第 11 节。

#### `metadata`

保留扩展字段，用于后续增强；首版不允许在核心逻辑里依赖它。

---

## 7. 对象级 schema

## 7.1 Intent object

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

#### Intent `status` 枚举

- `active`
- `paused`
- `completed`
- `archived`

#### 首版约束

- `itt start` 创建的新 intent 默认 `active`
- `state.active_intent_id` 应切换到它
- 同时允许历史 intent 继续存在
- 首版默认同一时刻只有一个 active intent 作为 workspace current context

## 7.2 Checkpoint object

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

#### Checkpoint `status` 枚举

- `candidate`
- `adopted`
- `superseded`
- `reverted`

#### 首版约束

- `itt snap` 创建时默认 `candidate`
- 新创建 checkpoint 自动成为 `state.current_checkpoint_id`
- 同一 intent 下允许多个 `candidate`
- 仅 `selected=true` 的 checkpoint 可以作为 human default current checkpoint
- adoption 完成后，对应 checkpoint 的 `adopted=true`，`adopted_by=<adoption_id>`

## 7.3 Adoption object

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

#### Adoption `status` 枚举

- `active`
- `reverted`

#### 首版约束

- 一个 checkpoint 在首版默认最多只能有一个 active adoption
- `itt revert` 会创建一条新的 adoption 记录或显式 revert record，二选一即可，但必须稳定。首版建议：**仍创建 adoption object，并通过 `reverts_adoption_id` 建立关系**
- adoption 不直接修改 Git，只记录 Git 关联状态

---

## 8. `state.json` contract

首版 `state.json` 必须固定至少包含以下字段：

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

### 8.1 字段说明

#### `mode`

枚举：

- `human`
- `agent`
- `ci`

首版可由 config 默认指定，也可由命令参数覆盖运行时行为。

#### `workspace_status`

这是最重要的聚合状态字段，必须用于 `status` 和 `inspect`。

建议枚举：

- `idle`
- `intent_active`
- `checkpoint_available`
- `candidate_ready`
- `adoption_recorded`
- `conflict_multiple_candidates`
- `blocked_no_active_intent`

### 8.2 `workspace_status` 推导规则

#### `idle`

- 尚未创建任何 intent 或 state 尚未初始化完整

#### `blocked_no_active_intent`

- 存在仓库但当前无 `active_intent_id`

#### `intent_active`

- 有 active intent，但没有 current checkpoint

#### `checkpoint_available`

- 有 current checkpoint，但尚未满足 adoption 推荐条件

#### `candidate_ready`

- 有 current checkpoint，且它尚未被 adoption，适合作为推荐采纳对象

#### `adoption_recorded`

- 最近一次动作是 adoption，且当前没有更高优先级待处理冲突

#### `conflict_multiple_candidates`

- 同一 intent 下存在多个未采纳 candidate，且没有唯一 `selected=true` 的 current checkpoint

### 8.3 `state.json` 更新原则

- 每次成功写命令后必须刷新 `updated_at`
- `state.json` 是 current workspace snapshot，不是历史记录
- 历史事件必须由对象文件承载，不能只存在于 state 中

---

## 9. 状态机与默认动作规则

## 9.1 最小状态流转

```text
init
  -> idle
start
  -> intent_active
snap
  -> candidate_ready
adopt
  -> adoption_recorded
snap (again)
  -> candidate_ready
```

## 9.2 默认动作规则

### `itt init`

- 创建 `.intent/` 目录
- 创建必要子目录
- 创建 `config.json`
- 创建 `state.json`
- 若已存在，默认不覆盖，返回可识别错误

### `itt start <title>`

- 创建新的 intent object
- 设置为 `active_intent_id`
- 将 `current_checkpoint_id` 置空
- `workspace_status= intent_active`

### `itt snap <title>`

- 要求存在 `active_intent_id`
- 创建 checkpoint object
- 自动成为 `current_checkpoint_id`
- 默认 `selected=true`
- 若原 current checkpoint 存在，则应将旧 checkpoint `selected=false`
- `workspace_status = candidate_ready`

### `itt checkpoint select <id>`

- 要求 checkpoint 存在且属于 active intent，或明确允许跨 intent 选择但需切换上下文。首版建议：**仅允许 active intent 下选择**
- 将目标 checkpoint `selected=true`
- 其他同 intent checkpoint `selected=false`
- 更新 `current_checkpoint_id`

### `itt adopt`

- 默认采用 `current_checkpoint_id`
- 若无 current checkpoint，返回 `state conflict`
- 若存在多个 candidate 且当前对象不明确，返回 `state conflict`
- 成功后创建 adoption object
- 更新 checkpoint adoption 字段
- 更新 `last_adoption_id`
- `workspace_status=adoption_recorded`

### `itt revert`

- 默认回退最近一条 active adoption
- 若无 active adoption，返回 object/state 错误
- 创建一条新的 adoption revert record，引用 `reverts_adoption_id`
- 被回退 adoption 标记为 `reverted`
- 对应 checkpoint 可视需要标记为 `reverted` 或恢复为 `candidate`。首版建议：**checkpoint 状态保持历史事实，不自动恢复为 candidate；恢复候选需显式重新 snap**

---

## 10. CLI contract：Surface 与 Canonical 映射

### 10.1 映射原则

Surface CLI 是人类高频入口；Canonical CLI 是稳定语义 contract。

建议首版内部即使只实现一套路由，也要在概念上保持如下映射：

- `itt start` = `itt intent create --activate`
- `itt snap` = `itt checkpoint create --select`
- `itt adopt` = `itt adoption create`
- `itt revert` = `itt adoption revert`

### 10.2 实现建议

- 内部代码以 canonical action handler 为主
- surface 命令只是参数预填与 UX 包装
- 所有 JSON 返回结构围绕 canonical object 设计

这会显著降低后续扩展子命令时的返工概率。

---

## 11. Git linkage contract

## 11.1 首版记录哪些 Git 字段

所有 checkpoint 与 adoption 至少记录：

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

### 11.2 `linkage_quality` 取值

- `stable_commit`：当前 HEAD 已存在可用提交
- `working_tree_context`：仅记录到当前工作区上下文，未绑定稳定 commit
- `explicit_ref`：用户通过 `--link-git <hash|HEAD>` 显式指定
- `none`：不在 Git 仓库中，或 Git 不可用

### 11.3 行为规则

#### checkpoint

- 允许在 dirty working tree 上创建
- 不要求必须有 commit
- 若有 HEAD，记录 HEAD；若无，则记录 `null` 并给出 linkage warning

#### adoption

- 默认尽量绑定当前 HEAD
- dirty working tree 允许继续，但文本输出与 JSON 中必须给出 warning 或质量降级
- strict mode 下可要求 clean tree + stable commit，否则失败

### 11.4 strict mode

首版建议支持以下配置位：

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
- 否则返回 `state conflict` 或 `general failure`，推荐使用 `state conflict`

---

## 12. 读命令 JSON contract

## 12.1 `itt status --json`

`status` 面向人，但其 JSON 仍必须稳定。

建议返回：

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

### 12.2 `itt inspect --json`

`inspect` 是机器标准入口，必须比 `status` 更完整且字段更稳定。

建议返回：

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

### 12.3 稳定性要求

- 顶层字段必须固定
- 缺失对象时返回 `null`，不要随意省略字段
- 列表为空时返回 `[]`
- 所有枚举值必须文档化，不允许半自由文本

---

## 13. 写命令 JSON contract

所有写命令支持 `--json`，并返回统一结构：

```json
{
  "ok": true,
  "object": "checkpoint",
  "action": "create",
  "id": "cp-001",
  "state_changed": true,
  "result": { ...object payload... },
  "next_action": {
    "command": "itt adopt -m \"...\"",
    "reason": "Checkpoint created and selected"
  },
  "warnings": []
}
```

### 13.1 最低要求字段

- `ok`
- `object`
- `action`
- `id`
- `state_changed`
- `result`
- `warnings`

### 13.2 `--id-only`

支持机器调用场景：

```text
cp-001
```

要求：

- 仅输出对象 id
- 不附带说明文本
- 错误时仍走 stderr / 非零 exit code

---

## 14. 错误模型与 exit code

## 14.1 exit code 规范

首版固定：

- `0`：success
- `1`：general failure
- `2`：invalid input
- `3`：state conflict
- `4`：object not found

### 14.2 JSON 错误格式

所有 `--json` 错误输出必须稳定：

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

### 14.3 推荐 error code 字符串

- `GENERAL_FAILURE`
- `INVALID_INPUT`
- `STATE_CONFLICT`
- `OBJECT_NOT_FOUND`
- `ALREADY_EXISTS`
- `NOT_INITIALIZED`
- `GIT_STATE_INVALID`

### 14.4 典型错误场景

#### `itt init` 在已初始化仓库执行

- exit code: `1` 或 `2`
- 建议：`1` 若视为环境状态冲突；`2` 若视为参数无关。首版建议：`1`

#### 无 active intent 时执行 `itt snap`

- exit code: `3`
- code: `STATE_CONFLICT`

#### checkpoint id 不存在

- exit code: `4`
- code: `OBJECT_NOT_FOUND`

#### 参数缺失或非法 flag

- exit code: `2`
- code: `INVALID_INPUT`

---

## 15. 幂等语义

## 15.1 为什么要尽早定义

agent / automation 最怕“重复执行导致重复对象”。因此首版必须明确哪些命令天然非幂等，哪些需要提供保护开关。

## 15.2 首版建议

### `itt start`

默认非幂等。每次执行创建新 intent。

可选保护：

- `--if-not-exists <dedupe-key>` 暂可不做
- 首版仅保留未来扩展位

### `itt snap`

默认非幂等。每次执行创建新 checkpoint。

### `itt adopt`

必须支持基础幂等保护：

- `--if-not-adopted`

行为：

- 若目标 checkpoint 已存在 active adoption，则返回 success-like no-op 或明确 no-op 结构
- 推荐：返回 `ok=true`、`state_changed=false`、原 adoption id

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

### `itt init`

天然幂等性应谨慎处理。首版建议：

- 默认非幂等
- 若目录已存在则失败
- 后续可增补 `--force` 或 `--if-missing`

---

## 16. Non-interactive policy

### 16.1 首版必须支持的 flag

所有核心写命令建议支持：

- `--json`
- `--id-only`
- `--yes`
- `--no-interactive`

### 16.2 行为规则

当使用 `--no-interactive` 时：

- 不允许进入选择器、prompt 或确认问答
- 遇到状态不明确时直接失败
- 必须返回可消费错误对象

这条规则尤其适用于：

- `itt adopt`
- `itt checkpoint select`
- `itt revert`

### 16.3 模糊默认值处理

例如多个 candidate 存在但无唯一 current checkpoint：

- human 模式可提示下一步
- non-interactive 模式必须直接报 `STATE_CONFLICT`

---

## 17. 输出文本规范

### 17.1 文本输出优先讲动作结果

例如：

```text
Adopted checkpoint cp-001
Intent: intent-001 Reduce onboarding confusion
Git: a91c3d2 (clean)
Next: itt log
```

### 17.2 不推荐输出

```text
Created adoption object adopt-001
```

### 17.3 输出结构建议

普通文本模式建议稳定包含：

1. 核心动作结果
2. 目标对象
3. 关键上下文（intent / git）
4. next action

---

## 18. 首版测试矩阵

## 18.1 初始化

- 未初始化仓库执行 `itt init` 成功
- 已初始化仓库重复 `itt init` 失败
- 初始化后目录结构完整

## 18.2 start

- `itt start` 创建 intent 成功
- state 中 active intent 正确更新
- 无 checkpoint 时 `workspace_status=intent_active`

## 18.3 snap

- 有 active intent 时成功创建 checkpoint
- 新 checkpoint 自动 selected
- 旧 selected checkpoint 被取消 selected
- state.current_checkpoint_id 正确更新

## 18.4 adopt

- 默认采纳 current checkpoint 成功
- adoption 正确绑定 checkpoint
- latest_adoption / last_adoption_id 正确更新
- `--if-not-adopted` 在重复执行时 no-op 正确

## 18.5 conflict

- 无 active intent 时 snap 返回 `STATE_CONFLICT`
- 无 current checkpoint 时 adopt 返回 `STATE_CONFLICT`
- 多 candidate 且默认对象不清晰时 adopt 返回 `STATE_CONFLICT`

## 18.6 inspect/status

- `status --json` 顶层字段稳定
- `inspect --json` 缺失对象时返回 `null`
- 建议下一步动作与当前状态一致

## 18.7 git linkage

- Git clean repo 下 checkpoint / adoption 记录 HEAD
- dirty working tree 下 linkage_quality 降级
- strict mode 下 dirty tree adopt 失败

---

## 19. 开发顺序建议

建议按以下顺序实现：

### Phase 1：底层对象与状态层

- `.intent/` 初始化
- id 生成器
- JSON 文件读写
- `state.json` 读写与 workspace_status 推导

### Phase 2：最小写路径

- `itt start`
- `itt snap`
- `itt adopt`

### Phase 3：最小读路径

- `itt status`
- `itt log`
- `itt inspect --json`

### Phase 4：错误模型与机器可读 contract

- exit code
- `--json`
- `--id-only`
- `--no-interactive`
- `--if-not-adopted`

### Phase 5：增强与整理

- `itt checkpoint select`
- `itt revert`
- strict mode
- 更完整的 README demo

---

## 20. 开工前冻结项清单

正式开工前，以下内容建议冻结，不再随实现临时改名：

- `.intent/` 目录名
- `state.json` 文件名
- 对象类型名：intent / checkpoint / adoption / run / decision
- ID 前缀：intent / cp / adopt / run / decision
- `workspace_status` 枚举
- `linkage_quality` 枚举
- `status --json` 顶层字段
- `inspect --json` 顶层字段
- exit code 0/1/2/3/4
- `STATE_CONFLICT` / `OBJECT_NOT_FOUND` 等错误码字符串

如果这些点不冻结，后续 README、demo、agent / Skill、IDE integration 与远端平台原型都会反复返工。

---

## 21. 一句话结论

Intent CLI 现在最需要的，不是继续扩大战略叙事，而是把本地对象层、状态机、JSON contract 与错误模型尽快冻结。

只要这层足够稳定，后续 README、agent / Skill、IntHub、远端同步、可视化 history 才会建立在硬基础上；否则每往前走一步，都会回头重构一遍语义底座。
