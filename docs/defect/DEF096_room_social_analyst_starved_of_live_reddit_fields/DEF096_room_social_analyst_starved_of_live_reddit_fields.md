# DEF096 — In the Room, the Social Media Analyst is denied 3 of the 4 live Reddit fields its own job names

**Filed:** 2026-07-23 · **Source:** prompt-reported (Saiful: *"check and ensure the rooms have all
the data they need to do their jobs"*)
**Track:** AT:R59 (protect-the-Room lane — diagnosis + brief; the build team fixes)

---

## The finding

The live Reddit pipeline computes five fields from real Adanos data. Three of them are computed,
stored on the profile, and then **never rendered into the block the Room agents actually read**.

`room_runner.py:381-388`, on a live convene:

```python
sentiment = fetch_live_sentiment(ticker)
if sentiment:
    profile["sentiment_tone"]  = format_sentiment_tone(sentiment)   # rendered ✅
    profile["sentiment_score"] = format_sentiment_score(sentiment)  # rendered ✅
    profile["mention_trend"]   = format_mention_trend(sentiment)    # DROPPED ❌
    profile["influencer_take"] = format_community_read(sentiment)   # DROPPED ❌
    profile["pattern"]         = format_pattern(sentiment)          # DROPPED ❌
```

`_format_profile()` in `room_prompts.py` — the function that builds the fact-sheet every live agent
receives — renders `sentiment_tone` and `sentiment_score` (`:338`) and **nothing else from social**.
`mention_trend`, `influencer_take`, and `pattern` do not appear anywhere in `room_prompts.py`
(grepped: zero hits). Their only other reference is `room_runner.py:162` — the **scripted mock
template**, not the live path. So on a real convene they are computed and thrown away.

**What each dropped field carries** (`social_context.py:265-276`):

| field | actual content | example |
|---|---|---|
| `mention_trend` | mention **volume** + trend direction | `"1,240 Reddit mentions over 7d, trend: rising"` |
| `influencer_take` | **most-active communities** | `"most active in r/wallstreetbets, r/stocks"` |
| `pattern` | **buzz score** + the numeric **bullish/bearish split** | `"buzz score 72/100, bullish 61% / bearish 24%"` |

## Why it matters — this is exactly the analyst's declared job

`content/agents/social_media_analyst.md`:
- **Inputs (line 16):** *"Reddit-only aggregate sentiment (**mention volume, buzz score,
  bullish/bearish split, most-active communities**), pulled live where configured."*
- **Output style (line 23):** *"When real data is present, **ground your read in it (mention counts,
  buzz score, bullish/bearish split)** without inventing details beyond what's given."*

The Room hands it the categorical tone (`bullish/mixed/bearish`) and one sentiment score — and
**withholds mention volume, buzz score, the bullish/bearish split, and the communities**, which are
3 of the 4 input categories the prompt names and the exact numbers the output style tells it to
ground its read in. An analyst instructed to cite the split and the buzz score, and structurally
prevented from seeing them, either omits its own analysis or reaches for a number it wasn't given.

**It bit on live traffic.** In the INGN convene (2026-07-22, from `llm_audit`) the Social Media
Analyst wrote: *"Reddit sentiment is currently bullish (+0.09) … Volume is below the 20-day
average."* That is tone + score — then, having no Reddit mention volume, it substituted the
**price** volume (a market-analyst field) to fill the gap. No buzz score, no split percentages, no
subreddits appear, because none were in its block.

## The asymmetry that proves it's a Room defect, not a data-availability limit

The data exists and is already formatted for an analyst prompt — just not for this one.
`social_context.py:279` `build_social_context_block()` assembles a *richer* block for the **1-on-1
chat** path (Social Media Analyst only), including real post snippets. So the same analyst, asked
the same question, is **well-fed in 1-on-1 chat and starved in the Room**. The Room is the degraded
surface.

## Shape

Same class as **DEF074**: a field computed live from real data, then silently dropped from the
block the agent reads, with a thinner value shown in its place. There the dropped field was
`support` (the 52-week low was shown instead); here it is three social fields (only the tone is
shown). Both are the **CR040 degrade-loudly** family — the pipeline does the work and the surface
throws it away, invisibly.

## Proposed fix (build team owns it)

Render the three fields in `_format_profile()` when `social_source == "live"`, adjacent to the
existing `Retail sentiment:` line — e.g.

```
Retail sentiment: bullish (+0.09 live Reddit sentiment, Adanos)
  Mentions: 1,240 over 7d, trend: rising
  Buzz score 72/100, bullish 61% / bearish 24%
  Most active in r/wallstreetbets, r/stocks
```

Gate on `social_source == "live"` so the synthetic path shows nothing fabricated (the data-source
disclosure header already declares social live/not-live, so no honesty regression). Keep it out of
the block when social is not live — do not surface the mock values.

**Guard:** a test that builds a live-social Room profile and asserts the rendered block contains the
mention count, the buzz score, and the bullish/bearish split — the three fields the analyst's job
names. This is the DEF074 guard generalised: *a field computed live must appear in the block the
agent reads, or the computation is dead code.*

## Scope note — everything else in the Room checks out

Audited alongside this (Saiful's ask was the whole Room, not just social):
- **Fundamentals** — `profile.update(live)` (`room_runner.py:329`) merges the full DEF053 set:
  P/S, EV/EBITDA, PEG, FCF yield, sector/industry, dividend yield, analyst consensus, 52-week range,
  net cash, next-earnings date + consensus EPS. Complete.
- **Technicals** — RSI/tone, trend, volume tone, support, breakout, all live. MACD / MA-crossover /
  Bollinger are *deliberately* absent and the prompt no longer claims them (DEF052). Not a gap.
- **News** — top headline plus all `news_headlines[1:]` render, with publisher + recency + sentiment
  tag (`_catalyst_line`, `:412`). Forward catalyst is the real FOMC countdown. Complete.
- **Trader** — receives no derived R:R / drawdown figure for its own proposal (DEF066 gates those to
  RISK/VERDICT). Already filed as **DEF095**; not re-filed here.

So the answer to *"do the rooms have all the data they need?"* is: **yes, except two holes —
DEF095 (Trader's own derived math) and this one (social).**

## Governance

Relates to **CR024** (which added live Reddit and wired these formatters), **DEF074** (same
drop-a-computed-field shape), **CR040** (degrade loudly), and **DEF095** (the other Room data hole
found in the same audit). Diagnosis + brief only from this lane; needs an architect lane, `coder.api`
owns `room_runner.py` / `room_prompts.py`.
