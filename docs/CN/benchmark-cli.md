# Intent Benchmark CLI

中文 | [English](../EN/benchmark-cli.md)

`itt benchmark` 用小型、可再分发的 fixture 仓库运行可复现的接续实验。默认协议为每个任务冻结唯一的 Session A 后 checkpoint，为每个条件复制同一 checkpoint，并且只调用干净的 Session B。这样可以从接续比较中去掉不同条件下 Session A 行为的混淆。

实验协议及允许得出的结论已经固定在公开的
[接续 benchmark 预注册](../benchmarks/continuation-benchmark-preregistration.md)中。
screening 结果只属于工程证据，不能作为确认结果。

## 默认 Continuation 运行

直接使用 `itt benchmark` 会选择冻结 checkpoint 的 continuation 协议，但真实 Codex 运行必须显式指定预注册模型。本 cohort 强制使用 `gpt-5.6-terra` 和 `low` 推理档位。

```bash
itt benchmark \
  --stage screening \
  --tasks bug-cli-config-cache-001 \
  --conditions no-history,git-only,flat-facts-matched,intent-full \
  --repeat 1 \
  --model gpt-5.6-terra \
  --reasoning-effort low \
  --timeout 600 \
  --seed 1729
```

默认单 trial timeout 为 600 秒。命令行仍输出 Intent CLI 的标准 JSON 包；`result.runs` 保存原始 trial 行，持久化的 `manifest.json` 与 `report.json` 是审计主数据源。

### 研究与资源参数

| 参数 | 含义 |
|---|---|
| `--stage screening\|confirmation\|exploratory` | 记录研究阶段。默认为 `screening`；只有标为 `confirmation` 的预注册 holdout 运行才可能获得确认性判定。 |
| `--confirmation-lock FILE` | `confirmation` 必填；校验冻结 task hash、conditions、repeats、seed、model、effort 与预注册 hash。 |
| `--seed N` | 固定任务别名、pair 顺序和 Latin rotation 后的条件顺序。默认为 `1729`。 |
| `--max-pairs N` | 完整 task/repeat block 的硬上限，必须结束在完整 task wave 边界。 |
| `--max-total-input-tokens N` | 在下一组完整 pair 开始前检查的累计软阈值。 |
| `--max-total-wall-seconds S` | 在下一组完整 pair 开始前检查的 suite wall-time 软阈值。 |
| `--timeout S` | 单 trial runner timeout。默认为 `600`。 |
| `--repeat N` | 完整成对 wave 数；所有预注册 repeat 都计入结果。 |
| `--out DIR` | 写入指定目录；替换已有输出必须显式使用 `--force`。 |

token 与 wall 阈值不会在一个 pair 中途打断运行，因此最后一个 pair 可能超过阈值。若需要硬性的调用次数和单调用时间边界，请同时使用 `--max-pairs` 与单 trial timeout。Codex JSONL 事件中的 token 数据用于资源审计，不等同于账单金额。

## 冻结内容

任何模型调用前，continuation runner 会：

1. 从可变源码树中加载并分离任务 spec；
2. 生成并校验唯一的 Session A 后 canonical checkpoint；
3. 记录任务和 checkpoint hash；
4. 使用固定 seed 生成完整成对计划；
5. 同时包含 `flat-facts-matched` 与 `intent-full` 时，校验两者的事实和上下文长度一致性。

同一 pair 的每个条件都从相同源码 checkpoint 与干净 Git 状态开始。Intent 完整图通过外部临时 fixture 调用真实 `inspect --full` 产品视图生成；系统不会只向 Intent trial 仓库添加 `.intent/`。

本协议只有 Session B 调用 Codex。记录成本和自动 Session A 捕获属于不同研究问题，应使用旧两段协议或独立实验。

## 主要公平条件

默认 continuation 条件为：

- `no-history` — 仅提供仓库 checkpoint 与当前 Session B 目标；
- `git-only` — 提供任务定义允许的 canonical Git handoff；
- `flat-facts-matched` — 对与 Intent 完全相同的语义事实进行无分组、确定性渲染；
- `intent-full` — 将同一组事实表示为完整 Intent 对象图，包括状态、`why`/`reason` 和关系。

`flat-facts-matched` 是检验对象模型价值的主要公平基线，不能用更弱、独立撰写的摘要代替。若 `intent-full` 与它持平，结果可以在同时胜过 code-only 基线时支持“语义交接有价值”，但不能证明 Intent 结构优于同等信息量的平铺表示。

通用 harness 仍可能提供 `chat-summary`、`full-transcript`、`flat-facts` 等旧版或调试条件；它们不是预注册的主要 flat 基线。

## 隔离与标签遮蔽

每个 Session B 都使用全新的临时 `HOME` 和 `CODEX_HOME`：

