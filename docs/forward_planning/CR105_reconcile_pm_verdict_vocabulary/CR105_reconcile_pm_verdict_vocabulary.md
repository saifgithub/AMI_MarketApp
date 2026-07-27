# CR105 — Agent-prompt copy drift: remove false statements, keep the parser contracts

**Filed:** 2026-07-27 · **Status:** proposed · **Decision:** Saiful, 2026-07-27 — *"create a CR"*, following Kimi's (track K) read-only assessment of the 13 base prompts in `content/agents/`.
**Amended:** 2026-07-28 (AT:R59, room-quality) — *"modify CR105 to deliver what is feasible and logical."* Scope cut from 7 items to 5, two items dropped, one item added, one split out as a defect. **Read Amendment 1 before the original Scope below it.**

---

## Amendment 1 (2026-07-28) — what this CR now delivers

The original scope was written from a read of the prompt files. Every item was then checked
against **the code that reads the model's output**. Two of the four prompt edits turned out to
sit on a live parser contract, one item was already tried and measured, and one item is a
user-facing defect rather than copy drift.

### Verification of each original finding

| # | Original claim | Verified? | Disposition |
|---|---|---|---|
| 1 | PM verdict vocabulary inconsistent across 4 layers | **Partly.** Layers do disagree, but the divergence is deliberate and load-bearing (see below). The 1-on-1 half is harmless: `_normalize_pm_action`/`_parse_pm_verdict` exist **only** in `room_runner.py`, so nothing parses a PM verdict outside the Room. | **Prompt half DROPPED. Doc half KEPT** (`safety_floor.md` stale JSON). |
| 2 | Trader ticket block / RM 3-part conflict with `_PROSE_FORMAT` | **Yes, but the ticket block is load-bearing.** DEF095's coherence rewriter extracts the Trader's levels from the narration by whole-word label — `_LEVEL_PATTERNS` (`room_runner.py:931-936`) matches `entry`/`stop`/`target`/`size`. Those labels come from `trader.md`'s ticket block. Rescoping it to 1-on-1 weakens a structural control. | **RESHAPED** — RM only; Trader left alone. |
| 3 | Unfulfillable prompt-as-control instructions | **Yes.** `portfolio_manager.md:26` ("Run the deterministic compliance check") + `:34` ("Always log your reasoning to the Decision Journal"); RM overlay mandate-version tag. | **KEPT.** |
| 4 | Bare `50%` literal vs `SINGLE_NAME_ABSOLUTE_CAP_PCT` | **Yes, and it is currently *correct*** — `sizing.py:26` is `50.0`. Latent drift, not a live defect. | **KEPT + guard extended.** |
| 5 | Stale design docs | **Yes.** `twelve_agents.md:52` lists Bollinger/MACD as Market Analyst tools while `market_analyst.md` explicitly instructs *"No MACD … or Bollinger Bands are computed anywhere in this app — do not cite them"*. `:211` still says "vLLM Gemma 4 31B" (it is `ami-llm`, Qwen). | **KEPT.** |
| 6 | Concierge capability claims unverified | **Verified — and they are unwired.** `backend/app` has no scheduler/cron/sender and zero `mute` symbols; `daily_briefing` is a mandate field echoed at onboarding with nothing to deliver it; the Concierge has no tool layer. Worse than stated: the claim is also in `overlay_generator.py:484-485`, i.e. the **live injected prompt**. | **SPLIT OUT → DEF129.** User-facing, CR023 class, not copy drift. |
| 7 | No structural alignment guard between analyst "Inputs" claims and `_format_profile` | **Yes — and it had no Scope entry.** The only item that prevents recurrence rather than cleaning one instance. CR104 made it cheap: `profile["field_state"]` is now the single per-field provenance mechanism. | **PROMOTED INTO SCOPE** (test-only). |

### Why the PM vocabulary edit is dropped — measured, not argued

The prohibition the original item 1 wants **already exists, one layer closer to the model.**
`_PM_VERDICT_FORMAT` (`room_prompts.py:108-113`), appended last in the assembled prompt, says:

> *"There are exactly two action values: APPROVE and PASS. … Do NOT write 'MODIFY',
> 'MODIFY-AND-APPROVE', or any other value — they are discarded and your verdict is lost."*

That landed with DEF067 (`ea77bc5`, 2026-07-20 01:22 +0300). Live `llm_audit`,
`agent_id='portfolio_manager'`, strictly after that commit (7.8 days, n=161), measured
2026-07-28:

| action emitted | n |
|---|---:|
| `pass` | 101 |
| `approve` | 41 |
| `modifyandapprove` | 13 |
| `modify` | 5 |
| `modifyapprove` | 1 |

