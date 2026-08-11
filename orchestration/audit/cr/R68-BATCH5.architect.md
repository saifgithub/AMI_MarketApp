<!--
R68-BATCH5.architect.md — architect submission lane. State derives from round numbers here vs
R68-BATCH5.auditor.md.
GATE: none was used while building. Batch 5 of the CR143 prompt + data-feed remediation programme
(one handshake PER BATCH, Saiful 2026-08-11).
-->

# R68-BATCH5 — audit lane (CR145 Tier C · CR151 Tier A)

**SHA:** `f9f4cd87` (`main`, pushed to origin)
**SCOPE:** chunk — two CRs' single tiers, not either CR's definition-of-done. Both stay
`in_progress`.
**depends-on:** R68-BATCH1 (`0ef2893f`, COMPLETE r1) · R68-BATCH2 (`0a5b4f1e`, COMPLETE r1) ·
R68-BATCH3 (`de1fd8a7`, COMPLETE r1) · R68-BATCH4 (`6b5fe052`, awaiting).

**Item:** the lane firewall. `_format_profile(profile)` → `_format_profile(profile, agent_id=None)`.
Prompt bytes change ⇒ **CR142 Tier A**.

**Re-sequenced deliberately.** The survey put this last (Batch 9) *solely* because it was blocked on
the visibility matrix. Saiful decided that matrix on 2026-08-11, so it moved ahead of the render
batches: the change is **subtraction**, it fits "subtract before you add", and doing it first stops
every field Batches 6/7/9 add from being rendered to all twelve and then clawed back — two Tier-A
audit cycles per field instead of one.

---

## What was wrong

`_format_profile` took no `agent_id`, so all twelve agents received a **byte-identical** fact sheet
carrying every domain's numbers. Measured over 18 convenes / 72 analyst turns (CR145):

| analyst | cites another lane's data |
|---|---|
| news_analyst | valuation **16/18**, technicals 13/18, sentiment 9/18 |
| social_media_analyst | technicals **13/18** |
| fundamentals_analyst | technicals 8/18, news 3/18 |
| market_analyst | sentiment 2/18, news 1/18 |

The four-analyst separation exists to produce four independent lenses. That is the product's core
claim, and it was leaking.

**A correction CR145 is built on, restated here because it is the reason this shipped at all.**
CR143 Phase 3b rejected the scope-firewall concern using the M2b differentiation result (the four
analysts were the *least*-similar pairing at 0.128). Wrong instrument: agents can differ sharply in
emphasis and vocabulary while still borrowing each other's facts. Differentiation is not lane
discipline.

## The matrix

**Default-open** (Saiful, 2026-08-11). `_AGENT_LANES` names **only** the four upstream analysts;
every other agent resolves to `_ALL_DOMAINS`.

| agent | sees |
|---|---|
| Bull, Bear, Research Manager, Trader, PM, 3× Risk Debator | full sheet, byte-identical to before |
| fundamentals_analyst | fundamentals |
| market_analyst | technicals |
| news_analyst | news |
| social_media_analyst | social |

**The default is open on purpose.** Their job IS the cross-lane join — a Bull that cannot see
technicals cannot weigh a thesis against them — and an unlisted 13th agent fails **open** rather than
being silently starved, which is this CR's own failure mode pointed the other way.

