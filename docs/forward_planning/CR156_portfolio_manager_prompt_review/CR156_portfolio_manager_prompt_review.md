# CR156 — The gatekeeper's verdict is read by one key and gated on one datum, and neither is wired

**Filed:** 2026-08-08 · **Status:** proposed · **Decision:** Saiful, 2026-08-08 — *"book CRs one for
each agent."* One CR per agent so each remedy is decided on its own evidence rather than bundled.
**Source:** CR143 Phase 1/3b plus two independent reviews of the Portfolio Manager — a blind
prompt-coherence audit ([`external_review/room/portfolio_manager.md`](../CR143_agent_prompt_audit/external_review/room/portfolio_manager.md))
and a codebase-verified data-sufficiency audit ([`external_review/room/kimi/portfolio_manager_data_sufficiency.md`](../CR143_agent_prompt_audit/external_review/room/kimi/portfolio_manager_data_sufficiency.md)).

Every claim below carries a **supplier check** (does the code inject the data the prompt claims?) and
a **parser check** (does anything read the output the instruction shapes?) before it became scope.
CR105 Amendment 1 is the precedent: written from prompt files alone, two of its four findings were
wrong once checked against the parser, and the proposed fix would have turned an existing guard red.

**Evidence base.** Epoch 2026-08-07 12:00 onward. `corpus/llm_audit_2026-08-07-epoch.json` — 216 real
turns with verbatim `system_prompt`, of which **n=18 PM turns**. `corpus/room_runs_2026-08-07-epoch.json`
— the 18 stored verdicts. `backend/tests/unit/fixtures/pm_verdict_corpus.txt` — **n=811** deduplicated
`room_runs.verdict->>'reason'` strings carrying a `$`, **all-time on Alpha, not epoch-scoped**; it is
cited only for structural prevalence and never pooled with an epoch rate.

**The 18 convenes span three different mandates** — single-name cap 10.0% (1), 3.0% (10), 100.0% (7);
`max_drawdown_pct` 50 / 30 / 100. The same ticker appears twice under different caps (AMD 10.0% then
3.0%; GRAB 100.0% then 3.0%; NVDA, SNDK, KTOS likewise). Nothing here is averaged across that
boundary. CR153 filed a wrong finding by pooling two same-ticker convenes; this CR states the mandate
whenever a rate could depend on one.

---

## Why

The PM is the only agent whose output becomes a **decision**. It is parsed into a structured
`Verdict` (`_parse_pm_verdict`, `room_runner.py:945`), vetoed by the deterministic floor
(`enforce_safety_floor`, `safety_floor.py:676`), rendered on the Verdict Board, and written to the
permanent Decision Journal (`build_journal_entry_for_run`, `room_runner.py:2178` — `title` and
`summary` are `verdict.action` and `verdict.reason` verbatim). Its prompt is the largest in the
system: median **22,788 chars** over the 18 real prompts (min 21,161, max 24,320), of which a median
**10,121 chars (44%)** is the eleven-turn transcript.

Three things are wrong with it, and none of them is what either review led with.

### 1. The one data feed built exclusively for this agent has never reached it

CR026 gave the PM — and only the PM — the portfolio's real sector allocation, so the agent that
gatekeeps against the sector cap reasons from data instead of a guess. `_format_sector_allocation`
(`room_prompts.py:489`) is gated to `AgentId.PORTFOLIO_MANAGER` at `room_prompts.py:453-455`.

`_stream_pm_response` — **the only call site that builds the live PM's Room prompt** — calls
`build_room_messages(...)` at `room_runner.py:3655-3672` and **does not pass `sector_weights`**. The
kwarg defaults to `None`, and `_format_sector_allocation(None)` returns its empty-state copy:

```text
- sector allocation: no open positions yet (0% in every sector).
```

