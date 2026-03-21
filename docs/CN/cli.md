# Intent CLI

中文 | [English](../EN/cli.md)

Schema version: **1.0**

Intent CLI 是 Intent 的本地 semantic-history CLI。它只管理三类对象：

- `intent`：可恢复的目标
- `snap`：某个 intent 下的语义检查点
- `decision`：跨 intent 持续生效的长期约束

命令面刻意保持很小：

- 恢复工作用 `itt inspect`
- 诊断结构问题用 `itt doctor`
- 图谱浏览交给 IntHub
- 不再提供 `list` 命令

## 命令总览

### 全局

| 命令 | 作用 |
| --- | --- |
| `itt version` | 输出 CLI 版本 |
| `itt init` | 在当前 Git 仓库初始化 `.intent/` |
| `itt inspect` | resume-first 恢复视图 |
| `itt doctor` | 结构诊断视图 |

### Intent

| 命令 | 作用 |
| --- | --- |
| `itt intent create TITLE --query Q [--rationale R]` | 创建一个新的 intent |
| `itt intent activate [ID]` | `suspend` → `active` |
| `itt intent suspend [ID]` | `active` → `suspend` |
| `itt intent done [ID]` | `active` → `done` |

### Snap

| 命令 | 作用 |
| --- | --- |
| `itt snap create TITLE [--intent ID] [--origin LABEL] --summary S` | 创建语义检查点（仅有一个 `active` intent 时可省略 `--intent`；`origin` 默认从环境自动推断，可用参数覆盖） |
| `itt snap feedback ID TEXT` | 覆盖写入 snap 反馈 |

### Decision

| 命令 | 作用 |
| --- | --- |
| `itt decision create TITLE --rationale R` | 创建一个新的 decision |
| `itt decision deprecate ID` | `active` → `deprecated` |
### Hub

| 命令 | 作用 |
| --- | --- |
| `itt hub link [--project-name NAME] [--api-base-url URL] [--token TOKEN]` | 必要时先配置本地 IntHub 访问，再绑定当前工作区 |
| `itt hub sync [--api-base-url URL] [--token TOKEN] [--dry-run]` | 把本地语义快照推送到 IntHub |

## 全局命令

### `itt version`

输出当前 CLI 版本。

```bash
itt version
```

### `itt init`

在当前 Git 仓库中初始化 `.intent/`。

```bash
itt init
```

### `itt inspect`

resume-first 恢复视图。

- 在 session 开始时使用，用来继续干活
- 默认输出：`active_intents`、`active_decisions`、`suspended`、`warnings`
- 不负责完整对象浏览

```bash
itt inspect
```

### `itt doctor`

结构诊断视图。

- 当 `inspect` 出现 warning，或你怀疑对象图不一致时使用
- 默认输出：`healthy`、`issues`
- 校验断链引用、非法状态和单向关系

```bash
itt doctor
```

## 对象命令

### Intent

`create` 用来识别并落下新的可恢复目标。`activate`、`suspend`、`done` 是状态流转。

```bash
itt intent create "Fix the login timeout bug" \
  --query "why does login timeout after 5s?" \
  --rationale "users on slow networks get logged out mid-session"

itt intent suspend intent-001
itt intent activate intent-001
itt intent done intent-001
```

说明：

- 新建 intent 默认是 `active`
- 创建 intent 时会自动挂载当前全部 `active` decision
- 重新激活 intent 时，会补挂当前全部 `active` decision
- `activate`、`suspend`、`done` 可以显式传 `ID`，也可以在恰好只有一个匹配对象时自动推断
- 省略 `ID` 且没有匹配对象时，会返回 `NO_ACTIVE_INTENT` 或 `NO_SUSPENDED_INTENT`
- 省略 `ID` 且有多个匹配对象时，会返回 `MULTIPLE_ACTIVE_INTENTS` 或 `MULTIPLE_SUSPENDED_INTENTS`，并在 `error.details.candidates` 中列出候选项

### Snap

`create` 在某个 active intent 下记录一个语义检查点。语义检查点用来保留发生了什么变化、学到了什么，以及后续反馈。`feedback` 故意单独拆开，并且是覆盖语义。

```bash
itt snap create "Raise timeout to 30s" \
  --summary "Updated timeout config and ran the login test"

# 多个 intent 同时 active 时必须指明：
itt snap create "Raise timeout to 30s" \
  --intent intent-001 \
  --summary "Updated timeout config and ran the login test"

itt snap feedback snap-001 "works in staging"
```

说明：

