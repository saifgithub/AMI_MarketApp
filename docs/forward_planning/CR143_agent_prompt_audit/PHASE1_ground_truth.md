# CR143 Phase 1 — Ground truth

Not findings. This is the map Phase 2 walks: what the model is actually sent, what reads its reply,
what supplies the data each prompt claims, and what scaffolding exists only because the model
misbehaves. Nothing here adjudicates a defect — every "gap" noted is a *state*, to be verified and
attributed in Phase 2.

Generated 2026-08-08 at `3f4d33d2`. Corpus artifacts in [`assembled/`](assembled/).

---

## 1a. The assembled corpus — and the proof it is faithful

`backend/scripts/dump_assembled_prompts.py` calls the production builders and writes what they
return. **38 prompts** — 13 agents across the surfaces each one actually has (the Concierge has no
Room or 1-on-1 surface, which is why those two are 12 and not 13):

| Surface | Prompts | Total chars | Largest |
|---|---:|---:|---|
| Room | 12 | 115,420 | portfolio_manager, 12,759 |
| 1-on-1 | 12 | 64,339 | portfolio_manager, 7,564 |
| Concierge | 1 | 60,415 | — (348-lesson catalogue) |
| Brief Your Agent | 13 | 39,162 | concierge, 4,076 |
| **Total** | **38** | **279,336** | |

**Faithfulness — the CR143 acceptance gate — PASSES.** `--verify` diffs the reconstruction against
the 5 most recent real `room_pm` prompts in melehost's `llm_audit`:

```
PASS — 5/5 samples: same layers, same order, every char of difference attributed.
```

Marker order is identical in all 5 (grounding → base → holdings → safety floor → Room block → fact
sheet → mandate → transcript → verdict format), and the 8.8k–11.6k char size gap attributes almost
entirely to the transcript the dump deliberately leaves empty. Unattributed residual: **−26 to −31
chars** against a ±64 tolerance.

Two things worth recording from the dump itself:

- **The Room prompt is ~12.8k chars before a single word of debate.** By the time the PM speaks it is
  ~23k. The base `.md` file is 2,332 chars of that — **18% of the PM's pre-transcript prompt, 10% of
  its real one.** Every prior "agent prompt review" in this project read only that 18%.
- Running the dump without `USE_REAL_MARKET_DATA=true` renders **every numeric field as
  `unavailable`** — correct CR104 behaviour, and a reminder that a Mac-local read of the fact sheet
  shows an empty one. Alpha's ships 22 live fields.

---

## 1b. Parser map — what reads the model's reply

`failure_patterns` P4: *a prompt and the parser that reads its output are one contract.* Every
output-shaping instruction in the assembled prompts, and its consumer.

| Instruction (where it lives) | Consumer | Failure mode |
|---|---|---|
| `_PM_VERDICT_FORMAT` — "ENTIRE reply must be one JSON object", `action` ∈ {APPROVE, PASS} (`room_prompts.py:178-208`) | `_parse_pm_verdict` (`room_runner.py:945`) | Unparseable → `_reformat_pm_response` retry (`:3436`), then **fail-safe to PASS**. DEF058/DEF059. |
| Same, action vocabulary | `_normalize_pm_action` (`:872`) + `_PM_ACTION_SYNONYMS` (`:854`) — strips to `[^A-Z]`, maps MODIFY-forms onto APPROVE | Absorbs the banned vocabulary the prompt forbids. Deliberate (CR105 Amdt 1). |
| Same, affirmative vs negative | `_AFFIRMATIVE_ACTION_TOKENS` / `_NEGATION_ACTION_TOKENS` (`:866-867`), `_RAW_ACTION_RE` (`:890`) | Out-of-enum action → negation wins. |
| PM narration must be substantive | `_PM_NO_RATIONALE` (`:937`) | DEF232 — a 19-char reason shipped with a sized APPROVE. |
| `trader.md`'s `Entry:/Stop:/Target:/Size:` ticket block | `_LEVEL_PATTERNS` (`:1118-1123`) — whole-word label, price within a 15-char digit-free gap | **Load-bearing: CR105 explicitly refused to rescope this block because the parser reads its labels.** |
| Any narrated R:R (Trader, Market Analyst, PM) | `_extract_stated_rr` (`:1066`), `_RR_CLAIM_RE` (`:1129`), `_annotate_rr_against_levels` (`:1147`) | Rewrites the ratio to AMI's computed one; **flag-only, never vetoes** (DEF059). CR046. |
| PM directional instructions ("reclaim $X") | `_DIRECTIONAL_CLAIMS` (`:1229`) → `_DIRECTION_CLAIM_RES` (`:1292`) → `_direction_contradictions` (`:1327`), called at `:1385` | DEF231→DEF234, four fixes. Compares one parsed level against the structured `last_close`. Precision-biased: "retest" deliberately absent. |
| `_STANCE_FORMAT` — leading `[STANCE: … CONVICTION: … HEADLINE: …]` (`room_prompts.py:264-277`) | `parse_stance_envelope` (`:1478`), applied `:3187`; `_STANCE_LINE_RE`/`_STANCE_TAIL_RE`/three field REs (`:1443-1460`) | Absent envelope → null stance, prose untouched. DEF147 moved it leading. |
| Length budget (`_LENGTH_GUIDE` / `_AGENT_MAX_TOKENS`) | `_mark_if_truncated` (`:1564`), applied `:3193`; `_TRUNCATION_MARK` (`:1557`) | Provider `length` stop → `[AMI: …incomplete]`. DEF125. |
| `_PROSE_FORMAT` — bold, no headings/tables/fences | **no consumer** | Soft-only. Rendered as Markdown; a violation degrades the display, nothing parses it. |

