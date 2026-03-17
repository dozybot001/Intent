[English](CHANGELOG.md) | 简体中文

# 变更记录

这里记录项目的重要变更。

## 0.3.0 - 2026-03-17

### 调整

- **重大简化**：对象模型从 5 种（intent、checkpoint、adoption、run、decision）缩减为 2 种（intent、checkpoint）
- 核心闭环从 `init → start → snap → adopt → log` 变为 `init → start → snap → done`
- intent 状态从 4 种（active、paused、completed、archived）简化为 2 种（open、done）
- workspace 状态从 6 种简化为 3 种（idle、active、conflict）
- 所有输出改为 JSON-only；无人类可读文本模式，不需要 `--json` flag
- `snap` 现在默认创建 adopted checkpoint；使用 `--candidate` 进行比较工作流
- `adopt` 现在直接采纳 candidate checkpoint（不再创建独立的 adoption 对象）
- `revert` 现在直接修改 checkpoint 状态（不再创建独立的 revert record）
- `done` 替代旧的 `complete`/`abandon` 命令用于关闭 intent
- schema version 从 "0.1" 升级为 "0.2"
- `.intent/` 目录现在只包含 `intents/` 和 `checkpoints/`（移除了 `adoptions/`、`runs/`、`decisions/`）
- `state.json` 简化为 4 个字段：`schema_version`、`active_intent_id`、`workspace_status`、`updated_at`
- `inspect` 输出扁平化，使用 `suggested_next_action`（单数，不是数组）

### 移除

- `status` 命令（用 `inspect` 替代）
- `log` 命令
- `decide` / `decision create` 命令
- `run start` / `run end` 命令
- `checkpoint select` 命令
- Surface CLI 与 Canonical CLI 的区分
- `--json`、`--id-only`、`--no-interactive`、`--if-not-adopted` 等 flag
- `adoption`、`run`、`decision` 对象类型
- state.json 中的 `mode`、`active_run_id`、`current_checkpoint_id`、`last_adoption_id`
- `config.json` 中的 `git.strict_adoption`
- `render.py` 模块（无人类可读输出）
- selector（`@current`、`@latest`、`@active`）

### 新增

- `done` 命令用于关闭 intent
- `snap` 的 `--candidate` flag 用于比较工作流
- `show` 命令，从 ID 前缀推断类型
- 以 `setup/install.sh` 为入口的 repo-backed 安装流程
- `setup/` 下的 agent 集成资源，覆盖 Codex、Claude 和 Cursor

### 说明

- 这是相对 v0.1.0 的 breaking change
- 使用 schema "0.1" 的旧 `.intent/` 数据可能需要手动迁移

## 0.1.0 - 2026-03-17

### 新增

- 初始版本地 `.intent/` 对象层
- 主 surface 流程：`init`、`start`、`snap`、`adopt`、`revert`、`status`、`inspect`、`log`
- `intent`、`checkpoint`、`adoption`、`run`、`decision` 的 canonical / read-side 命令
- `status --json`、`inspect --json` 以及写命令的结构化机器输出
- `run start/end/list/show` 与 `decision create/list/show`
- human demo、agent demo、smoke script，以及统一的 `scripts/check.sh`
- 基础 GitHub Actions CI 和 package build 验证

### 说明

- 当时的 package 版本是 `0.1.0`
- 这是仓库的第一个已打 tag 版本
