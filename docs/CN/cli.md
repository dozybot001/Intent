[English](../EN/cli.md) | 简体中文

# Intent CLI 统一设计文档

用途：作为 Intent CLI 的单一 source of truth。本文同时定义首版 CLI 的项目边界、命令语义、对象模型、状态机、JSON contract、错误模型和实现优先级。

## 这篇文档回答什么

- Intent CLI 在首版到底要做什么，不做什么
- 首页命令、对象模型和 human path 应该如何组织
- `.intent/` 本地对象层、`state.json`、Git linkage 应如何落地
- `status --json` / `inspect --json`、写命令返回结构、错误码与 exit code 应如何冻结

## 这篇文档不回答什么

- 为什么 agent 时代需要 Intent：见 [愿景与问题定义](vision.md)
- 长期远端协作和平台化路线
- UI、Hub、同步协议等更后续的问题

## 与其他文档的边界

- 术语定义以 [术语表](glossary.md) 为准
- 为什么需要 Intent、Intent CLI / Skill / IntHub 的长期关系，以 [愿景与问题定义](vision.md) 为准
- CLI 的设计、命令语义和实现 contract，以本文为准

## 1. 设计目标

Intent CLI 是一个构建在 Git 之上的 semantic history 工具，用来记录：

- 当前想解决什么问题
- 形成过哪些候选结果
- 最终正式采纳了什么
- 必要时如何回退这次采纳

首版不是做“大而全”的流程平台，而是先把本地最小闭环跑通：

`init -> start -> snap -> adopt -> log`

这条路径必须同时满足三件事：

- 对人：容易理解，能形成肌肉记忆
- 对开发者：本地对象层清晰、可实现、可 Git 跟踪
- 对 agent：对象、状态、JSON 和错误模型稳定可消费

Git 前提：

- V1 中 Intent 只工作在 Git worktree 内
- 非 Git 目录不是“未初始化的 Intent 仓库”，而是无效运行环境
- 在非 Git 目录中，用户应先执行 `git init` 或进入已有 Git 仓库

## 2. v1 边界

### 2.0 本节的使用方式

本节定义的是 V1 对外承诺的边界，而不是“未来可能会有”的全部想法。

理解规则：

- 写进“必须覆盖”的，属于 V1 范围
- 写进“可延后”的，不要求进入第一版交付
- 写进“首版不做”的，不应在 V1 继续扩散讨论

### 2.1 首版必须覆盖的命令

- `itt init`
- `itt start`
- `itt status`
- `itt snap`
- `itt adopt`
- `itt log`
- `itt inspect`
- `itt checkpoint select`
- `itt revert`

### 2.2 首版核心对象

- `intent`
- `checkpoint`
- `adoption`
- `state`

### 2.3 可延后对象

- `run`
- `decision`

要求：

- 目录可以先保留
- `inspect --json` 中可返回 `null` 或空列表
- 不能影响 `init -> start -> snap -> adopt -> log` 的最小闭环

### 2.4 首版不做的事

- 替代 Git 的版本控制能力
- 保存全部原始对话
- 引入远端同步命令
- 把更多对象塞进首页主路径
- 在第一版就把平台叙事做得比本地 contract 更重
- 把 CLI 扩成完整对象浏览器
- 在 V1 冻结 `log --json`、复杂过滤器、分页或完整对象浏览器语义
- 支持在非 Git 目录中初始化或运行 Intent

## 3. 首页主路径

README 首页只暴露这 6 个命令：

```bash
itt init
itt start
itt status
itt snap
itt adopt
itt log
```

最小示例：

```bash
itt init
itt start "Reduce onboarding confusion"

# explore and change code with agent...

itt snap "Landing page candidate B"
git add .
git commit -m "refine onboarding landing layout"
itt adopt -m "Adopt progressive disclosure layout"
itt log
```

跑完后用户应立刻理解：

- Git 还在正常管理代码
- Intent 记录的是更高层的采纳历史
- `start -> snap -> adopt` 比对象名更值得被记住

## 4. 对象模型与曝光顺序

首版继续保留五对象模型，但 onboarding 只暴露最少必要动作。

| 对象 | 回答的问题 | 首页是否出现 | 表层命令 | 说明 |
| --- | --- | --- | --- | --- |
| `intent` | 当前想解决什么问题 | 是 | `itt start` | 当前默认语义上下文 |
| `checkpoint` | 目前有哪些候选结果 | 是，但通过 `snap` 暴露 | `itt snap` | adoption 的直接前置对象 |
| `adoption` | 最终正式采纳了哪个候选 | 是 | `itt adopt` | semantic history 的 headline object |
| `decision` | 为什么是这个，而不是那个 | 否 | `itt decide` | 只在取舍值得沉淀时显式出现 |
| `run` | 这一轮 agent 执行做了什么 | 否 | `itt run start/end` | 更偏 agent、automation、telemetry |

