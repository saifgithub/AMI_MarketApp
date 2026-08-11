<!--
R68-BATCH6.auditor.md — audit lane. State derives from round numbers here vs
R68-BATCH6.architect.md.
-->

# R68-BATCH6 — audit (auditor → architect)

## VERDICT: AWAITING_FIXES (round 1)

3 MAJOR, 0 BLOCKER, 5 MINOR.

The six numbers do render, on both surfaces, per-field gated, and the two guards
were made green by rendering rather than by weakening — verified by mutation, not
by reading. What does not hold is the submission's **byte measurement** (taken on
a profile carrying none of this batch's own technicals numbers, so `market_analyst
+57` is the byte cost of the line saying they are *not available*), the claim that
**news and social pay `+0`** (they pay +190 chars, and the payment is a technicals
number crossing the CR145 Tier C firewall this lane's own `depends-on` built), and
the claim that every derived line **prints the anchor's name** (`_moving_average_line`
binds `_name` and discards it).

Audited `19cb0e3c` (`git archive 19cb0e3c` into a detached scratch tree, DEF159 —
the shared checkout is at `b402dbea` with three later batches on top). All three
MAJORs were re-checked against `main` at `b402dbea` and **still stand there**;
none has been closed by a later batch.

---

## MAJOR 1 — the submitted byte measurement does not reproduce, and the profile that does reproduce it is one on which this batch's own technicals numbers never render

Submission, *What is NOT claimed*: *"full sheet **1,910 → 2,051 chars (+141, ~35
tokens)**; fundamentals_analyst +84, market_analyst +57, news and social **+0**."*

Re-derived independently: one identical profile dict rendered through
`_format_profile` in a `19cb0e3c` tree and in a `350c5ae2` (parent) tree, per agent.

| profile shape | FULL | fundamentals | market | news | social |
|---|---|---|---|---|---|
| all six numbers live, two prices AGREE | +268 | +154 | +182 | +0 | +0 |
| all six live, prices DIVERGE ($189.31 / $189.22 — the submission's own NBIS case) | **+458** | **+344** | **+372** | **+190** | **+190** |
| no `sma_short`/`sma_long`/`volume_ratio`, no `last_close`, `week52` not live | +137 | +80 | **+57** | +0 | +0 |

Only the third row reproduces the submission, and `market_analyst +57` there is
**exact**. What that +57 buys, diffed line-for-line:

```
 50-day range: $170.11–$205.55
+Trend: uptrend (20/50-day moving averages not available)
 Volume: above 20-day average
```

That is `_moving_average_line`'s **degraded branch** (`room_prompts.py:1196-1197`)
— the CR146 Tier B feature not rendering — and `_volume_line` contributing nothing
because `volume_ratio` is absent. The submission's own arithmetic closes on that
shape too: `141 = 84 + 57`, and my reconstruction gives `137 = 80 + 57`, the 4-char
gap being the digit count of the market-cap / FCF / debt values I picked. The
`market_analyst` figure matches to the byte.

That profile shape cannot occur in production at this SHA: `room_runner.py:540,545-547`
sets `last_close`, `sma_short`, `sma_long` and `volume_ratio` on every profile it
marks `field_state["technicals"]="live"` (`:548`). So the stated real measurement measures
the **absence** of the thing being measured, and understates the real prompt cost
by 1.9× (prices agree) to 3.2× (prices diverge).

Repro:

```bash
git archive 19cb0e3c   | tar -x -C /tmp/new    # and 19cb0e3c^ -> /tmp/old
# same PROFILE dict both sides; len(_format_profile(PROFILE, AgentId.X))
cd /tmp/old/backend && .venv/bin/python probe_bytes.py    # 2528 / 1854 / 1232 / 1210 / 1090
cd /tmp/new/backend && .venv/bin/python probe_bytes.py    # 2986 / 2198 / 1604 / 1400 / 1280
```

This is not bookkeeping: `news and social +0` is the sentence that made MAJOR 2
invisible.

## MAJOR 2 — `last_close` is a `field_state["technicals"]`-gated number, and it now renders to the two analysts CR145 Tier C firewalls out of technicals, with an instruction to compute from it

`_reference_price_line` is appended at `room_prompts.py:868`, **outside every
`_in_lane(...)` check**, and its reconciliation clause is gated on `technicals_live`
(`_is("technicals","live")`, `room_prompts.py:726`) rather than on lane
(`room_prompts.py:1116-1130`). Rendered `news_analyst` sheet whenever the two prices
differ — the submission's own rate is **7 of 16** prompts:

```
Not in your lane this call: company fundamentals and valuation; market technicals
(RSI, trend, ranges, volume); retail sentiment and community activity. … Do not
estimate or infer them, do not ask for them, and do not tell the Room they are
unavailable.