**Instructions with no consumer** — soft-only, worth naming because P2 says these are wishes, not
controls: `_PROSE_FORMAT`; every `## You DO NOT` bullet in all 13 base prompts; the "use ONLY numbers
from the data block" line in `room_addition`; the grounding directive itself (`llm_gateway.py:96`,
explicitly documented as *"a SOFT control — prompt instructions are ~30% effective"*).

Note the asymmetry Phase 2 should test: **every hard parser sits on the PM and the Trader.** The four
analysts, three researchers and three risk debators have exactly one machine-read field between them
(the stance envelope), and it is nullable by design.

---

## 1c. Supplier map — what backs each "## Inputs" claim

Per-field provenance measured live for AAPL, 2026-08-08 (`assembled/_profile.json`): **22 fields
`live`, 1 `unavailable`**.

| Agent | Prompt claims | Supplier | State |
|---|---|---|---|
| Fundamentals | P/E trailing **and forward**, P/S, EV/EBITDA, PEG (+basis), FCF yield, rev growth, margin, net cash, 52w, sector, dividend, consensus rating+target, next-earnings EPS | `fundamentals.py:163-277` → `_format_profile` | all `live`; forward P/E present post-DEF233 |
| Fundamentals | "Not available at all: full financial statements"; "buybacks and M&A **not available**" | — | correctly disclaimed, rendered as *"buybacks/M&A: not available, not claimed"* |
| Market Analyst | RSI(14), 20/50-day MA trend, volume vs 20-day, 50-day range + position in it, last close | `technicals.py` → `_format_profile` | `live`; DEF227/228 fixed trend direction + current price |
| Market Analyst | "No MACD, MA-crossover, Bollinger — do not cite them"; "no intraday" | — | true negative; `twelve_agents.md` still contradicts it (CR105 item 5) |
| News Analyst | headlines, publisher, recency | `news_context.py` (yfinance) | `live` |
| News Analyst | Alpha Vantage per-article sentiment tag, *"where configured"* | `news_context.py:168` gated on `settings.alpha_vantage_api_key` | **key absent from melehost `.env`** — the conditional is permanently false on Alpha |
| Social Analyst | Reddit aggregate sentiment, *"where configured"* | `social_context.py` | `field_state.social = unavailable`; no Reddit keys in melehost `.env`. **DEF063, open** |
| Bull / Bear | Decision Journal history for this ticker | `build_journal_context_block(user_id, ticker, plan)`, Room `journal_note` (`room_prompts.py:381-385`) | supplied, Bull/Bear only, plan-gated |
| Bull / Bear / Research Mgr | — | `researcher_cap_note` injects the enforced single-name cap (CR055) | supplied |
| Trader | RM synthesis, risk debators, portfolio, remaining drawdown capacity | transcript + `_drawdown_snapshot_line` + holdings block | supplied |
| Risk debators | mandate, `max_drawdown_pct`, derived contribution | `_drawdown_snapshot_line` (RISK/VERDICT only, DEF066) | supplied |
| Conservative | *"current drawdown, and any recent loss patterns"* | — | **neither supplied.** The prompt carries the 30% *cap* and the cooldown *rule* (1.0h), not the user's actual drawdown or loss history |
| PM | *"user's current portfolio state + remaining drawdown"* | holdings block + `_format_sector_allocation` (PM-only, CR026) | portfolio supplied; **"current drawdown" not supplied** |
| PM | full mandate, single-name cap | overlay + `render_safety_floor_block` (`[[CAP]]` from the same resolver the check enforces) | supplied, shown == enforced |
| Concierge | 348-lesson catalogue with group codes | `lessons_service.all_meta()` → static head (CR077) | supplied; 13,651 est. tokens |
| Concierge | journal, unlocked agents, unlock paths | `_format_journal` / `_format_unlocked` / `_format_unlock_paths` | supplied |