- `--summary` 必填
- `--intent` 可选：省略时若恰有一个 `active` intent 则挂到该 intent；若没有 `active` intent 则报错 `NO_ACTIVE_INTENT`；若有多个则报错 `MULTIPLE_ACTIVE_INTENTS`，并在 `error.details.candidates` 里列出候选项供 agent 选择
- 落盘的 `origin` 由 **`itt` 子进程继承的环境变量** 自动推断，Agent 不必在命令里写。可在 shell 配置或 IDE 集成里设置 `ITT_ORIGIN` / `INTENT_ORIGIN` 作为稳定标签；内置启发式包括：`CURSOR_TRACE_ID` → `cursor`、`CODEX_INTERNAL_ORIGINATOR_OVERRIDE=\"Codex Desktop\"` → `codex-desktop`、`CODEX_THREAD_ID` / `CODEX_SHELL` / `CODEX_CI` → `codex`、`TERM_PROGRAM=vscode` → `vscode`，以及 Codespaces、GitHub Actions、Gitpod 等。若单次命令要强制覆盖，再用 `--origin LABEL`。
- 新建 snap 默认是 `active`
- 创建 snap 时会同时写入 `snap.intent_id` 和父 intent 的 `snap_ids`
- 用户反馈通过后续的 `itt snap feedback` 单独记录
- 若要纠正旧 checkpoint，应追加 feedback 或写新的 snap，而不是回滚旧 snap

### Decision

`create` 用来记录长期约束。

```bash
itt decision create "Timeout must stay configurable" \
  --rationale "Different deployments have different latency envelopes"

itt decision deprecate decision-001
```

说明：

- 新建 decision 默认是 `active`
- 创建 decision 时会自动挂载当前全部 `active` intent
- `deprecate` 会保留历史，只停止未来自动挂载

CLI 不再提供 `show` 命令。

- 默认恢复入口是 `itt inspect`
- 面向人的对象浏览交给 IntHub

## Hub 命令

### `itt hub link`

必要时先配置本地 IntHub 访问，然后绑定当前 GitHub-backed 工作区。

```bash
itt hub link --api-base-url http://127.0.0.1:7210 --project-name "Intent"
itt hub link --api-base-url http://127.0.0.1:7210 --token dev-token --project-name "Intent"
```

说明：

- 要求当前 `origin` remote 是受支持的 GitHub 仓库
- 会写入 `.intent/hub.json`
- 会持久化 `api_base_url`、可选本地 token、`workspace_id`、`project_id`、`repo_binding`

### `itt hub sync`

把当前 `.intent/` 快照和 Git 上下文推送到 IntHub。

```bash
itt hub sync
itt hub sync --dry-run
```

说明：

- 上传的是完整快照，不是增量 patch
- 会附带 `branch`、`head_commit`、`dirty`、`remote_url` 等 Git 上下文
- `--dry-run` 只输出将要发送的 payload，不真正发请求

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

`inspect` 返回：

```json
{
  "ok": true,
  "active_intents": [],
  "active_decisions": [],
  "suspended": [],
  "warnings": []
}
```

### `doctor`

`doctor` 返回：

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
| `GIT_STATE_INVALID` | 当前不在 Git worktree 中 |
| `STATE_CONFLICT` | 状态流转非法 |
| `OBJECT_NOT_FOUND` | 找不到对应对象 ID |
| `INVALID_INPUT` | 参数非法或缺少必填输入 |
| `NO_ACTIVE_INTENT` | `snap create`、`intent suspend` 或 `intent done` 在省略目标时，没有 `active` intent |
| `MULTIPLE_ACTIVE_INTENTS` | `snap create`、`intent suspend` 或 `intent done` 在省略目标时，存在多个 `active` intent |
| `NO_SUSPENDED_INTENT` | `intent activate` 在省略目标时，没有 `suspend` intent |
| `MULTIPLE_SUSPENDED_INTENTS` | `intent activate` 在省略目标时，存在多个 `suspend` intent |
| `HUB_NOT_CONFIGURED` | 缺少 IntHub API base URL |
| `NOT_LINKED` | 当前工作区还没绑定到 IntHub |
| `PROVIDER_UNSUPPORTED` | 当前 Git remote 不受支持 |
| `NETWORK_ERROR` | 无法连接 IntHub |
| `SERVER_ERROR` | IntHub 返回错误或非法 JSON |

## 运行约束

- `.intent/` 是本地工作区元数据，不应进入 Git 历史
- 对象内容是 append-only 的，不应回写旧标题或旧摘要
- `snap feedback` 是唯一允许的事后覆盖路径
- ID 按对象类型单调递增并零填充，例如 `intent-001`、`snap-001`、`decision-001`