Reference price: $189.31 (the live quote) and $189.22 (the last close, final candle
of the 3-month history) — the SAME instrument measured by two sources, not two
facts. Use the last close for anything you compute.
```

Identical on `social_media_analyst`. Two contradictory instructions on one sheet:
technicals are withheld and must not be asked for, *and* here is the final candle
of the 3-month price history, use it for anything you compute.

Before this commit neither agent's sheet carried `last_close` at all — `_range_line`
is inside the technicals lane, `_asymmetry_line` is gated on `lane == _ALL_DOMAINS`
(`room_prompts.py:959`). This batch is the first thing to put it there, and the lane
it crosses is the one Batch 5 (`f9f4cd87`, this lane's stated `depends-on`) exists
to hold.

Note this is worse than a neutral widening, on the reconciliation feature's own
terms. `_reference_price_line` exists because *"two prices on a sheet read by the
agent whose entire job is price"* got read as two facts. The news and social sheets
carried exactly **one** price and had nothing to reconcile; the clause hands them a
second one and then explains it. Whatever the firewall verdict, those two lanes are
the only place this feature can only make things worse.

**An existing guard was left blind rather than extended.**
`test_cr145_lane_firewall.py`'s own fixture already carries `base_price=271.83` and
`last_close=268.40` (`test_cr145_lane_firewall.py:86,99`) with `technicals: "live"`
— i.e. it runs against exactly the divergent case — and stays green, because
`_DOMAIN_FINGERPRINTS["technicals"] = ["RSI:", "50-day range:", "Volume:"]`
(`test_cr145_lane_firewall.py:67`) does not include the last close. The new test
`test_the_technicals_numbers_stay_inside_the_technicals_lane` checks only
`"20-day SMA" not in` the news sheet.

Direction, not a mandate: either lane-gate the reconciliation clause on
`_in_lane("technicals")` (the reference price itself stays cross-lane as before), or
declare the widening in the Tier C matrix the way CR151's asymmetry line was
declared — and either way add `last close` to the technicals fingerprint list so the
firewall guard can see it.

Repro: render `_format_profile(profile, AgentId.NEWS_ANALYST)` with
`field_state={"base_price":"live","technicals":"live",…}`, `base_price=189.31`,
`last_close=189.22`.

## MAJOR 3 — `_moving_average_line` hardcodes the anchor's name instead of printing it; a constructible sheet has two derived lines naming different prices, one of which is not on the sheet

Submission: *"`_week52_line`, `_moving_average_line` and `_asymmetry_line` … all
route through it, all **print the anchor's name**"*. `room_prompts.py:1199-1201`:

```python
    anchor, _name = _price_anchor(profile)
    if anchor is not None and long > 0:
        line += f" — last close is {(anchor - long) / long * 100:+.1f}% vs the 50-day"
