---
name: intent-cli
description: >-
  在用户已明确为指定仓库或任务启用 Intent 自动维护时，贯穿工作过程维护语义历史
  （.intent/）；也处理明确的一次性 Intent 记录、接续和 IntHub 同步请求。
  自动维护在每轮开头读取、结束前判定闭环，仅记录已验证的语义变化。
  安装 Skill、已有历史、普通笔记或提到 Intent 均不代表启用。
  网络同步始终需要独立的明确请求。
---

# Intent CLI

保存足够让另一个 Agent 接续的已验证语义，不把对话变成日志。已授权维护或记录的每轮都要判定闭环，不是每轮都要创建对象。没有进入授权流程时，闭环分类不适用。

## 范围与授权

- **自动维护：**用户直接、或通过可信且经用户批准的项目指令，明确为指定仓库或任务启用。此后持续授权本地 inspect 与记录，直到撤销；不要每轮再次询问。先确定范围。修改本 Skill 本身不代表在任何仓库启用。
- **一次性记录：**明确要求通过 Intent 或 `.intent/` 写入，仅授权这次记录流程。普通总结、笔记或状态汇报不是授权。
- **接续：**明确要求通过 Intent 恢复时，先只读。继续工作不代表持续记录授权，除非已启用自动维护。
- **同步：**只有明确要求把 Intent 数据推到 IntHub 才授权网络同步。执行前读 [references/sync.md](references/sync.md)。Git push、记录授权和自动维护都不授权同步、登录或公开发布。

用户要求只读、本轮不记录或关闭维护时优先遵守。仓库存在、已有历史和 Skill 安装都不代表启用。授权不跨仓库。没有已授权模式时，不运行 `itt`。

## 自动工作闭环

1. **开头——读一次。**确定已授权的 Git 根目录。没有 hook 结果时运行一次 `itt inspect`；可信 hook 的成功、无 warning 且对应此根目录与当前 turn 的结果可复用。已提供的失败、超时、图 warning 或身份不匹配会禁用本轮历史写入；不要把它当作缺失上下文，再 inspect 来恢复写权限。图 warning 用 doctor 诊断，主任务继续。使用相关检查点与 active Decision，不逐条播报历史。仅当目标 Intent 最新检查点不足时读取 `itt inspect --intent ID --history 3`。缺失事实不猜测。
2. **过程中——保存关键变化。**优先复用匹配 Intent。目标或可独立验证的里程碑明确后，趁上下文新鲜记录，尤其在进入漫长或高风险的下一阶段前。不把计划写成完成事实，不记录每条工具调用或中间编辑。只有协调 Agent 写入，子 Agent 向它提供已验证事实。
3. **最终回复前——判定闭环。**为每个发生实质变化的目标保存已验证结果或准确接续检查点，并验证最终状态。整轮归为 **recorded**（已记录）、**no-op**（没有接续关键的新语义，或用户明确跳过记录）、**failed**（记录不可用、未完成或未验证）。里程碑已记录且最新检查点准确时，不重复追加结束 Snap。

常规成功和 no-op 静默完成；不要求用户额外执行检查仪式或再次确认。失败或部分写入时简短报告，并列出成功对象 ID，不把主任务冒充为失败。Intent 失败停止历史写入，不妨碍其他已授权的项目工作。中断或崩溃不算成功闭环；过程里程碑只能减少损失，不能保证最终检查点。

这里的闭环是 Agent 义务，不是已实现的回执命令。只有接入 Codex hooks 时才读 [references/codex-hooks.md](references/codex-hooks.md)。不要虚构回执、启用命令，或声称 hooks 已安装。

## 按语义选择，不按数量选择

- 一个 **Intent** 是有独立结果与生命周期的连贯目标。可独立接续的目标应分开，不为“一个 Intent 配额”合并。复用匹配的 active Intent；只有实际恢复工作或追加 Snap 时才用显式 ID 激活匹配的 suspended Intent。只为真正的新目标创建对象。不按 session、query、文件、提交、命令或实现层拆分。
- 一个 **Snap** 是且仅是一个 Intent 内只追加的里程碑、已验证结论、纠正或检查点。能独立验证或取代的结论应拆开，同一结论的证据合并。跨 Intent 分别写 Snap。跳过日志和常规机械编辑；Intent、Snap 均无数量配额。
- 发生变化且仍未结束的 Intent，最新 Snap 必须自包含：**Verified / Boundary / Next / Blocker / Constraints**。写清已验证状态、未完成或不在范围内的边界、下一具体动作、blocker（没有时写 `none`）及局部约束。紧凑编码进 `what` 与 `why`；前置结果可摘要。未变化且已准确的检查点不重写。
- **Decision** 是未来处理不同问题的 Intent 仍要遵守的规则。用户明确给出的持久规则已经确认；自行推断的实现选择不是。未确认候选留在 Snap 的局部约束里或省略。确需确认时，整个流程至多合并成一次简短批量询问；不要仅为收集 Decision 打断用户。

Intent `what` 命名目标，`why` 解释动机。Snap `what` 写已验证变化或检查点，`why` 写推理与约束。纠错追加后续 Snap，不重写旧对象。

Query 边界不改变 Intent 生命周期。仍在推进的目标保持 active。只有验证目标解决才 done；主动放弃时带原因 cancel；真正暂停时先保存检查点再 suspend。done 前确保已保留完成证据与有意延期的边界。

## 一次性记录与显式接续

一次性记录遵守同样的 inspect、语义筛选和验证闭环。只记录当前上下文中已验证的工作，不声称知道上次记录以来的一切。零写入合法。区别于静默自动维护，简短报告记录了什么或为何没有写入。

显式接续先 inspect，不先读旧聊天或从代码重新发现事实。行动前仅根据 Intent 陈述目标与原因、已验证边界、下一步或 blocker、适用 Decision。缺口如实标明；代码和测试重发现、用户重解释不算 Intent 恢复证据。只为目标 Intent 读取受限历史；最近三条仍不足时报告缺口，不无限读取。只有用户要求实际继续，才激活 suspended Intent；仅查看不激活。

## 执行边界

第一条命令前读 [references/execution.md](references/execution.md)，使用安全 argv 执行与失败处理。固定不变量：绝对仓库 cwd、逐条等待命令结束、解析 JSON 并要求 `ok: true`、捕获显式 ID、不直接编辑 `.intent/`。

常规 turn 不自动初始化。首次 `NOT_INITIALIZED` 仅在明确包含初始化授权的设置/启用流程或一次性记录中允许继续 `itt init`，之后重新 inspect。接续与常规自动维护则报告历史不可用。`inspect` 的对象图 warning 要运行 `itt doctor` 并停止写入，不自动修复。其他命令的提示性 warning 不自动等于图损坏，应判断其含义。

不盲目执行 `suggested_fix`、不暴露凭据、不修改 Git remote、不自动运行认证、hub 服务或同步命令。

## 本地命令范围

```text
itt init
itt inspect
itt inspect --intent ID --history 3
itt doctor
itt intent create WHAT [--why WHY]
itt intent activate ID
itt intent suspend ID
itt intent done ID
itt intent cancel ID [--reason REASON]
itt snap create WHAT --intent ID [--why WHY]
itt decision create WHAT [--why WHY]
itt decision deprecate ID [--reason REASON]
```
