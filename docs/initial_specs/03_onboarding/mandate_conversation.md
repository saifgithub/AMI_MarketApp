# The Mandate Conversation

The conversational interview the Concierge runs to produce the user's mandate. Conducted in natural language, with chips appearing only as accelerators when the agent detects hesitation.

## Design principles

1. **Conversational, not form-based.** Free-form input always works. Chips are optional.
2. **AI runs the interview.** Concierge can ask follow-ups, back-track, infer.
3. **Action-based questions over self-ratings.** "What would you do in this scenario?" beats "rate your risk tolerance 1–5."
4. **Read back at the end.** Plain English summary; user confirms or edits inline.
5. **3-minute target** (Express path). 6–8 questions max.

## The Express path (6 core questions + 3 scenarios)

### Q1 — What brings you here?

```
CONCIERGE: What's bringing you here?

(Chips appear if user hesitates >3 sec:)
- Save for retirement
- Build long-term wealth
- Generate income now
- Save for a specific goal (house, kids, etc.)
- Learn to trade short-term
- Just exploring
```

**Maps to:** `primary_goal`, `path` (active vs long_horizon — Concierge infers from response).

If user picks "retirement" or "long-term wealth" → likely `path: long_horizon`.
If user picks "short-term" or "trading" → `path: active`.
Concierge can ask a clarifying follow-up.

### Q2 — Time horizon

```
CONCIERGE: Roughly how far out are we looking? 
           Are you thinking weeks, months, years?
```

Concierge may pre-fill from Q1. E.g., if Q1 was "retirement" and user mentioned an age, Concierge computes the horizon and confirms.

**Maps to:** `horizon` (short / medium / long / very_long), `target_outcome` (if specific).

### Q3 — Risk Scenario 1: Drawdown stress

```
CONCIERGE: I'm going to walk you through three quick scenarios 
           so I can calibrate your team's risk posture. 
           
           Scenario one. Two months in, your $10K simulator 
           has dropped to $7K because the whole market 
           corrected. Walk me through what you'd actually do.
```

**What Concierge listens for:**
- Sell everything → risk component 1
- Sell losers, keep winners → risk component 2
- Hold and wait → risk component 3
- Buy more cautiously → risk component 4
- Buy aggressively → risk component 5

**Sentiment cues:**
- Panic words ("freak out", "terrified") → lower
- Calm words ("hold tight", "ride it out") → middle
- Opportunity language ("on sale", "discount") → higher

**Maps to:** `risk_component_a` (1–5).

### Q4 — Risk Scenario 2: Regret asymmetry

```
CONCIERGE: Now the opposite. You stayed in cash. Over the next 
           6 months, the market rallied 25%. You missed it 
           completely. 
           
           Which one stings more — being in and watching it 
           drop 25%, or being out and missing the 25% up?
```

**What Concierge listens for:**
- "Missing out" feels worse → asymmetry toward upside (bumps `risk_score` +1)
- "Losing" feels worse → asymmetry toward loss (bumps `risk_score` -1)
- "Same" → neutral asymmetry (no bump)

**Maps to:** `regret_asymmetry` (−1 / 0 / +1).

### Q5 — Risk Scenario 3: Concentration tolerance

```
CONCIERGE: One more. You've got real conviction on a single 
           stock — your homework is done, your team agrees. 
           
           Would you put 10%, 30%, or 60% of your portfolio 
           in it? And tell me why.
```

**What Concierge listens for:**
- 10% / "anything can happen" / risk-aware → low concentration tolerance
- 30% / "balanced conviction" → moderate
- 60% / "all-in if I'm sure" → high

The **reasoning** matters more than the number. "60% because I'm sure" reveals overconfidence (might bump risk down for protection). "10% because anything can happen" reveals appropriate humility.

**Maps to:** `risk_component_c` (1–5), feeds Trader and Risk Debator overlays.

### Final risk_score derivation

```python
def derive_risk_score(a: int, b: int, c: int, asymmetry: int) -> int:
    # a, c are 1-5; b/asymmetry is -1, 0, or +1
    base = round((a + c) / 2)
    adjusted = max(1, min(5, base + asymmetry))
    return adjusted
```

The reasoning quotes are stored verbatim — useful when the user later asks *"why does my Conservative Debator behave this way?"* and Concierge can point back at their own words.

### Q6 — Maximum drawdown

```
CONCIERGE: Last numbers question. What's the largest 
           temporary loss you could stomach in your sim 
           before you'd lose sleep?
           
           (Chips:)
           - 10%
           - 20%  
           - 30%
           - 50%
           - No cap, I can ride anything out
```

Concierge may *suggest* a number based on `risk_score`:
- risk_score 1 → suggest 10%
- risk_score 2 → suggest 20%
- risk_score 3 → suggest 30%
- risk_score 4 → suggest 50%
- risk_score 5 → suggest 50–100%

User confirms or overrides.

**Maps to:** `max_drawdown_pct`. **Hard floor enforced by Portfolio Manager.**

### Q7 — Constraints

