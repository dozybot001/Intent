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
  --why "only transient provider failures are safe to retry"

itt snap create "Added a three-attempt exponential backoff" \
  --why "it absorbs short provider interruptions without extending checkout indefinitely"

itt intent suspend
```

The recording contains one recoverable goal, two meaningful milestones, and one user-confirmed standing constraint. It does not store the raw conversation, command log, or every implementation step.

## Session B — recover without reconstructing the old chat

The next agent starts with:

```bash
itt inspect
```

The recovery response includes the suspended goal and its motivation, the complete latest snap, and the active decision with its reason. Variable fields such as timestamps and origin are shortened below:

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
      "latest_snap_id": "snap-002",
      "latest_snap": {
        "id": "snap-002",
        "object": "snap",
        "created_at": "...",
        "what": "Added a three-attempt exponential backoff",
        "why": "it absorbs short provider interruptions without extending checkout indefinitely",
        "intent_id": "intent-001",
        "origin": "..."
      }
    }
  ],
  "warnings": []
}
```

The agent can now state the recovery boundary before changing code:

> The retry path already distinguishes transient provider failures from business rejections and uses a bounded three-attempt backoff. The remaining work should preserve the no-unbounded-retry decision.

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