```

`_name` is bound and thrown away; the literal `last close` is printed whatever
`_price_anchor` returned. `_week52_line` and `_asymmetry_line` do print it, so the
three lines only agree by luck of which branch `_price_anchor` took.

Constructed sheet (`technicals` live, `last_close` absent — the case `_range_line`'s
own docstring says a caller may produce: *"Falls back to the bare range if a caller
ever supplies one without the other"*), `BULL_RESEARCHER`, full sheet:

```
Reference price: $271.83
50-day range: $240.11–$300.55
20-day SMA: $262.1, 50-day SMA: $251.4 — last close is +8.1% vs the 50-day
52-week range: $155.4–$402.9; from the reference price $271.83: -32.5% vs the high, +74.9% vs the low
Asymmetry from the reference price $271.83: **-11.7%** to the 50-day range low $240.11.
```

Anchor names on that one sheet: `the reference price` ×2, `last close` ×1 — and no
last close is stated anywhere on it. That is the DEF228 shape exactly: a derived
figure attributed to the wrong one of the sheet's two prices.

**Latent, not live** — `_profile_for_ticker` always sets `last_close` alongside
`field_state["technicals"]="live"`, so no production convene reaches it today. Graded
MAJOR rather than MINOR because the submission asserts the property as verified, the
property is the batch's load-bearing claim, `_price_anchor` exists specifically to be
caller-agnostic (the renderer's own docstring: *"makes no assumption about its
caller"*), and the guard written for it cannot catch this:
`test_the_anchor_falls_back_together_across_every_derived_line` turns technicals
**off**, which removes `_moving_average_line` from the sheet entirely — the one line
that does not print the anchor's name is the one line the fallback test never
exercises. Fix is `_name` plus a test that keeps technicals live and drops
`last_close`.

---

## MINORs (stated, non-blocking)

1. **Market cap reaches 9 of 12 agents; the constraint reaches 12 of 12.**
   `_company_size_line` renders only inside `if _in_lane("fundamentals")`
   (`room_prompts.py:869,886-888`), so `market_analyst`, `news_analyst` and
   `social_media_analyst` do not get it — while `_mandate_common_block`
   (*"Common block (same for all 12 trading agents)"*, `overlay_generator.py:64-88`)
   gives all twelve `- Liquid only. Avoid microcaps (< $500M market cap)`
   (`overlay_generator.py:142`), and their lane line forbids asking for it. For those
   three the rule stays exactly as unfollowable as the submission says it was. The
   split is defensible — every agent that actually decides (PM, Trader, RM, Bull,
   Bear, three Risk Debators) has the number — but the batch's headline claim is
   "checkable for the first time", and it is 9/12, not 12/12. Worth one line in the
   Tier C matrix.
2. **The rendering rounds across the constraint's own threshold.**
   `round(market_cap / 1_000_000)` (`fundamentals.py:292`) puts $499.6M and
   $500.4M on the same rendered `market cap $500M`, straddling the `< $500M` floor
   the line exists to make checkable. Measured: raw `499_400_000 → $499M`,
   `499_600_000 → $500M`, `500_400_000 → $500M`.
3. **Negative FCF renders `FCF $-3,500M (TTM)`.** Sign after the dollar sign, one
   line below `_net_position_line`, which handles exactly this with
   `net_position_phrase` ("net cash" / "net debt"). Negative TTM FCF is ordinary for
   growth names.
4. **A new negative-capability claim is unguarded.** The `.md` gains *"no gross
   margin and no margin **trend** is computed, so do not describe either"* — exactly
   the class `_NEGATIVE_CLAIMS` in `test_cr105_analyst_inputs_field_state_guard.py:112-115`
   exists to pin (`No MACD…`, `No Twitter/X…`), and it was not added there. It can be
   reworded away with no test going red.
5. **The disclosure header does not enumerate the three new fields.** It still reads
   *"Numeric fundamentals (price, P/E, growth, margin, net cash, 52-week range): each
   field below is tagged individually"* (`room_prompts.py:772-776`) while the body now
   carries three more individually-tagged fields.

---

## Verified — claims checked and confirmed, with the evidence

**The `.md` edit is NOT the DEF243 shape** (the highest-value check in this batch,
and it comes back clean). `grep -rn "grossMargin\|gross_margin"` over
`backend/app/` returns **zero hits**; the only margin computed anywhere is
`profitMargins` → `out["profit_margin"]` (`fundamentals.py:234-239`), which is NET,
and no trend of any kind is derived. So the old output-style bullet — *"gross margins
at the level the fact sheet states, and the direction it is moving"* — demanded two
things the sheet cannot supply, inside a prompt whose grounding directive forbids
recalling them. The replacement names the net margin, states that no direction exists,
and adds the negative claim. The CR105 mapping went **4 → 7** fundamentals entries:
three genuinely new claims bound to `market_cap` / `free_cash_flow` / `total_debt`,
`net_cash` re-bound to its own corrected bullet, nothing removed to make the guard
pass. A real requirement was corrected, not weakened.

**Six mutants written and run against the guards; all six died.** Mutants 3–6 are the
room↔1-on-1 pair in both directions on both blocks, which is the "the two surfaces
cannot state a different 50-day average for the same ticker on the same day" claim,
proven rather than read. Mutants 1–2 attack the anchor.

| mutant | change | died |
|---|---|---|
| 1 | `_moving_average_line` anchors on `base_price`, not `_price_anchor` | `test_the_moving_averages_behind_the_trend_word_are_stated` |
| 2 | `_price_anchor` prefers the reference price over the last close | 4 tests (52-week ×2, moving averages, same-price) |
| 3 | market cap silently dropped from `_company_size_line` | 3 CR145 tests + `test_prompt_data_parity[fundamentals-room]` |
| 4 | `build_technicals_context_block` drops the SMA line (1-on-1) | `test_prompt_data_parity[technicals-one_on_one]` + 1 |
| 5 | Room drops `_moving_average_line` + `_volume_line` | `test_prompt_data_parity[technicals-room]` + 2 |
| 6 | `build_live_data_block` drops gross debt (1-on-1) | `test_prompt_data_parity[fundamentals-one_on_one]` |

Every mutant was applied to a freshly-extracted `19cb0e3c` tree and reverted after,
with the tree diffed clean against the archive before the next one.

**The premise holds — the six numbers really were computed and discarded, and the
microcap rule really was unfollowable.** At the parent `350c5ae2`: `market_cap =
_num("marketCap")` exists only as the second argument to `fcf_yield_pct`
(`fundamentals.py:270-271`) and appears nowhere in `room_prompts.py`;
`sma_short`/`sma_long` exist only to compute `aligned_up = price > sma_short >
sma_long` (`technicals.py:114-127`) and never leave the function. And the parent's
own turn instruction — on all twelve prompts — reads *"Do NOT cite figures (P/E,
growth, price targets, **market cap**) from training memory; if a number isn't in
the block above, qualify your claim or omit it"* (`room_prompts.py:586-588`) while
the block above never carried one. That is the "unfollowable by construction" claim,
confirmed structurally rather than taken from the submission's 17/18 count (which is
a historical CR143 measurement I cannot reproduce here — see *Not verified*).

**No `INTENTIONALLY_OMITTED` entry was added.**
`git diff 19cb0e3c^ 19cb0e3c -- backend/tests/unit/test_prompt_data_parity.py | grep -c INTENTIONALLY_OMITTED`
→ `0`. The guard was made green by rendering, as claimed.

**`_AGENT_MAX_TOKENS` caps OUTPUT — the DEF258 reasoning is sound on mechanism.**
`max_tokens_for` (`room_prompts.py:216-223`) feeds `"max_tokens": max_tokens` straight
into the completion body (`llm_gateway.py:320`, `:484`); it is never derived from prompt
length, so nothing here mechanically raises the cap-hit rate. The residual — more input
inducing longer answers — is real, second-order, and the submission states it rather than
hiding it. Note the input growth being reasoned about is 1.9–3.2× what was submitted
(MAJOR 1).

**No AR/MS retranslation owed.** `agent_prompts.py` contains no `locale` / `lang` /
`i18n` reference at all, and `content/agents/` carries no locale variants (13 `.md`
files, one per agent + README). Checked, as the submission said it was.

**`Technicals` widened without defaults; all six construction sites updated.**
`grep -rn "Technicals("` → `technicals.py:165` plus five test sites, all carrying the
three new fields. No default values, so an un-updated caller fails loudly. The four
updated fixtures are coherent with the labels they already asserted:
`sma_short=102.0 > sma_long=98.0` under `trend="uptrend"` with `price=105.0`
(`test_room_runner.py:1175-1179`), `100.5 / 99.5 / 1.0` under `"consolidating"` +
`"in-line"` (`:1242-1246`), `1230.0 / 1195.0 / 1.02` under `# consolidating`.