设计原则：

- 对象模型可以完整
- 首页只暴露最少必要动作
- `adopt` 是系统中心动作
- 高级对象延后显现

## 5. 命令体系

### 5.1 Surface CLI

给人高频使用的短命令：

```bash
itt init
itt start
itt status
itt snap
itt adopt
itt log
itt revert
```

按需出现：

```bash
itt inspect
itt checkpoint select
itt decide
itt run start
itt run end
```

首版不提供 `itt new` alias。

### 5.2 Canonical CLI

V1 需要冻结的是“语义动作名”，不是一次性把全部对象子命令都做出来。

首版必须成立的 canonical action 只有这组：

```bash
itt intent create

itt checkpoint create
itt checkpoint select

itt adoption create
itt adoption revert

itt run start
itt run end

itt inspect
```

这组命令的意义是：

- 作为内部 handler 和机器语义的命名基线
- 为 Surface CLI 提供稳定映射
- 为后续扩展 `list/show/switch` 预留一致对象空间

V1 的对外公开命令承诺，核心仍然到这里为止。下面这些对象命令主要属于保留方向，不进入首页承诺矩阵：

```bash
itt intent list
itt intent show
itt intent switch

itt checkpoint list
itt checkpoint show

itt adoption list
itt adoption show

itt decision create
itt decision list
itt decision show

itt run start
itt run end
itt run list
itt run show
```

实现原则：

- 内部 handler 优先围绕 canonical action 组织
- Surface CLI 只做参数预填和 UX 包装
- 即使实现中提供了少量 `list/show` 辅助命令，它们也不应盖过 `init -> start -> snap -> adopt -> log` 这条主路径
- V1 不要求把保留方向里的对象子命令做成首页承诺或长期兼容承诺

当前 helper-command 说明：

- 当实现中提供 `show` 辅助命令时，可以支持 `@active`、`@current`、`@latest` 这类保留选择器，方便机器读取当前对象

### 5.3 Surface 与 Canonical 映射

| Surface CLI | Canonical 语义 |
| --- | --- |
| `itt start` | `itt intent create --activate` |
| `itt snap` | `itt checkpoint create --select` |
| `itt adopt` | `itt adoption create` |
| `itt revert` | `itt adoption revert` |

## 6. Current Object 机制

Intent CLI 保留 current object philosophy，但它主要服务 human UX，不是 automation 的主契约。

### 6.1 active intent

系统维护一个 active intent，作为默认语义上下文。

### 6.2 current checkpoint

系统维护一个 current checkpoint，作为默认候选对象。

创建新 checkpoint 时：

- 自动成为 current checkpoint

显式切换时：

```bash
itt checkpoint select cp-012
```

### 6.3 默认行为规则

人类模式：

- `itt start` 创建并切换到 active intent
- `itt snap` 创建并切换到 current checkpoint
- `itt adopt` 默认采纳 current checkpoint
- `itt status` 优先围绕 current object 组织信息

agent 模式：

- 优先显式传 `intent id` / `checkpoint id`
- 可以读取 current object，但不应把它当成强契约
- 推荐先 `itt inspect --json` 再执行写操作

### 6.4 冲突处理

如果存在多个未采纳候选且默认对象不清晰：

- `itt adopt` 不应猜测
- 返回 `STATE_CONFLICT`
- 输出明确 next action，例如 `itt checkpoint select`

## 7. 本地目录结构

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

### 7.1 目录职责

| 路径 | 职责 |
| --- | --- |
| `.intent/config.json` | 仓库级配置，不保存运行态上下文 |
| `.intent/state.json` | 当前 workspace 的活动状态和默认对象引用 |
| `.intent/intents/` | intent 对象文件 |
| `.intent/checkpoints/` | checkpoint 对象文件 |
| `.intent/adoptions/` | adoption 对象文件 |
| `.intent/runs/` | run 对象文件 |
| `.intent/decisions/` | decision 对象文件；首版可为空 |

### 7.2 文件组织原则

- 一个对象对应一个 JSON 文件
- 文件名默认等于对象 id，例如 `intent-001.json`
- 不使用单一大数据库文件
- 首版不依赖 sqlite
- 文件内容必须可读、可 Git 跟踪、可被其他工具消费

### 7.3 `config.json` contract

首版 `config.json` 至少包含：

```json
{
  "schema_version": "0.1",
  "git": {
    "strict_adoption": false
  }
}
```

规则：

- `config.json` 只保存仓库级配置，不保存运行态上下文
- V1 只冻结 `schema_version` 和 `git.strict_adoption`
- 其他配置项不进入首版 contract

## 8. 命名与 ID 规则

### 8.1 ID 前缀

| 对象 | 前缀示例 |
| --- | --- |
| intent | `intent-001` |
| checkpoint | `cp-001` |
| adoption | `adopt-001` |
| run | `run-001` |
| decision | `decision-001` |