**Two fields are dual-lane, on DOMAIN rather than provenance.** `next_earnings` also rides the news
lane (a scheduled date IS a forward catalyst — the News Analyst's job description). `week52` also
rides technicals: it arrives from `fetch_live_fundamentals`, but a 52-week high/low is a **price
range**, and the Market Analyst already holds the 50-day one.

> **That second one was not foreseen, and an existing guard caught it.** The first cut had `week52`
> fundamentals-only; `test_room_prompts.py::test_recent_range_floor_is_technical_support_not_52w_low`
> — DEF074's guard, which drives the MARKET_ANALYST — went red. Fixed in the **renderer**, not by
> editing the guard. Editing a defect's guard to accommodate a new change is the DEF243 mistake; the
> guard is unmodified.

## The trap this could easily have become (CR040)

Silently omitting technicals from the News Analyst's sheet leaves it to conclude none exist — and the
next honest thing it does is **tell the Room they are unavailable**. That is a fabrication in the
other direction, produced by a firewall built to stop fabrication.

So an out-of-lane domain is **never** routed through the existing *"not available this call"* /
*"alpha simulation scaffolding"* disclosures. It gets `_out_of_lane_line`:

> *Not in your lane this call: company fundamentals and valuation; market technicals (RSI, trend,
> ranges, volume); retail sentiment and community activity. Another analyst on this desk holds each
> of those and will speak to it — this is a division of labour, NOT missing data. Do not estimate or
> infer them, do not ask for them, and do not tell the Room they are unavailable.*

Asserted including the negative (`test_an_out_of_lane_domain_is_not_disclosed_as_unavailable`).

## "Not this agent's lane" ≠ "dropped" — proved, not asserted

This is the batch's real work, per CR145 Tier C's own warning about the 558-line parity suite.
`test_prompt_data_parity.py` asks whether a computed field is rendered **anywhere**. The guarantee
that keeps its answer honest is that the **union of all twelve agents' sheets equals the full
sheet**, and `test_the_union_of_all_lanes_is_the_full_sheet` fails on any line reaching no agent.

The parity suite stayed **green and unmodified** — the `agent_id=None` default means its question is
unchanged, and non-Room callers are byte-identical.

## CR151 Tier A — the asymmetry line, and the reconciliation it asked for

`_asymmetry_line` renders the up/down asymmetry from numbers already on the sheet. No new provider,
no new fetch, no new field. DEF228 is the exact precedent, on the same reasoning (*arithmetic on two
numbers already on the sheet asserts nothing new*) for the same reason (an agent joined two rendered
numbers wrongly and the whole Room adopted it).

- **One anchor, named in the line** — `last close` when technicals are live, `reference price`
  otherwise, and the string says which. Deriving one half from each of the sheet's two prices is how
  DEF228 happened.
- **Each half independently `field_state`-gated** (CR104): a missing target drops the upside clause,
  not the line. With neither half live the line is **absent**, not rendered as *"Asymmetry: not
  available"* — DEF053's rule, no label for a number we never had.
- **Gated to full-sheet agents only.** CR151 rejected a SYNTHESIS-only gate because the errors
  originate upstream at the Bull and Bear — and Bull, Bear and the RM all keep the full sheet, so its
  named targets still get it. It does **not** reach the four firewalled analysts, because it is a
  cross-lane *join* and would hand back exactly what the firewall removed. CR151 asked this matrix to
  state the reconciliation explicitly rather than let the two decisions drift; it is stated in the
  code beside the matrix and pinned by
  `test_the_asymmetry_line_is_not_a_way_back_across_the_firewall`.
- Not to be confused with `trading_math.trade.trade_asymmetry`, which measures a **proposed trade's**
  geometry and is read by two post-hoc call sites only (`room_runner.py:1380`, `:3461`). It reaches
  no prompt — so before this tier **no agent had ever seen an asymmetry figure of any kind**.

## Verification

**Prompt-side, on the fact sheet** (fixture with every domain live):

| | chars | lines | vs full |
|---|---|---|---|
| full sheet | 2,651 | 27 | — |
| fundamentals_analyst | 1,842 | 16 | **−30.5%** |
| market_analyst | 1,221 | 11 | **−53.9%** |
| news_analyst | 1,245 | 9 | **−53.0%** |
| social_media_analyst | 1,197 | 11 | **−54.8%** |

**On the REAL assembled prompts**, not only the fixture — `dump_assembled_prompts --ticker AAPL
--no-live`, all 12 Room prompts:

- `Catalysts — recent` → news_analyst + the 8 full-sheet agents, **0** on fundamentals/market/social.
- `Retail sentiment:` → social_media_analyst + the 8, **0** on the other three.
- The three non-fundamentals analysts retain **exactly one** `P/E` occurrence each, and it is the
  anti-fabrication instruction (*"Do NOT cite figures (P/E, growth, price targets, market cap) from
  training memory"*) — never a fact-sheet line. Checked rather than assumed, because a grep count
  alone would have read as leakage.
- `Not in your lane this call` → **1** on each of the four, **0** on the eight.

**Tests:** `backend/tests/unit/test_cr145_lane_firewall.py`, **40 tests**. Full shared-checkout suite:
**3238 passed, 1 skipped**, 410.99s. (The one intermediate failure was `test_registers_no_drift` —
DEF159's guard firing on the CR145/CR151 row edits before the table was regenerated; green after
`gen_registers.py gen all`.)

## What is NOT claimed

- **The acceptance is a response-side rate and it has not been measured.** The citation table above
  is what this tier must move, on ≥30 convenes post-promotion. Removing the data from the prompt is
  the necessary half, not the sufficient one — an agent can still cite a number from training memory,
  which is why the anti-fabrication line stays.
- Batch 1's re-measurement showed truncation returning (DEF258). This batch **subtracts** 30–55% of
  four agents' fact sheets, which buys some of that headroom back — but only for those four, and the
  agents that clipped (PM, two debators, bear_researcher) are all full-sheet, so **nothing here is
  claimed to fix DEF258's cause**.
- CR145 Tiers A/B/D and CR151 Tiers B/C/D are untouched. Both CRs move `proposed` → `in_progress`,
  not `done`.
- The lane assignment is a **judgement**, not a measurement. `week52` and `next_earnings` are
  dual-lane on my reading of what the field is about; the DEF074 guard forced the first of those two
  and is the reason to expect the second to be worth re-examining.

---

**SUBMITTED: round 1**
