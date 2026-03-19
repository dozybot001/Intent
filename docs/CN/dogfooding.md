# Dogfooding: 跨 Agent 协作实录

本文记录了 Intent + IntHub 在真实开发中的一次跨 agent、跨 session 协作过程。内容基于 `.intent/` 中的 snap 链（snap-050 至 snap-061）整理而成，不是事后虚构的案例。

## 背景

intent-013 的目标是"规划 IntHub 首期设计方向"。IntHub 是 Intent 的远端协作层——一个只读 Web 界面，让团队成员和 agent 查看语义历史，无需本地运行 `itt inspect`。

在这条 intent 下，用户在不同 agent 之间自然切换，完成了从基础设施搭建到前端重写再到 SKILL 同步的完整工作链。

## 时间线

### 第一阶段：Codex 搭建 IntHub（snap-050 → 052）

Codex 负责前期工作：推送 README 中的 skill 安装说明，说明 IntHub Web 的查看入口，并在本地启动 IntHub API + Web 服务，完成 `itt hub login → link → sync` 全链路接入。

此时 IntHub 已经可以在 `http://127.0.0.1:3000` 查看项目的语义历史。

### 第二阶段：Claude Code 重写前端（snap-053 → 059）

用户在浏览器中查看 IntHub 后，发现前端有显示问题。Claude Code 先做了一轮快速修复（snap-053），但用户给出反馈：

> "决定推翻当前前端，完全重来。之前的修补不再需要。"

Claude Code 随即运行 `itt inspect`，读取 Codex 在 snap-052 中留下的上下文（API 地址、数据库路径、已接入的数据），然后完成了完整的前端重写（snap-054）——从单页长滚动改为两栏 Handoff-first 布局。

之后是一系列由用户反馈驱动的迭代：

| Snap | 用户反馈 | Agent 响应 |
|---|---|---|
| 055 | 溢出 BUG、decision 冗余、deprecated 显示问题 | 修复溢出、去除冗余、分层展示 deprecated |
| 056 | 文字一大段没有分段 | 新增渲染层 formatText()，按句号拆段 |
| 057 | —（agent 自查） | timeline 折叠、英文分段支持、loading 状态 |
| 058 | older snaps 不该有删除线、snaps 只显示 10 条 | 拆分折叠样式、API 去掉截断 |
| 059 | intent 历史应该全部展示 | API 返回全量 intent、前端按状态分组 |

每轮交互都遵循同一个模式：用户给反馈 → `itt snap feedback` 记录 → agent 修改 → `itt snap create` 记录做了什么和没做什么。

### 第三阶段：Codex 补充 SKILL（snap-060）

用户发现 CLI 新增的 `doctor` 和 `hub` 命令没有写进 SKILL，决定切回 Codex 处理——因为 Codex 是命令的原始设计者，更清楚命令的边界在哪。

Codex 通过 `itt inspect` 看到了 Claude Code 的全部前端改动（snap-053 到 059），在 snap-060 的 query 里写道：

> "目前我让 Claude Code 重构了一下前端。"

它没有重复问用户发生了什么，而是直接进入自己的工作：补充 `doctor`、`hub login/link/sync` 命令说明，更新过滤参数，细化 intent 创建判断标准。

### 第四阶段：Claude Code 发现并纠正失误（snap-061）

用户切回 Claude Code，问"Codex 改了吗，你看到了吗"。

Claude Code 运行 `itt inspect`，看到 snap-060 的标题和 summary，确认了 Codex 的改动内容。然后它做了一件 Codex 没做到的事：发现 Codex 改的是本机 skill 副本（`~/.agents/skills/intent-cli/SKILL.md`），而不是仓库源文件（`SKILL.md`）。

Claude Code 在 snap-060 上记录了 feedback：

> "改动方向对但改错了位置——应该改仓库 SKILL.md 再重装 skill，而不是直接改本机 skill 副本。"

然后 diff 两个文件，确认改动质量后将内容同步回仓库。

## 这说明了什么

**Agent 切换不需要交接会议。** 用户在不同 agent 之间多次切换，没有一次需要重新解释上下文。每个 agent 通过 `itt inspect` 读取当前状态，通过 `itt snap show` 读取前一个 agent 留下的 summary，然后直接开始工作。

**Feedback 在正确的位置被消费。** snap-053 的 feedback（"推翻重来"）直接影响了 snap-054 的方向。snap-060 的 feedback（"改错位置"）直接导致了 snap-061 的纠正动作。feedback 不是事后总结，而是下一步的输入。

**Summary 为下一个 session 而写。** 每条 snap 的 summary 都回答三个问题：做了什么、没做什么、下一步需要什么上下文。这不是日志，是交接文档。

**Decision 是活的约束，不是备忘录。** 整个过程中 5 条 active decisions 持续约束着实现选择（比如 `.intent/` 不进 Git、Hub 不放进 PyPI 分发）。这些约束不是 agent "记住"的——每次 `itt inspect` 都会重新加载，并在实现前检查。

**错误被结构化捕获。** Codex 改错了文件位置，Claude Code 通过 diff 发现了问题。如果没有 Intent，这个错误可能在下次 `npx skills add` 时才会暴露——因为本机 skill 看起来是对的，但仓库源文件没有更新。snap-060 的 feedback 永久记录了这个失误和原因，未来 agent 更容易看到并避免重复这类错误。

## 数据来源

以上所有内容可通过以下命令复现：

```bash
itt inspect
itt snap show snap-050   # 到 snap-061
```

或在 IntHub Web 界面中查看：打开 intent-013 的 detail → Snap Timeline → 展开 older snaps。
