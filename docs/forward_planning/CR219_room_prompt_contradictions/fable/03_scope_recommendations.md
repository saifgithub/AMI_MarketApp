# 03 — Scope: per-finding resolutions and what else rides in CR219

Saiful's call: everything that improves the Room's decision rides in this one CR. The
CR's original six scope items survive; this restates them under the generated-block
mechanism and adds the data work. Ordered so the structural mechanism lands first and
every later item flows through it.

## Class A (findings 1–8) — solved structurally

The 8 false denials are deleted from persona prose (migration step 3 in
[`02`](02_generated_availability_design.md)); the 3 true ones (peer-basket P/E,
MACD/Bollinger, Twitter/X) move into `SHEET_ABSENTS`. No per-finding wording work: the
generated block states what the sheet may carry, and the guard makes a recurrence
unbuildable. The doubling across the Room and 1-on-1 surfaces closes at the single
injection point.

## Class B (findings 9–14) — instruction fights, resolved per finding

- **#9 (Technical: overlay demands monthly/quarterly trend the persona forbids).** The
  registry `limit` string is the arbiter: `_market_analyst_block` rewritten to demand
  trend "as direction over the 64-day window, not a month-over-month series" —
  ideally interpolating the registry string, worst case pinned by
  `test_overlay_demands_are_registry_backed`.
- **#10 (Bull: end with CONVICTION vs write it once at top).** Pick one — recommend
  keeping the top-of-turn stance envelope (it is the parsed one) and deleting the
  "end with" clause.
- **#11 (Bull: "date it and say so" vs no-speculation).** Scope the dating instruction
  to catalysts the sheet actually carries (`_catalyst_line`); delete the general form.
- **#12 (Trader: WAIT vs "never skip the stop-loss").** Instruction-side fix: scope the
  stop-loss demand to BUY turns in `trader.md`/overlay. The uncommitted CR210 WAIT
  branch is *correct* to exclude Entry/Target/Stop (its own rationale: those would be
  fabrication on a no-position turn) — do not extend the regex; fix the sentence that
  fights it. See [`01`](01_review_of_findings.md) Overlap 1, including the ask to
  commit the CR210 diffs with a results artifact.
- **#13/#14 (ROs: handed operands + a prohibition on multiplying them).** Apply CR179
  Leg 4 as written: precompute the drawdown contribution per ladder rung in code
  (`risk_officer.py` already prints the mandate's ladder — extend
  `build_risk_officer_instruction` rows with the derived per-rung drawdown figure) and
  delete both the "use the figure as written" trap (#13) and the multiplication
  prohibition (#14).

## Class C (findings 15, 16) — delete the unbackable demand

`overlay_generator.py:447`'s short/medium branch drops earnings revisions, surprise
history, and guidance (none supplied — same move CR146 made for the market analyst),
replaced with registry-backed momentum: YoY margin trend, TTM revenue growth, next
consensus-EPS date. The arms measured this line lowering conviction ("I would have
increased my conviction level if I could verify… as requested by the user mandate"),
so this is a decision-quality fix, not tidying. If revision/guidance data ever lands,
the registry announces it — the overlay never re-grows a data claim
(`test_overlay_demands_are_registry_backed` enforces this).

## Class D — acknowledge in briefs (decided)

The 8 downstream agents keep the full sheet; their grouped-digest data-boundary block
is the acknowledgment. Own commit, banked corpus as before-arm. Lane restriction is
explicitly not in scope; if ever proposed, it is a separate measured CR.

## Class E — same mechanism, second surface

The 1-on-1 `build_live_data_block` lines get `surfaces={"one_on_one"}` registry
entries, so the Fundamentals Analyst's 1-on-1 block honestly lists the technicals it
is handed, with a role-boundary clause (price-path prediction stays the Technical
Strategist's job). No behaviour change to what data flows.

## Finding #17 — make `primary_goal` branch

Recommend **branching**, not deletion: six goal values are collected at onboarding and
today change nothing (`overlay_generator.py:93` prints; nothing branches). Sketch —
one overlay line per goal, added where the horizon branch already lives:

| goal | added emphasis |
|---|---|
| `long_term_wealth` | (current default behaviour; no extra line) |
| `income_now` | dividend safety: payout coverage, FCF vs dividend, buyback-vs-dividend mix |
| `preserve_capital` | downside first: drawdown framing, balance-sheet strength, position-size conservatism |
| `learning` | show the working: name the metric, the threshold, and why it moved the call |
| `speculative_growth` | asymmetry framing: what the upside case requires to be true, stated as conditions |
| *(sixth value as defined in the Mandate enum)* | *(derive on the same pattern at build time)* |

Every line must demand only registry-backed data (same guard). Caveats: goal-branch
*verdict* effects are not measurable at `pm_self_consistency_samples=1` (~19.7% flip
rate) — measure emphasis/citation shifts, not verdicts; and re-run the arms harness
with the `path=` hardcode fixed (see [`01`](01_review_of_findings.md) Gap 1) if a
before/after is wanted.

## Data enrichment — "the free ones" plus ATR

In scope per Saiful; each field enters **through the registry**, which is the first
live proof of the mechanism (persona blocks update automatically; the matching
`SHEET_ABSENTS` entries' collision markers force their own deletion).

1. **Interest coverage** (operating income ÷ interest expense) — the #1 arm request,
   21× from 9 of 12 agents; the Room built an insolvency narrative on CAT's $39.2B net
   debt without it. Zero network cost: `_fetch_statement_facts_uncached` already pulls
   `quarterly_income_stmt` behind the 6h TTL and discards these rows.
2. **Capex line** — already implicit in the rendered FCF, then discarded.
3. **Buyback pacing** — the four-quarter series is already fetched, summed to TTM, and
   thrown away; render the pacing.
4. **ATR(14) for the Trader and ROs** — 4× requested; the Execution Desk must set a
   stop on every BUY with no volatility measure beyond beta. *Needs a look, not
   asserted:* confirm the daily-bar window already fetched for the range/trend lines
   covers 14+ sessions at zero extra network cost; if it does, render ATR into the
   technicals lane with `(LIVE)` provenance.

Standard field rules apply: CR104 provenance (LIVE or ABSENT, never faked),
degrade-loudly on fetch absence, compose-parity guard if any env flag is involved.

## Declared-absent instead (goes on `SHEET_ABSENTS`, not built)

- **Debt maturity / fixed-vs-floating split** — not cheaply available from yfinance;
  the absent entry's note ("total debt is rendered; its structure is not — do not
  infer refinancing risk from the total") is what stops the next insolvency narrative.
- **Historical median multiples (5–10y)** — flagged as the one verdict-flipping gap in
  the record (PM: "if I had proof that 24.5x was a normal mid-cycle baseline… I might
  have approved"). Not cheap; **worth its own future CR** — note it in the CR doc's
  follow-ups rather than stretching CR219 further.
- **Segment/geographic revenue split, multi-year FCF/capex series, order book /
  options flow, intraday bars** — same treatment: honest absent entries so agents say
  "not supplied" instead of narrating around the gap.

## Carried-forward open items (unchanged from the CR doc)

- Sweep the concierge and Brief-Your-Agent surfaces (26 of 38 prompts unswept) — the
  claims guard should scan `concierge.md` from day one; Brief-Your-Agent user overlays
  are user text and out of the guard's jurisdiction, but the composed prompt's
  generated block still states the truth above them.
- The PM answering an appended instruction *outside* its JSON contract — harness-
  induced, not a production defect, but worth its own look given DEF067's parser
  history.
