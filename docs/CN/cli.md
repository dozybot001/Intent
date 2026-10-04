# Intent CLI

中文 | [English](../EN/cli.md)

Intent CLI 是 Intent 的本地 semantic-history CLI。它只管理三类对象：

- `intent`：可恢复的目标
- `snap`：语义快照 — 做了什么、为什么
- `decision`：跨 intent 持续生效的长期约束

命令面刻意保持很小：

- 恢复：`itt inspect`
- 诊断：`itt doctor`
- 浏览：IntHub

## 命令

### Global

| 命令 | 作用 |
|---|---|
| `itt version` | 输出 CLI 版本 |
| `itt init` | 在项目目录初始化 `.intent/`；Git 可选 |
| `itt inspect [--intent ID] [--history N]` | 恢复视图，返回目标原因、最新 Snap、可选的受限历史、有效 Decision 和完整图诊断 |
| `itt doctor` | 返回同一套完整对象图诊断，并显式给出 `healthy` 结果 |

### Intent

| 命令 | 作用 |
|---|---|
| `itt intent create WHAT [--why W]` | 创建 intent。自动挂载所有 active decision。 |
| `itt intent activate [ID]` | `suspend` → `active`。补挂 active decision。唯一候选时自动推断 ID。 |
| `itt intent suspend [ID]` | `active` → `suspend`。唯一候选时自动推断 ID。 |
| `itt intent done [ID]` | `active` → `done`（终态）。唯一候选时自动推断 ID。 |
| `itt intent cancel [ID] [--reason TEXT]` | `active` / `suspend` → `cancelled`（终态）。只有一个未结束 intent 时自动推断 ID。 |

### Snap

| 命令 | 作用 |
|---|---|
| `itt snap create WHAT [--why W]` | 创建语义快照。自动挂载到 active intent；多个时需指定 `--intent ID`。 |

### Decision

| 命令 | 作用 |
|---|---|
| `itt decision create WHAT [--why W]` | 创建长期约束。自动挂载所有 active intent。 |
| `itt decision deprecate ID [--reason TEXT]` | `active` → `deprecated`（终态）。保留历史，停止未来自动挂载。 |

### 共享语义历史

Git 可选。Intent 独立保存语义历史；代码仓库的 Git origin 不参与项目身份。

| 命令 | 作用 |
|---|---|
| `itt status [--local]` | empty / up_to_date / ahead / behind / diverged；--local 可离线使用。 |
| `itt remote [-v]` | 查看独立的 IntHub 地址和项目。 |
| `itt remote add origin URL --project NAME` | 设置唯一共享远端；项目名默认取语义根目录名。 |
| `itt push [--project NAME] [--api-base-url URL] [--dry-run]` | 必要时关联项目，保存同步版本；相同内容不新增版本，预览不写远端。 |
| `itt pull [--project NAME] [--api-base-url URL] [--dry-run]` | 本地未变化可快进，本地领先保持不变；双方变化报告分歧并保留双方。 |
| `itt auth login / status / logout` | 全局账户认证，凭据由 credential helper 保存并跨项目复用。 |
| `itt hub start` | 启动本地浏览器。 |

两个本地目录配置相同 remote/project 后共享同一历史，不创建 workspace。Intent、Snap、Decision 是版本内的内容，Snap 不等于同步版本。无需暂存区、手动 commit、分支或 rebase。

版本 ID 由父版本与规范快照校验值计算。服务端事务锁定项目头，拒绝非快进覆盖。推送响应丢失时可按内容收敛，不新增重复版本。对象仍遵守追加和生命周期约束；没有强制覆盖或自动合并。

旧 workspace 同步、导出和恢复协议已移除。Git origin 不影响同步；不同副本只需选择相同 remote/project。`hub sync`、`hub link/status` 仅委托同一共享主链，没有独立协议。

实现：[共享 CLI](../../src/intent_cli/commands/shared.py)、[版本服务](../../apps/inthub_api/history.py)、[双客户端测试](../../tests/test_shared_history.py)。

## 对象模型

```mermaid
flowchart LR
  D1["🔶 Decision 1"]
  D2["🔶 Decision 2"]

  subgraph Intent1["🎯 Intent 1"]
    direction LR
    S1["📸 Snap 1"] --> S2["📸 Snap 2"] --> S3["📸 ..."]
  end

  subgraph Intent2["🎯 Intent 2"]
    direction LR
    S4["📸 Snap 1"] --> S5["📸 Snap 2"] --> S6["📸 ..."]
  end

  D1 -- auto-attach --> Intent1
  D1 -- auto-attach --> Intent2
  D2 -- auto-attach --> Intent2
```