**19 of 60 affirmative verdicts (31.7%) still use a MODIFY-form**, with the strongest possible
prohibition immediately in front of them. Down from DEF067's 90%, not gone — CR038's ~30%
compliance figure, reproduced on the PM path.

Consequences for the original item 1:

- Editing `portfolio_manager.md:32,39` is **strictly weaker leverage** than the deployed
  prohibition that is already being ignored 31.7% of the time. Expected payoff: zero.
- All 19 are absorbed in the **first-pass** parse by `_PM_ACTION_SYNONYMS` (`room_runner.py:746`)
  — no reformatter round trip, no loss. There is no measured cost to fix.
- [`failure_patterns.md` P4](../../initial_specs/08_tech/failure_patterns.md) already rules on
  this, with a guard behind it: *"Contradiction between layers is not resolved by prompt wording…
  **Make the parser tolerant of everything any layer offers.**"*
- The original item 6 (a test asserting the base prompt contains **no** `MODIFY-AND-APPROVE`)
  **collides head-on** with the existing DEF067 guard, `test_room_prompt_parity.py:68`:
  ```python
  assert any("MODIFY" in t for t in tokens)
  ```
  Shipping items 1 + 6 as written turns that test red.

### Scope-line correction

The original **"Copy alignment only — no behaviour change"** is false. `content/agents/*.md` **is**
model input; every prompt item changes what the model reads. The acceptance was "new test green +
full pytest green", which is precisely the P4 failure mode: *"green tests, because no test builds
the assembled prompt and checks it against the parser that consumes its output."* Amended
acceptance below requires a post-promotion re-measure for any item that changes an assembled prompt.

---

## Amended Scope (this is what the lane builds)

**Rule for the whole CR: before editing any prompt string, grep for code that reads the model's
output for that string.** Two of the original four failed that check.

1. **Delete unfulfillable instructions** (original 3 — unchanged). Per CR038 the honest fix is
   **deletion, not rewording**; an instruction the model cannot act on is noise in a 12-agent
   prompt budget.
   - `content/agents/portfolio_manager.md:26` — drop "Run the deterministic compliance check" (the
     parenthetical already concedes it happens automatically). Replace step 1 with a statement of
     fact: *"A deterministic compliance check runs on your verdict automatically. You cannot skip
     or override it."*
   - `content/agents/portfolio_manager.md:34` — "Always log your reasoning to the Decision Journal"
     → *"Your verdict and reasoning are logged to the Decision Journal automatically."*
   - RM overlay "tag synthesis with mandate version" → delete (the backend tags).
   - **Parser check:** none of these strings is read by any parser. Safe.

