[English](../../EN/archive/roadmap-v0.1.0.md) | 简体中文

# Intent 路线图归档：v0.1.0

用途：保留从初版 CLI 概念走到第一个 tag 版本时使用过的路线图。

## 历史阶段

当时的实现目标是这条本地最小闭环：

- `.intent/` 本地对象层
- `init -> start -> snap -> adopt -> log`
- `status --json` / `inspect --json`
- surface CLI 与最小 canonical action
- Git 前置条件、错误模型和基础测试
- 基础 read-side 命令
- 面向 human / agent 的 demo 脚本
- 初始版 `run` lifecycle 和最小 `decision` 支持
- 基础 CI、本地安装说明和 package build 验证

当时的推进顺序是：

1. 先把 v1 CLI 打磨到稳定可用
2. 再补读能力和 agent 入口
3. 再引入 `run` / `decision`
4. 最后再考虑更远的协作层

## 历史优先级原则

- 优先补会提升可靠性和可用性的能力
- 优先补会让人和 agent 都更容易接入的能力
- 优先补能尽快形成演示和验证材料的能力
- 暂不为了“对象完整性”提前实现低频能力
- 暂不进入远端同步、平台化协作、复杂筛选器

## 历史 Milestones

### Milestone 1: 打磨 v1 CLI

目标：补齐当前 CLI 的基础可用性与演示材料。

建议项：

- 补充只读命令：`intent show`、`checkpoint show`、`adoption show`
- 补充基础列表命令：`intent list`、`checkpoint list`、`adoption list`
- 为 `config.json` 提供最小读写入口，例如 `itt config show`
- 增加一个官方 smoke script，方便快速验证主路径
- 准备一个 human demo，用 `itt log` 展示采纳历史
- 把 human 输出进一步对齐文档中的文案基线
- 补充更多错误分支测试和 JSON contract 测试

完成标志：

- 常见读写命令都能在本地自洽使用
- 主要错误场景都有测试覆盖
- 新用户按 README 可以完成一次完整演示

### Milestone 2: 强化 Agent / Automation 体验

目标：让 Intent 更容易被 agent、脚本和自动化稳定消费。

建议项：

- 补全 canonical CLI 的最低只读能力
- 让 `inspect --json` 在冲突、空状态、revert 后场景更丰富
- 准备一个 agent demo，用 `inspect --json` 驱动下一步动作
- 为写命令补更多 machine-friendly 字段，例如更一致的 `next_action`
- 增加 `--id-only` 和 `--json` 的回归测试矩阵
- 增加可复用的 fixture / helper，降低未来测试维护成本

完成标志：

- agent 可以只靠 `inspect --json` + canonical action 完成主路径
- JSON 返回结构在主要状态切换中保持稳定

### Milestone 3: 引入 `run`

目标：记录一次 agent 执行或一轮探索过程，为 provenance 和 automation 提供语义 span。

建议项：

- 落地 `run start` / `run end`
- 在 `state.json` 中正确维护 `active_run_id`
- 让 checkpoint / adoption 可以挂接 `run_id`
- 定义 run 的最小 inspect 输出

完成标志：

- 一轮 agent 执行可以被正式建模
- run 不影响已有 `start -> snap -> adopt` 闭环

### Milestone 4: 引入 `decision`

目标：把“为什么是这个，而不是那个”从 adoption 附注提升为更长期可复用的对象。

建议项：

- 增加 `decision create`
- 明确 decision 与 adoption / intent 的关联方式
- 设计适合沉淀原则判断的最小 schema
- 明确 decision 何时应该出现，避免强制化

完成标志：

- 关键取舍可以被稳定引用
- decision 不挤占首页主路径

### Milestone 5: 分发与协作

目标：让 CLI 更容易安装、试用、分享，并为未来协作层铺路。

建议项：

- 完善安装方式和版本管理
- 增加 CI，自动运行测试
- 补使用示例、演示脚本和发布说明
- 结合真实 repo 做 dogfooding
- 在本地 layer 稳定后，再评估 Skill / IntHub 接入点

完成标志：

- 外部用户可以方便安装和试用
- 每次改动都有自动化验证

## 历史当前下一步

如果当时只做一轮实现，顺序是：

1. human demo：`itt log` 对比 `git log`
2. agent demo：`inspect --json` 驱动下一步动作
3. 更完整的 JSON / error 测试
4. `run start/end`

## 历史暂缓项

- 远端同步
- 平台化 timeline UI
- 复杂过滤器与查询语言
- 大规模对象扩张
- 把 `log` 变成全量 JSON timeline API

## 历史总结

这份归档路线图记录的是通向 `v0.1.0` 的那条路径：先把本地 semantic layer 做稳，再逐步扩到后续对象和协作设想。