The sibling call site for the eleven prose agents *does* pass it (`room_runner.py:3471`) — where the
PM-only gate makes it a no-op. The data is computed correctly and per run
(`_build_room_sector_context`, `room_runner.py:774`, invoked `:2915`), lands on `ctx.sector_weights`,
and is handed to the deterministic floor (`room_runner.py:3239-3241`) — so the **sector cap itself is
enforced**. Only the prompt line is dead.

**Measured, epoch, n=18 PM prompts:** the empty-state copy is rendered **18/18 (100%)**. Eight of
those prompts carry a non-empty holdings block in the same prompt — 4 positions (AMD, GRAB, TSLA,
NVDA, BAC), 5 positions (SNDK, KTOS), and one with `GME ×500 (95.8% of portfolio)` (SNOA). **In 8 of
8 convenes where the line could be false, it was false.** It has been correct only by coincidence,
on the ten runs whose book was genuinely empty.

This is the CR040 class named in CLAUDE.md — a shipped feature dark for want of one line, degrading
into a *positive false claim* rather than silence. The two existing tests
(`test_cr026_sector_allocation.py:464-508`) call `build_room_messages` directly with
`sector_weights=...`; nothing asserts that production supplies it. `scripts/dump_assembled_prompts.py:218`
passes it too, which is why CR143's `assembled/` corpus renders the feature working and masks this —
Phase 1's `--verify` gate compares layer order and segment size, not content.

Both reviews reported the false line. Both attributed it to `_build_room_sector_context` degrading to
`{}` on exception or to missing marks. **That attribution is wrong** and would have produced a fix in
the wrong file: `SectorMapProvider.get` cannot raise (`sector_allocation.py:283-297`), and the same
run's `Portfolio value: $9,411.21` against `Cash: $7,161.28` proves `portfolio.holdings` was
non-empty with live marks at that moment.

### 2. The parser reads one key; the profile teaches a different one — and the miss is disclosed as a lie

`_parse_pm_verdict` reads `narration` and nothing else (`room_runner.py:955`). The base profile's
still-live `## Output format` block (`content/agents/portfolio_manager.md:36-45`) labels the same
field `Reasoning:`.

**GRAB, 2026-08-07 19:19:37Z, mandate cap 3.0% — the PM's verbatim reply:**

```json
{"action": "MODIFY", "size_pct": 2.0, "entry": 3.67, "stop": 3.45, "target": 5.89,
 "horizon_days": 88,
 "rationale": "The Trader's proposal to size at the full 3.0% cap is rejected as too aggressive …
   I modify the size to 2.0% and tighten the stop to $3.45 (6.0% below entry) … This captures the
   44% upside to the $5.89 target against the $4499M net cash fortress …"}
```

Three complete sentences of real reasoning, under the wrong key. `_normalize_pm_action` absorbs
`MODIFY` → `APPROVE` (`room_runner.py:854-887`, DEF067, working as designed). `size_pct` is present,
so the APPROVE branch runs, the reformatter is never invoked, and `narration` is `""`.

Re-run against **HEAD's parser on the real reply** (`_parse_pm_verdict`, `_RoomContext`, this
mandate):

```text
ACTION: APPROVE | size 2.0 entry 3.67 stop 3.45 target 5.89 | prov {'entry':'pm','stop':'pm','target':'pm'}
REASON: [AMI: the Portfolio Manager returned this decision as data only — it wrote no rationale for
        the call. Nothing was said to defend it, so there is nothing here to weigh. Treat it as an
        unexplained decision, not a reasoned one.]
```

That string is `_PM_NO_RATIONALE` (`room_runner.py:937`), DEF232's fix. It is rendered on the Verdict
Board as the decision's justification, amber-marked by CR106 §3.3's `content.contains('[AMI')`, stored
as the PM's transcript turn, and written into the Decision Journal — **and on this class of failure it
is false.** The PM wrote a rationale. AMI tells the user it did not, in AMI's loudest honesty voice.

