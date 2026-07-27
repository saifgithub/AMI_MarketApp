# DEF123 — The Room fact sheet declares synthetic fundamentals as LIVE Yahoo data

**Filed:** 2026-07-27 · **Track:** AT:R59 (room-quality) · **Kind:** Defect · **Area:** backend / prompt
**Found by:** Saiful — *"look at the room that was convened for bigbear.ai. i suspect we had hallucinations"*

---

## Verdict on Saiful's suspicion

He was right that the numbers were wrong, and wrong about who lied. **The agents did not
hallucinate the P/E — the prompt handed it to them.** Under the triage rule this is a
**data-provenance defect**, the DEF059 class: the system fabricated a number, labelled it live,
and four agents faithfully quoted it.

## The BBAI convene

Run `1906ccf2-bae9-49c8-a83e-9e82e18ec144`, 2026-07-27 14:48:38Z, `completed`, 208.8s, tier `mid`,
verdict `PASS`. Every one of the 12 agents ran against `vllm` with zero errors.

The fact sheet each of the 12 received (`llm_audit.system_prompt`, verbatim):

```
Data source disclosure — some fields below are real, some are not:
- Numeric fundamentals (price, P/E, growth, FCF, range): LIVE from Yahoo Finance as of this call.
...
Reference price: $2.81
P/E: 43.0
TTM revenue growth: -1%, profit margin: -227%
Net cash $325M
```

`P/E: 43.0` is **not** from Yahoo. It is the deterministic synthetic baseline value for the
seed `"BBAI"`. Reproduced exactly:

```python
rng = random.Random(zlib.crc32("BBAI".encode()))
rng.uniform(0, 400)          # base_price draw
f"{rng.uniform(12, 55):.1f}" # -> '43.0'
```

BigBear.ai is loss-making, so yfinance has no `trailingPE` for it. The live payload simply
omitted the key, and the synthetic value survived.

**What the Room then did with it** — the fabricated multiple propagated to 4 of 12 agents and was
*rationalised*, which is the worst possible shape:

- **Fundamentals Analyst:** *"**P/E** sits at **43.0** despite a **-227%** profit margin,
  indicating the multiple is driven by expectations rather than current earnings power."*
  A positive P/E on a -227% margin is arithmetically impossible; the model noticed the
  contradiction and invented a narrative to reconcile it.
- **News Analyst:** *"operating at a **-227%** profit margin with **43.0x** P/E"*
- **Bear Researcher:** *"buying a cash-burning tech services firm at **43.0x** P/E is not long-term
  wealth creation—it is speculative gambling"* — the fabricated number became a load-bearing
  argument for the recommendation.
- **Bull Researcher:** *"despite the **-227%** profit margin and **43.0x** P/E"*

## Root cause — a partial dict merge under a whole-block disclosure

Three files line up to produce it:

1. **`backend/app/services/fundamentals.py:168-201`** — `fetch_live_fundamentals` builds `out`
   key-by-key and sets each **only when yfinance has that field**:
   `if pe is not None: out["pe"] = ...`, same for `rev_growth`, `profit_margin`, `net_cash`,
   `base_price`/`low`/`high`/`support`/`breakout`. It returns a dict as long as *either* price or
   `trailingPE` exists (`:165-166`) — so a payload with a live price and no P/E is a normal success.
2. **`backend/app/services/room_runner.py:376-380`** —
   ```python
   live = fetch_live_fundamentals(ticker)
   if live:
       profile.update(live)
       profile["data_source"] = "yfinance_live"
   ```
   `dict.update` overwrites **only the keys present in `live`**. Every key absent from the live
   payload keeps the `rng` value built at `:326-373`. `data_source` is then flipped to
   `"yfinance_live"` for the **whole profile**, unconditionally.
3. **`backend/app/services/room_prompts.py:351,367-371`** — `fundamentals_live = profile.get("data_source") == "yfinance_live"`
   drives **one** header line covering *price, P/E, growth, FCF and range together*. The
   disclosure is per-block; the data is per-field. There is no way for the header to be honest
   about a partial payload, and it isn't.

Net effect: **any numeric fundamental yfinance lacks is silently replaced by an rng value and
declared live.** The affected fall-through set is `pe`, `rev_growth`, `profit_margin`, `net_cash`
— and `base_price`/`low`/`high`/`support`/`breakout` in the price-missing-but-P/E-present case.

## Scale — measured, not estimated

`llm_audit`, melehost, `flow='room' AND agent_id='fundamentals_analyst'`, 60-day window,
**895 prompts** (842 declared LIVE, 53 correctly declared scaffolding). Each rendered value was
compared against the rng value its own ticker seed produces.

| Field | Prompts declared LIVE carrying the synthetic value | Share | Distinct tickers |
|---|---|---|---|
| `P/E` | **178** | **21.1%** | **36** |
| `TTM revenue growth` | **32** | 3.8% | 8 |
| `profit margin` | 1 of 6 renderable\* | — | 1 (SCHD) |
| `net cash` | 1 of 5 renderable\* | — | 1 (SCHD) |