### 8.2 生成规则

- 首版使用单仓库内单调递增序号
- 每类对象独立递增
- 删除对象后不复用旧 id
- 已分配 id 在不同执行间必须稳定

### 8.3 显示名与标题分离

- 机器标识使用 `id`
- 面向人展示时同时显示 `id` 与 `title`

示例：

```text
intent-003  Reduce onboarding confusion
cp-012      Landing page candidate B
```

## 9. 通用对象 schema

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

字段说明：

| 字段 | 说明 |
| --- | --- |
| `id` | 对象唯一标识 |
| `object` | 对象类型字符串，不允许省略 |
| `schema_version` | 首版固定为 `0.1` |
| `created_at` / `updated_at` | RFC3339 UTC 时间戳 |
| `title` | 面向人的短标题 |
| `summary` | 可选摘要；首版允许为空字符串 |
| `status` | 枚举值，不允许自由文本 |
| `intent_id` | 除 intent 自身外，其余对象必须指向所属 intent |
| `run_id` | 首版可为 `null` |
| `git` | Git 关联上下文 |
| `metadata` | 扩展字段；首版核心逻辑不得依赖 |

## 10. 对象级 contract

### 10.1 Intent

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

### 10.2 Checkpoint

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
- adoption 成功后，对应 checkpoint 更新为：
  `status=adopted`，`adopted=true`，`adopted_by=<adoption_id>`，`selected=false`
- revert 成功后，被回退的 checkpoint 更新为：
  `status=reverted`，`adopted=false`，`adopted_by=null`，`selected=false`
- V1 不自动写入 `superseded`；该状态保留给后续版本或显式迁移逻辑

### 10.3 Adoption

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
  "run_id": null,
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
- 新创建的 revert record `status=active`
- 被回退 adoption 标记为 `reverted`
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
  "run_id": null,
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

### 10.4 Run

```json
{
  "id": "run-001",
  "object": "run",
  "schema_version": "0.1",
  "created_at": "2026-03-15T14:05:00Z",
  "updated_at": "2026-03-15T14:25:00Z",
  "title": "Agent exploration",
  "summary": "",
  "status": "active",
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

`status` 枚举：

- `active`
- `completed`

约束：

- `itt run start` 要求存在 active intent
- `itt run start` 创建新的 run object，并设置 `state.active_run_id`
- V1 同一时间最多只允许一个 active run
- `itt run end` 将 active run 标记为 `completed`
- `itt run end` 清空 `state.active_run_id`
- 在 active run 期间创建的 checkpoint 和 adoption 应记录对应的 `run_id`

## 11. `state.json` contract

首版 `state.json` 至少包含：

```json
{
  "schema_version": "0.1",
  "mode": "human",
  "active_intent_id": "intent-001",
  "active_run_id": null,
  "current_checkpoint_id": "cp-001",
  "last_adoption_id": null,
  "workspace_status": "candidate_ready",
  "updated_at": "2026-03-15T14:20:00Z"
}
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `mode` | `human` / `agent` / `ci` |
| `active_intent_id` | 当前默认 intent |
| `active_run_id` | 当前 run；首版可为 `null` |
| `current_checkpoint_id` | 当前默认 checkpoint |
| `last_adoption_id` | 最近一次 adoption |
| `workspace_status` | 当前 workspace 聚合状态 |
| `updated_at` | 最近刷新时间 |

`workspace_status` 枚举：

- `idle`
- `blocked_no_active_intent`
- `intent_active`
- `candidate_ready`
- `adoption_recorded`
- `conflict_multiple_candidates`

推导规则：

| 状态 | 触发条件 |
| --- | --- |
| `idle` | 尚未创建任何 intent，或 state 尚未初始化完整 |
| `blocked_no_active_intent` | 当前无 `active_intent_id` |
| `intent_active` | 有 active intent，但没有 current checkpoint |
| `candidate_ready` | 有 current checkpoint，且它尚未被 adoption，适合作为推荐采纳对象 |
| `adoption_recorded` | 最近一次动作是 adoption 或 revert record，且当前没有更高优先级冲突 |
| `conflict_multiple_candidates` | 存在多个未采纳 candidate，且没有唯一 `selected=true` 的 current checkpoint |

更新原则：

- 每次成功写命令后必须刷新 `updated_at`
- `state.json` 是当前快照，不是历史记录
- 历史事件必须由对象文件承载，不能只存在于 `state.json`

## 12. 核心写命令行为规则

### 12.1 `itt init`

作用：初始化当前 Git 仓库的 `.intent/` 元数据层。

要求：

- 要求当前目录位于 Git worktree 中
- 创建 `.intent/`
- 创建必要子目录
- 创建 `config.json`
- 创建 `state.json`
- 若已存在，默认不覆盖，返回可识别错误
- 若当前目录不在 Git worktree 中，返回 `GIT_STATE_INVALID`

