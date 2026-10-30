# Continuation case

[中文](../CN/continuation-case.md) | English

This synthetic case shows the core promise: recording stays small, and a later agent still gets enough to continue. It is a reproducible example, not a measurement of time saved.

## Session A: record only the milestones

In a Git repository:

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

That is one goal, two milestones and one standing rule. The session's commands, file reads and false starts are not recorded.

## Session B: recover without the old chat

A new agent, which never saw Session A, runs:

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

Agents get the same data as JSON. That is enough to state the position before touching code:

> The goal is to stabilize checkout retries, because provider timeouts leave orders pending. The three-attempt limit is verified, for checkout calls only. Next I'll prove repeated submissions can't duplicate charges, then add alerts. Retries stay bounded.

Every part of that statement comes from the goal, the latest Snap and the Decision. Nothing is borrowed from the previous conversation. If the latest checkpoint is not enough, `itt inspect --intent intent-001 --history 3 --json` adds the most recent Snaps, oldest first.

Then the agent resumes the goal:

```bash
itt intent activate intent-001
```

If later work shows the goal is no longer needed, the history keeps the reason instead of pretending it was finished:

```bash
itt intent cancel intent-001 --reason "Provider-side idempotency removed the need for client retries"
```

When the goal is finished, close it with `itt intent done intent-001`.

## Where IntHub fits

All of this works locally. After `itt remote add origin URL --project NAME` and `itt push`, IntHub shows the same history in a browser and the Overview page offers it as a brief you can copy to the next agent.
