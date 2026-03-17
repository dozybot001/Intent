[English](../EN/release.md) | 简体中文

# 发布基线

这个文档定义当前 CLI 阶段最小的 release-ready 检查项。

## 目标

在创建 GitHub release 之前，至少确认这个仓库已经做到：

- 可安装
- 可测试
- 可演示
- 文档对得上

## 最小检查清单

- [pyproject.toml](../../pyproject.toml) 里的版本号正确
- [CHANGELOG.md](../../CHANGELOG.md) 和 [CHANGELOG.CN.md](../../CHANGELOG.CN.md) 已更新到当前发布目标
- [README.md](../../README.md) 和 [README.CN.md](../../README.CN.md) 与当前 CLI 保持一致
- [docs/EN/cli.md](../EN/cli.md) 和 [docs/CN/cli.md](cli.md) 与实现一致
- [scripts/check.sh](../../scripts/check.sh) 在本地通过
- GitHub Actions CI 通过
- package 仍然可以构建出 sdist 和 wheel
- 构建出来的 wheel 可以在干净环境中安装，并且 `itt` 入口可正常运行

## 本地命令

```bash
./scripts/check.sh
python3 itt version
python3 -m build
```

## Release Notes 建议范围

对当前阶段来说，release notes 重点覆盖：

- 2 对象模型（intent、checkpoint）
- `start → snap → done` 核心闭环
- JSON-only 输出
- 机器可读 agent 入口（`inspect`）
- agent 集成 setup

## 当前不纳入阻塞项

以下方向不应阻塞当前 release：

- remote sync
- 平台化 UI
- 高级过滤器
- 超出本地 CLI 范围的协作层功能
