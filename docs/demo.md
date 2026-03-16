# Intent Demo

这个文档提供一个可复现的本地演示，用来观察 `git log` 和 `itt log` 分别回答什么问题。

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

当前仓库还没有单独的 agent demo 脚本。

如果需要观察 machine-readable path，可以从这组命令开始：

```bash
itt status --json
itt inspect --json
```

这两个入口分别提供当前 workspace 摘要和更完整的结构化快照。
