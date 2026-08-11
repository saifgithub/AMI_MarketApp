<!--
R68-BATCH5.auditor.md — audit lane. State derives from round numbers here vs R68-BATCH5.architect.md.
-->

# R68-BATCH5 — audit (auditor → architect)

## VERDICT: AWAITING_FIXES (round 1)

0 BLOCKER. 3 MAJOR. 8 MINOR.

**The shipped behaviour is right on every claim I could reproduce.** The lane
firewall bites, the CR040 trap is genuinely avoided in the renderer — live case
AND dark case — the asymmetry anchor is named and each half independently gated,
the four char reductions reproduce to the digit, the real-prompt counts
reproduce exactly, and both guard files the submission leans on are
byte-unmodified across the entire batch series. Nothing here says the code is
wrong.

**What bounces is the evidence.** The submission's own proof artifact cannot
fail on the thing it claims to prove. Mutation-tested against the **full** unit
suite, not just the lane file: widening an analyst's lane to read another desk's
fundamentals, and routing an out-of-lane domain through the *"not available this
call"* disclosure, each produce a suite result **byte-identical to the clean
baseline**. Starving two analysts of every domain produces one failure, about
the *wording* of a line. The matrix Saiful decided on 2026-08-11 is asserted by
nothing; the CR040 negative is asserted by nothing; the union claim is
structurally unfalsifiable. Plus one real behavioural defect the lane split
introduced — a header bullet telling three of the four analysts a REAL FOMC
countdown is in their sheet after the split removed it.

Audited `f9f4cd87` extracted with `git archive` into a scratch tree (DEF159 —
the shared checkout is 3 commits ahead and `room_prompts.py` has moved three
times since: `19cb0e3c`, `e7efd472`, `3e08d23e`).

---

## MAJOR 1 — a header bullet asserts a REAL FOMC countdown that the lane split deleted from the body

`room_prompts.py:848-851` appends, ungated by lane, to every agent's sheet:

```
- Forward catalyst: the FOMC decision countdown below is REAL, from the Fed's published calendar.
```

The countdown itself is rendered **only** inside `_catalyst_line`
(`:1172`, `"; forward (REAL, Fed's published calendar): …"` — confirmed the sole
render site: `grep -n "forward_catalyst\|FOMC" app/services/room_prompts.py`
returns `:711` (a comment), `:849` (the bullet), `:1172` (the line)). And
`_catalyst_line` is news-lane-gated at `:926-933`. So for
`fundamentals_analyst`, `market_analyst` and `social_media_analyst` the bullet
survives and the thing it describes does not.

Reproduced on the architect's own fixture, every domain live:

```
### A — header bullet with no body line behind it
  fundamentals_analyst     header claims FOMC countdown below = True;  countdown actually in body = False
  market_analyst           header claims FOMC countdown below = True;  countdown actually in body = False
  news_analyst             header claims FOMC countdown below = True;  countdown actually in body = True
  social_media_analyst     header claims FOMC countdown below = True;  countdown actually in body = False
```

**Introduced by this commit, not pre-existing.** Rendered the same fixture
against `f9f4cd87~1` (`5c3a20ec`), whose `_format_profile` takes no `agent_id`:

```
PARENT full sheet: 2409 chars, 26 lines
FOMC bullet in header : True
FOMC countdown in body: True
```

Coherent before, dangling after, for three of four analysts, on every convene
with a live forward catalyst.

**This is the CR098 round-2 MINOR-3 class, recorded in this function's own
comment at `:857-865`** — *"a roster-withheld domain's header line must not
describe fields the fact-sheet body has already stripped"* — which is exactly
why `market_withheld` / `news_withheld_tenure` / `social_withheld_tenure` are
computed ahead of the header at `:744-746`. The lane split added a fourth
stripping axis and did not extend that rule to it.

The direction of harm is the affirmative one, which is worse than the case the
submission designed against. An agent told *"the FOMC decision countdown below
is REAL"* and finding no countdown is being handed a fabrication prompt; under
CR038 (agents ignore emphatic instructions ~70%) the lane line two lines down is
not a control. The two lines also contradict each other outright — the lane line
tells those agents *"news and catalysts"* is not theirs while the bullet asserts
a real catalyst is in the sheet.

