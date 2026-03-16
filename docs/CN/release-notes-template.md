[English](../EN/release-notes-template.md) | 简体中文

# Release Notes 模板

把这份模板作为 GitHub release notes 的固定结构。

## 摘要

用一小段话说明这次发布在实际使用层面意味着什么。

## 基线

- 上一个 tag：`vA.B.C` 或 `none`
- 发布日期：`YYYY-MM-DD`

## Highlights

- 亮点 1
- 亮点 2
- 亮点 3

## 变更内容

### Added

- 新增项

### Changed

- 调整项

### Fixed

- 修复项

## 验证

- `./scripts/check.sh`
- wheel install 验证
- 其他 repo 特定验证

## 说明

- 仍然存在的已知边界
- 本次发布明确不包含的内容

## Next

- 下一阶段最可能推进的方向

## 输出格式

- 不要包含顶层标题；GitHub release 的标题单独填写
- 在对话里输出 release note 时，把最终正文放进 fenced `md` 代码块
