---
name: intent-cli
description: 记录语义历史（.intent/）——目标、快照和决策，跨 agent session 持久化。用户要求记录语义时触发。
---

# Intent — 语义记录指南

本仓库使用 Intent（`.intent/`）记录语义历史：**做了什么、为什么**，结构化为正式对象，跨 session、跨 agent 不丢失。

`itt` 命令输出 JSON——解析它，不要猜测。

## 何时激活

- 用户键入 `/intent-cli`
- 用户说"记录语义"、"记录一下"、"record what we did"或类似表达

## 记录流程

记录是**回溯式**的。回顾**从上一次语义记录到现在**的工作并总结。这确保了语义连续性——每次记录接上上一次的终点。如果找不到上一次记录（inspect 为空），告知用户将从当前 session 开头开始记录。

1. 运行 `itt inspect` 检查当前状态（active intent、decision、suspended）
2. 创建**一个 intent** — 本次交互的目标
3. 创建**若干 snap** — 每个有意义的里程碑一个
4. 识别 **decision** — 值得正式化的长期约束（需用户确认）
5. `itt intent done` — 目标已完全解决时

```bash
itt intent create "实现了认证重试逻辑" \
  --why "慢网络用户会被踢出登录"
itt snap create "API 客户端增加指数退避重试" \
  --why "上游间歇性 503 导致级联失败"
itt snap create "更新登录流程的错误处理" \
  --why "旧处理器静默吞掉了重试错误"
itt intent done
```

## 如何写出高质量语义

每个对象有两个核心字段：**`what`**（简洁行动/主题）和 **`why`**（推理）。

### Intent：`what` + `why`

- `what`：一句话概括目标——**不是**一个步骤，不是一个文件名
- `why`：目标背后的上下文或动机

| 好 | 差 |
|---|---|
| "迁移认证中间件到 JWT" | "改 auth.py" |
| "修复慢网络下的级联超时" | "修 bug" |

**一次记录一个 intent，不是一个步骤。** 一次记录通常只产生一个 intent。

### Snap：`what` + `why`

Snap 是**里程碑**——intent 下一块有意义的已完成工作。

- `what`：做了什么，在列表中可快速扫读
- `why`：为什么选择这个方案，不是复述 what

| 好 | 差 |
|---|---|
| what: "增加指数退避重试" | what: "修改了 api_client.py 第 42-78 行" |
| why: "线性重试在恢复期压垮了上游" | why: "因为需要重试" |

### Snap 边界判断

```
问自己："去掉这个 snap，intent 的故事会断吗？"
  会 → 保留为 snap
  不会 → 粒度太细，合并或跳过
```

经验法则：
- **该记**：架构选择、非显而易见的权衡、重大代码变更、调查后的结论
- **不记**：常规编辑、格式化、依赖升级、不需要解释的琐碎修复

### Decision：`what` + `why`

Decision 是**长期约束**，生命周期超越当前 intent。

**判断标准：**未来一个完全不同的问题，仍然需要遵守它？是 → decision。否 → 写进 snap。

| Decision | 不是 Decision（写 snap） |
|----------|--------------------------|
| "所有 API 响应必须包含 request_id 用于追踪" | "在认证端点响应中加了 request_id" |
| "SKILL 必须自包含——agent 只读 SKILL" | "重写 SKILL 以澄清记录流程" |

**未经用户确认，绝不创建 decision。**

| 路径 | 触发条件 | 动作 |
|------|---------|------|
| 显式 | 用户说 `decision-[文本]` 或 `决定-[文本]` | 直接创建 |
| 发现 | 你发现了一个长期约束 | 问："要不要把这个记录为 decision？" → 确认后才创建 |

如果用户请求与 active decision 冲突，明确指出并询问是否废弃。

## Session 恢复

激活时，先运行 `itt inspect`：

1. **Active intent** → 从 `latest_snap` 继续，不要让用户重新解释
2. **Active decision** → 作为现行约束遵守
3. **Suspended intent** → 相关则提及
4. **Warnings** → 运行 `itt doctor`
5. **全部为空** → 全新工作区

## 关键规则

- **记录由用户发起** — 和 git commit 一样，用户要求时才记录
- **一次记录一个 intent** — 概括目标，不是逐步骤
- **Snap 记录推理，不记录操作** — 记 why，不记 diff
- **Decision 必须用户确认** — 绝不凭自己判断单独创建
- **完成的 intent 必须 `done`** — 残留 intent 会污染 inspect
- **Decision 清理** — 当 `active_decisions > 20` 时，提醒："当前有 N 条 active decision，要做一轮清理吗？"

## 对象

| 对象 | 字段 | 状态 |
|------|------|------|
| **Intent** | `what`, `why`, `snap_ids[]`, `decision_ids[]` | `active` → `suspend` ↔ `active` → `done` |
| **Snap** | `what`, `why`, `intent_id` | 不可变 |
| **Decision** | `what`, `why`, `intent_ids[]`, `reason` | `active` → `deprecated` |

所有对象还包含：`id`、`object`、`created_at`、`origin`（自动检测）。

关系**双向**且**只增不删**。对象创建后**不可变**——通过新建 snap 修正。

## 命令参考

### 全局

| 命令 | 功能 |
|------|------|
| `itt init` | 在当前 git 仓库创建 `.intent/` |
| `itt inspect` | 恢复视图 — 每次记录从这里开始 |
| `itt doctor` | 验证对象图 |
| `itt version` | 打印版本 |

### Intent

| 命令 | 功能 |
|------|------|
| `itt intent create WHAT [--why W]` | 新建 intent（自动挂载 active decision） |
| `itt intent activate [ID]` | `suspend` → `active`（同步 decision；唯一时自动推断） |
| `itt intent suspend [ID]` | `active` → `suspend`（唯一时自动推断） |
| `itt intent done [ID]` | `active` → `done`（唯一时自动推断） |

### Snap

| 命令 | 功能 |
|------|------|
| `itt snap create WHAT [--why W]` | 语义快照（自动挂载到 active intent；多个时用 `--intent ID`） |

### Decision

| 命令 | 功能 |
|------|------|
| `itt decision create WHAT [--why W]` | 新建 decision（自动挂载 active intent） |
| `itt decision deprecate ID [--reason TEXT]` | `active` → `deprecated` |

### Hub

| 命令 | 功能 |
|------|------|
| `itt hub start [--port PORT] [--no-open]` | 启动 IntHub Local |
| `itt hub link [--project-name NAME] [--api-base-url URL]` | 绑定工作区到 IntHub |
| `itt hub sync [--dry-run]` | 推送语义历史到 IntHub |

## JSON 输出

**成功：** `{"ok": true, "action": "...", "result": {...}, "warnings": []}`

**Inspect：** `{"ok": true, "active_intents": [], "active_decisions": [], "suspended": [], "warnings": []}`

**错误：** `{"ok": false, "error": {"code": "...", "message": "...", "suggested_fix": "itt ..."}}`

有 `suggested_fix` 时，照做。