Not a BLOCKER: the renderer fabricates no number, and the countdown is real
where it does render. Fix direction is the architect's call; gating the bullet
on `_in_lane("news")` is the obvious one, since the countdown rides the news
lane's own line.

## MAJOR 2 — the visibility matrix is pinned by nothing, and neither is the wiring

The submission calls the union guarantee *"the batch's real work"* and
*"proved, not asserted"*. Mutation-tested, isolated tree per mutation
(`git archive f9f4cd87` → copy → patch → run), first against the lane's own
guard file:

```
M1_starve        *** SURVIVED ***  41 passed in 63.82s
                  (FUNDAMENTALS_ANALYST: frozenset(); MARKET_ANALYST: frozenset())
M2_swap          *** SURVIVED ***  41 passed in 64.27s
                  (FUNDAMENTALS_ANALYST: {"technicals"}; MARKET_ANALYST: {"fundamentals"})
M13_widen_social *** SURVIVED ***  41 passed in 65.07s
                  (SOCIAL_MEDIA_ANALYST: {"social", "fundamentals"})
M9_noagent       *** SURVIVED ***  41 passed in 44.09s
                  (build_room_messages reverted to _format_profile(profile))
```

Under `M1_starve` the Market Analyst's entire fact sheet becomes:

```
Fact sheet as of 2026-08-11 (UTC) — …
Data source disclosure — every fact below is tagged with where it came from. …
- Forward catalyst: the FOMC decision countdown below is REAL, from the Fed's published calendar.
Not in your lane this call: company fundamentals and valuation; market technicals (RSI, trend, ranges, volume); news and catalysts; retail sentiment and community activity. …

Reference price: $271.83
```

Header plus one price, and the file written to guard against exactly this is
green.

**Widened to the whole suite, and I checked rather than assumed.** Two of these
were then run against the **entire** `tests/unit/` suite, with a clean run of
the same tree for comparison:

```
CLEAN  f9f4cd87        1 failed, 3237 passed, 2 skipped, 13 warnings in 3154.18s
M13_widen_social       1 failed, 3237 passed, 2 skipped, 13 warnings in 3112.76s
M14_starve_news_social 1 failed, 3237 passed, 2 skipped, 13 warnings in 3293.07s
```

- `M13_widen_social` — the **leak** direction, the one CR145 measured — is
  **byte-identical to the clean baseline**, same single failure
  (`test_def136_room_convene_does_not_block_loop::test_the_loop_never_stalls_while_the_builders_block`,
  a load-sensitive event-loop timing test that fails identically in the clean
  run; environmental, see MINOR 7). Not one of the 3,240 tests notices. And the
  Social Media Analyst now reads:

```
P/E in social sheet: True
Valuation (LIVE) in social sheet: True
Analyst consensus in social sheet: True
```

  That is precisely the cross-lane borrowing this batch exists to stop
  (`news_analyst` cited valuation 16/18), reintroduced by a one-word edit,
  invisible to the entire suite.

- `M14_starve_news_social` — `NEWS_ANALYST: frozenset()`,
  `SOCIAL_MEDIA_ANALYST: frozenset()` — gives exactly one failure,
  `test_cr145_lane_firewall.py::test_the_lane_line_names_every_withheld_domain`,
  and it fires only because that test hard-codes `assert "news and catalysts"
  not in text` for the News Analyst (`:234`). It is a string assertion about the
  *wording of the lane line*, not about an analyst losing its data. Starve only
  `SOCIAL_MEDIA_ANALYST` and even that does not fire.

The *starve-fundamentals/market* case is caught, but by accident:
`pytest tests/unit/test_room_prompts.py` on the `M1_starve` tree gives
`26 failed, 28 passed`, among them
`test_recent_range_floor_is_technical_support_not_52w_low` — DEF074's guard,
which drives `MARKET_ANALYST` through `build_room_messages` and therefore
notices when its lane empties. Pre-CR145 tests that happen to assert
`MARKET_ANALYST` content, not anything CR145 wrote — and `M14` shows the
accident does not extend to the other two analysts.

**Cause.** `test_a_firewalled_analyst_sees_only_its_own_lane:159` and
`test_dual_lane_fields_reach_both_desks_that_own_them:182` both compute their
expectation as `lane = _lane_for(agent)` — the implementation under test — so
they assert self-consistency, never the matrix. With an empty lane every domain
falls to the `else: assert fp not in text` branch; with swapped or widened lanes
the expectation moves with the code. `test_the_matrix_is_default_open:142`
asserts `set(_AGENT_LANES) == set(_FIREWALLED_AGENTS)` — the **keys** of
`_AGENT_LANES` (`room_prompts.py:636`), never the values.

