[English](../EN/demo.md) | 简体中文

# Intent Demo

这个文档提供两个可复现的本地演示，用来观察 `git log` 和 `itt log` 分别回答什么问题，以及 agent 如何从 `itt inspect --json` 推进下一步。

## Human Demo

目标：展示 `git log` 更偏向代码提交历史，而 `itt log` 更偏向采纳历史。

运行方式：

```bash
scripts/demo_log.sh
```

这个脚本会：

- 创建一个临时 Git 仓库
- 初始化 Intent
- 创建一个 intent
- 生成两个 checkpoint
- 记录一次 adoption
- 输出 `git log --oneline`
- 输出 `itt log`

观察点：

- `git log` 展示的是提交顺序和提交说明
- `itt log` 展示的是 adoption timeline，以及 adoption 关联的 intent、checkpoint 和 Git head

如果想手动复现，也可以按这个顺序执行：

```bash
itt init
itt start "Reduce onboarding confusion"

# candidate A
itt snap "Landing page candidate A"
git add .
git commit -m "landing candidate A"

# candidate B
itt snap "Landing page candidate B"
git add .
git commit -m "landing candidate B"

itt adopt --checkpoint cp-002 -m "Adopt progressive disclosure layout"
git log --oneline
itt log
```

## Agent Demo

当前仓库提供了一个可运行的 agent demo：

```bash
scripts/demo_agent.sh
```

这个脚本会：

- 创建一个临时 Git 仓库
- 初始化 Intent
- 反复读取 `itt inspect --json`
- 提取 `suggested_next_actions[0].args`
- 按返回的参数执行下一步命令

观察点：

- `inspect --json` 会返回机器可消费的 `suggested_next_actions`
- action payload 同时包含可展示的 `command` 和可执行的 `args`
- agent 可以不依赖长 prose，直接沿着结构化状态往前推进
