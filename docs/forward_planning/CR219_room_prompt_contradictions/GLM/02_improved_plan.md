# CR219 — improved plan (GLM)

TRACK: K · ROLE: GLM · INSTANCE: - · Session tag: AT:K2 · Date: 2026-09-02

Kimi's skeleton with Saiful's five rulings folded in (R1–R5, see [`README.md`](README.md)),
fable's collision-marker idea stolen into the guard design, and the two stale facts in the
CR doc corrected. Every phase names its deliverable, its commit shape, and its acceptance.

---

## Phase 0 — diagnostics before edits (½ day)

1. **One diagnostic convene on the cached CAT profile at HEAD** to settle #13/#14: the
   snapshot already computes the per-role drawdown line from `agent_size_pct`
   (`room_prompts.py:1225-1238`), so the question is whether the Aggressive RO still
   quotes a 2.5% figure while pushing 3.0% — i.e. whether the residual defect is the
   overlay's "Push for full mandate-allowed sizing" naming a size the snapshot didn't
   compute for. Do not rewrite both blind.
2. **Correct the two stale lines in the CR doc** (docs-only commit):
   - arms section: "`pm_self_consistency_samples` defaults to **1**" → defaults to **5**
     since CR214 (`config.py:751`, `docker-compose.yml:407`); the ~19.7% flip rate is a
     harness property, not a product property.
   - "`An uncommitted `trader_block_regex` hunk in `room_prompts.py`" → landed via the
     CR210 commit `49380813` (WAIT-branch Size line); the Stop half remains open.
3. **Dispositions**: file a DEF for the PM breaking its JSON-only contract under
   instruction pressure (Open item 3 of the CR; DEF067 lost ~13% of verdicts to parser
   fragility — an obedient-to-appendix gatekeeper is a real fragility, not a curiosity).

## Phase 1 — contradiction fixes + guard v2, one commit set (R1)

1. **Rewrite the 7 false Class-A denials** in the four analyst personas; keep the 3 true
   ones. #8 per the caution in [`01_review.md`](01_review.md) §3 — name exactly what the
   mention trend does and does not baseline; never grant a sentiment baseline that does
   not exist.
2. **Disambiguate #10's "conviction" collision in vocabulary** ("End your prose with what
   would raise or lower your conviction"); fix #11 by bounding the date-pairing rule to
   the consensus-target line it was written about.
3. **Fix #12 in `trader.md`**: the output template gets a WAIT/HOLD branch
   (`Entry: N/A | Target: N/A | Stop: N/A (no active order)`), and `## You DO NOT` gets
   the carve-out ("Skip the stop-loss on a BUY"). The landed CR210 regex and this persona
   fix are one logical change — land them together.
4. **Resolve #13/#14 per the Phase-0 finding** — expected shape: the overlay stops
   naming a size the snapshot didn't compute for; the "AMI computed this" line stays.
5. **#15/#16 — soften the demand text now** (R4 backs them with real fetches in Phase 3;
   until those fields land, an unbacked demand is the live Class-C defect).
