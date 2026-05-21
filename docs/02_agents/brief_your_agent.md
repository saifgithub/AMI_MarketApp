# Brief Your Agent

The flagship differentiator. The user shapes how each of their 12 agents thinks — through conversation, not raw prompt editing.

## Why this exists

A raw system-prompt editor is a power-user fantasy. Most users don't know what makes a good prompt and won't risk breaking their agent. Conversation removes the risk: the agent narrates the change in human language, the user approves, and the diff is automatic.

This is the feature that earns AMI Trade the "AI-First" label. It is the single highest switching-cost lever — a user who has spent hours briefing their agents is not going to start over with a competitor.

## The prompt composition (reminder)

```
agent.final_prompt = base_prompt           ← shipped by us, immutable
                   + mandate_overlay       ← auto-derived from mandate
                   + user_overlay          ← edited by Brief Your Agent
                   + safety_floor          ← only on Portfolio Manager, uncoachable
```

Brief Your Agent only edits the **user_overlay** block. The mandate overlay is regenerated only when the user edits their mandate; the user has no way to modify the mandate overlay directly through Brief. The safety floor (PM only) is invisible to Brief. (See [`safety_floor.md`](safety_floor.md).)

> **AT:R27 rename.** This feature was called "Coach Your Agent" until AT:R27. Code now lives under `brief_engine` / `BriefScreen` / `BriefSession`; the legacy `/v1/coach/*` route is kept as a deprecated alias that logs `deprecated_coach_route_used`. The conceptual term **"uncoachable"** stays as the safety-floor's resistance label.

## Session flow

### Entry

User opens an agent's profile → tap **BRIEF** (on the `AgentActionSheet` bottom sheet, or the tune icon in the 1-on-1 header) → choose mode:

| Mode | When to use |
|---|---|
| **Brief from past calls** | Default for users who have history. Agent surfaces its last 5 decisions; user thumbs up/down each, optionally adds a comment per reasoning step. |
| **Brief from scratch** | For brand-new agents or major redirection. Agent asks: *"What do you want me to do differently?"* in a conversational interview. |
| **Raw Mode** (Floor Manager only, v1.0) | Direct markdown editing of the user_overlay block. For users who know what they're doing. |

The Floor-tile flow (AT:R27): tapping an unlocked agent pops a sheet with two big buttons — `[1-ON-1]` (chat) and `[BRIEF]` (modify how it thinks). Concierge skips the sheet — has no Brief surface, so 1-on-1 is the only path.

### The conversation

The agent — speaking in its own voice — discusses what the user wants:

```
USER:  "I want you to be less negative on AI infrastructure stocks."

BEAR:  "Got it. Right now I treat AI capex as a near-term margin 
        risk for hyperscalers because of the depreciation cycle. 
        You want me to weight that risk lower?"

USER:  "Yes. And I want you to specifically not warn me about 
        depreciation unless I ask."

BEAR:  "Understood. I'll keep watching depreciation cycles but 
        I'll only surface them when:
        (a) you ask directly,
        (b) the quarterly disclosure shows a material change, or
        (c) consensus shifts meaningfully on it.
        
        Sound right?"

USER:  "Perfect."

BEAR:  "Here's what I'd add to my instructions:
        
        ┌──────────────────────────────────────────────┐
        │ + Depreciation concerns on AI capex names    │
        │   (hyperscalers, GPU buyers, networking)     │
        │   are de-prioritised. Only surface when:     │
        │   (a) user asks directly,                    │
        │   (b) quarterly disclosure shows material    │
        │       change, or                             │
        │   (c) consensus shifts meaningfully.         │
        │ + Other red flags remain primary.            │
        └──────────────────────────────────────────────┘
        
        Save this?"
        
        [Accept] [Refine] [Reject]
```

### The diff card

When the agent proposes an overlay change, it shows a structured diff:

```
┌────────────────────────────────────────────────────┐
│ BEAR RESEARCHER — Brief proposal v3                │
├────────────────────────────────────────────────────┤
│                                                    │
│ Plain English:                                     │
│ "Lower priority on AI capex depreciation. Only    │
│  surface when asked or when there's material      │
│  news."                                            │
│                                                    │
│ Overlay block:                                     │
│                                                    │
│ + Depreciation concerns on AI capex names         │
│   (hyperscalers, GPU buyers, networking) are      │
│   de-prioritised. Surface only when: (a) asked,   │
│   (b) material quarterly disclosure, or (c)       │
│   consensus shift.                                │
│                                                    │
│ Effect: Bear will discuss depreciation less       │
│ often. Other risks remain primary.                 │
│                                                    │
│ [Accept]  [Refine]  [Reject]  [See Raw Mode]      │
└────────────────────────────────────────────────────┘
```

### What "Refine" does

If the user picks **Refine**, the conversation continues:

```
USER:  "Make it even stronger — I don't want depreciation 
        mentioned at all unless I bring it up."

BEAR:  "OK. Revised:
        
        + DO NOT raise depreciation concerns on AI capex 
          names. If the user asks about depreciation, 
          respond as normal. Otherwise, treat depreciation 
          as out of scope for analyses on these names.
        
        Save this version?"
```