This also corrects DEF232's own diagnosis. Its row says *"the PM produced no prose"* for this exact run
(`84bb2cf9`, 19:17Z) and asks where `"Synthesis defended."` came from. The `llm_audit` row answers it:
prose existed, the parser dropped it on a key name. DEF232's rate — **23 of 965 non-fail-safe verdicts
(2.4%)** carry a reason under 40 chars — is the size of the *class*; a key mismatch is one identified
mechanism inside it, not necessarily all of it.

**Epoch rate: 1/18 (5.6%, 95% CI [0.1%, 27.3%]).** One convene, so the interval is wide; the *mechanism*
is not probabilistic and the fix is two lines.

### 3. The REPLACES line reconciles the output block and leaves the decision sequence contradicting it

`_PM_VERDICT_FORMAT` says (`room_prompts.py:183-185`):

> This output format REPLACES the 'Verdict:' / 'Output format' block described earlier in your profile.

That covers `content/agents/portfolio_manager.md:36-45`. It does **not** cover, in the same prompt:

| Layer | Line | Text |
|---|---|---|
| base profile | `portfolio_manager.md:27` | *"If compliance fails → **REJECT** with the specific violation."* |
| base profile | `portfolio_manager.md:32` | *"Issue: **APPROVE**, **REJECT**, or **MODIFY-AND-APPROVE**"* |
| mandate overlay | `overlay_generator.py:471` | *"If any compliance violation: **REJECT** with explanation."* |
| mandate overlay | `overlay_generator.py:475` | *"Issue: APPROVE / REJECT / MODIFY-AND-APPROVE"* |
| mandate overlay | `overlay_generator.py:477` | *"If **MODIFY**: propose specific size/timing adjustment."* |
| safety floor | `safety_floor.py:129-139` | *"YOU MUST **REJECT** any trade that…"* then *"your output MUST be `{"action": "PASS"…}`"* |

Against `_PM_VERDICT_FORMAT`'s *"There are exactly two action values: APPROVE and PASS."*

The parser survives all of it — `_normalize_pm_action` maps `REJECT`→`PASS` and `MODIFY-AND-APPROVE`→
`APPROVE`, and `test_room_prompt_parity.py` guards exactly that. **The user does not.** The wire action
is what colours the card; the prose is what they read.

**Measured, epoch, n=18** (spans all three mandates; the artefact is prompt-side, not mandate-side):

| | rate | 95% CI |
|---|---|---|
| narration says *"reject/rejected"* inside a **PASS** verdict | **6/18 = 33.3%** | [13.3%, 59.0%] |
| raw `"action"` is a banned MODIFY-form | 1/18 = 5.6% | [0.1%, 27.3%] |
| first-pass parse succeeded | **18/18 = 100%** | [81.5%, 100%] |
| `_reformat_pm_response` fired | **0/18 = 0%** | [0%, 18.5%] |

One narration literally opens `"PASS — REJECTED due to mandate conflict: …"`.

`mobile/lib/screens/room/room_screen.dart:1158-1172` renders PASS in **slate** and REJECT in **amber**,
with a comment stating outright that PASS *"doesn't read as a rejection (DEF056: PASS is now a real,
distinct outcome)"*. So a third of PM verdicts present a neutral slate card whose body says the trade
was rejected — and `REJECT` is a real, reachable state that means something entirely different: the
deterministic floor overrode the PM (`safety_floor.py:729-733`, `overridden_from_llm=True`). The word
the user reads cannot tell them which authority turned the trade down.

### And the trailing tag line is not unsatisfiable — it is unreliable, which is worse

Both reviews concluded the safety floor's *"End every verdict with this exact line: Worked example —
classroom simulation, not financial advice."* (`safety_floor.py:121-122`) can never appear, because
`_PM_VERDICT_FORMAT` demands pure JSON and nothing appends it downstream. **Measured, both wrong:**
the model puts it *inside* `narration`, so it lands in `Verdict.reason` and ships.

