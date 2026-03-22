# Agent 视角的改进建议

来源：Claude Code (Opus 4.6) 对 Intent CLI 的使用体验反馈，2026-03-22。

---

## 1. SKILL.md 太重（已在处理）

当前 ~23KB，每次 session 全量加载消耗 ~6000 token。大部分教学内容在 agent 熟练后成为死重。

**方案：** 拆为核心 SKILL（~10KB）+ 按需加载的 SKILL-guide.md。

## 2. 缺少 list / show / search 命令

`list` 和 `show` 已被移除，但 agent 经常需要：
- 查看某 intent 下所有 snap（inspect 只显示 latest_snap）
- 按关键词搜索 decision（确认约束是否已存在）
- 查看已完成的 intent 历史

目前只能手动 `cat .intent/intents/intent-001.json`，违背结构化 CLI 初衷。

**方案：** 恢复 `itt intent show <ID>` 和 `itt decision list [--status active]`。

## 3. Active decision 无限累积，inspect 越来越吵

当前 13 条 active decision 全部平铺在 inspect 输出中，每条都 auto-attach 到每个新 intent。

**方案：**
- 支持 decision 分组/标签（`--tag architecture`）
- inspect 按相关性排序或分组
- 或引入 decision scope，只 attach 到匹配 tag 的 intent

## 4. 对象不可变 + 无修正机制 = 噪声累积

写错 snap 的 `what` 只能再建一个"更正 snap"；intent 的 `why` 写差了无法修正。

**方案：** 引入 `itt snap amend <ID>` 或 `itt intent annotate <ID> --note "..."`——不修改原对象，创建显式修正记录，inspect 优先展示最新修正。

## 5. 跨 intent 关联缺失

多个 intent 经常有因果关系（调查发现→新 intent，依赖→阻塞），目前无法表达。

**方案：** `itt intent create ... --follows intent-005` 或 `--blocked-by intent-008`，或简单的 `related_ids` 字段。

## 6. --why 在 intent 上可选、snap 上必填，不一致

有时 snap 的 why 不明显（纯机械性变更），强制填写只会产出废话。

**方案：** 两者都可选（inspect 时高亮缺少 why 的对象），或两者都必填。消除不一致。

## 7. ID 格式天花板

零填充 3 位（max 999）。本项目已 44+ intent，长期运行项目会触顶。

**方案：** 改为 4 位或动态宽度。

## 8. `itt hub start` 必须从 Intent 仓库目录运行（已解决）

将 `apps/` 打包进 pip package，`itt hub start` 从任意目录可用。

---

## 更大的思考：以 inspect 恢复质量为核心指标

Intent 的核心价值在于 `inspect` 输出能否让下一个 session 立刻干活。最大杠杆：

- **inspect 输出质量**：目前只列 `what`，不展示 latest snap 的 `next`（恢复的关键信息）
- **减少 agent 判断负担**：SKILL 中大量 "evaluate whether..."、"determine which path..." 消耗推理 token 且结果不稳定