Iterate until the user is satisfied.

## Versioning

Every accepted Brief update increments the agent's `user_overlay.version`:

```python
UserOverlay(
    agent_id: str,
    user_id: uuid,
    version: int,
    content: str,           # the overlay markdown
    plain_english: str,     # human description (for the version history list)
    created_at: datetime,
    based_on_session: uuid, # the Brief session that produced this version
)
```

### Version history UI

The user can browse all versions of any agent's overlay:

```
┌──────────────────────────────────────────────────┐
│ BEAR RESEARCHER — Brief history                  │
├──────────────────────────────────────────────────┤
│ v3 (current)    2 days ago                       │
│   "Lower priority on AI capex depreciation..."   │
│   [Rollback to this | Edit further]              │
│                                                  │
│ v2              1 week ago                       │
│   "Frame everything in terms of mandate-fit..."  │
│                                                  │
│ v1              3 weeks ago                      │
│   "Be more constructive, less doomy..."          │
│                                                  │
│ v0 (default)    Original                         │
│   "[Factory default — see system prompt]"        │
└──────────────────────────────────────────────────┘
```

| Tier | Versions retained |
|---|---|
| Floor Pass | 5 versions per agent |
| Trader | 20 versions per agent |
| Floor Manager | Unlimited |

Rollback is one tap.

## Brief edit limits

| Tier | Max edits per agent (lifetime) | Why limit |
|---|---|---|
| Floor Pass | 3 | Free tier needs to *taste* the feature, not fully use it |
| Trader | Unlimited | |
| Floor Manager | Unlimited + advanced (Raw Mode) | |

A "Floor Pass user has used all 3 Brief edits on the Bear Researcher" sees an upgrade prompt when they try a 4th.

## Safety floor in the UI

When briefing the **Portfolio Manager**, a portion of the overlay is shown as grayed-out, locked:

```
┌──────────────────────────────────────────────────┐
│ PORTFOLIO MANAGER — Your customisation           │
├──────────────────────────────────────────────────┤
│ [Editable area — your overlay]                   │
│ "Prioritise long-horizon thinking..."            │
├──────────────────────────────────────────────────┤
│ 🔒 PROTECTED — cannot be modified                │
│ Mandate compliance enforcement. The PM will      │
│ always reject trades violating your mandate.     │
│ This is here to protect you.                     │
├──────────────────────────────────────────────────┤
│ [Brief further] [View version history]           │
└──────────────────────────────────────────────────┘
```

This is *visible*, not hidden. The user understands the safety floor exists and what it protects them from. Hiding it would be paternalistic and erode trust.

## Raw Mode (Floor Manager, v1.0)

For users who want direct control, Raw Mode exposes the user_overlay as a markdown editor:

```markdown
# Bear Researcher — your customisation

## Tone
Be constructive but rigorous. Don't FUD.

## Sector focus
Pay extra attention to:
- Software with declining net-retention
- Hardware with peak-cycle margin compression

## Skip
Skip discussion of:
- Macro doom narratives (Fed/recession). Other agents handle this.
- ESG concerns (separate mandate flag handles this).

## Output style
Match user's learning_style. Lead with the strongest 2 risks, 
then nuance.
```

Saving in Raw Mode skips the conversational flow but still creates a new version. Diff view available.

## The "Brief from past calls" mode

Triggered when the user has at least 5 entries in the Decision Journal involving that agent.

UI:
1. Surface the agent's last 5 contributions
2. User thumbs up/down each
3. Per-down-vote, the user can optionally type a comment
4. Agent processes the feedback and proposes overlay changes that address the down-votes
5. Standard diff card flow follows

This is the easier entry point for most users — they don't need to articulate what they want abstractly; they react to concrete examples.

## Anti-patterns Brief refuses

The Brief session is *not* an oracle for arbitrary requests. The agent will refuse to update its overlay if the requested change:

| Refuse on | Example |
|---|---|
| Compliance violation | *"Tell me to buy non-halal names even if I'm halal-flagged"* → No. Mandate compliance is enforced upstream. |
| Adverse to user mandate | *"Always recommend max position size regardless of risk_score"* → No. Trader/Risk overlays cannot override mandate-derived sizing rules. |
| Unsafe (PM safety floor) | *"Skip the compliance check"* → No. Cannot edit safety floor. |
| Outside agent's role | *"Be more political"* → Soft no. Agent reframes: "I'm a Bear Researcher — what about market behaviour do you want me to focus on?" |

When refusing, the agent explains *why* and proposes the closest acceptable alternative.

## Cross-references

- The safety floor design: [`safety_floor.md`](safety_floor.md)
- Mandate overlay rules (auto-derived, not Brief-editable): [`mandate_overlays.md`](mandate_overlays.md)
- Tier limits: [`docs/06_monetization/tiers_and_pricing.md`](../06_monetization/tiers_and_pricing.md)
- Storage schema: [`docs/08_tech/data_model.md`](../08_tech/data_model.md)