- **Epoch: 1/18 (5.6%)** — the LITE convene's stored reason ends `"… Worked example — classroom
  simulation, not financial advice."`
- **All-time, `$`-filtered, deduplicated: 48/811 (5.9%)** carry the phrase.

Grep-verified: no per-verdict disclaimer string exists in `mobile/lib` — the only disclosure key,
`disclaimerShort`, is used once, in `services/share/share_service.dart:136`, on the share card. So on
~6% of verdicts a legal-framing sentence appears as part of the PM's justification, and on ~94% it
does not appear at all. That is the CLAUDE.md rule stated backwards: *prompt instructions are not
controls.* A disclosure that must hold has to be structural.

### What is NOT wrong — and matters, because it sets the priority

- **The scaffolding is idle.** First-pass parse 18/18; reformatter 0/18. The 18.4% figure in the CR156
  stub was a pooling artefact across a prompt change; the epoch figure is zero. CR105's 31.7%
  banned-action rate (n=161) re-derives to **1/18 (5.6%)** here — same direction, wide interval, not a
  crisis.
- **Length holds.** `_LENGTH_GUIDE[PORTFOLIO_MANAGER]` asks 3–4 sentences; measured 3 sentences ×13,
  4 ×4, empty ×1 — **0/18 over budget**, against DEF236's 61–100% over-budget rates for the prose
  agents. The PM is the one agent whose length guide the model obeys, because it is inside a JSON
  field rather than competing with `_PROSE_FORMAT`.
- **Format compliance is total.** 18/18 replies begin `{` and end `}` with no prose outside.
- **The floor is the control and it is wired.** `enforce_safety_floor` receives portfolio value,
  current drawdown, halal/classification/locale universes, sector holdings+marks+map, last-loss
  timestamp, trade timestamps, existing open risk and the proposed stop (`room_runner.py:3231-3252`).
  Current drawdown hard-blocks at `safety_floor.py:546-549`.
- **The PM is correctly excluded from the stance envelope** (`room_prompts.py:387-395`);
  `parse_stance_envelope` never runs on its reply. Nothing to do.

---

## Scope — four tiers, ordered by cost

### Tier A — two missing lines. No prompt change, no re-measure risk

**A1 — `_stream_pm_response` must pass `sector_weights=ctx.sector_weights`** (`room_runner.py:3655`).
One kwarg. Then make the empty-state honest: `_format_sector_allocation` currently conflates *"no
holdings"* with *"no weights supplied"*. Give it the holdings count (or a distinct sentinel) so a
non-empty book with no weights renders a loud unavailable line, never `0% in every sector` — CR040,
and the reason this went unnoticed for the life of CR026.

**A2 — `_parse_pm_verdict` must accept `rationale` and `reasoning` as `narration` aliases** before
falling through to `_PM_NO_RATIONALE` (`room_runner.py:955`). Read them in a fixed order, prefer
`narration`. `_PM_NO_RATIONALE` then means what it says.

Both are **defect-shaped, not feature-shaped** — a shipped behaviour that is broken versus spec. Ask
the Architect to mint two `DEF###` for them; this CR is the evidence file and the measurement, not the
ID. A1 and A2 are independent of each other and of everything below.

**Guards that must ship in the same commit** (the CR040 lesson is that the fix without the guard comes
back): a parity test asserting the *production* PM prompt path renders a real allocation for a
non-empty book — not `build_room_messages` called directly, which is what
`test_cr026_sector_allocation.py:464` already does and what let this through; and a parse test pinning
the GRAB reply verbatim from the corpus so an aliased key can never silently regress to
`_PM_NO_RATIONALE` again.

### Tier B — reconcile the vocabulary the REPLACES line leaves uncovered (prompt diff, must be re-measured)

Extend the reconciliation to the decision sequence, in both layers that carry one
(`content/agents/portfolio_manager.md:24-34` and `overlay_generator.py:468-477`), so the Room's
two-action vocabulary is not contradicted three lines after it is stated. Preferred shape: keep the
gatekeeper logic, rewrite the *verdict words* — "if compliance fails, PASS and name the rule" — and
widen `_PM_VERDICT_FORMAT`'s REPLACES sentence to name the decision sequence, not only the output
block.

