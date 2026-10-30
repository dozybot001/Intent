# 接续案例

中文 | [English](../EN/continuation-case.md)

这个合成案例展示核心承诺：记录保持克制，之后的 Agent 仍然拿得到足够接着做的信息。它是可复现的示例，不是节省时间的测量。

## 会话 A：只记录里程碑

在一个 Git 仓库中：

```bash
itt init

itt intent create "Stabilize checkout retries" \
  --why "Intermittent payment-provider timeouts leave orders pending"

itt decision create "Outbound payment calls use bounded retries" \
  --why "Unbounded retries can duplicate charges and hide provider incidents"

itt snap create "Separated provider timeouts from business rejections" \
  --why "Only transient provider failures are safe to retry" \
  --verified "Timeouts retry; declined payments do not"

itt snap create "Retries stop after three attempts with exponential backoff" \
  --verified "Integration tests cover timeout, rejection and the three-attempt limit" \
  --boundary "Checkout calls only; refunds are unchanged" \
  --next "Prove repeated submissions cannot duplicate charges, then add alerts" \
  --blocker none

itt intent suspend intent-001
```

这里只有一个目标、两个里程碑和一条长期规则。会话里的命令、读过的文件和走过的弯路都不记录。

## 会话 B：不靠旧对话恢复

一个没见过会话 A 的新 Agent 运行：

```bash
itt inspect
```

```text
Suspended
  intent-001  Stabilize checkout retries
              Next         Prove repeated submissions cannot duplicate charges, then add alerts
              Blocker      none
              Boundary     Checkout calls only; refunds are unchanged
              Verified     Integration tests cover timeout, rejection and the three-attempt limit
              snap-002 · 2026-10-31 05:39 · 2 snaps

Decisions
  decision-001  Outbound payment calls use bounded retries
```

Agent 得到的是同样内容的 JSON。这已经足够在动代码之前说清现状：

> 目标是稳定结账重试，因为支付服务超时会让订单卡在待处理。三次重试上限已经验证，只涉及结账调用。接下来我要证明重复提交不会重复扣款，然后加告警。重试仍然保持有界。

这段话的每一部分都来自目标、最新 Snap 和 Decision，没有借助之前的对话。如果最新检查点还不够，`itt inspect --intent intent-001 --history 3 --json` 会按从旧到新的顺序补上最近的 Snap。

然后 Agent 恢复这个目标：

```bash
itt intent activate intent-001
```

如果后来发现这个目标不再需要，历史会留下原因，而不是假装它完成了：

```bash
itt intent cancel intent-001 --reason "Provider-side idempotency removed the need for client retries"
```

目标完成后，用 `itt intent done intent-001` 收尾。

## IntHub 的位置

以上全部可以在本地完成。运行 `itt remote add origin URL --project NAME` 和 `itt push` 之后，IntHub 会在浏览器里展示同一份历史，概览页还能把它复制成一份简报，交给下一个 Agent。