2. **Replace the bare `50%`** (original 4 — unchanged, plus a guard).
   `content/agents/portfolio_manager.md:51` → defer to the floor block ("the single-name cap
   stated in the safety floor below"), removing the literal rather than interpolating it.
   **Extend** `test_safety_floor.py::test_safety_floor_prose_cap_equals_the_enforced_constant`
   (or add a sibling) so the assertion covers the **assembled PM prompt**, not just the floor
   block — i.e. no numeric single-name cap literal may appear anywhere in the PM's prompt other
   than the one interpolated from `SINGLE_NAME_ABSOLUTE_CAP_PCT`.
   **Parser check:** no parser reads this. Safe.

3. **Doc sweep** (original 5 + the doc half of original 1).
   - `docs/initial_specs/02_agents/safety_floor.md` — replace the stale `{"verdict": "REJECT"}`
     JSON with the shape the Room actually parses (`{"action": "APPROVE"|"PASS", …}`), plus one
     line: *REJECT / MODIFY / NO_VERDICT are produced in code, never parsed from the model.*
   - `docs/initial_specs/02_agents/twelve_agents.md:13,52` — remove MACD / Bollinger from the
     Market Analyst tool list; it directly contradicts `market_analyst.md`, which forbids citing
     them. Flag the row as Beta+ intent if the mapping is aspirational.
   - `docs/initial_specs/02_agents/twelve_agents.md:211` — "vLLM Gemma 4 31B" → `ami-llm`
     (`RedHatAI/Qwen3.6-35B-A3B-NVFP4`), per CLAUDE.md's runtime table.
   - `docs/initial_specs/02_agents/mandate_overlays.md:230` — same vocabulary note as
     `safety_floor.md`; do **not** change the overlay code it documents.
   - **Docs only. No prompt bytes change here.**

4. **RM output-structure scoping only** (original 2, reshaped).
   `content/agents/research_manager.md`'s "always 3 parts" → scope to 1-on-1
   ("In 1-on-1 output …; in the Room, follow the format instruction appended at the end").
   **`content/agents/trader.md`'s ticket block is explicitly OUT OF SCOPE** — its
   `Entry:`/`Stop:`/`Target:`/`Size:` labels are what `_LEVEL_PATTERNS` (`room_runner.py:931-936`)
   matches to recompute R:R and rewrite the transcript (DEF095, CR038-structural). Touching it
   weakens a shipped control. If a future lane wants to change it, the change must be measured
   against the level-extraction hit rate first, not shipped on a green suite.

5. **Analyst "Inputs" ↔ provenance alignment guard** (original *Why* item 7, promoted; **test-only,
   no production code**). One test that binds each analyst's declared inputs to what the renderer
   can actually source, so a new capability claim cannot drift in silently the way the Concierge's
   did (DEF129, CR023 class):
   - Derive the sourceable field set from `profile["field_state"]`'s populated keys
     (`room_runner.py:415-548`: the fundamentals fields, `week52`, `technicals`, `next_earnings`,
     `news`, `social`).
   - Assert every data field an analyst's `## Inputs` section claims as *real / live / pulled live*
     maps to one of those keys or to an explicitly-declared not-available line.
   - Assert the reverse for the two already-guarded negative claims (no MACD/Bollinger; no
     Twitter/X/StockTwits/Discord) — same shape as the existing
     `test_def084_halal_flag_copy_guard.py` / `test_def084_overlay_narration_copy_guard.py`.
   - Follows the P4 rule: build the **assembled** prompt, check it against the code that feeds it.

### Explicitly NOT in scope (recorded so it is not reopened)

- **Removing `MODIFY-AND-APPROVE` from `portfolio_manager.md` / `overlay_generator.py`.** Measured
  zero payoff; collides with `test_room_prompt_parity.py:68`. If ever revisited it must ship with
  `_PM_ACTION_SYNONYMS` untouched, that test amended rather than deleted, and a post-promotion
  re-run of the action-distribution query above.
- **A guard asserting the prompt lacks a vocabulary token.** The correct guard is the existing one
  (parser understands everything any layer offers), not its inverse.
- **`trader.md`'s ticket block** — see item 4.
- **The Concierge claims** — split to **DEF129**.

## Amended Acceptance

1. No base prompt or overlay instructs the model to perform an action only the backend can perform
   (items 1) — verified by reading the assembled PM + RM prompts, not the source `.md` alone.
2. No numeric single-name cap literal survives in the assembled PM prompt except the one
   interpolated from `SINGLE_NAME_ABSOLUTE_CAP_PCT`; the extended cap-parity test is **demonstrated
   red** against the pre-fix prompt before it is accepted green.
3. `safety_floor.md`, `twelve_agents.md`, `mandate_overlays.md` state the shipped reality
   (APPROVE/PASS parsed; REJECT/MODIFY/NO_VERDICT code-only; no MACD/Bollinger; `ami-llm`).
4. The analyst-inputs alignment guard is **demonstrated red** against a deliberately-added false
   input claim, then green.
5. `test_room_prompt_parity.py` and `test_safety_floor.py` still pass **unmodified in intent** — if
   either needed editing, that is a signal the CR drifted back into dropped scope.
6. Full `cd backend && .venv/bin/python -m pytest tests/unit/ -q` green.
7. **Because items 1, 2 and 4 change assembled-prompt bytes:** after `/promote-to-alpha`, re-run
   the PM action-distribution query and a PM-verdict parse-failure count over the first ≥50 live
   convenes and confirm no regression vs the 2026-07-28 baseline in Amendment 1. A green suite is
   not sufficient acceptance for a prompt change (P4).

## Governance

- Commit tag `(AT:R<N> CR105)`.
- **No independent audit required.** With the vocabulary edit and the Trader block dropped, nothing
  in this CR touches a parser contract or the safety floor's inputs; items 3 and 5 are docs/tests
  only. If a lane finds itself editing `_PM_ACTION_SYNONYMS`, `_LEVEL_PATTERNS` or
  `test_room_prompt_parity.py`, it has left this scope — stop and re-file.
- Relates to **DEF067 / P4** (the vocabulary contract this CR deliberately leaves alone),
  **DEF095** (the level labels item 4 protects), **CR038** (prompt instructions are not controls),
  **CR046 C-a** (the cap-literal class item 2 closes), **CR104** (`field_state`, which makes item 5
  feasible), **DEF129** (split out of original item 6).

---

## Original filing (2026-07-27, track K) — retained for the record

## Why

A track-K assessment of `content/agents/*.md` against their runtime composition
(`agent_prompts.py` → Room `room_prompts.py` / 1-on-1 `agent_runner.py`) found the prompts
themselves suitable and battle-hardened, but carrying **copy drift across layers** — the exact
CR038 failure class this repo already documented ("contradictory prompt copy degrades
compliance", `room_prompts.py` MINOR 3). The findings, ordered by severity:

1. **PM verdict vocabulary is inconsistent across 4 layers.** Base prompt
   `content/agents/portfolio_manager.md` ("Output format" block) and the PM mandate overlay
   (`backend/app/agents/overlay_generator.py::_portfolio_manager_block`) say
   `APPROVE / REJECT / MODIFY-AND-APPROVE`; the Room runtime instruction
   (`backend/app/services/room_prompts.py::_PM_VERDICT_FORMAT`) accepts JSON `APPROVE | PASS`
   only and explicitly forbids MODIFY/REJECT ("REPLACES the … block described earlier in your
   profile"); the safety-floor block (`backend/app/agents/safety_floor.py::SAFETY_FLOOR_BLOCK`)
   says PASS-on-violation (consistent with Room); the design doc
   `docs/initial_specs/02_agents/safety_floor.md` still shows the stale `{"verdict": "REJECT"}`
   JSON. The Room papers over the drift at runtime, but the 1-on-1 PM path has no such
   reconciliation — and `VerdictAction` (REJECT/MODIFY/NO_VERDICT) is only ever produced
   deterministically, never LLM-parsed.
2. **Base-prompt output structures conflict with the Room prose format.** Trader's labelled
   ticket block (`trader.md`) and Research Manager's "always 3 parts" (`research_manager.md`)
   vs `_PROSE_FORMAT` (thesis + bullets, no headings/tables). Later instruction wins, but the
   conflict is the same CR038 pattern.
3. **Unfulfillable instructions (prompt-as-control, CR038).** PM base/overlay: "Always log your
   reasoning to the Decision Journal" (the model cannot; the backend does). RM overlay: "Tag
   synthesis with mandate version". PM base step 1: "Run the deterministic compliance check"
   (it cannot; the parenthetical says so).
4. **Bare-literal drift risk.** `portfolio_manager.md` hardcodes "50%" single-name cap while
   the floor block interpolates `SINGLE_NAME_ABSOLUTE_CAP_PCT` — the CR046 C-a bug class the
   floor itself already fixed.
5. **Stale design docs.** `safety_floor.md` verdict JSON (finding 1); `twelve_agents.md` lists
   MACD/Bollinger under Market Analyst tools (flagged Beta+, a misread waiting to happen);
   `twelve_agents.md` names "vLLM Gemma 4 31B" vs the `ami-llm` Qwen rebrand.
6. **Unverified capability claims (Concierge).** `concierge.md` claims scheduling and
   mute/promote agents — if unwired, the CR023 fabricated-capability pattern. Verify before
   treating as a defect.
7. **No structural alignment guard** between analysts' "Inputs" claims and `_format_profile`
   fields beyond the two CR023/24 copy-guards; new data-field claims can drift silently.

## Original Scope (SUPERSEDED by Amendment 1)

Copy alignment only — **no behaviour change**.

1. **Reconcile PM verdict vocabulary** — update `portfolio_manager.md` output block +
   `overlay_generator.py::_portfolio_manager_block` + `safety_floor.md` to the APPROVE/PASS
   JSON shape the Room actually parses, with one line noting REJECT/MODIFY/NO_VERDICT are
   code-produced overrides.
2. **Resolve output-structure conflicts** — scope Trader's ticket block and RM's 3-part
   structure to 1-on-1 ("In 1-on-1, output …; in the Room, follow the format instruction
   appended at the end").
3. **Reframe unfulfillable instructions** — "Your verdict and reasoning are logged to the
   Decision Journal automatically" / "a deterministic compliance check runs on your verdict
   automatically"; drop the RM mandate-version tag instruction (the backend tags).
4. **Replace the bare "50%"** in `portfolio_manager.md` with wording deferring to the floor
   block ("the single-name cap stated in the safety floor below").
5. **Doc sweep** — `safety_floor.md` JSON shape, `twelve_agents.md` LLM name.
6. **Copy-guard test** — one test asserting the PM base prompt + overlay contain no
   `MODIFY-AND-APPROVE` / prose-verdict vocabulary (the DEF084 pattern).
7. **Concierge capability wiring check** (read-only) — verify scheduling / mute / promote
   exist; if not, strip the claim or file a DEF.

## Original Acceptance (SUPERSEDED by Amendment 1)

- PM-facing verdict vocabulary is identical in meaning across base prompt, overlay, Room
  instruction, floor block, and `safety_floor.md` — APPROVE/PASS for the LLM,
  REJECT/MODIFY/NO_VERDICT documented as code-only.
- No base prompt instructs the model to perform an action only the backend can perform.
- New copy-guard test green; full `pytest backend/tests/unit/ -q` green.
- Concierge claims verified wired or stripped; DEF filed if stripped.
