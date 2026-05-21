# 1-on-1 Chat

A solo conversation with a single agent. Cheaper than Convene the Room; the bread-and-butter agent interaction.

## What it is

The user picks an agent — from the Floor honeycomb, the agent profile screen, or via Concierge — and starts a free-form chat. The agent has its full mandate overlay and any user briefing applied. Responses stream in.

## Triggers

| Entry point | Behaviour | Status |
|---|---|---|
| **Tap an unlocked agent hex on the Floor** | Pops `AgentActionSheet` with `[1-ON-1]` + `[BRIEF]` buttons; `[1-ON-1]` opens full-screen chat (AT:R27 — Concierge skips the sheet, opens 1-on-1 directly). | ✅ shipped |
| **Tune icon in the 1-on-1 header** | Switches to Brief screen for the same agent. | ✅ shipped |
| **Concierge: "Ask my Bear Researcher about TSLA"** | Concierge routes the question to that agent's 1-on-1. | Not yet delivered |
| **Trade ticket: "Want a second opinion?"** | Quick 1-on-1 pre-loaded with the ticker context. | Not yet delivered |
| **Agent Academy module completion** | "Try a chat with [Agent]" CTA right after unlock. | Not yet delivered (Agent Academy itself is Phase 2) |

## Credit cost

| Tier | Per-session cost | Reason |
|---|---|---|
| Floor Pass | 1 credit (5/mo free) | Cheap model, single agent, short context |
| Trader | 1 credit (unlimited under mid-tier model) | |
| Floor Manager | 1 credit (unlimited under premium model) | |

A "session" is a continuous chat. Idle > 10 minutes = new session.

## What the agent has access to

When invoked in a 1-on-1, the agent has:
- Its own base prompt + mandate overlay + user overlay
- The user's recent Decision Journal entries (last 30 days) related to the conversation's topic
- The user's current sim portfolio holdings
- Real-time tools relevant to its role (e.g., Market Analyst can fetch chart data; News Analyst can fetch headlines)
- The current conversation context

The agent does **not** have access to:
- The user's account info (email, billing) — these are off-limits
- Other users' data
- The user's mandate version history (only current mandate)

## Interaction model

```
USER:  "What do you think about NVDA at $152?"

AGENT (Bear Researcher, in purple):
       "I want to push back on the consensus love. Three things 
        I'm watching:
        1) ..."

USER:  "Okay, but doesn't the AI capex story justify the multiple?"

AGENT: "It justifies *some* of it. Here's the math on what's 
        already priced in: ..."

USER:  "Can I see what the Bull would say?"

AGENT: "I can pass this to the Bull Researcher — or you can 
        Convene the Room for the full back-and-forth. Want me 
        to set that up?"
        
        [Convene the Room (8 credits)]  [Skip]
```

The agent stays in character — it does NOT pretend to be Bull when asked. It can *refer* to what Bull would say (its model knows the Bull's role), but it would suggest a Room or 1-on-1 with Bull for the actual case.

## Streaming responses

Responses stream token-by-token. The user can interrupt (tap "Stop") to redirect. Conversation history is local-first; persists to server on session close.

## What 1-on-1 is *not* good for

- **Full decisions.** Use Convene the Room for a structured, multi-perspective answer.
- **Reasoning trace.** 1-on-1 is conversational; Room is structured. Use the right tool.
- **Mandate edits.** Talk to Concierge for that.

The Concierge will gently redirect users who try to ask the wrong agent the wrong question. E.g., asking Fundamentals about chart patterns → Concierge: "That's the Market Analyst's domain. Want me to open a chat with them?"

## State persistence

Each chat turn (both Concierge and any of the 12 agents) is durably persisted as a row in `one_on_one_messages` — keyed by `session_id` + ordered by `created_at`. The actual table (per `backend/app/db/models.py::OneOnOneMessageRow`):

```python
class OneOnOneMessageRow(Base):
    __tablename__ = "one_on_one_messages"
    id: UUID                # primary key
    session_id: UUID        # client-generated; groups a continuous chat
    user_id: UUID           # owning user
    agent_id: str           # e.g. "bear_researcher", "concierge"
    role: str               # "user" | "assistant"
    content: str            # message body
    created_at: datetime
```

The richer per-session metadata in early designs (`OneOnOneSession` with `model_tier`, `credit_cost`, `related_journal_entries`, etc.) was never built. The session boundary is implied by `session_id` continuity; idle timeout / "new session" rules live client-side. Credit consumption is also not yet wired (see `subscription_events` event type `credits_consumed` — defined but no app code emits it).

### Not yet delivered

- A dedicated `OneOnOneSessionRow` table with `started_at` / `ended_at` / `mandate_version` / `credit_cost` aggregation.
- `related_journal_entries` cross-link surfaced server-side.
- `user_topic_tags` capture + retrieval.
- `status` field (`active | completed | interrupted`) — sessions today are open-ended.
- Credit deduction on each turn (gating exists in plan logic; the deduction itself isn't emitted).

## Cross-references

- Agent specifics: [`twelve_agents.md`](twelve_agents.md)
- Mandate overlay rules: [`mandate_overlays.md`](mandate_overlays.md)
- For multi-agent answer: [`convene_the_room.md`](convene_the_room.md)
- For mandate questions: [`concierge.md`](concierge.md)
- Briefing the agent's style: [`brief_your_agent.md`](brief_your_agent.md)
