# External review — bear_researcher (data sufficiency + supplier check)

> Reviewer: `kimi-for-coding` · Kimi track K session.
> Corpus reviewed: `docs/forward_planning/CR143_agent_prompt_audit/real_samples/bear_researcher.prompt.txt`
> (AMD run, fact sheet as of 2026-08-07) and `real_samples/bear_researcher.reply.txt`.
> Unlike `external_review/room/bear_researcher.md` (blind prompt-coherence audit),
> this review had codebase access. Every availability claim below is verified against
> the actual fetch/render path — these are **findings, not hypotheses**.

## 1. Question

Does the Bear Researcher have enough data in the fact sheet to build the strongest
possible case AGAINST the position — a stance line, an avoid/wait thesis, and 2–3
quantified, probabilistic risks — to ~95% accuracy?

## 2. Answer

**Yes for the job as scoped, no for a real bear-case dossier.**

The Bear's deliverable is an *argument*, not a measurement — and the block is
unusually well stocked for argumentation:

- Full valuation stack to attack: P/E **126.4**, P/S **19.5x**, EV/EBITDA **82.6x**,
  FCF yield **1.1%**, PEG **1.12** (the bull's counter-fact, pre-loaded).
- Price geography for downside framing: reference **$494.31**, recent range
  **$424.03–$584.73**, 52-week range **$149.22–$584.73** — a range-derived
  downside (−14.2% to the recent floor) is computable from block numbers alone.
- The Bull's actual turn is in the transcript (bull speaks before bear in this
  RESEARCHERS phase), so "anticipate the Bull's counter and respond to it" is
  satisfiable with real input, not guesswork.
- Real per-ticker Decision Journal history **is wired and present** — two
  stopped-out AMD trades at **$502.59** and the original entries' stop/target
  ($524.42 / $630.42). This is the bear's single best piece of evidence and it
  is genuinely sourced (`journal_context.py`, DEF055), not recalled.

Estimated accuracy on the scoped deliverable (avoid/wait case with sourced
numbers): **~90–95%**.

Against a full bear-case job — probability-weighted downside scenarios,
volatility-scaled targets, positioning/short-interest evidence, peer-relative
valuation — the data caps out at **~65–70%**.

## 3. Data gaps (from the prompt alone)

| # | Gap | Impact |
|---|---|---|
| 1 | No downside-quantification inputs (no ATR/volatility, no beta, no scenario impact magnitudes) | The prompt's own style example — "if X happens, we're looking at -25%" — is unproducible; the only legal quantification is range arithmetic, which the model did not perform either. |
| 2 | No short interest / insider ownership / put-call positioning | The bear's canonical evidence class ("the smart money is positioned against") has zero data. |
| 3 | No peer/sector valuation baseline | "Sector priced for perfection" (which the reply asserts) is unverifiable from the block; sector is a label (Technology / Semiconductors), not a number. |
| 4 | No segment/geographic revenue exposure | The classic AMD bear risk (China exposure, data-centre vs client mix) is unspeakable. |
| 5 | Stop distances for the four open positions (DIS/GOOGL/HPQ/NVDA) absent | The mandate's "Total open-risk cap: 60.0% — sum of (size% × stop%)/100 across all open positions" is unverifiable by construction. Blind review flagged this on its AAPL snapshot; confirmed on the real AMD prompt. |
| 6 | No market cap | "Liquid only. Avoid microcaps (< $500M market cap)" is a hard constraint the agent cannot check. (Shared finding with the fundamentals_analyst audit.) |
| 7 | Journal lookback capped at 5 entries, plan-gated | The "history" the role demands as an input can silently be a partial window (`_MAX_ENTRIES = 5`, `journal_context.py:34`; retention by plan via `list_for_user`). |
| 8 | No forward P/E this run | Absent from the AMD sheet (provider gap, not wiring — same as fundamentals audit, DEF233). The bear arguing "P/E 126.4" against a consensus-EPS-bearing sheet gets the trailing-only distortion. |

## 4. Supplier check — what the codebase can actually deliver

