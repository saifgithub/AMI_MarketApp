# External review — portfolio_manager (data sufficiency + supplier check)

> Reviewer: `kimi-for-coding` · Kimi track K session.
> Corpus reviewed: `docs/forward_planning/CR143_agent_prompt_audit/real_samples/portfolio_manager.prompt.txt`
> (AMD, fact sheet as of 2026-08-07) and `real_samples/portfolio_manager.reply.txt`.
> Unlike `external_review/room/portfolio_manager.md` (blind prompt-coherence audit),
> this review had codebase access. Every availability claim below is verified against
> the actual fetch/assembly path — these are **findings, not hypotheses**.

## 1. Question

Does the Portfolio Manager have enough data in the prompt to do its job to
~95% accuracy?

## 2. Answer

**Yes for the verdict it actually issued (PASS + narration), no for the full gatekeeper job.**

The PM's scoped deliverable is one JSON object — APPROVE with trade geometry, or
PASS with a 3–4 sentence narration — after weighing the debate and applying the
mandate. Against that scope the prompt is unusually well supplied:

- The full transcript is present: Trader's proposal (WAIT, size 0%), Research
  Manager's synthesis (**Neutral**), all 3 Risk Debators with concrete sizes and
  stops (10.0% / 4.0% @ $464.65 / 5.0% @ $464.65).
- The mandate caps are stated with worked semantics (50% portfolio-level drawdown
  cap, 10.0% single-name cap, 20% sector cap, pace caps, 60% open-risk cap).
- The drawdown arithmetic is **precomputed and handed over**: reference position
  (risk-tier ceiling 10.0% size, entry 494.31, stop 464.65) → 6.0% stop → ≈0.60 pt
  of the 50 pt cap. Deterministic, from code (`room_prompts.py:280-318`).
- Trade geometry is verified in-prompt: "[AMI verified the trade geometry … R:R
  3.8:1; 23.0% upside vs 6.0% downside]" — rendered from `trading_math`, not the
  model (`room_runner.py:1218`).

Estimated accuracy on the scoped deliverable: **~90–95%**.