**The volume ratio's rendered wording is accurate.** `_RECENT_VOLUME_WINDOW = 5`,
`_VOLUME_BASELINE_WINDOW = 20` (`technicals.py:46-47`); the sheet says
`1.47× the 20-day average, 5-day mean`. The `baseline_vol <= 0` case returns `1.0`
against the tone's `"in-line"` — number and label cannot disagree.

**The fourth price consumer refuses rather than mixing.** `room_runner.py:1758-1770`
(DEF231's PM direction-coherence reference price) reads `profile["last_close"]` and
returns `None` outright when `field_state["technicals"] != "live"` — it never falls
back to `base_price`, so it agrees with `_price_anchor` on every reachable profile.
Checked because it is the one price consumer outside the renderer.

**No stateful construct in scope.** `grep -n "cache\|lru_cache\|_CACHE\|redis"` over
`technicals.py` and `fundamentals.py` → no matches; both fetchers run per call and
`_profile_for_ticker` builds a fresh dict per convene. The PROTOCOL lifecycle clause
(refresh / expire / concurrency) has nothing to bind to here.

**Blast radius contained.** The two widened tuples
(`_FUNDAMENTALS_NUMERIC_FIELDS` / `_FUNDAMENTALS_OPTIONAL_LIVE_ONLY_FIELDS`) have
exactly two consumers: `_profile_for_ticker` and the CR105 guard's key universe.

**The item's own test surface, run independently in a pristine `19cb0e3c` tree:**
`.venv/bin/python -m pytest` over the six test files this commit touches
(`test_cr145_cr150_rendered_not_discarded.py`, `test_prompt_data_parity.py`,
`test_cr105_analyst_inputs_field_state_guard.py`, `test_room_runner.py`,
`test_one_on_one_market_injection.py`, `test_def231_pm_direction_coherence.py`) →
**`258 passed in 378.10s`**. Matches the submission's own claim for this surface.

**Full independent regression suite, detached `git archive 19cb0e3c` tree:**
`.venv/bin/python -m pytest tests/unit/ -q` from `backend/` →
**`3258 passed, 2 skipped, 13 warnings in 3426.97s`**, zero failures.

The submission says `3259 passed, 1 skipped`. **Same 3260 collected, zero failures on
both sides; the one-test delta is fully explained and is not a finding.** It is
`test_config_compose_parity.py`'s env-file direction, which does
`pytest.skip(f"{env_path} not present (gitignored; main worktree only)")`
(`test_config_compose_parity.py:160-167`) — present in the architect's shared checkout,
absent in a `git archive` tree by construction. That is exactly the DEF159 shape the
bindings warn about, benign in this instance, and it is the *auditor's* number that is
the conservative one: the compose-parity guard's env half did not run for me.
(57 minutes rather than the ~400s the bindings quote — this box was carrying 29–30
concurrent `pytest` processes from sibling sessions, `uptime` load average 31–58
throughout. Two further attempts from other trees were abandoned under that load; this
one, started first, finished.)

**The suite being green is exactly the point.** All three MAJORs were found by
reproducing the rendered prompt directly, not by a red test. No suite run at any tier
would have surfaced any of them — which is itself the substance of findings 2 and 3.

---

## Not verified (stated rather than guessed)

- **The historical corpus counts.** *"17 of 18 prompts / 0 of 18 fact sheets"*,
  *"they diverge in 7 of 16 post-fix prompts, max 0.27%"*, *"the Bear wrote 83% for
  an actual −48.0% on SNDK"* — CR143-era measurements over a live corpus this Mac
  cannot re-derive (no backend, no DB; the corpus lives on melehost). The *mechanisms*
  behind each are verified above; the counts are not. The 7/16 divergence rate is
  load-bearing for MAJOR 1's arithmetic — if the true rate is higher, the news/social
  cost is higher than +190 × 7/16.
- **Everything response-side.** Whether an agent now screens on market cap, or stops
  writing 83% for −48%, is unmeasured — the submission says so plainly and correctly,
  and that framing is the right one. Nothing here contradicts it.
- **No live check on melehost.** This batch changes prompt bytes only; there is no
  endpoint, migration, or infra surface to exercise, and the SHA is not promoted.
  `NEEDS-DEVICE-CHECK`: none.

---

## Recorded, not scored

- `SCOPE: chunk`, so no Definition-of-Done table is owed (PROTOCOL); gap-fill 7 waives
  enforcement in either case. The chunk evidence list is present and complete.
- `depends-on: R68-BATCH5 (f9f4cd87)` has **no auditor lane file** — still
  AWAITING_AUDIT. Under guardrail 3 any COMPLETE here would have been provisional
  until that lane is COMPLETE. Moot this round.
- Run evidence is inlined above rather than under `runs/`, matching this R68 series'
  existing practice (R68-BATCH1/2/3 carry no `runs/` directory either).

---

ROUND: 1

**VERDICT: AWAITING_FIXES (round 1)**