Git 前置规则：

- V1 所有命令都要求当前目录位于 Git worktree 中
- Git 环境校验优先于 `.intent/` 初始化校验
- 因此非 Git 目录下不返回 `NOT_INITIALIZED`，统一返回 `GIT_STATE_INVALID`

### 12.2 `itt start <title>`

作用：开始处理一个问题，并创建新的 active intent。

示例：

```bash
itt start "Reduce onboarding confusion"
```

canonical form：

```bash
itt intent create --title "Reduce onboarding confusion"
```

规则：

- 创建新的 intent object
- 设置为 `active_intent_id`
- 将 `current_checkpoint_id` 置空
- `workspace_status=intent_active`
- 首版默认每次执行都创建新 intent，不做幂等

### 12.3 `itt snap <title>`

作用：保存一个 checkpoint 的表层快路径命令。

示例：

```bash
itt snap "Landing page candidate B"
```

canonical form：

```bash
itt checkpoint create --title "Landing page candidate B"
```

规则：

- 要求存在 `active_intent_id`
- 创建 checkpoint object
- 自动成为 `current_checkpoint_id`
- 默认 `selected=true`
- 若原 current checkpoint 存在，则旧 checkpoint 变为 `selected=false`
- `workspace_status=candidate_ready`

### 12.4 `itt checkpoint select <id>`

规则：

- 要求 checkpoint 存在且属于 active intent
- 将目标 checkpoint `selected=true`
- 其他同 intent checkpoint `selected=false`
- 更新 `current_checkpoint_id`

### 12.5 `itt adopt`

作用：正式采纳某个 checkpoint。

推荐快路径：

```bash
itt adopt -m "Adopt progressive disclosure layout"
```

显式路径：

```bash
itt adopt --checkpoint cp-012 -m "Adopt progressive disclosure layout"
```

canonical form：

```bash
itt adoption create \
  --checkpoint cp-012 \
  --title "Adopt progressive disclosure layout"
```

规则：

- 默认采用 `current_checkpoint_id`
- 若无 current checkpoint，返回 `STATE_CONFLICT`
- 若存在多个 candidate 且当前对象不明确，返回 `STATE_CONFLICT`
- 成功后创建 adoption object
- 更新 checkpoint adoption 字段：
  `status=adopted`，`adopted=true`，`adopted_by=<adoption_id>`，`selected=false`
- 将 `current_checkpoint_id` 置空
- 更新 `last_adoption_id`
- `workspace_status=adoption_recorded`
- 成功输出应强调“采纳了一个候选结果”，而不是“创建了 adoption 对象”

### 12.6 `itt revert`

规则：

- 默认回退最近一条 active adoption
- 若无 active adoption，返回 object/state 错误
- 创建一条新的 adoption object 作为 revert record，引用 `reverts_adoption_id`
- 新 revert record 继承目标 adoption 的 `intent_id` 与 `checkpoint_id`
- 新 revert record `status=active`
- 被回退 adoption 标记为 `reverted`
- 被回退的 checkpoint 更新为：
  `status=reverted`，`adopted=false`，`adopted_by=null`，`selected=false`
- `current_checkpoint_id` 保持 `null`
- 更新 `last_adoption_id`
- `workspace_status=adoption_recorded`
- checkpoint 状态保持历史事实，不自动恢复为 `candidate`

### 12.7 `itt run start`

规则：

- 要求存在 active intent
- 创建 `status=active` 的 run object
- 设置 `state.active_run_id`
- 不改变 `workspace_status`
- 若已有 active run，返回 `STATE_CONFLICT`

### 12.8 `itt run end`

规则：

- 要求存在 active run
- 将 run object 标记为 `status=completed`
- 清空 `state.active_run_id`
- 不改变 `workspace_status`
- 若不存在 active run，返回 object/state 错误

### 12.7 `itt status`

作用：给人看当前 semantic workspace 状态，并推荐下一步动作。

它必须优先回答四件事：

- 当前在处理哪个 intent
- 当前默认对象是什么
- 当前整体状态是什么
- 下一步最合理的动作是什么

`status` 不是半结构化的 `inspect`。它首先是 human entrypoint。

V1 边界：

- 默认文本输出只聚焦“当前”，不展开历史列表
- 输出应围绕 4 个块组织：active intent、current checkpoint、workspace status、next action
- 若存在 latest adoption，可作为补充块显示
- `status --json` 只返回轻量 workspace summary，不返回 `pending_items` 或对象数组
- `status` 不承担对象枚举、时间线回放或完整上下文导出职责

### 12.8 `itt inspect`

作用：给机器输出稳定、完整、可消费的语义上下文。

设计定位：

- `inspect` 是 agent、Skill、IDE、automation 的标准入口
- 目标不是“好看”，而是“稳定”
- 缺失对象时应返回 `null`，而不是随意省略字段

