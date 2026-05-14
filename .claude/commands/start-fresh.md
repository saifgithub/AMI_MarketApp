---
description: Bootstrap a fresh session on this project — read HANDOVER.md + project plan, run Mac-side sanity checks against the live Alpha backend, switch to plan mode and wait for direction. Run this as the FIRST thing in a new session.
---

# /start-fresh

CLAUDE.md is already loaded by the harness — this skill picks up
everything else a fresh session needs before doing any work.
Mirrors the protocol the previous session left in `HANDOVER.md`'s
"Prompt to paste" block, but as a slash command so Saiful doesn't
have to copy-paste it manually.

## What to do, in order

Run every step. Don't ask for confirmation — just execute.

### 1. Read the freshest state on disk

```bash
cat HANDOVER.md
```

The "What's on disk + what's running" table near the top is
current truth (commit count, latest commit, alpha tags, test
count, content corpus state). The most recent
`## What just landed (this session — AT:R<N>)` section captures
substantive commits + carry-overs from the previous session.

Then skim:
- `docs/10_delivery/project_plan.md` — A1–A28 Alpha backlog,
  B1–B14 Beta, M1–M12 MVP. The Alpha "Carry-overs" list from
  HANDOVER is the live working set.
- `docs/10_delivery/promotion_protocol.md` — Mac → Alpha → Beta →
  Prod tag walk. Run before any deploy work.

You don't need to re-read the entire chronological narrative in
HANDOVER.md — the recent-session sections + the top table are
enough.

### 2. Sanity-check the running stack

Mac runs zero services. Every curl below hits the public
Cloudflare Tunnel that routes to the melehost api-alpha container.
If any fails, debug from melehost — see HANDOVER.md "Runtime
state" / `ssh melehost`.

```bash
git status                                # MUST print "working tree clean"
git log --oneline | head -10              # last 10 commits for context
git tag --list "alpha-*" | tail -5        # most recent alpha tags

curl -s https://api-alpha.agenticmarketintel.ai/v1/health
curl -s https://api-alpha.agenticmarketintel.ai/v1/llm/status
curl -s https://api-alpha.agenticmarketintel.ai/v1/sim/quote/AAPL
curl -s https://api-alpha.agenticmarketintel.ai/v1/lessons | head -c 100
```

Expected shape: health=ok, active_provider=vllm, quote returns a
price + source (`yfinance` when Yahoo's serving, `mock_walk` when
not — both fine), lessons returns 270+ entries.

If the tree is dirty: STOP and surface to Saiful — the previous
session didn't clean up; that's a bug, not something to bulldoze
through.

### 3. Pull the open bug list

The in-app bug reporter writes to `bug_reports` on melehost. Surface the
counts + the open titles so Saiful can choose to clear them before
starting new work.

```bash
ssh melehost "docker exec ami_postgres psql -U postgres -d ami_trade -P pager=off -c \"\
  SELECT status, COUNT(*) FROM bug_reports \
  WHERE status IN ('open','in_progress','pending_review') \
  GROUP BY status ORDER BY status;\""
```

If `status='open'` count is **> 0**, also pull the titles so the plan in
step 4 can list them:

```bash
ssh melehost "docker exec ami_postgres psql -U postgres -d ami_trade -P pager=off -c \"\
  SELECT to_char(created_at AT TIME ZONE 'Asia/Kuala_Lumpur', 'MM-DD HH24:MI') AS at, \
    LEFT(id::text, 8) AS short_id, category, title \
  FROM bug_reports WHERE status='open' ORDER BY created_at DESC LIMIT 10;\""
```

Note any `pending_review` rows too — those are bug-fix commits awaiting
your merge to main from a previous `/fix-bugs` worktree.

### 4. Name the session

HANDOVER.md's "Prompt to paste" block names the next session
(e.g. `AT:R15:`). Use it for chapter markers (`mark_chapter`)
and for any commit-message session-tag references.

### 5. Switch to plan mode

Load `EnterPlanMode` via ToolSearch if not already available:

```
ToolSearch query: "select:EnterPlanMode"
```

Then call `EnterPlanMode` with a plan that summarizes:
- Session name (AT:R<N>)
- One-line state read: commit count, test count, alpha tag, what
  Alpha is serving (LLM provider, lesson count, market data leaf
  source)
- **Open bug list from step 3** — render as a short table when count
  > 0. For each: `short_id · category · title`. Note any
  `pending_review` rows separately ("X bug fix(es) awaiting merge
  from previous /fix-bugs worktree").
- The current carry-over list from HANDOVER.md as bulleted
  options Saiful might pick from

Then **ask the user explicitly**, e.g. via AskUserQuestion or as the
final paragraph of the plan: *"Bugs first or carry-over first?"* —
phrased neutrally so he can also pick a brand new direction.

The expected directive choices Saiful might give:

| He says | Action |
|---|---|
| "fix bugs" / "yes, bugs first" | Invoke `/fix-bugs` (which spawns its own worktree, see that command's protocol). |
| names a specific bug (by short id or title) | Treat as a one-off fix on the current branch — skip the full `/fix-bugs` worktree dance. |
| names a carry-over / new direction | Start that work. |
| "ignore bugs for now" | Drop the bug list, proceed with whatever else he picks. |

ExitPlanMode is up to Saiful — he picks a direction, the plan adjusts,
and only THEN do any file edits start.

If the bug count is **0** for all of `open` / `in_progress` /
`pending_review`, drop the bug section from the plan entirely — don't
manufacture noise just to fill a heading.

## What NOT to do

- **Don't start editing files** before Saiful approves the plan.
  Plan mode exists exactly for this — surface intent, get
  agreement, then act.
- **Don't auto-pick** a carry-over item. Offer the list; let him
  pick.
- **Don't run `/promote-to-alpha`** as part of bootup. Promotion
  is its own deliberate step that happens after a code change
  lands and is tested.
- **Don't run `/handover`** at session start. That's the EXIT
  protocol; this is the ENTRY protocol.
- **Don't skip the sanity-check curls**. The handful of seconds
  they take is the cheapest way to catch a melehost outage
  before you propose work that assumes a working backend.
- **Don't skip the bug-list pull**. The user-facing bugs are the
  most expensive thing to leave unaddressed; surfacing them
  upfront forces a conscious "yes/no/later" rather than forgetting
  them.
- **Don't auto-claim or auto-fix bugs from /start-fresh**. This
  command only surfaces; `/fix-bugs` is the entry point for
  actually working through the queue (its own worktree + claim
  protocol).

## When to skip this

If Saiful's first message in the session is a specific task
("fix this bug", "add this feature", "promote what's on main"),
just do the task. `/start-fresh` is for the "let's keep going on
this project" opening, not every session.
