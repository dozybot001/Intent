[English](CHANGELOG.md) | 简体中文

# 变更记录

这里记录项目的重要变更。

## 0.2.0-rc.1 - 2026-03-17

### 新增

- 以 `setup/install.sh` 为入口的 repo-backed 安装流程，并固定 checkout 到 `~/.intent/repo`
- 放在 `setup/` 下的 agent 集成资源，覆盖 Codex、Claude 和 Cursor
- 双语 `distribution.md` 与 `structure.md` 文档，用来解释新的安装路径和仓库结构

### 调整

- 面向用户的安装路径现在从 GitHub 命令开始，暴露 `~/.intent/bin/itt`，并把本地 checkout 的 repo 作为唯一运行时来源
- 写命令现在接受 `--checkpoint @current` 和 `--adoption @latest` 这类 selector
- `STATE_CONFLICT` 的恢复信息现在会直接返回 candidate checkpoint 和明确的 `itt checkpoint select <id>` 下一步
- Codex 与 Claude 的 skill 现在明确教授 inspect-first 循环、selector 写法和冲突恢复

### 修复

- Cursor helper 的说明路径改为 `~/.intent/generated/cursor` 下的实际生成位置

### 说明

- 预发布 tag 目标：`v0.2.0-rc.1`
- 当前 package 版本更新为 `0.2.0rc1`
- 这个 prerelease 用来验证安装流程和 agent skill 体验，再决定稳定版 `v0.2.0`

## 0.1.0 - 2026-03-17

### 新增

- 初始版本地 `.intent/` 对象层
- 主 surface 流程：`init`、`start`、`snap`、`adopt`、`revert`、`status`、`inspect`、`log`
- `intent`、`checkpoint`、`adoption`、`run`、`decision` 的 canonical / read-side 命令
- `status --json`、`inspect --json` 以及写命令的结构化机器输出
- `run start/end/list/show` 与 `decision create/list/show`
- human demo、agent demo、smoke script，以及统一的 `scripts/check.sh`
- 基础 GitHub Actions CI 和 package build 验证

### 调整

- 文档重组为 `docs/` 下的 EN/CN 双语目录
- README 补上了本地安装和验证入口
- CLI 核心模块拆分出 constants、errors、git helpers、helpers、render 等更小文件
- 发布基线文档现在包含稳定的 release notes 模板

### 说明

- 当时的 package 版本是 `0.1.0`
- 这是仓库的第一个已打 tag 版本