`current drawdown` is requested in **3 places across 2 agents** and supplied by nothing — the only
claim in the map with no supplier at all. Phase 2 attributes it.

---

## 1d. Scaffolding inventory — and what it currently absorbs

Every mechanism that exists *only* because the model misbehaves, with the rate it absorbs **on the
current prompt epoch** (after 2026-08-07 12:00; n = 18 convenes / 198 prose turns / 18 PM verdicts).

| Scaffold | Built for | Historical rate | Current epoch |
|---|---|---|---|
| `_reformat_pm_response` + `_PM_REFORMAT_SYSTEM` (`:3411`) | DEF058 unparseable verdict | 18.4% pooled 30d; 68.2% on 2026-07-30; 28.1% on 07-19 | **0 / 18** |
| `_PM_ACTION_SYNONYMS` + `_normalize_pm_action` | DEF067 MODIFY-form vocabulary | 90% → 31.7% (CR105, n=161) | **0 / 18** |
| `parse_stance_envelope` null-stance gutter | DEF147 lost envelope | 27% missing at ship | **10 / 198 = 5.1%** |
| `_mark_if_truncated` + `_AGENT_MAX_TOKENS` | DEF125 mid-sentence truncation | 66% of RM turns pre-fix | **0 / 198** |
| `_annotate_rr_against_levels` | DEF095 unverified R:R | never rate-measured | not measured — Phase 3 |
| `_direction_contradictions` | DEF231, 4 fixes to DEF234 | 2 instances in one afternoon | not measured — Phase 3 |
| Grounding directive (soft) | CR056 assumed data | ~30% effective (CR038) | **not measured** — the CR037/CR038 guard P2 records as still missing |
| `MockProvider._CANNED` / `_TEMPLATES` | DEF059 LLM outage | — | 0 empty responses / 198 |

**The headline Phase 1 result.** Four of the six measurable scaffolds absorb nothing at all on the
current epoch. The premise CR143 was filed on — *the system is scaffolding around a model that cannot
follow instructions* — is materially weaker than the historical record suggested, and the 18.4%
figure in the original filing was my own pooling error (corrected in the CR doc).

Two caveats keep this from being the opposite conclusion:

1. **n = 18 convenes cannot distinguish "fixed" from "rare."** A failure at 5% needs ~60 convenes to
   show up once with any confidence. Phase 4a's ~30-ticker batch is what settles it.
2. **The one class that never had a guard is still unmeasured.** CR037/CR038's unhedged assertion on
   synthetic or absent data (~70%) is the largest claimed failure rate in the project and the only
   one with no detector. Building that detector is Phase 3's real deliverable — and note that
   `field_state` now marks exactly one field `unavailable` (social), which makes the measurement
   tractable for the first time.

The model arm (Phase 4b) is **not** justified by the historical table. It waits on 3 and 4a.

---

## What Phase 2 inherits

- Read `assembled/*.txt`, not `content/agents/*.md`. The base file is 10–18% of the PM's real prompt.
- Five candidates surfaced incidentally and are **unverified**: the PM's `Verdict:
  APPROVE|REJECT|MODIFY-AND-APPROVE` block vs `_PM_VERDICT_FORMAT` (CR105 kept this deliberately —
  `test_room_prompt_parity.py:68` asserts `MODIFY` is present); `market_analyst.md` demanding entry/
  target/stop/R:R from an agent that does not size; `conservative_debator.md`'s unsupplied "current
  drawdown / recent loss patterns"; the permanently-false "where configured" conditionals in the News
  and Social prompts; and `twelve_agents.md:52` still listing MACD/Bollinger against the prompt that
  forbids citing them.
- Every one gets a supplier check, a parser check, and an attribution tag before it becomes a finding.
