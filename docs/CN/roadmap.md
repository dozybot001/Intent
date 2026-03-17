[English](../EN/roadmap.md) | 简体中文

# Intent 路线图

用途：整理 v0.2 简化之后的后续工作。本文是当前路线图。

通向首个 release 的历史路线图见：[roadmap-v0.1.0.md](archive/roadmap-v0.1.0.md)

## 当前阶段

CLI 已从 5 对象模型（intent、checkpoint、adoption、run、decision）简化为 2 对象模型（intent、checkpoint）。Schema version 为 0.2。

核心闭环现在是 `start → snap → done`，所有输出为 JSON。重心已从"证明原型成立"转向"验证这个最小模型在实践中是否有用"。

## 已完成的部分

- `.intent/` 本地对象层，2 种对象类型
- `init → start → snap → done` 核心闭环
- `adopt` 和 `revert` 用于候选比较工作流
- `inspect` 作为主要的机器可读入口
- `list` 和 `show` 用于对象查询
- JSON-only 输出（无人类可读文本模式）
- CI、build 验证和 agent 集成 setup
- 双语文档（EN/CN）

## 优先级原则

- 优先从真实 agent 使用中拿反馈，而不是扩功能
- 优先保持简单——抵制添加新对象或状态
- 持续把本地 semantic layer 放在中心
- 在本地工作流被验证之前，不引入平台化范围

## Phase 1：Agent Dogfooding

目标：在真实 agent 工作流中使用 Intent，验证 2 对象模型。

关键问题：

- `start → snap → done` 对 agent 是否自然？
- `inspect` 是否给 agent 提供了足够的上下文？
- candidate/adopt 工作流是否有用，还是 default-adopted 就够了？
- 错误消息和 suggested fix 是否可操作？

完成标志：

- 重复真实使用时不再需要临时 workaround
- 清楚理解哪些部分有效、哪些需要改动

## Phase 2：Hardening

目标：基于真实使用反馈让实现更可靠。

- 修复 dogfooding 中发现的边界情况
- 稳定 JSON contract
- 确保测试覆盖真实的失败模式

## Phase 3：决定下一个方向

候选方向：

- 更丰富的 inspection 和查询能力
- IntHub 用于远端组织和人类可读视图
- 超出本地 CLI 的协作功能

决策原则：选择最小的、受真实使用驱动的下一步。

## 明确暂缓

- 把 remote sync 当成默认前提
- 平台化 timeline UI
- 重新引入已移除的对象（adoption、run、decision），除非被证明必要
- 在真实压力出现前就上复杂过滤器和查询语言
- 试图替代 Git 的版本控制角色

## 一句话总结

简化之后的路线图，核心是验证两个对象和一个简单闭环是否足以让 agent 驱动的开发更可追踪。