Three constraints, all checked, all capable of turning something red:

1. **`test_room_prompt_parity.py:68` asserts a `MODIFY` token survives in the assembled PM prompt.**
   Its extractor scans only `Issue:` / `Verdict:` / `"action":` lines. In the real Alpha prompt three
   lines supply the token (`:28`, `:35`, `:103` of the rendered prompt = profile `:32`, profile `:39`,
   overlay `:475`). Removing the `## Output format` block alone keeps the test green; removing the
   vocabulary everywhere turns it red. That assertion is a deliberate canary — *"If this ever
   disappears, revisit the profile too"* — so it may be changed, but only with the justification
   rewritten in the same commit. This is precisely the CR105 Amendment-1 trap and the reason this CR
   does not simply propose deleting the block.
2. **The `## Output format` block is load-bearing on the 1-on-1 surface.** `agent_runner.py:160` builds
   the PM's 1-on-1 prompt through `build_agent_prompt` with **no `_PM_VERDICT_FORMAT`**, so that block
   is the only format instruction the PM has there — and nothing parses it. Delete it and the 1-on-1
   PM is un-formatted. Keep or replace, never delete.
3. **The safety floor's REJECT/PASS pairing is not a candidate for editing** except in the tag-line
   sentence. The floor is uncoachable by design (DEF059) and is the sole vetoer; routing any of its
   flags into a verdict is out of scope by construction, and this CR proposes nothing that touches
   `enforce_safety_floor` or `check_mandate_compliance`.

Also here: **make the classroom disclosure structural.** Either drop *"End every verdict with this
exact line"* from `SAFETY_FLOOR_BLOCK` for the Room's JSON path and render the disclosure
deterministically at the verdict surface, or append it deterministically server-side after parse. What
it must not stay is a prompt instruction that fires 6% of the time inside the justification field.
Which of the two is a decision for Saiful — the client change is a new string needing `ar`/`ms`
translation (`retranslate:[ar,ms]`), the server change puts a fixed sentence in every Journal row.

### Tier C — render the three mandate figures already computed for the floor (one render block)

All three are fetched per run, handed to `enforce_safety_floor`, and never shown to the agent expected
to weigh them:

| figure | computed | consumed | in prompt |
|---|---|---|---|
| current drawdown % | `sim.valuation_snapshot` → `api/room.py:188` → `ctx.current_drawdown_pct` | `safety_floor.py:546` — hard block | no |
| existing open-risk % | `_build_room_risk_limit_context` → `sim_engine.py:481-501` | `check_mandate_compliance` 6f | no |
| trades today / this week | `trade_open_timestamps`, same call | `check_mandate_compliance` 6e | no |

The prompt asks for current drawdown **three times across two layers** (`portfolio_manager.md:21`
Inputs, `:31` decision sequence, `overlay_generator.py:474`) and supplies it nowhere. CR143 Phase 1
recorded it as the only claim in the whole supplier map with no supplier at all.

**Honest severity, measured:** the PM does **not** fabricate the missing figure. `0/18` epoch
narrations state a current-drawdown value; `0/811` all-time reasons contain the phrase *"current
drawdown"*. It omits the instruction rather than filling it — so this is a capability gap, not the
CR038 unhedged-assertion class, and it ranks below Tiers A and B. The reviewer's "Mid" impact is one
notch high.

**Overlap to resolve before building:** CR155 Tier C proposes rendering `existing_open_risk_pct` for
the Neutral Debator. Same render, same source. Ship it once, in whichever CR lands first, and delete
the tier from the other.

### Tier D — one documentation correction