```
CONCIERGE: Anything I should know about what you'd NEVER 
           want to invest in? Common ones:
           
           - Halal / Sharia-compliant only
           - ESG-leaning (avoid heavy polluters)
           - No tobacco / alcohol / gambling
           - No fossil fuels
           - Long-only (no shorting)
           - Liquid only (no microcaps)
           
           Or tell me freeform — I'm listening.
```

User can tap multi-select chips or type. Concierge confirms each.

**Maps to:** `compliance.{halal, esg_lite, no_tobacco_alcohol_gambling, no_fossil_fuels, long_only, liquid_only, ticker_blocklist}`.

### Q8 — Daily briefing

```
CONCIERGE: Do you want a 90-second briefing every morning 
           from your team? 

           (Chips:)
           - Yes, in [detected_locale]
           - Yes, in another language
           - Not now
```

If yes:
```
CONCIERGE: What time and timezone?

           (Default: detected device locale + 7am local)
```

If user picks a non-default language, Concierge briefly confirms voice options.

**REMOVED (CR114 / DEF129, 2026-07-29).** This question (Q8) and the `daily_briefing` mandate field
it mapped to were both deleted: the preference was collected and read back, and nothing anywhere
delivered a briefing. The question is gone from the interview — do not re-add it without A17.

## The readback

After all questions, Concierge produces a structured plain-language summary:

```
CONCIERGE: Here's what I've got for your mandate. Read this 
           and tell me if anything's off.

           🎯 GOAL
           Retirement in roughly 25 years.
           
           ⚖️ RISK
           Risk score 3 of 5 — moderate.
           Max drawdown you'd accept: 30%.
           
           🛡️ CONSTRAINTS  
           Halal / Sharia-compliant only.
           Long-only.
           
           🎙️ DAILY BRIEFING
           7:00 AM Riyadh time, in Arabic.
           
           🌐 PREFERENCES
           Language: Arabic.
           Learning style: Hands-on (you said you'd 
           rather try first, then read).

           [Looks right]  [Edit goal]  [Edit risk]  
           [Edit constraints]  [Edit other]
```

User can tap any badge to revise that field — Concierge enters a quick edit dialog for just that field, then re-confirms.

## Thorough path (Phase 2)

Adds 3–5 more questions for users who want more personalisation:

- **Q9 — Specific target outcome.** "Do you have a number in mind? (e.g., $1M by 2050)"
- **Q10 — Custom ticker blocklist.** "Any specific tickers you want to never see?"
- **Q11 — Sector caps.** "Anything you don't want over X% of portfolio?"
- **Q12 — Multi-scenario refinement.** Adds 2 more risk scenarios for finer risk-score precision.
- **Q13 — Learning style refinement.** "Quick reader / story-led / visual / hands-on" — chooses tutor voice.

At MVP we ship Express only. Thorough is a settings option to "refine your mandate" after first run.

## Conversation tone calibration — Not yet delivered (V1)

The intended adaptation:

| User signal | Tone shift |
|---|---|
| Short answers, terse | Concierge becomes more brief, fewer follow-ups |
| Long, exploratory answers | Concierge engages, offers framing |
| Hesitation, "I don't know" | Concierge offers a chip suggestion ("Most users in your situation pick…") |
| Confident, decisive | Concierge moves fast, doesn't over-explain |
| Anxious phrasing | Concierge slows down, reassures |

**Today (Alpha — V0 Concierge):** the engine is fully scripted and deterministic. See `backend/app/services/concierge_engine.py:1-15` — "V0 has no LLM dependency." Questions, follow-ups, and readback are hard-coded strings; there is no tone calibration. The V1 engine (LLM-driven, with `concierge_prompts.py` providing the prompt scaffold) will pick these signals up once the gateway is wired into the Concierge path.

## Storage during conversation

The actual Pydantic schema (`backend/app/schemas/onboarding.py::OnboardingSession`):

```python
class OnboardingSession(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: UUID                                  # session_id — the route's path param
    started_at: datetime
    updated_at: datetime

    locale: str = "en"
    timezone: str = "UTC"
    detected_display_name: str | None = None

    current_step: ConversationStep            # enum: WELCOME, Q1_GOAL, ..., COMPLETE
    messages: list[Message]                   # full transcript
    answers: dict[str, Any]                   # raw answers per step

    risk_components_partial: dict[str, int]   # computed as we go

    completed: bool = False
    claimed_user_id: UUID | None = None       # ⚠️ defined but never set today; see BL13
```

Persistence: `InMemorySessionStore` (`backend/app/services/session_store.py`) — dict keyed by `session_id`, 24h TTL evaluated on `.get()`. Not in Postgres. Replacement (Redis or Postgres) deferred — see the comment in `session_store.py:4-5`.

The derived mandate is **not** stored on the session — `concierge_engine.session_to_mandate_dict()` builds it on-demand. The persistent mandate row is only written later, on first `GET /v1/mandate/{user_id}` after claim (lazy creation).

## Cross-references

- Onboarding flow (the steps): [`flow.md`](flow.md)
- Mandate object schema: [`mandate_schema.md`](mandate_schema.md)
- Lifecycle (edit, version, audit, drift): [`lifecycle.md`](lifecycle.md)
- Concierge agent design: [`docs/initial_specs/02_agents/concierge.md`](../02_agents/concierge.md)