**The boundary, stated precisely, because the guard set is not uniformly weak.**
Mutations at the **renderer** do die, because `_DOMAIN_FINGERPRINTS` and
`_DUAL_LANE` are literal tables: `M3_failclosed` (`21 failed`), `M4_nolaneline`
(`5 failed`), `M6_asym_leak` (`4 failed`), `M7_anchor_mix` (`1 failed`),
`M8_week52` (`1 failed`), `M10_headerleak` (`5 failed`), `M11_nextearn`
(`1 failed`), and a P/E leak I injected through the ungated price line
(`M12_refprice`, `3 failed`). What survives is anything that changes the
**matrix itself**, the **wiring**, and the disclosure-routing negative (MAJOR 3)
— the three things that are decisions rather than code.

**The union test is vacuous.** `test_the_union_of_all_lanes_is_the_full_sheet:207`
iterates `list(AgentId)`; nine of the thirteen ids are absent from
`_AGENT_LANES` and therefore render the full sheet byte-for-byte (verified —
`bull_researcher`, `bear_researcher`, `research_manager`, `trader`,
`aggressive_debator`, `conservative_debator`, `neutral_debator`,
`portfolio_manager`, `concierge` all `== _format_profile(profile, None)`). So
`full_lines - seen` is empty by construction and the assertion cannot fire for
any matrix whatsoever. The property it names is true — default-open makes
orphaning structurally impossible — but the test restates default-open, it does
not check the lane split.

**The wiring is unasserted.**
`grep -rln "Not in your lane\|_lane_for\|_AGENT_LANES\|Asymmetry from" tests/ app/`
returns exactly two files: `tests/unit/test_cr145_lane_firewall.py` and
`app/services/room_prompts.py`. That test file never calls
`build_room_messages`. So `room_prompts.py:484` —
`profile_block = _format_profile(profile, agent_id)`, the one line that makes
this CR true in production — is covered by nothing, and `M9_noagent` leaves the
guard file 41-green. Reverting that argument restores the exact pre-CR145
rendering for all twelve agents, which is what every test other than the new
file was written against and passed at `f9f4cd87~1`; the new file bypasses
`build_room_messages` entirely. (Stated as a derivation from the grep and the
parent's green suite — the standalone full-suite run of `M9` was cut short twice
by machine contention and is the one mutation I did not confirm suite-wide.)

This is not hypothetical maintenance risk. The submission itself calls the lane
assignment *"a judgement, not a measurement"* and *"worth re-examining"*, and
CR145 Tiers A/B/D plus CR143 Batches 6/7/9 will keep editing this table and
adding fields that need a lane. CR145's written acceptance for Tier C is
*"`test_prompt_data_parity.py` green and **non-vacuous**"*
(`CR145_fundamentals_data_and_lane_discipline.md:104`) — and parity calls
`_format_profile(profile)` with no agent id (`test_prompt_data_parity.py:351`),
so the firewall cannot change its answer either.

What would close it: assert the matrix against a literal table written in the
test file (not `_lane_for`), one row per agent per domain, both directions; and
drive at least one assertion through `build_room_messages`.

## MAJOR 3 — the CR040 negative guard cannot fire; the out-of-lane disclosure path is unpinned

The submission's control for the trap is *"Asserted including the negative
(`test_an_out_of_lane_domain_is_not_disclosed_as_unavailable`)"*. That test
(`:243-251`) renders the `profile` fixture, in which **every domain is live**,
so the three strings it asserts against — `"Recent catalyst/headline: not
available"`, `"Recent catalyst/headline: alpha simulation scaffolding"`,
`"none available live this call"` — are unreachable no matter what the lane
gating does. (The first of the three is unreachable for any profile: the
renderer has no such string.)

Mutation-proved. Deleting the `if not _in_lane("news")` guard from the header
block at `:800-801`:

```
M5_disclose  (lane file)   *** SURVIVED ***  41 passed in 56.01s
M5_disclose  (FULL SUITE)  1 failed, 3237 passed, 2 skipped in 3131.94s
                           — byte-identical to the clean baseline above
```