Against the full job the role guidance describes — independently evaluating every
mandate cap ("Consider the user's risk_score and **current drawdown**", "remaining
drawdown" in the Inputs list, liquidity rule, open-risk cap, pace caps) — the data
caps out closer to **60–70%**, because every portfolio-risk *state* input is
missing, and the one sector input that IS rendered was false in this run.

## 3. Data gaps (from the prompt alone)

| # | Gap | Impact |
|---|---|---|
| 1 | **Current drawdown not given.** Inputs list promises "User's current portfolio state + remaining drawdown"; decision sequence step 3 says "Consider the user's risk_score and current drawdown". The mandate snapshot shows only the 50% cap and a reference contribution — never the actual current drawdown. The PM cannot weigh the headroom it is told to weigh. | Mid — matters exactly when the book is under water |
| 2 | **Sector allocation line false in this run.** Mandate snapshot: "- sector allocation: no open positions yet (0% in every sector)." — while the portfolio block lists 4 open positions (DIS 4.4%, GOOGL 3.8%, HPQ 6.3%, NVDA 9.4%) and the transcript's RM/Trader argue semiconductor concentration via NVDA. The prompt contradicts itself on the one datum the sector cap gates on. | High — a false fact sheet for the gatekeeper |
| 3 | **Market cap absent.** Compliance rule: "Liquid only. Avoid microcaps (< $500M market cap)". No market-cap figure anywhere in the block; the rule is unverifiable from the data. | Low for AMD, structural for small caps |
| 4 | **Total open-risk cap stated (60.0%), current open-risk sum not given.** Holdings carry no stops, so the PM cannot compute or even approximate the sum it is capping against. | Mid |
| 5 | **Trading pace cap stated (10/day, 50/week), no trade counts given.** Unverifiable by the PM. | Low |
| 6 | Max open positions 50 — countable from the portfolio block (4). **Not a gap.** | — |

Note on contradiction vs. role guidance: the role guidance twice instructs the PM
to weigh "current drawdown" (base prompt `content/agents/portfolio_manager.md`,
decision sequence step 3, and the Inputs list) — the prompt never supplies it.
That is guidance demanding an input the assembly does not render.

## 4. Supplier check — what the codebase actually delivers

PM prompt assembly: `build_room_messages()` — `backend/app/services/room_prompts.py:321-483`
(mandate snapshot at `:462-468`, sector line gated to the PM at `:450-455`,
`_PM_VERDICT_FORMAT` at `:178-208`). Deterministic enforcement:
`enforce_safety_floor()` — `backend/app/agents/safety_floor.py:676-734`, called at
`room_runner.py:3174`. Verdict parsing: `_parse_pm_verdict()` — `room_runner.py:945-1041`.

| # | Item | Verdict | Evidence |
|---|---|---|---|
| — | Upstream debate inputs (Trader / RM / 3 Debators) | **ALREADY WIRED** | `_format_transcript` (`room_prompts.py:886`); all six turns present in the real prompt. The blind review's "required upstream inputs are missing" hypothesis is **killed** — its corpus differed (3546 tokens, MSFT ×40 portfolio, 3.0% cap, no transcript). |
| — | Reference position + drawdown math | **ALREADY WIRED** | `_risk_tier_size_ceiling` (`room_runner.py:663-672` → `trading_math/sizing.py:73`); entry = base price, stop = base×0.94 (`room_runner.py:2910-2913`: 494.31×0.94 = 464.65 ✓); contribution via `drawdown_contribution` (`trading_math/risk.py:24`), rendered by `_drawdown_snapshot_line` (`room_prompts.py:280-318`, DEF066). |
| 1 | Current drawdown | **FETCHED, NOT SURFACED** | Real value resolved per run: `sim.valuation_snapshot()` at `backend/app/api/room.py:188-190` → `start_run(current_drawdown_pct=…)` → `ctx.current_drawdown_pct` (`room_runner.py:2882`) → `enforce_safety_floor` (`room_runner.py:3177`). Never rendered into the prompt — one line in the mandate-snapshot block. |
| 2 | Sector weights | **WIRED, DEGRADES TO A FALSE STATEMENT** | `_build_room_sector_context` (`room_runner.py:774-797`) returns `{}` on ANY exception, and `allocate_by_sector` returns `{}` when marks are missing (`sector_allocation.py:131-136`). `_format_sector_allocation` (`room_prompts.py:489-493`) renders falsy weights as "- sector allocation: no open positions yet (0% in every sector)." — conflating "no holdings" with "sector fetch failed". That is how this run's PM got a 0% sector line over a 4-position book. Also note the deterministic floor degrades the same way: empty context → sector cap "simply doesn't fire" (`room_runner.py:778-780`). The floor's silent skip is a documented choice; the prompt's false claim is not. CR040 loud-degrade violation. |
| 3 | Market cap | **FETCHED, DISCARDED** | `marketCap` read in `fundamentals.py` (~`:247`) as the denominator of the FCF-yield calc, never rendered. One render-key change — same finding as the fundamentals_analyst report. |
| 4 | Existing open-risk sum | **FETCHED, NOT SURFACED** | `_build_room_risk_limit_context` (`room_runner.py:800-`, invoked `:2864-2868`) computes `risk_existing_open_risk_pct` for the floor only; never rendered. |
| 5 | Trade pace counts | **FETCHED, NOT SURFACED** | `trade_open_timestamps` built in the same call (`room_runner.py:2864`), fed to `check_mandate_compliance` only. |
| — | Liquidity/universe data beyond market cap | **NOT AVAILABLE** without a new provider | No float/ADV-based liquidity measure in the yfinance surface in use (`.info`, `.fast_info`, `.history()`, `.news`, `.calendar`). The $500M market-cap proxy is the cheap version and is already in hand (#3). |

## 5. Prompt-internal contradictions — confirmed against code

The blind review's §2 findings, checked against the rendered sources:

1. **REJECT vs PASS — CONFIRMED, live in the real prompt.** `SAFETY_FLOOR_BLOCK`
   (`safety_floor.py:129-139`) says "YOU MUST REJECT any trade that…" then "your
   output MUST be {"action": "PASS"…}". Additionally the deterministic override
   emits `VerdictAction.REJECT` (`safety_floor.py:729-733`) — a real verdict state
   the PM's own binding vocabulary (`_PM_VERDICT_FORMAT`: "exactly two action
   values: APPROVE and PASS", `room_prompts.py:197-201`) can never produce.
2. **Trailing tag line vs JSON-only — CONFIRMED, unsatisfiable.** Safety floor:
   "End every verdict with this exact line: Worked example — classroom simulation,
   not financial advice." (`safety_floor.py:121-122`). Binding format: "Your
   ENTIRE reply must be one single JSON object" (`room_prompts.py:186-189`).
   Nothing downstream appends the tag — the string exists only at
   `safety_floor.py:122` in the backend and has **zero** hits in `mobile/lib`.
   The mandated line can never appear.
3. **Verdict vocabulary / schema (profile template vs binding JSON) — CONFIRMED but
   partially mitigated in the real prompt.** The base prompt's Output-format block
   (`content/agents/portfolio_manager.md`: "Verdict: APPROVE | REJECT |
   MODIFY-AND-APPROVE … Instrument, Side, Size…") survives into the rendered
   prompt, but the real prompt carries the reconciling line the blind corpus
   apparently lacked: "This output format REPLACES the 'Verdict:' / 'Output
   format' block described earlier in your profile" (`room_prompts.py:183-185`).
   The decision-sequence prose ("If compliance fails → REJECT", "Issue: APPROVE,
   REJECT, or MODIFY-AND-APPROVE") is NOT covered by that reconciliation.
4. **Single-name cap breached by supplied portfolio — NOT REPRODUCED.** Blind
   corpus: MSFT 26.1% vs 3.0% cap. Real sample: NVDA 9.4% under a 10.0% cap —
   consistent. Corpus-specific, not structural.
5. **"Only numbers from the data block" vs required trade geometry — largely
   KILLED.** The block precomputes a full reference position (10.0% / 494.31 /
   464.65 / 6.0% / 0.60 pt), the AMI-verified R:R line (3.8:1) adds target-side
   geometry, and the debators supply alternative sizes (4.0%, 5.0%). An APPROVE
   can be filled entirely from block numbers. Weakest field: `horizon_days` —
   only the 88-days-to-earnings anchor exists.

## 6. Structural caveats

1. **The sector fix is not "render more" — it is "stop rendering false."** The
   weights pipeline already runs per convene; the defect is the empty-state copy
   and the silent-skip floor path, not a missing fetch.
2. **Surfacing #1/#4/#5 is render-only, zero new provider cost** — all three are
   already computed per run for `enforce_safety_floor`. The risk is prompt bloat
   and number-noise, not rate limits.
3. **Market cap render shares the fundamentals lane's caveat**: fundamentals are
   fetched live per run with no cache; rendering an already-fetched field adds no
   new Yahoo exposure.

## 7. Recommended slice (if this becomes a CR)

1. Fix `_format_sector_allocation` to distinguish "no holdings" from "sector data
   unavailable" — render the latter loudly, never "0% in every sector" over a
   non-empty book. (Highest value; this run's prompt shipped a false fact.)
2. Render current drawdown, existing open-risk %, and today's/this week's trade
   counts into the PM's mandate snapshot — all already computed.
3. Resolve the tag-line contradiction: either drop "End every verdict with this
   exact line" from `SAFETY_FLOOR_BLOCK` for the Room JSON path, or append the tag
   deterministically at verdict-render time. Same change should reconcile
   REJECT/MODIFY vocabulary with the two-action JSON schema.
4. Render market cap (already fetched) so the liquidity rule is checkable —
   fold into the fundamentals_analyst slice if that CR lands.

## 8. Reply-sample verification (`real_samples/portfolio_manager.reply.txt`)

Checked line-by-line against the prompt's data block.

**Numerically clean.** Every figure is verifiably in the block: $494.31, $424.03,
$608.23, NVDA 9.4%, RSI 49, 126.4 P/E, 88 days, $584.73, risk_score 3. Zero
hallucinated numbers. The grounding directive held on facts.

**Format compliance:** single JSON object, begins `{` ends `}`, no prose outside ✓.
`action: PASS` with only narration — schema-conformant, and the parser's PASS
branch reads only `narration` (`room_runner.py:960-966`), so the explicit nulls
are harmless. Narration is 3 sentences (mandate: 3–4) ✓. No "As the X" preface ✓.
The safety-floor-mandated trailing tag line is absent — unsatisfiable inside pure
JSON (§5.2); the reply chose JSON compliance, and nothing downstream would have
added it anyway.

**Two non-numeric observations:**

1. **Sector claim navigated a prompt contradiction silently.** "adding AMD now
   would increase semiconductor concentration" — supported by the transcript
   (Trader: "increases sector concentration in Semiconductors"; RM likewise), but
   the prompt's own mandate snapshot said "0% in every sector", and NVDA's sector
   is never stated in the data block. The reply sided with the transcript — a
   reasonable resolution, but the underlying contradiction is the prompt's
   defect (#2), not the model's.
2. **"sits exactly between"** is the RM/Trader's phrasing, quoted — arithmetic
   says otherwise ($70.28 below vs $113.92 above), so the reply inherited a small
   transcript inaccuracy rather than creating one. Not hallucination.

**Stance-evidence tension:** none. PASS matches a cautionary body; conviction and
argument are aligned.

**Scope bleed:** none. Weighing the analysts, debate, Trader and debators is the
PM's defined role; quoting their numbers is the job, not a lane violation —
unlike the fundamentals_analyst reply, which drifted into other agents' domains.

**Net: GROUNDED.** Bound to the data on facts, bound to its role, format-compliant
on the binding contract. The two soft spots both trace to prompt defects
(false sector line, transcript's "exactly between"), not to the model.

## 9. Relationship to the blind review (`../portfolio_manager.md`)

| Blind-review claim | Verdict here |
|---|---|
| Required upstream inputs (Trader / RM / Debators) missing | **KILLED** — present in the real prompt; blind corpus was a different, transcript-less render. |
| Verdict vocabulary contradiction (3 values vs 2) | **CONFIRMED** in sources, partially mitigated by the REPLACES line the blind corpus lacked. |
| REJECT vs PASS contradiction | **CONFIRMED** — `safety_floor.py:129-139`; plus the floor itself emits REJECT, a state the PM cannot. |
| Tag line vs JSON-only output | **CONFIRMED** — unsatisfiable; never appended anywhere downstream. |
| Trade schema mismatch (Instrument/Side/… vs JSON) | **CONFIRMED** in sources, softened by the REPLACES line. |
| Portfolio breaches the cap it must enforce (MSFT 26.1% vs 3.0%) | **NOT REPRODUCED** in the real sample (NVDA 9.4% vs 10.0%) — corpus-specific. |
| "Only data-block numbers" blocks filling an APPROVE | **LARGELY KILLED** — reference position + verified R:R + debator sizes supply the geometry; `horizon_days` is the one weak field. |
| Hard compliance checks need absent data (drawdown, etc.) | **CONFIRMED AND EXTENDED** — current drawdown, open-risk sum, pace counts all fetched for the floor but never rendered; sector line actively false. |

Overlap is high on contradictions, but the blind review's two biggest structural
claims (missing inputs, unfillable trade plan) do not survive contact with the
real corpus, while its compliance-data claim understates the problem: the data
exists one function call away from the prompt, and one rendered field was wrong.