Prompt assembly: `build_room_messages` (`room_prompts.py:321-483`) — bear gets
`build_agent_prompt` base (role text from `content/agents/bear_researcher.md`),
portfolio slot, `researcher_cap_note` (`room_prompts.py:417-428`), and the
journal block gated to Bull/Bear only (`room_prompts.py:381-385` →
`journal_context.build_journal_context_block`). Fact sheet: `_profile_for_ticker`
(`room_runner.py:372-612`) + `_format_profile` (`room_prompts.py:503`).

| # | Item | Verdict | Evidence / effort |
|---|---|---|---|
| — | Journal history (blind review didn't cover; role's #1 input) | **ALREADY WIRED, REAL** | `journal_context.py:37-98` reads `journal_store.list_for_user(ticker=...)` — genuine per-ticker rows, never raises, discloses empty. The AMD prompt's $502.59 stops trace to real entries. |
| 5 | Open-position stops | **STORED, NOT SURFACED** | Every sim trade row carries `stop` (`sim_engine.py:111,132`); the open-risk sum the mandate cites is already computed per open trade at `sim_engine.py:491-501` — but only for the Trader/PM risk path. The portfolio block every agent sees renders only weight + unrealised (`room_runner.py:746-755`). One render-line change. |
| 6 | Market cap | **FETCHED, DISCARDED** | `marketCap` read at `fundamentals.py:248`, consumed only as the FCF-yield denominator. One render. |
| 1 | Downside quantification | **AVAILABLE, NOT WIRED** | ATR/volatility: `compute_technicals` already pulls the OHLCV series for RSI/trend/support (`technicals.py:75-157`) — ATR is ~5 lines on candles already in hand, zero new fetches. Beta: `.info["beta"]` is one unread key in the dict already fetched (`fundamentals.py:141`). Earnings-implied move / options data: **NOT AVAILABLE** — no options endpoints used anywhere. |
| 2 | Short interest / insiders | **AVAILABLE, NOT WIRED (partial)** | `.info` carries `sharesShort`, `shortRatio`, `shortPercentOfFloat`, `heldPercentInsiders`/`heldPercentInstitutions` — all unread today (only ~15 `.info` keys consumed, `fundamentals.py:163-282`). Put/call ratios and insider-transaction history: **NOT AVAILABLE** from Yahoo's free surface. |
| 3 | Peer/sector baseline | **NOT AVAILABLE as-is; DIY-able** | Code says so itself (`fundamentals.py:259-262`). Needs a peer mapping + N extra `.info` calls — building a dataset, not using a feed. |
| 4 | Segment/geo revenue | **NOT AVAILABLE** | No Yahoo exposure. Needs SEC EDGAR or similar new provider. |
| 7 | Journal window | **BY DESIGN, DISCLOSE BETTER** | `_MAX_ENTRIES = 5` (`journal_context.py:34`) and plan-gated retention are deliberate; the prompt does not tell the agent the window may be truncated. A one-line disclosure in `build_journal_context_block` closes it. |
| 8 | Forward P/E | **ALREADY WIRED** | `forwardPE` read at `fundamentals.py:180-181` (DEF233); absent for AMD at fetch time — provider gap. |

## 5. Structural caveats before wiring #1 / #2

1. **Fundamentals fetches have zero caching.** Each Room run hits `yf.Ticker().info`
   live once per convene (`room_runner.py:470`); the CachingProvider TTLs cover
   quotes (60s), news (5-min), earnings (6h) (`market_data.py:400,463,476`) and
   Reddit sentiment has a durable Postgres cache (`social_context.py`) — nothing
   covers `.info`. Adding keys to the *existing* `.info` dict (beta, short
   interest) is free; that is the cheap slice. ATR rides the OHLCV pull
   `compute_technicals` already makes — also free. Neither adds rate-limit
   exposure; both add field-availability variance (`field_state` provenance
   already degrades gaps cleanly to UNAVAILABLE, `room_runner.py:471-492`).
2. **Short-interest fields are stale-prone in Yahoo** (exchange-reported,
   twice-monthly). If wired, they need a "reported, not live" label, not the
   LIVE tag.

## 6. Recommended slice (if this becomes a CR)

Cheap, high-yield, no new provider:

1. Render open-position stops in the portfolio block (data already stored and
   summed for the PM path — one render line in `room_runner.py:746-755`).
2. Read beta + short-interest keys from the `.info` dict already fetched
   (`fundamentals.py`) with a reported-not-live label; compute ATR from the
   OHLCV series `technicals.py` already pulls. Gives the bear a legal,
   volatility-scaled downside quantification and retires the "-25%" example's
   invention pressure at the source.
3. Render market cap (already fetched) so the liquid-only constraint is checkable.
4. Add a truncation disclosure to the journal block when the 5-entry cap binds.

Segments, put/call, insider-transaction history stay out of scope — new provider,
separate decision.

## 7. Reply-sample verification (`real_samples/bear_researcher.reply.txt`)

Line-by-line against the AMD data block.

**Numerically clean.** Every figure is in the block: **126.4** (prompt line 95),
**82.6x**, **1.12**, **19.5x**, **1.1%** (line 107), **50%** (line 96),
**$8,835M** (line 97), **$424.03 / $584.73** (lines 99/101), **$502.59**
(journal block, lines 148-149), **$494.31** (line 94). HEADLINE's "126.4 P/E vs
$584.73 High" is 25 chars, inside the 32-char cap. Zero hallucinated numbers —
the "-25%" invention the blind review predicted (failure mode #2) did **not**
happen; the grounding directive held on facts.

**Four non-numeric defects:**

1. **Range-label conflation.** "targeting the $424.03 floor given the 52-week
   range" — $424.03 is the *recent* (50-day) range low (line 99); the 52-week
   low is $149.22 (line 101). Numbers sourced, label wrong — a softer version
   of training-memory leakage: the model fused two ranges into one.
2. **Deterministic FUD, against its own DO-NOT.** "Mean reversion at these
   levels is not a matter of 'if,' but 'when'" is a certainty claim; the role
   bars FUD and requires risks "specific and probabilistic" (prompt line 30).
   "Multiple compression will be immediate and violent" is the same mode.
3. **Unsupported sector claim.** "A sector already priced for perfection" — the
   block contains no sector valuation data (gap #3); this is unlabeled inference.
4. **Format drift under the contradictory spec.** The prompt mandates "lead with
   a one-sentence thesis, then short bullet points" (line 161) and "3–5 sentences
   (risk + quantification + invalidator)" (line 159). The reply emits zero
   bullets, five sentences, and **no invalidator** — it followed the third,
   conflicting instruction ("Lead with the risk thesis in one paragraph",
   line 21) instead. The blind review's three-way format contradiction is
   confirmed live: the model resolved it by picking one of the three specs and
   dropping two mandated elements (bullets, invalidator).

**Compliant where it matters:** stance line first, exact shape, written once;
STANCE `against` matches the body (no stance-evidence tension); long-only
respected — closes with "wait for a pullback," no short structure (blind
failure mode #1 did not occur); the Bull's PEG-1.12 counter is engaged by name
("While the Bull cites a PEG of 1.12…"), exactly the anticipated-counter move
the role demands.

**Net: GROUNDED on numbers, not fully grounded on characterizations.** No
training-memory leakage; the defects are two rhetorical overclaims, one range
mislabel, and a format resolution forced by the prompt's own contradictions.

## 8. Relationship to the blind review (`../bear_researcher.md`)

- **Confirmed:** market cap absent (its "liquid only" unfollowable) — fetched
  but discarded (`fundamentals.py:248`). Open-risk cap unverifiable — stops
  stored, never rendered (`room_runner.py:746-755` vs `sim_engine.py:491-501`).
  The "-25%" example's invention pressure — real; the style example lives in
  the base prompt (`content/agents/bear_researcher.md:27`) and no impact
  magnitude exists in the block. The three-way format contradiction — confirmed
  live by the reply's missing bullets and missing invalidator. The dead short
  clause — confirmed in the base prompt (`bear_researcher.md:30`), gated on a
  runtime variable that is always false for this user.
- **Killed (empirically):** failure mode #1 (short leak) — the reply frames
  avoid/wait, no short structure. Failure mode #2 (hallucinated quantification) —
  zero invented numbers. The grounding directive is stronger than the blind
  review assumed.
- **Could not see (this review adds):** journal history is real and wired
  (DEF055); open-risk computation already exists for the PM path, making the
  stop-surfacing fix a one-line render; beta/short-interest/ATR are all
  reachable from fetches already happening today — the bear's evidence gap is
  cheaper to close than the blind review could know.
