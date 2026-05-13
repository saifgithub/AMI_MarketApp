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

### 3. Name the session

HANDOVER.md's "Prompt to paste" block names the next session
(e.g. `AT:R15:`). Use it for chapter markers (`mark_chapter`)
and for any commit-message session-tag references.

### 4. Switch to plan mode

Load `EnterPlanMode` via ToolSearch if not already available:

```
ToolSearch query: "select:EnterPlanMode"
```

Then call `EnterPlanMode` with a plan that summarizes:
- Session name (AT:R<N>)
- One-line state read: commit count, test count, alpha tag, what
  Alpha is serving (LLM provider, lesson count, market data leaf
  source)
- The current carry-over list from HANDOVER.md as bulleted
  options Saiful might pick from
- An open question: "What would you like to work on?"

ExitPlanMode is then up to Saiful — he picks a direction (one of
the carry-overs, or something else), the plan adjusts, and only
THEN do any file edits start.

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

## When to skip this

If Saiful's first message in the session is a specific task
("fix this bug", "add this feature", "promote what's on main"),
just do the task. `/start-fresh` is for the "let's keep going on
this project" opening, not every session.