### Snap：字段分工

```mermaid
flowchart LR
  W["what\n🤖 AI 做了什么"] --> Y["why\n💡 为什么"]
```

### 什么时候创建 snap

```mermaid
flowchart TD
  Q["用户要求记录"] --> C{有意义的里程碑？}
  C -->|是| B["✅ 创建 Snap\nwhat = 做了什么\nwhy = 为什么"]
  C -->|否| A["⏭️ 不创建\n粒度太细"]
```

### 状态机

```mermaid
stateDiagram-v2
  state Intent {
    [*] --> active
    active --> suspend
    suspend --> active
    active --> done
    active --> cancelled
    suspend --> cancelled
  }
  state Decision {
    [*] --> active2: active
    active2 --> deprecated
  }
  state Snap {
    [*] --> immutable
  }
```

## 对象 Schema

| 字段 | Intent | Snap | Decision | 说明 |
| --- | :---: | :---: | :---: | --- |
| `id` | ✓ | ✓ | ✓ | 自增零填充（`intent-001`、`snap-001`、`decision-001`） |
| `object` | ✓ | ✓ | ✓ | `"intent"`、`"snap"` 或 `"decision"` |
| `created_at` | ✓ | ✓ | ✓ | ISO 8601 UTC 时间戳 |
| `what` | ✓ | ✓ | ✓ | Intent/Decision: 简短主题。Snap: 做了什么（简洁行为描述）。 |
| `origin` | ✓ | ✓ | ✓ | 从环境自动检测（如 `claude-code`、`cursor`、`codex-desktop`） |
| `why` | ✓ | ✓ | ✓ | Intent: 为什么要做。Snap: 为什么这么做。Decision: 为什么有这个约束。 |
| `status` | ✓ | | ✓ | Intent: `active` / `suspend` / `done` / `cancelled`。Decision: `active` / `deprecated`。 |
| `intent_id` | | ✓ | | 所属 intent |
| `snap_ids` | ✓ | | | 有序子 snap 列表 |
| `decision_ids` | ✓ | | | 关联 decision（创建时自动挂载） |
| `intent_ids` | | | ✓ | 关联 intent（创建时自动挂载） |
| `reason` | ✓ | | ✓ | intent 取消或 decision 废弃的原因（通过 `--reason` 设置） |

通过 CLI 创建后，`what`、`why`、`origin`、`created_at` 等描述性字段视为写一次。
后续命令可能推进 `status`，补充 `reason`，以及追加自动维护的关系字段（如 `snap_ids`、`decision_ids`、`intent_ids`）。

### Origin 检测

`origin` 从进程环境自动推断：

| 环境信号 | Origin 标签 |
|---|---|
| `ITT_ORIGIN` / `INTENT_ORIGIN` | *（自定义标签）* |
| `CURSOR_TRACE_ID` | `cursor` |
| `CODEX_INTERNAL_ORIGINATOR_OVERRIDE="Codex Desktop"` | `codex-desktop` |
| `CODEX_THREAD_ID` / `CODEX_SHELL` / `CODEX_CI` | `codex` |
| `TERM_PROGRAM=vscode` | `vscode` |
| Codespaces / GitHub Actions / Gitpod 环境变量 | `codespaces` / `github-actions` / `gitpod` |

优先级：显式 `--origin LABEL` > `ITT_ORIGIN` / `INTENT_ORIGIN` > 内置启发式。

## JSON 输出

### 标准成功包

除 `inspect` 外，成功响应统一为：

```json
{
  "ok": true,
  "action": "<command-name>",
  "result": {},
  "warnings": []
}
```

### `inspect`

`inspect` 返回接续已记录工作所需的上下文。`active_intents` 和 `suspended` 会包含目标的 `why`、存在时的完整最新 Snap 对象、`snap_count` 和 `has_more`；`active_decisions` 也会包含每项 Decision 的 `why`。在默认视图中，若 `latest_snap` 之前还有更早的 Snap，`has_more` 为 true。