V1 边界：

- 稳定 contract 只对 `inspect --json` 冻结
- `inspect` 返回的是当前 workspace snapshot，不是全量 semantic history dump
- 允许包含 `pending_items` 和 `suggested_next_actions` 这类派生信息
- 不返回 intents / checkpoints / adoptions 的完整列表
- 不承担替代 `log` 的时间线职责

### 12.9 `itt log`

作用：给人查看 semantic history，尤其是采纳历史。

首版边界：

- `log` 以 human-readable 输出为主
- 默认按时间倒序展示 adoption / revert 时间线
- 一条记录至少展示：时间、adoption id、标题、checkpoint 引用、intent 引用、git head
- 可以附带 checkpoint 和 intent 标题，帮助人快速理解“采纳了什么”
- 若仓库里还没有 adoption，返回明确 empty state，并给出下一步建议
- 不退化为对象文件列表
- V1 不定义 `log --json`
- V1 不做 `log --intent`、`log --checkpoint`、分页、复杂过滤器
- 人类输出示例见下文“输出文案基线与示例”

## 13. Git linkage contract

### 13.1 必须记录的 Git 字段

```json
{
  "git": {
    "branch": "main",
    "head": "a91c3d2",
    "working_tree": "clean|dirty|unknown",
    "linkage_quality": "stable_commit|working_tree_context|explicit_ref"
  }
}
```

### 13.2 `linkage_quality` 取值

- `stable_commit`
- `working_tree_context`
- `explicit_ref`

### 13.3 行为规则

checkpoint：

- 允许在 dirty working tree 上创建
- 不要求必须有 commit
- 若有 HEAD，记录 HEAD；若无，则记录 `null` 并给出 warning

adoption：

- 默认尽量绑定当前 HEAD
- dirty working tree 允许继续，但必须给出 warning 或质量降级
- strict mode 下可要求 clean tree + stable commit

补充说明：

- V1 不在非 Git 目录中运行任何 Intent 命令
- 非 Git 目录的错误统一在命令入口处以 `GIT_STATE_INVALID` 返回，而不是落到 Git linkage 降级状态

### 13.4 strict mode

首版将 `strict_adoption` 作为 V1 范围内但靠后的能力保留在 contract 中：

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

## 14. 读命令 JSON contract

