# CR221 — slot 2: I1 executive-change detail from 8-K Item 5.02 (architect lane)

**Item:** `CR221-SLOT2` — one build slot of CR221 (Room data-demand sourcing). The fourth
code-bearing slot, and the first that stores and renders **a filing's own prose** rather than
a number derived from tagged facts.

**SCOPE:** chunk — slot 2 of CR221. The Definition-of-Done table is not owed for a chunk; the
CR-level DoD lives in the CR doc and closes with the CR.

**TIER: B** — one independent round, cap 3. Why B and not C: this is the only CR221 line that
puts **untrusted third-party text** (a filing's own words, fetched over the network and stored)
into an agent's prompt, and the filing decides how much of the sheet it occupies. Why not A:
the render is behind a flag that defaults False and is OFF on Alpha, the migration is additive
and creates two new tables only, no new dependency, the ingest is a script no request path
calls, and nothing a user sees has changed yet.

**SHA:** `de2f5383` on `main` (= `origin/main` at submission). The slot is six commits:

| commit | what |
|---|---|
| `98e1b36f` | feat — store (2 tables + migration `cr221a0b0c0d4`), `services/edgar_8k.py`, `scripts/ingest_edgar_8k.py`, Room overlay, flag-gated render, persona change |
| `82f367a0` | docs — CR doc "Slot 2 built" section, the `exec` replay arm |
| `94fc8619` | fix — review round 1: unreadable index ≠ quiet filer, the count is the scan's, a heading starts a line |
| `c25fee09` | fix — review round 2: empty index unreadable, a sub-heading is not a terminator, the hidden-text filter is the list it states, the excerpt is bracketed |
| `d6c364c2` | fix — review round 3: a CSS property is matched whole, an at-rule block is not read, a reference line is passed over again |
| `de2f5383` | research — §7.11 round-4 measurement, the A6 probe, the row. **Docs/measurement only**; listed because it is the submission SHA |

**depends-on:** none. (Slot 4's `CR221-SLOT4` closed COMPLETE at round 3; this slot shares no
source file with it.)

## What and why

CR221's census recorded the News Analyst asking for executive-change detail — *who the new CFO
is, where they came from, why the last one left* — in **5 of 7 convenes**, and once tagged
`ABSENT (only the aggregated headline text was provided)`. The answer is in a filing we already
download: the SEC submissions JSON tags every filing with its 8-K **item codes**, and `5.02` is
"Departure of Directors or Certain Officers; Election of Directors; Appointment of Certain
Officers".

Store-backed, in three parts:

- **`app/services/edgar_8k.py`** — the producer. `recent_block` validates the submissions index
  it reads; `select_502_filings` picks in-window 8-Ks carrying `5.02`; `html_to_text` renders the
  filing's *visible* text; `extract_item_502` cuts the section; `strip_item_title` and `excerpt`
  (cap 1,200, sentence-bounded) shape it; `executive_change_line` is the seam that re-sanitises
  and brackets everything it emits. `IndexUnreadable` is raised, never swallowed.
- **`scripts/ingest_edgar_8k.py`** — fetches and stores; `Tally` names every ticker it could not
  read. The Room reads rows, never the network.
- **The Room** — `_overlay_executive_change` always populates and sets exactly one `field_state`
  key (`executive_change`); `room_prompts._format_profile` renders only when
  `room_executive_change_enabled` **and** the field state is `live`.

Five states, and the split between them is the whole design: **filed** and **none_in_window** are
live; **unscanned**, **stale** and **unreadable** are unavailable. A store that cannot vouch for
a window must never render "none filed" — that is the sentence a reader would act on.

## Tests — measured on the committed SHA, in a detached worktree (DEF159)

`git worktree add --detach … de2f5383`, `backend/.venv` symlinked, run bare:

```
cd backend && ./.venv/bin/python -m pytest \
  tests/unit/test_cr221_i1_executive_change.py tests/unit/test_cr219_availability_guard.py \
  tests/unit/test_agent_prompts.py tests/unit/test_config_compose_parity.py \
  tests/unit/test_prompt_data_parity.py \
  tests/unit/test_cr104_no_fabricated_numeric_reaches_room_prompt.py \
  tests/unit/test_cr216_test_selection.py tests/unit/test_cr221_a2_debt_split.py \
  tests/unit/test_cr221_d1_d2_revenue_breakdown.py -q -p no:cacheprovider
→ 253 passed, 1 skipped in 30.45s        exit=0
```

The slot's own file alone: **53 passed, exit=0**. (The skip is a pre-existing unrelated skip in
the guard file.)