```json
{
  "ok": true,
  "active_intents": [
    {
      "id": "intent-001",
      "what": "收紧发布流程",
      "why": "部分发布会让工作区处于不一致状态",
      "snap_count": 3,
      "has_more": true,
      "latest_snap": {
        "id": "snap-003",
        "object": "snap",
        "created_at": "2026-07-30T08:00:00+00:00",
        "what": "将产物发布改为原子切换",
        "why": "消费方不应观察到部分发布结果",
        "intent_id": "intent-001",
        "origin": "codex"
      }
    }
  ],
  "active_decisions": [
    {
      "id": "decision-001",
      "what": "先完成构建，再切换当前发布",
      "why": "构建失败时必须保留现行版本"
    }
  ],
  "suspended": [
    {
      "id": "intent-002",
      "what": "替换旧发布器",
      "why": "旧链路难以恢复",
      "snap_count": 0,
      "has_more": false,
      "latest_snap_id": null,
      "latest_snap": null
    }
  ],
  "warnings": []
}
```

使用 `itt inspect --intent intent-001` 可将恢复视图聚焦到一个 active 或 suspended Intent。再加正整数 `--history N` 时，响应会包含 `recent_snaps`，按记录顺序从旧到新返回最多最近 N 个完整 Snap 对象。为保持兼容，`latest_snap` 仍会保留；目标条目的 `has_more` 表示这次受限选择之前是否还有更早的 Snap。`--history` 必须与 `--intent` 同用；done 和 cancelled Intent 的历史仍通过 IntHub 浏览，不进入恢复视图。

```json
{
  "snap_count": 5,
  "has_more": true,
  "latest_snap": { "id": "snap-005" },
  "recent_snaps": [
    { "id": "snap-003" },
    { "id": "snap-004" },
    { "id": "snap-005" }
  ]
}
```

`warnings` 包含对象图校验返回的全部结构化问题，不再只检查孤立 Snap。每项问题都含有 `code`、`object`、`id` 和 `message`；对象图健康时返回空列表。在接续已记录的工作或新增语义记录前运行 `itt inspect`。

### `doctor`

`doctor` 运行与 `inspect.warnings` 相同的校验，并用显式健康标记包装结果。与其他命令的严格读取不同，它会在记录结构化解析、schema 或完整性问题后跳过当前坏对象并继续扫描，因此第一处损坏不会遮住后续问题：

```json
{
  "ok": true,
  "action": "doctor",
  "result": {
    "healthy": true,
    "issues": []
  },
  "warnings": []
}
```

### 错误包

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

## Error Code

