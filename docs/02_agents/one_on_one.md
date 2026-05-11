# 1-on-1 Chat

A solo conversation with a single agent. Cheaper than Convene the Room; the bread-and-butter agent interaction.

## What it is

The user picks an agent — from the Floor honeycomb, the agent profile screen, or via Concierge — and starts a free-form chat. The agent has its full mandate overlay and any user coaching applied. Responses stream in.

## Triggers

| Entry point | Behaviour |
|---|---|
| **Long-press an agent hex on the Floor** | Quick 1-on-1 opens as bottom-sheet overlay; dismissal returns to Floor |
| **Tap an agent profile → "Chat"** | Full-screen 1-on-1 session |
| **Concierge: "Ask my Bear Researcher about TSLA"** | Concierge routes the question to that agent's 1-on-1 |
| **Trade ticket: "Want a second opinion?"** | Quick 1-on-1 with user's choice of agent, pre-loaded with the ticker context |
| **Agent Academy module completion** | "Try a chat with [Agent]" CTA right after unlock |

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

Each 1-on-1 session creates a record:
```python
OneOnOneSession(
    id: uuid,
    user_id: uuid,
    agent_id: str,
    started_at: datetime,
    ended_at: datetime,
    mandate_version: int,
    model_tier: str,
    messages: list[Message],  # ordered chat history
    credit_cost: int,
    related_journal_entries: list[uuid],  # if any
    user_topic_tags: list[str],  # user-added tags
    status: "active" | "completed" | "interrupted"
)
```

## Cross-references

- Agent specifics: [`twelve_agents.md`](twelve_agents.md)
- Mandate overlay rules: [`mandate_overlays.md`](mandate_overlays.md)
- For multi-agent answer: [`convene_the_room.md`](convene_the_room.md)
- For mandate questions: [`concierge.md`](concierge.md)
- Coaching the agent's style: [`coach_your_agent.md`](coach_your_agent.md)