## Mutation proof — six mutations, six killed

Each applied alone to the worktree, the slot's file plus the CR219 guard re-run, then reverted
with `git checkout --`. Baseline before and after: **122 passed, exit=0**; worktree clean at the
end (`git status --short` empty apart from the symlinked `.venv`).

| # | mutation | result | killed by |
|---|---|---|---|
| a | `_NEXT_HEADING`: drop the `(?!5\.02\b)` lookahead | **killed** (3 failed) | `test_sibling_sub_item_headings_are_one_section`, `test_a_cross_reference_inside_the_section_does_not_end_it`, `test_a_short_departure_sub_item_before_the_appointment_is_kept` |
| b | `_COLLAPSED_BOX`: drop the `(?<![\w-])` left boundary | **killed** (2 failed) | `test_visible_text_a_near_miss_pattern_styles_is_kept`, `test_a_style_rule_names_a_property_whole_and_skips_at_rule_blocks` |
| c | `recent_block`: the zero-rows check no longer raises | **killed** (2 failed) | `test_an_unreadable_index_raises_rather_than_reading_as_a_quiet_filer[every column present, zero rows]`, `test_an_empty_recent_block_is_unreadable_not_a_quiet_filer` |
| d | `extract_item_502`: remove the pass-over `continue` branch | **killed** (1 failed) | `test_a_cross_reference_inside_the_section_does_not_end_it` |
| e | `room_prompts`: render ignores the Settings flag | **killed** (1 failed) | `test_the_flag_is_off_by_default_and_the_same_profile_renders_nothing` |
| f | `_overlay_executive_change`: a stale scan reads as `live` | **killed** (2 failed) | `test_a_backtest_before_the_scan_window_names_the_store_not_a_rerun`, `test_the_overlay_stale_scan_never_renders_none` |

Mutations a–d are exactly the four MAJOR findings the three review rounds landed; each now has a
test that dies without the fix.

## Live measurement — the real store, three tickers, one profile

The sqlite store at `measurement/edgar.db` holds a real ingest: scans for CAT and F (window 365
days, `covered_since` 2019-03-12 / 2019-05-20, scanned 2026-09-10) and four extracted Item 5.02
filings. Driven through the **real overlay** at `as_of=2026-09-11`:

| ticker | field_state | sub-state | total | unverified_days |
|---|---|---|---|---|
| CAT | `live` | `filed` | 1 | 1 |
| F | `live` | `filed` | 1 | 1 |
| MSFT | `unavailable` | `unscanned` | — | — |

CAT, rendered — the filing's own words, and the unverified gap named:

> Executive change (8-K Item 5.02) (LIVE): 1 filing between 2026-03-15 and 2026-09-10 (the
> issuer's SEC 8-K index, item code 5.02, verified by AMI's SEC scan through 2026-09-10), newest
> first — [1] 8-K filed 2026-04-10 (154 days before this sheet's run date; event date
> 2026-04-07; accession 0001104659-26-042062); the filing's own words, opening sentences (1,053
> of 2,058 chars, sentence-bounded): ⟦filing text begins⟧ Appointment of New Chief Financial
> Officer On April 8, 2026, Caterpillar Inc. (the "Company") announced that, on April 7, 2026,
> the Board of Directors (the "Board") of the Company appointed Kyle Epley as the Company's
> Chief Financial Officer, effective May 1, 2026, succeeding Andrew R.J. Bonfield. … ⟦filing
> text ends⟧ The 1 day after 2026-09-10, up to this sheet's run date, is NOT verified — a filing
> in that gap would not appear here. Item 5.02 also covers director elections and pay terms —
> report the role and circumstance the filing names; do not infer a reason it does not state.