- 仅复制 `auth.json` 和最小模型/provider 配置；
- 不复制全局 `AGENTS.md`、skills、plugins、memory、历史 sessions 或 project trust；
- 使用 `--ephemeral` 与 `--ignore-rules` 启动 Codex；
- 默认不向任务 agent 暴露 Intent CLI 内部实现。

当前预注册 runner 还使用 macOS `sandbox-exec`，拒绝读取兄弟 trials、evaluator 文件、真实 Codex home 与 Intent benchmark 源码。若平台缺少这层 evaluator 读隔离，本 cohort 会拒绝启动，而不是静默降低协议强度。

模型运行期间，任务名与 treatment 名会替换成不透明别名，suite 停止后才解码。这属于**标签遮蔽**，不是真正无法推断的盲测：agent 仍可能根据收到的表示推断条件。报告和结论必须保留这一准确边界。

## 审计产物

完成后的 suite 大致具有以下结构：

```text
.itt-benchmark/
  runs/
    continuation-YYYYMMDD-HHMMSS/
      manifest.json
      report.json
      tasks/
        <frozen-task>.json
      checkpoints/
        task-001/
          checkpoint.json
          repo/
      trials/
        trial-0001/
          run.json
          session-b/
            context.md
            instructions.md
            codex-events.jsonl
            repo/
```

`manifest.json`、`report.json`、checkpoint metadata 与逐 trial 记录共同保存：

- task spec 与 checkpoint hash；
- matched semantic facts 与渲染 context hash；
- 解码后的 task、condition、pair、repeat、顺序与 C0–C4 stratum；
- runner、model、reasoning effort、timeout、seed、环境与源码指纹；
- 原始得分、耗时、Session B token 使用、错误、无效 pair 与资源停止原因；
- 全体配对统计、按 stratum 统计、C2/C3 efficacy 统计和预注册阈值判定。

基础设施失败会使完整 pair 失效，而不会让单个有利条件留在聚合结果中。agent 自身的任务失败仍计为失败。冻结任务 spec 和所有已尝试 trial 产物都会保留用于审计。

## 有效性边界

- 从 `--stage screening` 开始，不得把 screening 输出描述为确认结果。
- 所有条件都接近 100% 表示天花板效应，不代表 Intent 有优势。
- 隐藏行为测试在隔离仓库副本中运行；源码字符串检查只能作为辅助诊断，不能单独构成证据。
- C0 代码充分控制、C2/C3 效果任务和 C4 安全控制分别报告。
- 模型、推理档位、任务版本、prompt、renderer 或协议不同的运行不得合并。
- 只有 holdout 运行及全部预注册阈值均通过，才能得出确认性结论。

现有的[低资源工程冒烟记录](../benchmarks/2026-07-30-low-resource-smoke.md)验证的是更早期的工程链路，并暴露了天花板效应。它不是正向有效性结果，也不会与新协议合并。

## 旧版自动两段 Session 协议

使用 `--protocol live` 运行旧版自动化 Session A + Session B 流程：

```bash
itt benchmark \
  --protocol live \
  --tasks bug-cli-config-cache-001 \
  --conditions no-history,intent-full \
  --repeat 1 \
  --model gpt-5.6-terra \
  --reasoning-effort low \
  --timeout 600
```

这个协议会分别为每个条件调用模型创建 Session A checkpoint，适合端到端工作流实验，但结果不得与冻结 checkpoint 的接续效果混合。

## 手工 Live 调试命令

`benchmark live` 子命令仍用于手工检查每个 handoff 步骤。

```bash
itt benchmark live start \
  --task bug-cli-config-cache-001 \
  --condition intent-full \
  --out /tmp/intent-live/run-001

itt benchmark live begin --run /tmp/intent-live/run-001 --phase a
itt benchmark live checkpoint --run /tmp/intent-live/run-001
itt benchmark live handoff --run /tmp/intent-live/run-001
itt benchmark live begin --run /tmp/intent-live/run-001 --phase b
itt benchmark live score --run /tmp/intent-live/run-001
itt benchmark live report --runs /tmp/intent-live
```

这些命令不会自动启动模型。每一步之间需要把生成的 `instructions.md` 交给对应的干净 session。

## 其他调试命令

```bash
# 列出任务 fixture
itt benchmark list

# 生成 canonical Session A 后仓库
itt benchmark materialize \
  --task bug-cli-config-cache-001 \
  --stage after_a \
  --out /tmp/intent-bench-task

# 渲染 fact-matched handoff
itt benchmark context \
  --task bug-cli-config-cache-001 \
  --condition flat-facts-matched \
  --out /tmp/context.md

# 渲染 Intent ablation
itt benchmark context \
  --task bug-cli-config-cache-001 \
  --condition intent-full \
  --ablation no-decision \
  --out /tmp/context.md

# 给已完成仓库评分
itt benchmark score \
  --task bug-cli-config-cache-001 \
  --repo /tmp/intent-bench-task
```

可用 Intent ablation 为 `no-intent`、`no-snap`、`no-decision`、`no-why`、`no-status` 和 `no-relations`。