`docs/initial_specs/02_agents/safety_floor.md:81` states: *"By placing the safety floor last, we make
it the dominant instruction."* `agent_prompts.py:95` repeats it. **True on the 1-on-1 surface; false in
the Room** — `build_room_messages` appends `room_addition` after `build_agent_prompt` returns, so the
floor is followed by a median **15,794 chars** (69% of a median 22,788-char prompt): the fact sheet,
the mandate snapshot, the full transcript and `_PM_VERDICT_FORMAT`. Verified 18/18.

This is a doc fix, not a behaviour change. The property is partly preserved on purpose —
`_PM_VERDICT_FORMAT`'s closing sentence re-anchors the floor as the last words the model reads
(*"The safety floor above still applies regardless of what you decide"*) — and the real control is
deterministic, not positional. Correct both docstrings to describe the two surfaces; do not move the
block on the strength of a recency argument nobody has measured here.

---

## Claims rejected after checking

| claim | source | why it is not scope |
|---|---|---|
| *"Required upstream inputs (Trader / RM / Debators) are missing"* | blind review | Dead. VERDICT is sequential and `_format_transcript` supplies all eleven prior turns; median 10,121 chars of transcript in 18/18 prompts. The blind corpus was a transcript-less render. |
| *"'Only numbers from the data block' makes an APPROVE unfillable"* | blind review | Dead. The reference position (`_drawdown_snapshot_line`, `room_prompts.py:280`) hands over size/entry/stop/stop-distance/contribution; the debators supply alternative sizes; the AMI-verified R:R line supplies target-side geometry. 3 APPROVEs in the epoch, every level sourced `pm`. |
| *"The supplied portfolio breaches the single-name cap it must enforce (MSFT 26.1% vs 3.0%)"* | blind review | Not reproduced. Checked every holding in all 18 prompts against that prompt's own cap: **zero** over-cap positions. SNOA's `GME ×500 (95.8%)` sits under a 100% cap. Corpus-specific to the blind reviewer's fixture. |
| *"The tag line can never appear / is unsatisfiable"* | both reviews | **False.** 1/18 epoch and 48/811 all-time reasons carry it, inside `narration`. The defect is the opposite of the one claimed: not absence, but 6% presence in the justification field. |
| *"The false sector line is caused by `_build_room_sector_context` returning `{}` on exception, or by missing marks"* | kimi review | Wrong mechanism. `SectorMapProvider.get` cannot raise; the same run's portfolio value proves live holdings and marks. The cause is a missing kwarg at `room_runner.py:3655`. Fixing the builder would have changed nothing. |
| *"Render market cap so the microcap rule is checkable"* | kimi review | Correct, and **already CR145 Tier A** — `marketCap` is read at `fundamentals.py:248` as the FCF-yield denominator and discarded. Not re-scoped here. PM-specific evidence handed to CR145: 33/811 reasons invoke microcap/illiquidity language, 0/811 state a market-cap figure. |
| *"Route a floor flag into the verdict"* | implied | Out of scope by construction. The floor is the sole vetoer (DEF059) and is uncoachable by design. |
| `_LENGTH_GUIDE` / `_PROSE_FORMAT` / `_STANCE_FORMAT` (DEF236), `_LEVEL_PATTERNS` (DEF235), `LearningStyle.QUICK`, per-agent fact sheet | cross-cutting | CR145. Also: none of them bind here — the PM gets `_PM_VERDICT_FORMAT`, not `_PROSE_FORMAT`, and is 0/18 over budget. |
| DEF231–234 direction-claim checker | in audit | Not re-litigated. Note the interaction in Acceptance. |
| DEF237 plausibility backstop | open | Its two live instances are debator turns, not PM turns, and are not caused by anything in this CR. |

---

## Could not verify

- **Whether A2's key mismatch accounts for all 23 of DEF232's sub-40-char reasons (2.4% of 965).** The
  epoch `llm_audit` covers 18 PM turns; the other 22 instances predate it and their raw replies were
  not exported. A2 fixes the one mechanism proven on the one case in hand; the residual is unknown.
