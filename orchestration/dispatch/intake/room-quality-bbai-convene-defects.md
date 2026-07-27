<!-- intake handoff from the Room-quality lane (AT:R59). DEF123/124/125 filed + registered; need laning. -->
# room-quality — three Room defects from the BBAI convene review

PROPOSED-KIND: Defect ×3 (already minted **DEF123 / DEF124 / DEF125** — register regenerated;
re-verify no collision at pickup, IDs move)
SOURCE: Saiful, 2026-07-27 — *"look at the room that was convened for bigbear.ai. i suspect we had
hallucinations"*
TRIAGE: READY-TO-LANE. **DEF123 is a prerequisite for CR098 — sequence it first.**

**Evidence base:** run `1906ccf2-bae9-49c8-a83e-9e82e18ec144` (BBAI, 2026-07-27 14:48:38Z,
`completed`, 208.8s, tier `mid`, verdict `PASS`), all 12 agents on `vllm` with zero errors, plus
60-day and 30-day `llm_audit` sweeps on melehost. Every number in the three briefs was measured in
session, none extrapolated.

## Verdict on Saiful's suspicion

He was right that the Room said wrong things, and the interesting part is **who lied**. Two of the
three findings are **not** LLM hallucinations — the prompt handed the agents bad data and they
obeyed. Only DEF124 is a genuine hallucination. That split matters because the fixes and owners
differ.

| | What | Class | Headline number |
|---|---|---|---|
| **DEF123** | Fact sheet declares synthetic fundamentals as LIVE Yahoo data | data-provenance (DEF059 class) | **178 / 842 (21.1%)** live-declared prompts carried an rng P/E, **36 tickers** |
| **DEF124** | No prompt states today's date ⇒ agents invent the earnings interval | true hallucination | **2 / 9,789** Room prompts carry any date anchor |
| **DEF125** | Flat `max_tokens=400` truncates the longest agents mid-sentence | silent failure (CR040) | **RM 66.1%**, **Bull 60.6%**, **Bear 25.6%** end mid-word |

## DEF123 — the one that blocks CR098

`profile.update(live)` (`room_runner.py:376-380`) is a **partial** merge: every numeric key
yfinance didn't supply keeps its `random.Random(zlib.crc32(ticker))` value, and `data_source` is
then set to `"yfinance_live"` for the whole profile. `_format_profile` (`room_prompts.py:351,367-371`)
renders **one** binary flag over `price, P/E, growth, FCF, range`, so the header cannot describe a
partial payload — and doesn't.

BBAI's `P/E: 43.0` is exactly the rng value for that seed (loss-making ⇒ no `trailingPE`). Four of
twelve agents quoted it; the Fundamentals Analyst rationalised the impossible pairing with a
-227% margin rather than doubting it. The cleanest illustration is **SCHD**, an ETF, rendered with
`TTM revenue growth: 8%, profit margin: 24%, Net cash $51296M` — all three exact rng values, all
declared live.

**Why it must land before CR098:** CR098's Amendment 1 is the same finding from the other side
(withholding a fetch leaves synthetic values in the slot) and wants the same change to
`_format_profile`'s per-field rendering. Doing them independently will conflict; DEF123 is the
foundation CR098 builds on.

## DEF124 — cheap, and the fix pattern is already in the file

`_forward_catalyst_text()` renders the FOMC date relatively and the agents got it right every time.
The earnings line (`room_prompts.py:459-465`) renders a bare ISO date, so the model has to guess the
interval — and guessed "13-month void" for something 3 days out, which then reached the PM's
recorded verdict reason. Render the interval; anchor the header with the run date.

## DEF125 — the biggest quality loss, and the least visible

One `max_tokens=400` for all 11 streamed agents (`room_runner.py:2260`). The four analysts and two
of three debators never approach it; the RM and both researchers are pinned against it. **The
Research Manager's synthesis — the sole input to EXECUTION/RISK/VERDICT — is cut off mid-sentence
in two convenes out of three, silently.** Likely the same family as **DEF058** (`max_tokens=600`
truncating the PM's verdict JSON, one line away at `:2430`); worth confirming while in there.

## Suggested lanes

- `coder.api` / `coder.room` — all three; they touch two files between them
  (`room_prompts.py::_format_profile`, `room_runner.py` profile builder + `:2260` cap) plus
  `fundamentals.py`. Batching them into one worktree is the obvious call (same precedent as
  DEF095+DEF096) — **but land DEF123 first inside that batch**, since CR098 rebases onto it.
- Room-quality (me) — review the fix, re-run the three measurement queries post-fix. Not coding it.

## Audit rationale

DEF123 changes what every agent is told is true, and DEF125 changes what reaches the transcript —
both upstream of the safety floor's inputs. Recommend the track R + track U handshake at least for
DEF123. DEF124 is low-risk and could ship without it.

## Ship discipline

None of the three is user-visible on its own; all three change agent inputs, so the acceptance test
is the **re-measurement**, not a green suite alone: DEF123 → the 178-prompt count must go to 0;
DEF125 → RM/Bull/Bear mid-word rate → ~0% and the decode-cost delta checked against the CR098
baseline before promotion.

## Also noted, not filed

- **Risk debators still narrate unchecked drawdown math.** In this run the Trader returned `WAIT`
  with `N/A` levels, so DEF095's fix (system computes every ratio from the Trader's levels) had
  nothing to compute from — and the Aggressive debator asserted *"contributing only 0.18 pt"* with
  no stop proposed, while the Conservative asserted both *"0.18 pt"* and *"a -18% drawdown on the
  capital allocated"* for the same 3.0% size, in the same message. Same class as DEF095, on the
  no-levels path DEF095's fix doesn't cover. Flagging for whoever picks up DEF125 — cheap to fold
  in, but it is a scope call, not mine to make.
- **Domain-boundary bleed.** The News Analyst's four bullets covered price action, fundamentals
  (P/E, margin, net cash) and sentiment — three other analysts' domains — despite an explicit
  *"Stay strictly inside your OWN domain"* instruction. CR038 territory (prompts are not controls);
  no defect filed because the fix is structural and unscoped.