| Code | 含义 |
| --- | --- |
| `NOT_INITIALIZED` | `.intent/` 不存在 |
| `ALREADY_EXISTS` | 运行 `init` 时 `.intent/` 已存在 |
| `STATE_CONFLICT` | 状态流转非法 |
| `OBJECT_NOT_FOUND` | 找不到对应对象 ID |
| `INVALID_INPUT` | 参数非法或缺少必填输入 |
| `INVALID_OBJECT_ID` | 显式对象 ID 不是与类型匹配的本地 ID，例如 `intent-001` |
| `UNSAFE_STORAGE` | `.intent/`、对象目录、锁或对象文件通过符号链接重定向，或越出存储边界 |
| `STORAGE_PARSE_ERROR` | 存储对象不是合法 UTF-8 JSON；`doctor` 会列出扫描到的全部解析失败 |
| `STORAGE_SCHEMA_ERROR` | 存储对象缺少必需字段，或字段类型不合法 |
| `STORAGE_INTEGRITY_ERROR` | 对象文件名与 JSON `id` 不一致；重试前需人工检查并修复报告的本地文件 |
| `STORAGE_WRITE_CONFLICT` | 创建目标已存在，或更新目标缺失、文件名不规范；不会覆盖已有对象 |
| `STORAGE_SECURITY_ERROR` | 其他存储安全不变量校验失败 |
| `NO_ACTIVE_INTENT` | `snap create`、`intent suspend` 或 `intent done` 在省略目标时，没有 `active` intent |
| `MULTIPLE_ACTIVE_INTENTS` | `snap create`、`intent suspend` 或 `intent done` 在省略目标时，存在多个 `active` intent |
| `NO_SUSPENDED_INTENT` | `intent activate` 在省略目标时，没有 `suspend` intent |
| `MULTIPLE_SUSPENDED_INTENTS` | `intent activate` 在省略目标时，存在多个 `suspend` intent |
| `NO_OPEN_INTENT` | `intent cancel` 省略目标，且没有 `active` 或 `suspend` intent |
| `MULTIPLE_OPEN_INTENTS` | `intent cancel` 省略目标，且存在多个 `active` 或 `suspend` intent |
| `WORKSPACE_BUSY` | 另一个 Intent 命令仍持有工作区写锁；可用时 details 会包含其 PID、操作和开始时间 |
| `GLOBAL_CONFIG_ERROR` | 用户级 IntHub 地址配置不合法或无法写入 |
| `CREDENTIAL_STORE_ERROR` | Git 已配置的 credential helper 无法保存或删除账户 token |
| `HUB_NOT_CONFIGURED` | 缺少 IntHub API base URL |
| `NOT_LINKED` | 远端共享项目尚未关联；正常 push 会按需自动关联 |
| `REMOTE_CHANGED` | 远端地址或项目身份变化；用 remote add 明确选择后再同步 |
| `NON_FAST_FORWARD` | 远端已变化，push 未覆盖；先 pull，分叉需人工处理 |
| `HISTORY_DIVERGED` | 本地和远端同时变化；双方历史均保留 |
| `HUB_STATE_INVALID` | 本地 remote 或 baseline 状态格式损坏 |
| `INVALID_LOCAL_SNAPSHOT` | 本地 Intent 历史不是合法完整图；pull 前应运行 `itt doctor` |
| `INVALID_REMOTE_SNAPSHOT` | 下载快照的身份、版本、schema 或对象图不合法 |
| `LOCAL_STATE_CHANGED` | 同步期间本地历史或 remote 配置发生变化；未应用覆盖 |
| `REMOTE_HISTORY_CONFLICT` | 远端历史删除、改写或不一致地改变了已记录数据 |
| `PULL_APPLY_FAILED` | 持有 workspace 锁的 journal 可恢复快照安装或恢复失败；`details.committed` 表示安装是否已到达 committed 状态，`details.recovery_required` 表示是否还需再次恢复 |
| `NETWORK_ERROR` | 无法连接 IntHub |
| `NETWORK_TIMEOUT` | IntHub 未在有界请求时间内响应；变更是否完成可能未知 |
| `SERVER_ERROR` | IntHub 返回错误或非法 JSON |

## 运行约束

- Git 可选；在 Git 仓库内 `itt init` 会将 `.intent/` 加入当前克隆的 `.git/info/exclude`，不修改团队共享的 `.gitignore`；写入失败会返回 warning
- 账户鉴权是全局的：默认服务地址属于用户级配置，token 交给 credential helper，项目级 `hub.json` 只保存地址、共享项目身份和同步 baseline
- `itt remote` 独立于 Git origin；不同本地副本通过相同地址和项目名共享历史；旧 workspace 入口已移除
- 显式 `--token` 和 `INTHUB_TOKEN` 会覆盖已保存凭据，且绝不会持久化到 `hub.json`
- Pull 校验版本内容并原子恢复完整共享历史，拒绝分叉覆盖；自动维护不会隐含 pull 授权
- IntHub Local 默认绑定 `127.0.0.1`，但当前 API 不强制校验 Bearer Token，且使用宽松 CORS；不要将它暴露到局域网或公网
- IntHub 生产配置使用 Tenon 统一登录和有时限的只读 HttpOnly Web 会话；CLI 写入使用当前账户签发的 access token（HTTP `Bearer`），项目读取和写入均按账户隔离，生产数据库使用 PostgreSQL，详见 [IntHub 生产部署](inthub-production.md)
- 对象和 Hub 配置通过原子替换写入，变更命令使用带有界 owner 诊断的工作区级跨进程写锁；这会串行化 Intent CLI 写入，但不会把 `.intent/` 变成多用户数据库
- IntHub 请求每次尝试最多等待 15 秒、最多尝试两次；随附 argv 适配器具有 60 秒进程安全超时，并始终输出一个 JSON 文档
- 对象 ID 在路径 I/O 前校验，对象路径必须留在对应类型目录内，`.intent/` 对象存储拒绝符号链接重定向
- 描述性字段写一次；状态与自动维护的关系字段会随着后续命令推进
- ID 按对象类型单调递增并零填充，例如 `intent-001`、`snap-001`、`decision-001`
