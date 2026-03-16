[English](../EN/roadmap.md) | 简体中文

# Intent 路线图

用途：整理 `v0.1.0` 之后的后续工作。本文是当前路线图，不是通向第一个 tag 版本时使用过的历史路线图。

通向首个 release 的历史路线图见：[roadmap-v0.1.0.md](archive/roadmap-v0.1.0.md)

## 当前阶段

`v0.1.0` 已经打 tag。初版本地 CLI 闭环已经成立，项目已经走出“先证明原型成立”的阶段。

下一步更重要的是使用、打磨、验证当前实现，而不是继续重复已经完成的 milestones。

## 已完成的部分

- `.intent/` 本地对象层
- `init -> start -> snap -> adopt -> log`
- `status --json` / `inspect --json`
- `intent`、`checkpoint`、`adoption`、`run`、`decision` 的 read-side 命令
- `run` 和 `decision`
- human / agent demos
- CI、build 验证、wheel install 验证
- 第一个已打 tag 的版本：`v0.1.0`

## 优先级原则

- 优先从真实使用里拿反馈，而不是继续扩对象面
- 优先补可靠性、可维护性和发布质量
- 持续把本地 semantic layer 放在中心
- 在本地工作流真正被验证之前，不提前引入平台化范围

## Phase 1：Dogfooding 与 Hardening

目标：把 `v0.1.0` 真正用到真实仓库里，并把粗糙处磨平。

建议项：

- 在一个或多个真实 repo 中使用 Intent，而不只是在合成 demo 里运行
- 收集命令文案、状态切换、恢复路径里的真实摩擦点
- 基于真实使用补 help、示例和 release 材料
- 只有在真实使用暴露缺口时，再继续打磨本地 check path 和 CI

完成标志：

- 在真实 repo 里重复使用时，不再需要临时 workaround
- 常见失败路径已经被理解并沉淀到文档中

## Phase 2：内部结构清理

目标：在再次扩语义模型之前，让代码更容易长期维护。

建议项：

- 把 `.intent/` 的存储和 ID 分配从剩余 core logic 中拆开
- 继续保持 rendering、git、state transition、storage 的职责分离
- 在确实有帮助时，用更好的 fixture 降低测试重复

完成标志：

- 核心领域逻辑更小、更容易演进
- 新功能不再需要同时碰太多不相关代码路径

## Phase 3：决定 `v0.2.0` 的方向

目标：在首个 tag 版本之后，选择下一个真正有意义的方向。

候选方向：

- 继续 dogfooding 和 UX 打磨，而不是继续大规模扩面
- 更好的 packaging 和 release 体验
- 更丰富的 query / inspection 能力
- 谨慎试验协作层或 remote-sync

决策原则：

- 选择最小、最受真实使用驱动的下一步，而不是追求抽象上的完整

## 明确暂缓

这些方向仍然不建议抢先做：

- 把 remote sync 当成默认前提
- 平台化 timeline UI
- 为了对称性而做的大规模对象扩张
- 在真实压力出现前就上复杂过滤器和查询语言
- 试图替代 Git 的版本控制角色

## 一句话总结

`v0.1.0` 之后的路线图，已经不是“把原型做出来”，而是“验证、打磨，并判断下一版真正应该优化什么”。
