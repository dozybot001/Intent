[English](../EN/demo.md) | 简体中文

# Intent Demo

这个文档提供可复现的本地演示，用来观察 Intent 如何在 Git 之上记录语义历史。

## Agent Demo

当前仓库提供了一个可运行的 agent demo：

```bash
scripts/demo_agent.sh
```

这个脚本会：

- 创建一个临时 Git 仓库
- 初始化 Intent
- 读取 `itt inspect` 了解当前状态
- 按照 `suggested_next_action` 推进工作流
- 完成完整的 `start → snap → done` 闭环

观察点：

- `inspect` 返回机器可消费的 `suggested_next_action`
- action payload 包含可展示的 `command` 和 `reason`
- agent 可以沿着结构化建议往前推进，不依赖长 prose

## Log Demo

```bash
scripts/demo_history.sh
```

这个脚本会：

- 创建一个临时 Git 仓库
- 初始化 Intent
- 创建一个 intent 并记录带理由的 checkpoint
- 展示 `inspect` 如何提供结构化的 workspace 快照

## Smoke Test

```bash
scripts/smoke.sh
```

运行完整命令集：init、start、snap、snap --candidate、adopt、revert、list、show、inspect、done。

## 完整验证

如果你想用一条命令跑完当前本地验证集，可以执行：

```bash
scripts/check.sh
```