- **Whether `_build_room_sector_context` returns non-empty weights on Alpha.** The prompt tells us
  nothing about it (the kwarg never arrives), the container was restarted 2026-08-08 08:37Z so the
  epoch's logs are gone (`room_sector_context_failed`: 0 hits in the surviving 48h window, from
  1 convene), and a direct DB read was not available in this session. The floor's sector check reads
  the same builder, so if it *is* degrading, the cap is silently skipped too. **A1's acceptance must
  assert a real allocation renders on a non-empty book, not merely that the kwarg is passed** —
  otherwise a green wiring fix could still ship the same empty line.
- **Whether the tag line's 6% presence is stable or drifting.** 1/18 and 48/811 agree, but the 811 are
  deduplicated and `$`-filtered across every prompt epoch; they are not a rate.
- **Recency weight of the safety floor's position.** Named as an open question in Tier D, not a
  finding. 3 APPROVEs in 18 is too few to test anything about instruction ordering.

---

## Acceptance

- **A1:** on ≥30 convenes with a non-empty book, `- current sector allocation (of invested value): …`
  renders with real weights in **≥95%**, and `0% in every sector` appears in **0** prompts whose
  holdings block lists a position. A failure to compute weights renders a loud unavailable line, never
  the empty-state copy. Production-path parity test green.
- **A2:** the GRAB reply from the epoch corpus parses to an APPROVE whose `reason` is the model's own
  three sentences. `_PM_NO_RATIONALE` appears **only** where the reply genuinely carries no rationale
  under any accepted key. Re-measure the sub-40-char reason rate against DEF232's 23/965 baseline.
  **Also re-measure DEF231's direction-signal rate**: recovering these narrations enlarges the
  population `_annotate_direction_against_price` reads, so its rate will move for a reason that is not
  a regression — record it before, not after.
- **B:** on ≥30 convenes, REJECT vocabulary inside a PASS narration falls from **6/18 (33.3%)** to
  ≤10%; banned MODIFY-form actions stay ≤5.6%; first-pass parse stays 100% and the reformatter stays
  at 0. The classroom disclosure is present on **100%** of verdicts by construction, or on 0% with the
  prompt instruction removed — not 6%. `test_room_prompt_parity.py` green, with any change to its
  MODIFY assertion justified in the same commit.
- **C:** current drawdown, existing open-risk % and today's/this-week's trade counts render in the PM's
  mandate snapshot; a `None` renders as *"unavailable this run"* (CR040), never as `0`. Any PM
  narration stating one of the three agrees with the rendered figure in ≥90% of cases.
- **D:** both docstrings describe the two surfaces accurately. No code moves.
- `pytest backend/tests/unit/ -q` green throughout, and CR143's six baselines re-measured
  post-promotion. A prompt edit whose effect is not re-measured is the CR105 Amendment-1 trap.

---

## Notes

Tier A is two lines and can ship alone, today; it is also the only tier that fixes something the user
is being actively misinformed by — a false fact in the gatekeeper's prompt in 8 of 8 eligible
convenes, and a false AMI disclosure over a rationale the PM actually wrote. Both are defect-shaped
and want `DEF###` from the Architect.

Tier B is the one with blast radius: it edits the base profile and the mandate overlay, which every PM
prompt on both surfaces carries, and it touches a test that was written to fail on exactly this kind
of edit. It should not ship in the same commit as Tier A, or the re-measure cannot attribute.

Tier C is cheap but ranks last on evidence — the missing data produces omission, not fabrication — and
it must be de-duplicated against CR155 Tier C before anyone writes it twice.

The headline for the whole review is worth stating plainly: **the Portfolio Manager follows its
instructions better than any other agent in the Room.** It is 100% format-compliant, 100% first-pass
parseable, 0% over budget, and its one hallucination-adjacent behaviour is quoting a transcript
inaccuracy rather than inventing a number. Every finding above is ours, not the model's.
