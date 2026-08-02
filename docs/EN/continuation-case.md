# Reproducible continuation case

[中文](../CN/continuation-case.md) | English

This synthetic case demonstrates Intent's core product contract: recording stays small, while a later agent receives enough structured context to resume. It is a reproducible product example, not a measured productivity claim.

## Session A — record only the semantic milestones

Start in an initialized Git repository:

```bash
itt init

itt intent create "Stabilize checkout retries" \
  --why "intermittent payment-provider timeouts leave orders pending"

itt decision create "Outbound payment calls use bounded retries" \
  --why "unbounded retries can duplicate charges and hide provider incidents"

itt snap create "Separated provider timeout from business rejection" \
  --intent intent-001 \
  --why "only transient provider failures are safe to retry"

itt snap create "Checkpoint: verified provider-timeout/business-rejection separation and a three-attempt exponential backoff; idempotency and failure observability remain unverified" \
  --intent intent-001 \
  --why "Next, prove repeated submissions cannot duplicate charges and add alerts; no current blocker; outbound payment calls remain bounded"

itt intent suspend intent-001
```

The recording contains one recoverable goal, two meaningful milestones, and one user-confirmed standing constraint. Its final Snap is also a self-contained continuation checkpoint. It does not store the raw conversation, command log, or every implementation step.

## Session B — recover without reconstructing the old chat

The next agent starts with:

```bash
itt inspect
```

The recovery response includes the suspended goal and its motivation, the complete latest Snap, Snap-count hints, and the active Decision with its reason. Variable fields such as timestamps and origin are shortened below:

```json
{
  "ok": true,
  "active_intents": [],
  "active_decisions": [
    {
      "id": "decision-001",
      "what": "Outbound payment calls use bounded retries",
      "why": "unbounded retries can duplicate charges and hide provider incidents"
    }
  ],
  "suspended": [
    {
      "id": "intent-001",
      "what": "Stabilize checkout retries",
      "why": "intermittent payment-provider timeouts leave orders pending",
      "snap_count": 2,
      "has_more": true,
      "latest_snap_id": "snap-002",
      "latest_snap": {
        "id": "snap-002",
        "object": "snap",
        "created_at": "...",
        "what": "Checkpoint: verified provider-timeout/business-rejection separation and a three-attempt exponential backoff; idempotency and failure observability remain unverified",
        "why": "Next, prove repeated submissions cannot duplicate charges and add alerts; no current blocker; outbound payment calls remain bounded",
        "intent_id": "intent-001",
        "origin": "..."
      }
    }
  ],
  "warnings": []
}
```

The agent can now state the recovery boundary before changing code:

> The goal is to stabilize checkout retries because provider timeouts leave orders pending. Timeout/rejection separation and a three-attempt backoff are verified; idempotency and failure observability remain unverified. Next, test repeated submissions and add alerts; there is no current blocker. The bounded-payment-retry Decision still applies.

That statement comes entirely from the goal, latest Snap, and Decision returned by default `inspect`; it does not borrow facts from the first Snap or rediscover them in code. `has_more: true` only signals older history. If the latest checkpoint is still insufficient, expand narrowly:

```bash
itt inspect --intent intent-001 --history 3
```

The target entry then adds `recent_snaps`, returning up to the three most recent Snaps in oldest-to-newest order. This case returns both `snap-001` and `snap-002`. Bounded history can add detail, but it does not replace the final-Snap continuation contract.

Then it resumes explicitly:

```bash
itt intent activate intent-001
```

If investigation later invalidates the goal, preserve that history instead of calling it complete:

```bash
itt intent cancel intent-001 \
  --reason "provider-side idempotency removed the client retry requirement"
```

If the goal is completed, close it with `itt intent done intent-001`.

## IntHub's role

Intent remains sufficient for local recording and terminal recovery. After a GitHub-backed workspace is linked, `itt hub sync` projects the same graph into IntHub for browsing and handoff. This is the intended boundary: Intent owns portable semantic history; IntHub amplifies it as an organization and collaboration surface.