\* Only the 6 most recent prompts use the current `profit margin:` label; older ones say
`FCF margin:` (the CR046 D-b mislabel, since corrected), so the margin/net-cash columns have a
6-row denominator, not 842. The mechanism is identical — this is a labelling artefact of the
measurement window, not evidence the other two fields are safe.

Tickers served a synthetic P/E under a LIVE disclosure (mostly loss-making names, exactly where
`trailingPE` is absent): `AMC BBAI BGS CAG CAR CLSK CZR F FCEL GIS HUT INGN INTC JBLU KHC LCID
MARA NIO OPEN OSCR PLUG RBLX RDW RIOT RIVN SEDG SNAP SOUN SPCE SRXH TAP TDOC UAA WBD XPEV XRX`.

**The clearest single illustration is an ETF.** Latest SCHD Room fact sheet, under
`Numeric fundamentals … LIVE from Yahoo Finance as of this call`:

```
Reference price: $33.29          <- live
P/E: 19.2                        <- live
TTM revenue growth: 8%, profit margin: 24%
Net cash $51296M
```

`synth("SCHD")` → `rev_growth=8`, `profit_margin=24`, `net_cash=51296`. All three match exactly.
**A dividend ETF was presented to all 12 agents as a company with 8% revenue growth, a 24% profit
margin and $51.3 billion of net cash** — none of which exists, all of it declared live. VGK is the
same case.

## Why it matters

- **CR040, degrade loudly.** The one mechanism built to keep the Room honest about provenance —
  the disclosure header — is the mechanism that does the lying. It is *more* dangerous than no
  disclosure, because the grounding directive at the top of every prompt tells the agent to trust
  exactly these numbers and never to substitute training memory. The agent obeys and is wrong.
- **DEF059 class, exactly.** LLM down → confident fake APPROVE was the same shape: a silent
  synthetic path presented with full confidence. This one has been live for the whole window
  measured.
- **It defeats the grounding directive.** Every agent is instructed *"Use only the facts and
  numbers explicitly provided in this prompt … never fill the gap with an assumption."* Compliance
  with that instruction is what propagated the fabrication.
- **CR098 depends on the fix.** Amendment 1 of CR098 is the same finding reached from the other
  direction (withholding a fetch leaves synthetic values in the slot). CR098's fact-sheet
  stripping and this defect's per-field provenance want the **same** rendering change; doing them
  twice will conflict.

## Proposed fix (build team decides the shape)

The lane recommendation, per CR038 (*remove the opportunity, don't instruct*):

1. **Never carry a synthetic numeric into a live profile.** When `fetch_live_fundamentals`
   returns a payload, every numeric key it did **not** supply should be **deleted** from the
   profile, not left at its rng value. Absence is honest; a plausible number is not.
2. **Render absence explicitly.** `_format_profile` omits the line, or prints
   `P/E: not available (company has no trailing EPS)`. The Fundamentals Analyst's prompt already
   handles missing data correctly (*"If a fact you need is absent, say it is unavailable"*) — it
   was never given the chance.
3. **Make the disclosure per-field, or make the block honest.** One boolean cannot describe
   `{price: live, P/E: synthetic}`. Either track provenance per key, or drop any field the live
   payload didn't supply so the block flag becomes true again. The second is simpler and is what
   (1) achieves for free.
4. **Guard it.** A unit test that feeds a live payload missing `trailingPE` and asserts no rng
   value reaches the rendered fact sheet, plus the reverse for `rev_growth`/`profit_margin`/
   `net_cash`. Second occurrence of the silent-synthetic class ⇒ `failure_patterns.md` entry with
   the guard named (CLAUDE.md conventions).
5. **Decide the ETF case separately.** Company fundamentals are meaningless for SCHD/VGK. The
   right answer is probably to omit the whole company-fundamentals block for funds, not to render
   it empty.

**Coordinate with CR098.** Whoever lands first owns `_format_profile`'s per-field rendering; the
other rebases onto it. This defect is the **prerequisite** — CR098's Amendment 1 assumes a fact
sheet that can honestly omit a line.

## Verification

1. `cd backend && .venv/bin/python -m pytest tests/unit/ -q` green.
2. New test: live payload without `trailingPE` ⇒ rendered fact sheet contains no `P/E:` line (or an
   explicit not-available line), and **never** the value `random.Random(zlib.crc32(ticker)).…`.
3. Re-run the measurement above after the fix — the 178-prompt count must go to **0**.
4. Live smoke after promotion: convene BBAI; confirm the fact sheet shows no fabricated P/E and the
   Fundamentals Analyst says the multiple is unavailable rather than quoting one.

## Related

**DEF059** (silent synthetic presented as real), **CR040** (degrade loudly), **CR038** (structural
over prompt-instructional), **CR046 D-b** (the `FCF margin` → `profit margin` relabel visible in
the measurement window), **DEF096** (Room dropped live Reddit fields — same fact-sheet renderer),
**CR098 Amendment 1** (same rendering surface; sequence this first), **DEF124** / **DEF125** (the
other two findings from the same BBAI convene).
