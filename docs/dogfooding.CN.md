[English](dogfooding.md) | 简体中文

# 吃自己的狗粮：用 Intent 开发 Intent

Intent 是用自己开发出来的。这篇文档记录了真实发生的事情——不是营销，而是 `.intent/` 如何影响了一次 agent 驱动的开发 session。

## 背景

一个开发者，一个 AI agent（Claude），一个下午。目标：把 Intent 从一个可用原型变成已发布的工具。这个 session 涵盖了 PyPI 发布、文档重写、bug 修复、新功能（suspend/resume），以及 Hacker News 发布。

## 实际发生了什么

### 13 个 intent，35 个 snap

整个 session 创建了 13 个 intent，部分摘要：

| Intent | 标题 | Snap 数 |
|---|---|---|
| intent-004 | 精简为 agent-only 最小 CLI | 1 |
| intent-007 | 统一命名：checkpoint → snap | 1 |
| intent-008 | 发布到 PyPI 并提供 agent 集成模板 | 2 |
| intent-010 | 对齐 intent 对象的定位 | 2 |
| intent-011 | 三阶段推广计划 | 5 |
| intent-012 | 修复 PyPI 中文 README 链接 | 1 |

### 上下文切换不丢失

关键时刻：在推进 intent-011（三阶段推广计划）时，发现 PyPI 的一个 bug——中文 README 链接无法点击。没有丢失上下文：

```
itt suspend                          # 暂停推广计划
itt start "修复 PyPI 中文 README 链接"  # 处理 bug
itt snap "..." -m "..."
itt done                             # bug 修复完成
itt resume                           # 回到推广计划
```

Agent 从中断的地方精确恢复，无需重新解释。

### Rationale 的缺口

Session 中途，开发者问："intent-011 下的 snap 是什么？" 列表显示 snap-031 的 rationale：

> PyPI (git-intent 0.3.2) + GitHub Release + agent 集成模板均已就绪。下一步：阶段二，HN Show HN 曝光。

阶段三的目标完全丢失了。没有它，未来的 session 会知道有"三阶段计划"，但不知道第三阶段是什么。这导致了两个改变：

1. 新增 snap-033，在 rationale 中记录了完整的战略全景
2. 更新 agent 集成指南：**进度类 snap 的 rationale 应包含完整画面——已完成、进行中、待做，以及战略上下文**

### 命名的教训

Agent 机械地记录 snap——"我做了什么"——却没有捕捉"我们到哪了"。这揭示了一个事实：教 agent *命令*是不够的。它们需要理解*对象语义*：intent 代表什么（目标，而非任务）、snap 代表什么（步骤）、rationale 应该包含什么（决策、进度和前瞻状态）。

## 我们学到了什么

1. **suspend/resume 是必需的。** 真实的工作不是线性的。你会被打断。没有 suspend，你要么关闭未完成的 intent（丢失状态），要么无视中断。

2. **Rationale 需要全景。** 一个说"因为 Y 做了 X"的 snap 是有用的。一个说"因为 Y 做了 X；A 已完成，B 进行中，C 是下一步；约束：周四截止"的 snap 才是让下一个 session 真正自主的。

3. **Agent 需要语义，不只是命令。** 告诉 agent"每次 commit 前执行 `itt snap`"会产出低价值 snap。告诉它"rationale 应该记录下一个 session 需要什么来重建计划"会产出高价值的。

4. **工具在使用中发现自己的缺口。** 用 Intent 开发 Intent，让我们发现了缺失的功能（suspend/resume、`list --intent` 过滤）、文档缺口（对象语义指南）、以及设计洞察（rationale 作为全景捕捉），这些纯粹靠设计思考是发现不了的。
