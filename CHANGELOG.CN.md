[English](CHANGELOG.md) | 简体中文

# 变更记录

这里记录项目的重要变更。

项目目前还没有正式 public release，下面这条主要用于描述正在收尾中的当前发布基线。

## 0.1.0 - Unreleased

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

### 说明

- 当前 package 版本仍是 `0.1.0`
- 这一条 changelog 代表发布基线，不是已打 tag 的正式 release 公告
