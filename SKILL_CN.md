---
name: intent-cli
description: >-
  在已启用项目级维护的项目内持续维护已验证的 Intent 语义历史；itt init 默认启用。
  每轮开头读取、过程中保存关键变化、结束前以 recorded/no-op/failed 回执闭环。
  也处理明确的项目启用、Intent 一次性记录、接续和 IntHub 推送/拉取请求。
  已关闭或旧版项目不自动启用；网络同步需要独立明确请求。
---

# Intent CLI

保存足够让另一个 Agent 接续的已验证语义，不把对话变成日志。持续维护是常规模式；每轮判定闭环，不是每轮新增 Snap。

## 项目范围

- 首次启用、缺少 `itt` 或需要可选 IntHub 认证时读 [onboarding.md](references/onboarding.md)。缺少 `itt` 时先征得安装确认，再安装、验证并继续原流程，不停在“找不到命令”。本地记录不需要账号。
- 确定规范化的语义根目录；Git 可选。可信且对应本项目、当前轮的 hook 上下文就是开头快照，否则检查 `itt maintenance status`。执行命令前读 [execution.md](references/execution.md)。
- 新历史的 `itt init` 默认开启维护并安装项目级 Codex hooks；已有历史只需一次 `itt maintenance on`。 `itt maintenance off` 只关闭当前项目。安装 Skill 不会开启其他项目。
- 已配置不等于已执行：Codex 需要审核并信任 hooks。仅设置、缺失 hooks 或宿主适配时读 [codex-hooks.md](references/codex-hooks.md)。
- IntHub 可选。用户明确需要且认证缺失时，引导到 IntHub 官网登录并创建 access token，再由用户私下输入 `itt auth login`；不要求把 token 粘贴到聊天。完整路径见 [onboarding.md](references/onboarding.md)。
- 已关闭或未初始化的项目不自动写语义。仍可明确要求一次性记录；仅请求的设置、记录或恢复确实需要时初始化。接续先只读。
- 用户要求只读、本轮跳过或关闭维护时优先遵守。不自动同步、登录、公开发布或改 Git remote。明确推送/拉取时分别读 [sync.md](references/sync.md) / [pull.md](references/pull.md)。遵守请求顺序；未来上传计划不是当前授权。

## 静默工作闭环

1. **读一次。**复用本轮 hook 上下文，否则 inspect 已启用的根目录。缺少事实时只读目标 Intent 的 `--history 3`；被截断的上下文不是完整历史。代码重发现和用户解释不算 Intent 恢复证据。
2. **保存关键进展。**复用匹配目标，趁上下文新鲜保存已验证里程碑，尤其在漫长或高风险阶段之前。只有协调 Agent 写入。不记录每条工具调用、中间编辑，不把计划写成完成事实。
3. **回复前收尾。**变化且未结束的目标需要准确接续检查点。有 hook token 时提交以下回执；没有 token 时判定闭环，不虚构 token 或声称硬性保障。

```text
itt maintenance close recorded --turn TOKEN [--objects ID ...]
itt maintenance close no-op --turn TOKEN --reason REASON
itt maintenance close failed --turn TOKEN --reason REASON
```

`recorded` 校验真正变化的对象，ID 可自动推导。`no-op` 是没有接续关键变化或用户跳过记录的正常结果：给简短原因，不制造凑数 Snap。`failed` 如实确认记录不可用或未验证。回执是本地每轮元数据，不是语义对象。Stop 重试只补收尾，不授权重复同步或任务副作用。

正常成功与 no-op 静默完成；未解决或部分记录失败时简短披露成功 ID。可恢复错误经诊断、验证后继续，不盲目重试创建或执行 suggested_fix。未解决的历史错误只暂停受影响历史操作，不妨碍其他已授权工作。

## 语义边界

- **Intent：**有独立结果与生命周期的连贯目标。可独立接续的目标拆开；实际继续时复用匹配的 active/suspended 目标。无配额，不按 query、session、文件、命令、提交或实现层拆分。
- **Snap：**仅一个 Intent 内只追加的已验证里程碑、结论、纠正或检查点。可独立验证/取代的结论拆开，同一结论的证据合并，跨 Intent 分别写 Snap。跳过日常日志，纠正追加后续 Snap。
- **Decision：**未来处理不同问题的 Intent 仍须遵守的稀缺规则。用户明确的持久规则已确认；推断的实现选择保留在局部或省略。必要澄清整个流程最多一次简短批量询问，不逐候选打断。

Intent `what` 命名目标，`why` 解释动机；Snap 字段保留已验证变化及推理。变化且仍开放或即将暂停的 Intent，最新 Snap 应独立回答 **Verified / Boundary / Next / Blocker / Constraints**，没有 blocker 写 `none`。未变化且准确的检查点不重写。

一轮问答结束不代表 Intent 结束。验证目标解决且保留完成证据/延期边界才 done；主动放弃带原因 cancel；真正暂停先保存检查点再 suspend。

## 显式记录 / 接续

只记录当前上下文验证的工作，不声称知道“上次以来的一切”；零写入合法。一次性记录简短报告结果，持续维护则静默。

接续先 inspect，不先读旧聊天或代码；行动前仅根据 Intent 陈述目标/原因、边界、下一步/blocker 与 Decision。缺口如实标明；最近三条 Snap 仍不足时报告缺口，不无限读历史。仅查看 suspended 目标不激活它。
