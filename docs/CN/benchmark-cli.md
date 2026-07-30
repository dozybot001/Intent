# Intent Benchmark CLI

中文 | [English](../EN/benchmark-cli.md)

`itt benchmark` 是随 Intent CLI 分发的通用、可复现 benchmark harness，用于从 agent 实际使用的同一个 CLI 中测试 Intent 的工作流成本和接续收益。

benchmark 刻意独立于 Intent 自身开发历史。每个任务都是一个小型 fixture 仓库，包含：

- base 文件
- Session A 的改动与记录
- Session B 的续做目标
- Intent 风格的上下文对象
- 用于给 Session B 完成结果评分的隐藏 oracle

## 一条命令运行

默认路径会在 `.itt-benchmark/runs/<run-id>/` 里自动创建干净任务仓库，依次启动 Codex Session A、生成交接层、再启动干净 Codex Session B，最后输出成功率、总用时、B 段用时和 handoff 字符量。

```bash
itt benchmark
```

常用覆盖项：

```bash
itt benchmark \
  --out /tmp/intent-live \
  --conditions no-history,git-only,chat-summary,intent-full,full-transcript \
  --tasks bug-cli-config-cache-001 \
  --repeat 1 \
  --model gpt-5.6-terra \
  --reasoning-effort low
```

输出仍是 Intent CLI 的标准 JSON，其中 `result.table` 是紧凑对比表，`result.runs` 保留每个 trial 的明细。默认 runner 是 `codex`，要求本机可执行 `codex exec`。推理档位默认是 `low`；正式对比应显式指定模型与档位，并保证所有条件一致。

每次运行也会把真实数据源写入 benchmark 专用目录：

```text
.itt-benchmark/
  runs/
    run-YYYYMMDD-HHMMSS-ffffff/
      manifest.json
      report.json
      tasks/
        bug-cli-config-cache-001.json
      trials/
        bug-cli-config-cache-001__intent-full__r01/
          run.json
          session-a/
          session-b/
```

- `manifest.json` 记录 runner、model、reasoning effort、tasks、conditions、repeat、Intent CLI 版本和路径。
- `report.json` 是本次 benchmark 的主结果，可作为后续分析和对比的数据源。
- `tasks/` 保存本次使用的 task spec 快照，避免后续 task 修改后无法复现。
- `trials/*/run.json` 保存单个两段 session 的事件、分数、用时和错误。

## 纯净 Codex Session

自动 runner 不直接使用当前用户的完整 `~/.codex`。每个 phase 都会创建独立的临时 `HOME` / `CODEX_HOME`：

- 只复制 `auth.json` 和最小模型/provider 配置。
- 不复制 `AGENTS.md`、skills、plugins、历史 sessions、memory 或 project trust 配置。
- 启动参数包含 `--ephemeral` 和 `--ignore-rules`。
- `manifest.json` 中的 `runner_isolation` 会标记为 `clean-home`。

这样 benchmark 更接近“干净 agent session”，避免被本机全局 agent 指令污染。

## 资源与有效性边界

- 先用单任务、两个条件、`repeat=1` 和 `--reasoning-effort low` 做冒烟验证，确认 checkpoint、runner 与评分链路有效后再扩跑。
- 现有 fixture 只适合作为工程 pilot。任务过少或所有条件成功率接近 100% 时，不应据此宣称 Intent 优于 Git 或普通摘要。
- 最终评分会在隔离副本中运行隐藏行为测试，并结合显式策略约束；源码字符串检查只作为辅助信号。
- Session A 指令包含精确 checkpoint。若 agent 越过停点提前完成 Session B 修复，该 trial 应记为 checkpoint failure，而不是产品效果数据。
- 模型、推理档位、任务快照和重复次数必须保存在 manifest 中；不同资源配置的结果不可直接合并。
- 自动 Codex runner 会从 JSONL 事件中记录输入、缓存输入、输出与推理 token；这些计数用于资源审计，不直接等同于账单。

首个低资源工程冒烟结果见 [2026-07-30 记录](../benchmarks/2026-07-30-low-resource-smoke.md)。两个条件均成功，说明当前任务存在天花板效应；该结果不能作为 Intent 有效性的正向证据。

## 调试命令

列出任务：

```bash
itt benchmark list
```

生成 Session A 后的仓库：

```bash
itt benchmark materialize \
  --task bug-cli-config-cache-001 \
  --stage after_a \
  --out /tmp/intent-bench-task
```

生成给 Session B 的上下文包：

```bash
itt benchmark context \
  --task bug-cli-config-cache-001 \
  --condition intent-full \
  --out /tmp/context.md
```

生成 ablation 后的 Intent 上下文：

```bash
itt benchmark context \
  --task bug-cli-config-cache-001 \
  --condition intent-full \
  --ablation no-decision \
  --out /tmp/context.md
```

给完成后的仓库评分：

```bash
itt benchmark score \
  --task bug-cli-config-cache-001 \
  --repo /tmp/intent-bench-task
```

## Live 两段 Session

Live benchmark 用于真实测试“Session A 做到 checkpoint 后交接给干净 Session B”的效果。

创建 run：

```bash
itt benchmark live start \
  --task bug-cli-config-cache-001 \
  --condition intent-full \
  --out /tmp/intent-live/run-001
```

Session A 开始前计时：

```bash
itt benchmark live begin --run /tmp/intent-live/run-001 --phase a
```

把 `/tmp/intent-live/run-001/session-a/instructions.md` 交给干净 Session A。Session A 完成 checkpoint 并停手后：

```bash
itt benchmark live checkpoint --run /tmp/intent-live/run-001
itt benchmark live handoff --run /tmp/intent-live/run-001
```

Session B 开始前计时：

```bash
itt benchmark live begin --run /tmp/intent-live/run-001 --phase b
```

把 `/tmp/intent-live/run-001/session-b/instructions.md` 交给干净 Session B。Session B 完成后：

```bash
itt benchmark live score --run /tmp/intent-live/run-001
```

汇总多个 run：

```bash
itt benchmark live report --runs /tmp/intent-live
```

Live report 同时输出成功率和用时；当不同条件成功率都接近 100% 时，重点比较 total time、B time 和 handoff time。

## 上下文条件

- `no-history`
- `git-only`
- `chat-summary`
- `full-transcript`
- `intent-full`

## Ablation

Ablation 只用于 `intent-full`：

- `no-intent`
- `no-snap`
- `no-decision`
- `no-why`
- `no-status`
- `no-relations`