6. **Guard v2 in the same commit** (R1, with fable's collision markers):
   - every negative claim truth-checked against the rendered sheet, whole-file scan
     (fixture: false denial planted in `## Voice` must go red);
   - collision markers on each known absence — a future field addition that contradicts
     a persona line fails the build until the line is updated;
   - overlay demands mapped to field_state keys (same pattern as `_CLAIMED_REAL_INPUTS`);
   - the guard's authored-mapping limit documented in the test docstring.
7. **Wire `primary_goal` into the overlays as weighted guidance** (R2). Goal-specific
   lines per agent — `income_now` shifts the fundamentals overlay toward dividend cover
   and capital-return sustainability (the CR218 fields), `capital_preservation` toward
   balance-sheet strength and sizing, `learning_to_trade` toward explanation. The PM
   keeps holistic gatekeeping — **no hard-coded filter gates**. Guard entries for the
   new branches.

**Acceptance**: every negative claim in every `content/agents/*.md` resolves against the
rendered sheet; the guard fails red on a contradicting field addition and on a false
denial in `## Voice`, both demonstrated with deliberate fixtures; `pytest
backend/tests/unit/ -q` green including `test_cr105_*`, `test_prompt_data_parity.py`,
`test_config_compose_parity.py`.

## Phase 2 — surfaces

1. **Class D implementation (R3)**: the 8 downstream briefs name the sheet + the numbers
   rule ("quote the sheet's figures; do not re-derive"), with before/after measurement —
   one convene pair per arm profile, PM vote mirroring production's 5-way path.
2. **Class E**: lane-gate `build_live_data_block()` on the 1-on-1 surface.
3. **Sweep concierge + Brief Your Agent** (26 prompts) with the existing scripts,
   extended — `dump_sheets.py` + `assemble_room.py` already exist for the Room surface.

## Phase 3 — data additions (R4: all in CR219; each its own commit, personas + guard entries included)

In priority order from the arms' 102 requests, weighted by impact evidence:

1. **Interest coverage, capex, buyback pacing** (free — CR218 pattern; bytes already
   fetched behind the 6h TTL). The #1 request: 21× from 9 of 12 agents.
2. **ATR / volatility for stop sizing** (computable from fetched daily bars). The Trader
   must set a stop on every BUY with no volatility measure of any kind.
3. **Historical median multiples** (5/10-yr P/E, EV/EBITDA) — fetch + cache. The only
   gap with demonstrated verdict impact (the PM's own words on CAT).
4. **Earnings revisions, surprise history, guidance** — fetch + cache; backs #15/#16 and
   removes the interim softening from Phase 1 item 5.
5. **Debt split industrial vs captive finance** from SEC segment filings. Scope to
   captive-finance-heavy names; if the filings parse proves unreliable, the fallback is a
   documented limitation, not silent omission.

**Sequencing rule**: Phase 1 must exist before this phase adds a single field, and each
new field ships with its persona line and guard entries in the same commit — adding
fields while personas still deny existing ones is how CR219 happened.

## Phase 4 — benchmark + thinking experiment (R5)

1. **Build the benchmark harness**: 4–5 cached profiles spanning archetypes (mega-cap
   cyclical = existing CAT, high-growth, dividend payer, distressed, one halal-screened
   name), run through the production prompt assembly; the PM verdict drawn through the
   **production 5-way self-consistency vote** so a verdict is a majority, not a single
   draw; a rubric scored per turn (mechanical where possible, model-judged where not):
   grounding, mandate adherence, lane discipline, contradiction-free output, JSON
   contract compliance.
2. **PM-only thinking experiment, measured**: enable thinking for the PM only via the
   gateway's quirks hook if this vLLM build honors it, serve-side otherwise; **re-derive
   the PM decode budget first** (reasoning tokens count inside `completion_tokens` —
   CR130's failure mode if unbudgeted — and CR210's `_CHARS_PER_TOKEN_WORST_CASE` test
   must be re-derived for the visible portion); replay the banked corpus with thinking
   on vs off. If it wins, extend to the Research Manager; the eleven formulaic turns
   likely never need it. Never Room-wide unmeasured.
3. **Pre/post run**: success = citation recovery on post-fix Alpha traffic (the banked
   corpus is the before-arm and already exists) **and** rubric improvement on the fixed
   profiles with verdict stability measured through the same vote production uses.

## Decision register — resolved

| # | Decision | Ruling | Phase |
|---|---|---|---|
| R1 | Fix mechanism | **Hand-fix + guard** (with collision markers) | 1 |
| R2 | `primary_goal` | **Wire as weighted guidance**, no hard PM gates | 1 |
| R3 | Class D | **Name + numbers rule** | 2 |
| R4 | Data scope | **All in CR219** | 3 |
| R5 | Thinking mode | **In CR219, measured** (PM only, budget re-derived first) | 4 |

Supersessions: R1 replaces fable's resolved decision #1 (generated availability section);
R3 replaces fable's #3 (acknowledge, don't restrict). Kimi's D1–D6 are confirmed by
R2–R5. The CR doc's two stale facts are corrected in Phase 0 item 2.