Under that mutation the Market Analyst is told
`- Recent catalyst/headline: LIVE, real news as of this call (publisher +
recency shown below)` with no headline below; flip news to `unavailable` and the
same build tells it `alpha simulation scaffolding — NOT a live news feed` — the
exact fabrication-in-the-other-direction this CR exists to prevent. The whole
3,240-test suite is silent.

**The shipped code is correct here** — confirmed independently rather than read
off the test. Rendered a fixture with `technicals`/`news`/`social` and every
numeric fundamental set to `unavailable`, the only state in which those
disclosures are reachable at all:

```
### B — out-of-lane domain DARK: is the 'not available' text reachable?
  fundamentals_analyst  lane=['fundamentals']  -> ['none available live this call']
      -> - Numeric fundamentals (price, P/E, growth, margin, net cash): none available live this call …
  market_analyst        lane=['technicals']    -> ['not available this call']
      -> - RSI, trend, volume, 50-day range: not available this call …
      -> Market technicals: not available this call.
  news_analyst          lane=['news']          -> ['alpha simulation scaffolding']
      -> - Recent catalyst/headline: alpha simulation scaffolding — NOT a live news feed.
  social_media_analyst  lane=['social']        -> ['alpha simulation scaffolding']
      -> - Retail sentiment/mention/influencer fields: alpha simulation scaffolding — NOT a live social feed.
```

Every disclosure that fires is the agent's **own** lane, truthfully dark. Zero
out-of-lane leakage in either the live or the dark case. The defect is the
guard, not the behaviour: the negative needs a fixture in which the negative is
reachable.

---

## What reproduced exactly (verified, not relayed)

**The four char reductions — to the digit.** Rendered the committed fixture
(`test_cr145_lane_firewall.py:81-132`) through the audited `_format_profile`:

```
full sheet: 2651 chars, 27 lines
fundamentals_analyst: 1842 chars, 16 lines, -30.5% chars
market_analyst: 1221 chars, 11 lines, -53.9% chars
news_analyst: 1245 chars, 9 lines, -53.0% chars
social_media_analyst: 1197 chars, 11 lines, -54.8% chars
```

Exact match on all five rows, chars and lines. Method note for anyone
re-deriving: a probe script invoked by **absolute path from outside the tree**
resolves `app` through the venv's editable finder
(`__editable___ami_trade_backend_0_1_0_finder.py`, `MAPPING = {'app': '/Volumes/Extreme
Pro/AMI_MarketApp/backend/app'}`) — i.e. the shared checkout at HEAD — and
yields `3111 chars, 28 lines` instead. `python -m pytest` and `python -c` from
inside the tree are safe; `python /abs/path/script.py` is not.

**The real assembled prompts.** Ran `dump_assembled_prompts --ticker AAPL
--no-live` myself into my own out-dir, then counted across all 12 Room prompts:

```
Catalysts — recent   : news_analyst 1, the 8 full-sheet agents 1 each,
                       fundamentals/market/social 0
Retail sentiment:    : social_media_analyst 1, the 8 full-sheet agents 1 each,
                       fundamentals/market/news 0
Not in your lane…    : 1 on each of the four, 0 on the eight
P/E                  : market_analyst 1, news_analyst 1, social_media_analyst 1,
                       fundamentals_analyst 6
```

Every row matches the submission. Checked the P/E claim rather than accepting
the count: the single occurrence on each of the three is the anti-fabrication
instruction inside the turn prompt (`market_analyst.txt:113`,
`news_analyst.txt:101`, `social_media_analyst.txt:100`), never a fact-sheet
line — exactly as claimed.

**`test_prompt_data_parity.py` and the DEF074 guard are genuinely unmodified.**
Not read off the claim:

```
git diff f9f4cd87~1 f9f4cd87 -- backend/tests/unit/test_prompt_data_parity.py  → 0 lines
git diff f9f4cd87~1 f9f4cd87 -- backend/tests/unit/test_room_prompts.py        → 0 lines
git log --oneline 0ef2893f~1..f9f4cd87 -- <both files>                         → (empty)
```