F, rendered — a short section, so `complete` rather than an excerpt:

> … [1] 8-K filed 2026-04-15 (149 days before this sheet's run date; event date 2026-04-15;
> accession 0000037996-26-000081); the filing's own words, complete (202 of 202 chars): ⟦filing
> text begins⟧ On April 15, 2026, Ford Motor Company (the "Company") was notified that J.
> Douglas Field, Chief EV, Digital, and Design Officer, has elected to leave the Company next
> month after a period of transition. ⟦filing text ends⟧ …

MSFT, unscanned — **no line at all**, and a warn that names both causes and the fix:

```
edgar_8k_ticker_not_scanned  ticker=MSFT
fix="no scan row for this ticker: either it is not on the ingest list, or its last
backend/scripts/ingest_edgar_8k.py pass failed before writing one
([submissions_failed]/[index_unreadable] in that run's summary) — check the list and re-run"
```

**Render seam, on ONE profile** (§7.5's control arm is a flag flip, not a second build):

```
field_state['executive_change'] = 'live'   default flag on a fresh Settings: False
flag=False  sheet=  904 chars  'Executive change' lines=0  'Kyle Epley' present=False
flag=True   sheet= 2998 chars  'Executive change' lines=2  'Kyle Epley' present=True
```

(Two occurrences with the flag on: the sheet line and the persona instruction that tells the
analyst how to read it.)

## Measured in the Room — §7.11, round 4

`20260910T191437Z`, CAT × {short, medium, long} × {`off`, `exec`}, 6 convenes, 36 analyst turns,
on this code. Two results, and they point in opposite directions:

- **Primary endpoint: zero.** I1 was asked for **0 times in both arms and all three mandates**
  (and in rounds 2 and 3 too). The census that justified the build recorded 5 of 7 convenes
  asking; with the sheet answering it, the rank-limited "five things I lacked" shortlist names
  five other things and the total stays flat at 48/48. There was never a number to move.
- **Secondary endpoint: 1 of 1 askers, every mandate.** The News Analyst quoted the filing
  accurately each time — both names, both dates, the item code, the accession — read the
  **stated age** and acted on it ("153 days old", "settled", "likely absorbed into the reference
  price of $802.47"), read the **absence** correctly ("no new Item 5.02 filings since
  2026-04-10"), and the fact **propagated**: the Bull Researcher cited it second-hand.

Cost **+7.9%** prompt tokens (155,407 → 167,713 over 3 convenes) for 1,975 characters. Verdicts
move in both directions and are **not attributed** (§7.1: 19.7% split on identical inputs).

## What I am NOT claiming

- **No promotion.** The flag is OFF on Alpha and stays OFF: it needs Saiful's go and the
  in-container ingest first (§7.6c — the flag renders nothing without scan rows).
- **One ticker, three mandates.** The citation result is 1 asker in 3 convenes. It is not a rate.
- **The hidden-text filter is a filter, not a control (CR038).** Hiding by colour, by an external
  stylesheet, by layout, by a compound selector, or by a rule inside an `@media` block is **not**
  detected, and the module docstring says so. What reaches the prompt is capped, sanitised and
  bracketed as a filing quote; the defence is the bracket and the cap, not the filter.
- **Two tickers ingested on the Mac**, not 150. The 150-ticker run is a promotion step.
- **`de2f5383` adds no code** — it is the round-4 write-up and the A6 probe. The measured code is
  `d6c364c2`.

## Known limits, stated rather than hidden

- The excerpt cap is 1,200 characters, sentence-bounded; CAT's real filing is 2,058, so **1,005
  characters of it never reach the sheet** — the pay bullets, in that filing's case.
- `MAX_ITEMS_RENDERED = 2`: a filer with four in-window 5.02 filings renders the newest two and
  the line says so ("4 filings (newest 2 shown; 2 older not shown)").
- A single-capital abbreviation before a period can end a sentence early in the excerpt cut. It
  never *lengthens* an excerpt, so it cannot admit text the cap excluded.
- The CR219 availability guard cannot see flag-gated store-backed lines by construction; the pin
  for the retired persona denial lives in this slot's own test file.

SUBMITTED: round 1
