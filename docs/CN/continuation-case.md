# 可复现的项目接续案例

中文 | [English](../EN/continuation-case.md)

这个合成案例展示 Intent 的核心产品契约：记录时保持克制，后续 agent 又能拿到足以接续的结构化上下文。它是可复现的产品示例，不是已经完成的效率测量。

## Session A：只记录有价值的语义节点

在一个已经初始化的 Git 仓库中执行：

```bash
itt init

itt intent create "稳定结账重试链路" \
  --why "支付服务偶发超时会让订单停留在处理中"

itt decision create "支付出站请求必须使用有界重试" \
  --why "无界重试可能造成重复扣款，也会掩盖供应商事故"

itt snap create "区分供应商超时与业务拒绝" \
  --why "只有供应商的瞬时故障适合重试"

itt snap create "加入最多三次的指数退避" \
  --why "吸收短时供应商抖动，同时避免无限拉长结账过程"

itt intent suspend
```

这次记录只有一个可恢复目标、两个有意义的里程碑，以及一条经过用户确认的长期约束。它不保存原始对话、命令日志，也不记录每个实现步骤。

## Session B：不重建旧对话也能恢复

下一个 agent 从这里开始：

```bash
itt inspect
```

恢复结果会包含被暂停目标及其动机、完整的最新 Snap，以及带理由的现行 Decision。下面缩略了时间戳和来源等可变字段：

```json
{
  "ok": true,
  "active_intents": [],
  "active_decisions": [
    {
      "id": "decision-001",
      "what": "支付出站请求必须使用有界重试",
      "why": "无界重试可能造成重复扣款，也会掩盖供应商事故"
    }
  ],
  "suspended": [
    {
      "id": "intent-001",
      "what": "稳定结账重试链路",
      "why": "支付服务偶发超时会让订单停留在处理中",
      "latest_snap_id": "snap-002",
      "latest_snap": {
        "id": "snap-002",
        "object": "snap",
        "created_at": "...",
        "what": "加入最多三次的指数退避",
        "why": "吸收短时供应商抖动，同时避免无限拉长结账过程",
        "intent_id": "intent-001",
        "origin": "..."
      }
    }
  ],
  "warnings": []
}
```

在改代码前，agent 已经可以明确说出接续边界：

> 当前重试链路已经区分瞬时供应商故障与业务拒绝，并采用最多三次的退避；后续工作必须继续遵守“禁止无界重试”的长期约束。

然后显式恢复目标：

```bash
itt intent activate intent-001
```

如果后续调查证明这个目标已经失效，应保留这段历史，而不是把它误记为完成：

```bash
itt intent cancel intent-001 \
  --reason "供应商提供的幂等能力消除了客户端重试需求"
```

如果目标确实完成，则使用 `itt intent done intent-001` 收口。

## IntHub 的角色

Intent 本身足以完成本地记录和终端恢复。绑定一个 GitHub 仓库后，`itt hub sync` 会把同一对象图投影到 IntHub，供浏览和交接使用。边界由此保持清晰：Intent 负责可迁移的语义历史，IntHub 作为组织与协作界面放大它的价值。