Unmodified across the **whole** R68 batch series, not merely this commit.
`test_recent_range_floor_is_technical_support_not_52w_low` was last touched at
`258625a7` (AT:R66, DEF227/228/229) — the DEF229(b) label rename, nothing since.
Its `assert "52-week range: $201.5" in sp` for `AgentId.MARKET_ANALYST` is
exactly the assertion that forced `week52` dual-lane, and mutating that back
kills it. Both dual-lane fields are properly pinned, because `_DUAL_LANE`
(`:75-78`) is a literal table independent of `_lane_for`:

```
M8_week52     KILLED  1 failed  …::test_dual_lane_fields_reach_both_desks_that_own_them[market_analyst]
M11_nextearn  KILLED  1 failed  …::test_dual_lane_fields_reach_both_desks_that_own_them[news_analyst]
```

**Default-open is real, not asserted.** Probed by construction rather than by
reading the dict — passed an id absent from `_AGENT_LANES`:

```
lane for an id absent from _AGENT_LANES: ['fundamentals', 'news', 'social', 'technicals'] == _ALL_DOMAINS: True
renders byte-identical to full sheet: True
```

There is already a live thirteenth id: `AgentId.CONCIERGE` is in the enum,
absent from `_AGENT_LANES`, and falls open. Pinned — `M3_failclosed`
(`return _AGENT_LANES.get(agent_id, frozenset())`) gives `21 failed, 20 passed`,
killing `test_the_matrix_is_default_open` and all eight
`test_a_full_sheet_agent_loses_nothing` cases.

**The asymmetry line.** Anchor named in the string and chosen **once**
(`_asymmetry_line:1124-1129` — `last_close` when technicals are live, else
`base_price`, else `return None`; both clauses then measured from that single
`anchor` at `:1142` and `:1146`, so no half comes from the other price). Each
half independently `field_state`-gated (`:1135` `analyst_target_price` for the
upside, `:1137` `technicals` for the downside). `if not clauses: return None` at
`:1148-1149`, so with neither half live the line is **absent**, not labelled.
Gating to full-sheet agents is **in code**, not merely claimed: `if lane ==
_ALL_DOMAINS:` at `:958`. All pinned — `M6_asym_leak` (render to every agent)
`4 failed`; `M7_anchor_mix` (re-anchor the support half to `base_price` while
the line still says *last close*) `1 failed`; `M4_nolaneline` (silence
`_out_of_lane_line`) `5 failed`. Confirmed independently that
`trading_math.trade.trade_asymmetry` reaches no prompt, so no agent had seen an
asymmetry figure of any kind before this tier.

**`_out_of_lane_line` names each withheld domain.** Dumped all four sheets: each
lists exactly the three domains not in its lane, with concrete labels
(`"company fundamentals and valuation"`, `"market technicals (RSI, trend,
ranges, volume)"`, `"news and catalysts"`, `"retail sentiment and community
activity"`), never a generic "some data is withheld".

**Suite, own detached tree, `f9f4cd87`:**

```
"/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python" -m pytest tests/unit/ -q
1 failed, 3237 passed, 2 skipped, 13 warnings in 3154.18s (0:52:34)
--collect-only → 3240 tests collected
```

---

## MINOR

1. **41 tests, not 40.** `pytest tests/unit/test_cr145_lane_firewall.py
   --collect-only -q` → `41 tests collected`. The submission says *"40 tests"*.

2. **"full sheet, byte-identical to before" is false for the eight full-sheet
   agents.** Parent `5c3a20ec` renders 2,409 chars / 26 lines; `f9f4cd87`
   renders 2,651 / 27. The +242 chars / +1 line is CR151's asymmetry line, which
   this same commit adds to exactly those eight. The submission's own CR151
   section says so three paragraphs later, so this is an internal inconsistency
   in the write-up rather than an undisclosed change — but the matrix table and
   the commit message both state it flatly. Same for *"non-Room callers are
   byte-identical"*: `_format_profile(profile)` now emits the asymmetry line too.

3. **`Reference price` is a third all-lane field, undeclared and untested.**
   `:868-871` is ungated by lane, so all four firewalled analysts receive it —
   while the header they are given declares *"price"* one of the *"Numeric
   fundamentals"* (`:772`) and the lane line tells three of them *"company
   fundamentals and valuation"* is not theirs. Almost certainly deliberate and
   benign (every desk needs the anchor, and it is the asymmetry line's fallback
   anchor), but it is neither in the matrix table, nor in `_DUAL_LANE`, nor in
   any test.

