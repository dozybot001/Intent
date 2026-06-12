# Intent 评估设计

中文 | [English](../EN/evaluation.md)

Intent 的核心主张不能只靠逻辑推导证明。它需要一个可复现、可证伪的评估框架来回答两个问题：

- `itt` 对工作流的额外负担是否足够小
- `intent / snap / decision` 是否足以帮助下一次 session 恢复工作，而且对象边界是否必要

## 1. 核心假设

### H1：低干扰

使用 Intent 后，记录语义历史不应显著增加用户或 agent 的工作负担。

可观察信号：

- 额外命令数
- 记录耗时
- 额外 token / 字符数
- 用户确认次数
- 记录对象数量是否失控

### H2：高接续收益

在新 session、换 agent 或上下文丢失后，`itt inspect` 应显著降低重新解释和重复调查成本。

可观察信号：

- 开始正确下一步的时间
- 向用户追问上下文的次数
- 重复读取、重复调查、重复试错的次数
- 是否违反长期约束
- 最终补丁是否沿着原目标推进

### H3：对象设计必要且充分

`intent / snap / decision` 应该是一个低冗余的最小对象集合。

- 充分性：完整 Intent 上下文应接近完整 transcript 的接续质量，但成本明显更低
- 必要性：删除某类对象或关键字段后，应出现可解释的退化

## 2. 通用任务套件

评估任务不应从 Intent 自身或某个已有项目历史中挑选特例。任务应重新设计为通用、可复现的小型开发场景，并放在独立 fixture 仓库中。

每个任务包含：

- 一个小型代码仓库
- 初始代码状态
- Session A 的目标
- Session A 结束后的代码状态
- 可选的长期约束
- Session B 的续做目标
- 隐藏 oracle：正确行为、禁止行为、评分标准

任务应覆盖常见 agent 开发工作，而不是只覆盖 Intent 擅长的场景。

### 任务类型

| 类型 | 测什么 | 示例 |
| --- | --- | --- |
| Bug continuation | 最近调查结论和下一步是否能继承 | Session A 定位到真正原因但未完成修复；Session B 继续修 |
| Feature continuation | 目标和已完成里程碑是否清楚 | Session A 完成 API 层；Session B 接 UI 或测试 |
| Refactor continuation | 架构意图是否能延续 | Session A 抽出接口；Session B 迁移剩余调用点 |
| Decision inheritance | 长期约束是否会被遵守 | 约束“不要引入依赖”或“保持 public API 兼容” |
| Decision conflict | 冲突是否会被发现 | Session B 的请求与 active decision 冲突 |
| Negative handoff | 无意义语义是否不会污染恢复 | Session A 只有机械改动或失败尝试 |
| Multi-intent ambiguity | 多目标状态是否会被区分 | 一个 active，一个 suspended，Session B 只应继续相关目标 |
| Correction recovery | 错误记录或方向变更是否可恢复 | Session A 中途推翻方案，Session B 不应沿用旧方向 |

## 3. 任务生成规则

为了避免“为 Intent 量身定制任务”，每个任务应满足以下约束：

- 仓库规模小，但不是玩具：通常 5-20 个文件
- 任务需要跨至少 2 个文件，避免单点编辑过于简单
- Session A 必须留下非显然上下文，例如调查结论、权衡、被排除方案或长期约束
- Session B 不能只靠 diff 直接推出全部答案
- oracle 必须能判断“做对”和“看似完成但方向错误”
- 每类任务至少有多个等价实例，避免单例过拟合

通用任务可以用以下领域构造：

- CLI 工具
- REST API
- 小型前端组件
- 数据处理脚本
- 配置/部署脚本
- 文档与 agent skill 同步

## 4. 对照条件

同一个任务应在多个上下文条件下运行。

| 条件 | Session B 可见内容 | 目的 |
| --- | --- | --- |
| No history | 仅仓库代码 | 下界 |
| Git only | 代码 + commit / diff / commit message | Git 基线 |
| Chat summary | 人写或 agent 写的普通总结 | 非结构化语义基线 |
| Full transcript | 完整或高质量压缩对话 | 高成本上界 |
| Intent full | `intent + snap + decision` | 被测方案 |

## 5. Ablation 条件

为了检验对象设计，而不是只检验“有总结比没总结好”，需要删除对象或字段。

| Ablation | 预期退化 |
| --- | --- |
| 无 intent | 目标边界不清，容易继续错任务 |
| 无 snap | 最近推进和调查结论丢失，重复工作增加 |
| 无 decision | 长期约束更容易被违反 |
| 无 why | 知道做了什么，但不知道为什么，方案延续能力下降 |
| 无状态 | 可能继续 done / deprecated 对象 |
| 无关系链接 | 检索和归因成本升高 |

如果某个 ablation 没有稳定退化，说明对应对象或字段未被证明必要，应重新收敛设计。

## 6. 评分指标

### 工作流成本

- `record_command_count`
- `record_elapsed_seconds`
- `record_token_estimate`
- `user_confirmation_count`
- `objects_created`

### 接续质量

- `time_to_first_correct_action`
- `clarification_count`
- `repeated_investigation_count`
- `decision_violation_count`
- `wrong_direction_edits`
- `task_success`
- `patch_quality_score`

### 盲评

评审者只看 Session B 的行为和结果，不知道使用了哪种上下文条件。

评分维度：

- 是否理解目标
- 是否理解最近进展
- 是否遵守长期约束
- 是否避免重复调查
- 是否产出正确补丁

## 7. 判定标准

Intent 的目标不是超过完整 transcript 的信息量，而是在成本显著更低时接近它的接续效果。

一个合理成功标准：

- `Intent full` 的接续质量显著高于 `Git only` 和 `Chat summary`
- `Intent full` 的记录和读取成本显著低于 `Full transcript`
- 删除 `intent / snap / decision` 任一对象后，在对应任务类型上出现可解释退化
- `No history` 与 `Git only` 条件下常见的重复调查、决策违反或目标误解，在 `Intent full` 中明显减少

## 8. 最小可行评估

第一版不需要大规模实验，可以先做一个小而严谨的 benchmark：

- 8 类任务
- 每类 3 个实例
- 5 个上下文条件
- 6 个 ablation 条件
- 每个条件至少重复 3 次

这样可以得到第一批可复现数据，并暴露对象设计中真正薄弱的地方。

首版可运行 harness 通过 [`itt benchmark`](benchmark-cli.md) 暴露，方便不同 agent 在相同任务上生成上下文、完成续做并评分。

## 9. 反证优先

评估的目的不是证明 Intent 永远正确，而是尽早发现它在哪些情况下不成立。

需要特别关注：

- 普通 summary 是否已经足够
- decision 是否会累积成噪声
- snap 是否会被写成机械日志
- `why` 是否经常变成空泛解释
- 对象关系是否真的降低恢复成本
- 用户触发记录是否比自动记录更可靠

如果这些问题被数据证实，Intent 应该调整对象模型或记录流程，而不是维护原始设想。