### 14.1 `itt status --json`

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
  "active_run": null,
  "current_checkpoint": {
    "id": "cp-001",
    "title": "Landing page candidate B",
    "status": "candidate"
  },
  "latest_adoption": null,
  "workspace_status": "candidate_ready",
  "workspace_status_reason": "A current checkpoint is available for adoption.",
  "git": {
    "branch": "main",
    "head": "a91c3d2",
    "working_tree": "clean"
  },
  "next_action": {
    "command": "itt adopt --checkpoint cp-001 -m \"Adopt candidate\"",
    "args": ["adopt", "--checkpoint", "cp-001", "-m", "Adopt candidate"],
    "reason": "Current checkpoint is ready for adoption."
  },
  "warnings": []
}
```

### 14.2 `itt inspect --json`

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
    "last_adoption_id": null,
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
  "latest_adoption": null,
  "latest_event": null,
  "candidate_checkpoints": [
    {
      "id": "cp-001",
      "title": "Landing page candidate B",
      "status": "candidate",
      "selected": true,
      "adopted": false
    }
  ],
  "workspace_status_reason": "A current checkpoint is available for adoption.",
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
      "args": ["adopt", "--checkpoint", "cp-001", "-m", "Adopt candidate"],
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

### 14.3 稳定性要求

- 顶层字段必须固定
- 缺失对象时返回 `null`
- 列表为空时返回 `[]`
- 所有枚举值必须文档化

空值规则：

- 若当前目录不在 Git worktree 中，`status --json` 与 `inspect --json` 返回错误对象：
  `ok=false`，`error.code=GIT_STATE_INVALID`
- 若 `.intent/` 尚未初始化，`status --json` 与 `inspect --json` 返回错误对象：
  `ok=false`，`error.code=NOT_INITIALIZED`
- 在成功返回中，`status --json` 必须始终包含这些顶层字段：
  `ok`、`object`、`schema_version`、`active_intent`、`current_checkpoint`、`latest_adoption`、`workspace_status`、`workspace_status_reason`、`git`、`next_action`、`warnings`
- 其中 `active_intent`、`current_checkpoint`、`latest_adoption`、`next_action` 可为 `null`
- `git` 必须始终为对象；`warnings` 必须始终为数组
- 在成功返回中，`inspect --json` 必须始终包含这些顶层字段：
  `ok`、`object`、`schema_version`、`mode`、`state`、`active_intent`、`active_run`、`current_checkpoint`、`latest_adoption`、`latest_event`、`candidate_checkpoints`、`workspace_status_reason`、`pending_items`、`suggested_next_actions`、`git`、`warnings`
- `state.active_intent_id`、`state.active_run_id`、`state.current_checkpoint_id`、`state.last_adoption_id` 可为 `null`
- `active_intent`、`active_run`、`current_checkpoint`、`latest_adoption`、`latest_event` 可为 `null`
- `candidate_checkpoints`、`pending_items`、`suggested_next_actions`、`warnings` 必须始终为数组
- `workspace_status_reason` 必须始终为字符串
- `next_action` 与 `suggested_next_actions` 若存在，必须同时包含 `command`、`args`、`reason`

成功返回下的最低状态约定：

| 状态 | `status --json` | `inspect --json` |
| --- | --- | --- |
| `idle` | `active_intent=null`、`current_checkpoint=null`、`latest_adoption=null`、`next_action` 指向 `itt start` | 对应对象为 `null`，`candidate_checkpoints=[]` |
| `blocked_no_active_intent` | `active_intent=null`、`current_checkpoint=null` | 对应对象为 `null`，数组字段为 `[]` |
| `intent_active` | `current_checkpoint=null` | `current_checkpoint=null`，`candidate_checkpoints=[]`，`pending_items=[]` |
| `candidate_ready` | `current_checkpoint` 为对象，`next_action` 指向 `itt adopt` | `current_checkpoint` 为对象，`candidate_checkpoints` 至少包含当前 candidate |
| `adoption_recorded` | `current_checkpoint=null` | `state.current_checkpoint_id=null`，`current_checkpoint=null`，`latest_event` 指向 adoption 或 revert |

## 15. 写命令 JSON contract

所有写命令支持 `--json`，并返回统一结构：

```json
{
  "ok": true,
  "object": "checkpoint",
  "action": "create",
  "id": "cp-001",
  "state_changed": true,
  "workspace_status": "candidate_ready",
  "workspace_status_reason": "A current checkpoint is available for adoption.",
  "result": {},
  "next_action": {
    "command": "itt adopt --checkpoint cp-001 -m \"Adopt candidate\"",
    "args": ["adopt", "--checkpoint", "cp-001", "-m", "Adopt candidate"],
    "reason": "Checkpoint created and selected"
  },
  "warnings": []
}
```

最低要求字段：

- `ok`
- `object`
- `action`
- `id`
- `state_changed`
- `workspace_status`
- `workspace_status_reason`
- `result`
- `warnings`

若存在 `next_action`，其最低字段为：

- `command`
- `args`
- `reason`

### 15.1 `--id-only`

支持机器调用场景：

```text
cp-001
```

要求：

- 仅输出对象 id
- 不附带说明文本
- 错误时仍走 stderr / 非零 exit code

### 15.2 基础参数边界

V1 参数边界：

- `start`、`snap`、`adopt`、`revert`、`run start`、`run end` 必须支持 `--json`
- `start`、`snap`、`adopt`、`revert`、`run start`、`run end` 必须支持 `--id-only`
- `init`、`start`、`snap`、`adopt`、`revert`、`run start`、`run end`、`checkpoint select` 必须支持 `--no-interactive`

`itt adopt` 额外必须支持：

- `--if-not-adopted`
- `--checkpoint <id>`
- `--link-git <hash|HEAD>`

公开语法冻结：

- V1 只冻结 `itt adopt --checkpoint <id>` 这一种显式 checkpoint 指定语法
- V1 不支持 `itt adopt <checkpoint-id>` 这种位置参数写法

V1 不要求：

- `--yes`
- 全局 `--verbose`
- 全局 `--quiet`
- 为 `log` 增加专用过滤 flags

## 16. 错误模型与 exit code

### 16.1 exit code

| code | 含义 |
| --- | --- |
| `0` | success |
| `1` | general failure |
| `2` | invalid input |
| `3` | state conflict |
| `4` | object not found |

### 16.2 JSON 错误格式

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

### 16.3 V1 error code 集合

- `GENERAL_FAILURE`
- `INVALID_INPUT`
- `STATE_CONFLICT`
- `OBJECT_NOT_FOUND`
- `ALREADY_EXISTS`
- `NOT_INITIALIZED`
- `GIT_STATE_INVALID`

### 16.4 典型错误场景

| 场景 | exit code | error code |
| --- | --- | --- |
| 非 Git 目录执行任意命令 | `1` | `GIT_STATE_INVALID` |
| 已初始化仓库重复执行 `itt init` | `1` | `ALREADY_EXISTS` |
| 无 active intent 时执行 `itt snap` | `3` | `STATE_CONFLICT` |
| checkpoint id 不存在 | `4` | `OBJECT_NOT_FOUND` |
| 参数缺失或非法 flag | `2` | `INVALID_INPUT` |

## 17. 幂等与 non-interactive

### 17.1 幂等语义

`itt start`

- 默认非幂等
- 每次执行创建新 intent

`itt snap`

- 默认非幂等
- 每次执行创建新 checkpoint

`itt adopt`

- 必须支持 `--if-not-adopted`
- 若目标 checkpoint 已存在 active adoption，返回 success-like no-op 结构

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

- V1 定义为非幂等
- 若目录已存在则失败

### 17.2 non-interactive policy

规则：

- 不允许进入选择器、prompt 或确认问答
- 遇到状态不明确时直接失败
- 必须返回稳定错误对象
- 既然 V1 不进入交互确认流，命令正确性不能依赖 `--yes`

多个 candidate 并存但无唯一 current checkpoint 时：

- human 模式可提示下一步
- non-interactive 模式必须直接报 `STATE_CONFLICT`

## 18. Agent-Friendly 要求

- 所有读命令支持 `--json`
- 所有写命令返回稳定结果结构
- 所有核心写命令支持 non-interactive 模式
- 所有核心写命令支持基础幂等保护
- `inspect --json` 是标准上下文入口

推荐 agent 调用顺序：

1. `itt inspect --json`
2. 判断 context 和 pending actions
3. 显式执行对象命令
4. 再次 `itt inspect --json` 验证状态变化

补充边界：

- V1 agent 集成的写入口，优先走 Surface CLI + 显式 flag，或其对应 canonical action
- agent 不应依赖文本 `status` / `inspect` 输出做稳定解析
- 若只需要当前摘要，用 `status --json`
- 若需要稳定上下文和待办推导，用 `inspect --json`

## 19. 输出文案原则

CLI 文案必须优先讲动作结果，而不是对象创建细节。

不推荐：

```text
Created adoption object adopt-007
```

推荐：

```text
Adopted checkpoint cp-012
Intent: Reduce onboarding confusion
Git: a91c3d2
Next: itt log
```

用户应该优先看到：

- 做成了什么动作
- 对哪个对象生效
- 当前处于什么状态
- 下一步该做什么

### 19.1 Human Text Contract

V1 不冻结逐字逐句的文案，但冻结输出的信息层级和组织方式。

规则：

- 第一行必须先讲结果，不先讲对象创建细节
- 接下来优先展示与当前动作直接相关的对象引用
- `Git:` 只在有帮助时出现，不强制每个命令都显示完整 Git 上下文
- `Next:` 是默认收尾行，用来提示下一步最合理动作
- `Warning:` 仅在存在质量降级、dirty working tree 或状态风险时出现
- 可恢复的人类错误输出可以附带 `Error:` 行，但第一行仍应先讲“发生了什么”
- 缺失信息直接省略，不用输出 `null`、`N/A` 之类占位文本

推荐字段顺序：

- 动作 headline
- `Intent:`
- `Checkpoint:` / `Adoption:`
- `Status:` / `Git:`
- `Warning:`
- `Error:`
- `Next:`

空状态与错误状态规则：

- empty state 用中性 headline，不用 `Error:` 开头
- 可恢复错误先说明阻塞原因，再给出明确下一步
- 若错误直接对应稳定 error code，可在第二屏或下一行显示 `Error: <CODE>`
- human text 不需要展示 exit code
- `status` 和 `log` 即使在 empty state，也应尽量给出具体命令作为下一步

### 19.2 Human Output Examples

以下示例是 V1 人类文本输出的基线，重点冻结“信息结构”和“强调顺序”。

`itt init`

```text
Initialized Intent in .intent/
Git: main @ a91c3d2
Next: itt start "Describe the problem"
```

`itt start "Reduce onboarding confusion"`

```text
Started intent intent-001
Title: Reduce onboarding confusion
Status: intent_active
Next: itt snap "First candidate"
```

`itt snap "Landing page candidate B"`

```text
Saved checkpoint cp-001
Intent: intent-001  Reduce onboarding confusion
Checkpoint: Landing page candidate B
Git: main @ a91c3d2 (dirty)
Next: itt adopt -m "Adopt progressive disclosure layout"
```

`itt adopt -m "Adopt progressive disclosure layout"`

```text
Adopted checkpoint cp-001
Intent: intent-001  Reduce onboarding confusion
Adoption: adopt-001  Adopt progressive disclosure layout
Git: a91c3d2
Next: itt log
```

`itt status`

```text
Semantic workspace
Intent: intent-001  Reduce onboarding confusion
Current checkpoint: cp-001  Landing page candidate B
Status: candidate_ready
Next: itt adopt -m "Adopt candidate"
```

`itt status` empty state

```text
Semantic workspace
Status: idle
No active intent
Next: itt start "Describe the problem"
```

`itt status` not initialized

```text
Intent is not initialized in this repository
Error: NOT_INITIALIZED
Next: itt init
```

`itt status` outside Git worktree

```text
Intent requires a Git repository
Error: GIT_STATE_INVALID
Next: git init
```

`itt status` conflict state

```text
Semantic workspace
Intent: intent-001  Reduce onboarding confusion
Status: conflict_multiple_candidates
Warning: Multiple candidate checkpoints exist and no unique current checkpoint is selected
Next: itt checkpoint select cp-002
```

`itt log`

```text
Semantic history