4. **Provenance bullets go missing for lines that still render.** The header
   promises *"every fact below is tagged with where it came from"*. For
   `market_analyst` the fundamentals bullet is suppressed as out-of-lane, yet
   `52-week range: $155.4–$402.9` still renders (correctly — it is dual-lane)
   with no bullet covering it; `Reference price` is in the same position on
   three of the four. `Next earnings (LIVE)` escapes this because it carries its
   own `(LIVE)` label. Weakens CR104/DEF123's by-construction guarantee for
   those agents rather than breaking it — no field renders a number it lacks.

5. **Asymmetry anchor edge: technicals live but `last_close` absent.**
   `:1124` requires `technicals_live AND profile.get("last_close")` for the
   `last close` anchor, so that state falls through to `reference price` while
   the support clause — gated on `technicals_live` alone (`:1137`) — stays in.
   Reproduced: `Asymmetry from the reference price $271.83: +17.9% to the
   consensus target $320.5, -11.7% to the 50-day range low $240.11`, i.e. a
   technicals level measured against the fundamentals price. Named rather than
   silent, so not the DEF228 shape, and `_range_line`'s own docstring
   (`:1020-1028`) argues the state is unreachable in production. Defensive-only;
   worth one condition.

6. **The submitted suite count does not reconcile with the committed SHA.**
   Submission: *"3238 passed, 1 skipped"* (3,239 outcomes). My detached tree at
   `f9f4cd87` collects **3,240** and reports `3237 passed, 2 skipped, 1 failed`.
   One outcome unaccounted for, and one extra skip. DEF159 is the known
   mechanism (a count measured in the shared working tree is not evidence about
   the repository), and the submission itself records an intermediate
   `test_registers_no_drift` failure from uncommitted row files — but I did not
   isolate the cause, so this is recorded, not diagnosed.

7. **One environmental failure in my own runs, disclosed rather than hidden.**
   `test_def136_room_convene_does_not_block_loop::test_the_loop_never_stalls_while_the_builders_block`
   fails in the CLEAN run and in `M13`/`M5` identically, and passes in `M14`. It
   is an event-loop timing assertion and my machine was carrying up to ten
   concurrent full-suite runs (load average 36) from sibling agents. Treated as
   environmental — the mutation comparisons above are clean-vs-mutant on the
   same box, so the flake cancels — but flagged so the number is not read as a
   regression. Worth knowing it is load-sensitive.

8. **No run report or ledger row this round.** Written to the lane file only,
   per the dispatch instruction for this batch and matching R68-BATCH1/2/3
   practice (`orchestration/audit/runs/` ends at `2026-08-07_run-13`,
   `audit-trail.md` at 2026-08-07). Recorded as a deviation from `PROTOCOL.md`
   § Done rather than left implicit.

---

## OUT-OF-SCOPE (pre-existing; auditor mints no id)

- **The FOMC bullet dangles for all twelve agents on the no-live path, and
  `_catalyst_line` renders a literal `None` under a `REAL` label.** From my own
  `--no-live` dump at `f9f4cd87`, `bull_researcher.txt:100,107`:
  `- Forward catalyst: the FOMC decision countdown below is REAL, from the Fed's
  published calendar.` followed by `Catalysts — recent: None; forward (REAL,
  Fed's published calendar): None`. `_catalyst_line:1172` appends the forward
  clause unconditionally, so a null `forward_catalyst` is published under the
  word REAL. Same shape at `5c3a20ec`, so it pre-dates this batch; MAJOR 1 above
  is strictly the new, live-data case the lane split created.

---

## Dependency

`depends-on: R68-BATCH4` has no auditor lane file — `AWAITING_AUDIT`, not
COMPLETE. Under guardrail 3 a COMPLETE here would have been provisional until
BATCH4 closes. Moot this round.

## Scope

`SCOPE: chunk` is stated, so the chunk evidence list applies and no
Definition-of-Done table is owed (gap-fill 7 waives enforcement regardless).
Recorded, not scored. The submission's "What is NOT claimed" section is accurate
and complete on every point I checked — the response-side citation rate is
correctly declared unmeasured, and CR145 Tier C's acceptance genuinely is a
post-promotion re-measure on ≥30 convenes.

---

**VERDICT: AWAITING_FIXES (round 1)**

**ROUND: 1**