2026-03-15 14:20  adopt-001  Adopt progressive disclosure layout
  Intent: intent-001  Reduce onboarding confusion
  Checkpoint: cp-001  Landing page candidate B
  Git: a91c3d2

2026-03-15 14:30  adopt-002  Revert progressive disclosure layout
  Intent: intent-001  Reduce onboarding confusion
  Checkpoint: cp-001  Landing page candidate B
  Reverts: adopt-001
  Git: b02d441
```

`itt log` empty state

```text
Semantic history
No adoptions recorded yet
Next: itt status
```

`itt log` not initialized

```text
Intent is not initialized in this repository
Error: NOT_INITIALIZED
Next: itt init
```

`itt log` outside Git worktree

```text
Intent requires a Git repository
Error: GIT_STATE_INVALID
Next: git init
```

`itt revert`

```text
Reverted adoption adopt-001
Intent: intent-001  Reduce onboarding confusion
Checkpoint: cp-001  Landing page candidate B
Adoption: adopt-002  Revert progressive disclosure layout
Next: itt log
```

`itt adopt` conflict error

```text
Cannot adopt because the current checkpoint is not unambiguous
Intent: intent-001  Reduce onboarding confusion
Error: STATE_CONFLICT
Next: itt checkpoint select cp-002
```

`itt snap` without active intent

```text
Cannot save a checkpoint without an active intent
Error: STATE_CONFLICT
Next: itt start "Describe the problem"
```

any command outside Git worktree

```text
Intent requires a Git repository
Error: GIT_STATE_INVALID
Next: git init
```

## 20. 首版测试矩阵

- 初始化：`itt init` 首次成功、重复失败、目录结构正确
- start：创建 intent 成功，`active_intent_id` 更新，`workspace_status=intent_active`
- snap：创建 checkpoint 成功，自动 selected，旧 selected 取消，`current_checkpoint_id` 更新
- adopt：默认采纳 current checkpoint 成功，checkpoint 与 adoption 正确关联，`last_adoption_id` 更新
- revert：创建新的 revert record，原 adoption 标记为 `reverted`，`last_adoption_id` 更新
- conflict：无 active intent 时 `snap` 失败；无 current checkpoint 时 `adopt` 失败；多 candidate 且默认对象不清晰时 `adopt` 失败
- inspect/status：`status --json` 和 `inspect --json` 顶层字段稳定；缺失对象返回 `null`
- object transitions：checkpoint 在 adopt 后变为 `adopted`，在 revert 后变为 `reverted`；adoption 后 `current_checkpoint_id=null`
- config/init：`config.json` schema 正确；非 Git 目录 `itt init` 返回 `GIT_STATE_INVALID`
- git prerequisite：所有命令在非 Git 目录下统一返回 `GIT_STATE_INVALID`，优先于 `NOT_INITIALIZED`
- human output：`init`、`start`、`snap`、`adopt`、`status`、`log`、`revert` 的文本输出保持既定信息层级，headline 与 `Next:` 行正确
- empty/error output：`status` 的 idle / not initialized / outside Git / conflict 文案正确；`log` 的 empty / not initialized / outside Git 文案正确；可恢复错误包含明确 `Next:`
- git linkage：clean repo 记录 HEAD；dirty tree 质量降级；strict mode 下 dirty tree adopt 失败

## 21. 建议实现顺序

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

## 22. 开工前冻结项

- `.intent/` 目录名
- `config.json` 最小 schema：`schema_version`、`git.strict_adoption`
- `state.json` 文件名
- V1 对外命令面：`init/start/status/snap/adopt/log/inspect/checkpoint select/revert`
- 所有命令仅在 Git worktree 中运行；非 Git 目录统一返回 `GIT_STATE_INVALID`
- 对象类型名：`intent` / `checkpoint` / `adoption` / `run` / `decision`
- ID 前缀：`intent` / `cp` / `adopt` / `run` / `decision`
- checkpoint 在 `adopt/revert` 后的状态迁移
- `workspace_status` 枚举
- `linkage_quality` 枚举
- `itt adopt --checkpoint <id>` 是唯一显式 checkpoint 指定语法
- `status --json` 顶层字段
- `inspect --json` 顶层字段
- `log` 只做人类时间线，不冻结 `log --json`
- exit code `0/1/2/3/4`
- `STATE_CONFLICT` / `OBJECT_NOT_FOUND` 等错误码字符串

## 23. 一句话结论

首版最该冻结的不是更大的叙事，而是单一的 CLI source of truth：本地对象层、状态机、JSON contract、错误模型，以及围绕 `start -> snap -> adopt` 的最小可用工作流。
