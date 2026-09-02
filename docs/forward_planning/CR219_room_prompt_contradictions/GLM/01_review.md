# CR219 — GLM review of the findings and the three reviewer packages

TRACK: K · ROLE: GLM · INSTANCE: - · Session tag: AT:K2 · Date: 2026-09-02

Reviewer scope per Saiful: review and improve the plan for the prompt-enhancement
enhancement. The aim: a set of prompts that is the best at evaluating a ticker, giving
the user an answer grounded in their risk profile and constraints, with the deliberation
transparent. Everything collected is in this folder; the three prior reviewer packages
(`kimi/`, `antigravity/`, `fable/`) are inputs to this review, not alternatives to
supersede wholesale.

---

## 1. Verdict on the investigation

Sound. I re-verified the load-bearing claims in source rather than trusting the doc:

| Claim | Result |
|---|---|
| `analysis/verify_citations.py` | exit 0 — all citations resolve |
| `evidence/rendered/fundamentals_analyst.txt` | both halves of the contradiction in one file: L22 "What you do **not** have is a margin *trend*" and L59 "There is still no margin *trend* on the sheet" vs L128 `Margin trend, YoY (LIVE): gross +1234bps…` |
| `pm_self_consistency_samples` default | **5** (`config.py:751`, CR214) — the CR doc's "defaults to 1" (arms section) is **stale**; kimi's correction is right, fable's `05` doc still repeats the stale figure |
| `enable_thinking: False` (`llm_gateway.py:1021`) | applies **only to the DashScope provider**; the vLLM path sends nothing — fable's finding that thinking is off on the live model is confirmed |
| `trader_block_regex` "uncommitted hunk" | **landed** via the CR210 commit `49380813` ("WAIT-branch Size line") — the CR doc's "uncommitted" is stale in the other direction: the Size half is fixed at HEAD, the Stop half is not |
| #13/#14 at HEAD | `room_prompts.py:1225-1238` already renders the per-role "AMI computed this" drawdown line from `agent_size_pct`; the equality carve-out is gone. The residual defect is the **overlay** (`_aggressive_block`, "Push for full mandate-allowed sizing") naming a size the snapshot didn't compute for — kimi's read is right |
| `content/agents/trader.md` | confirmed: `Stop:` renders unconditionally in the output template; `## You DO NOT` says "Skip the stop-loss" with no WAIT/HOLD carve-out. The #12 fix belongs in the persona |
| `_AGENT_LANES` | Class D confirmed — only the four analysts are lane-gated |

The evidence discipline in this folder is above the repo's bar. The findings stand.
**What needs work is the plan** — and the three reviewer packages disagree with each
other in places that matter, which is what §2 settles.

---

## 2. The three reviewer packages — where they agree, where they conflict

Three independent reviews exist. Reading them against each other:

### Agreed by all three (safe to build without further debate)

- The 17 findings are real; Class A's measured cost (24.2% vs 95.5% on adjacent lines of
  identical sheets) is the strongest datum in the folder.
- The guard gap is real: negative claims are presence-checked, never truth-checked, and
  the scan window (`## Inputs` → `## Output`) misses `## Output style` and `## Voice`,
  where findings 2, 6, 7 and 8 live.
- The free data additions (interest coverage, capex, buyback pacing) are CR218's exact
  pattern — zero network cost, bytes already fetched behind the 6h TTL.
- #15/#16 (overlay demands `earnings revisions`, `surprise history`, `guidance` — none
  fetched anywhere) are live for every short/medium-horizon user, and CR146 deleted four
  demands of exactly this shape from the market-analyst block with a measured 0/18
  justification.
- `primary_goal` is printed and inert — the largest single lever on the stated aim after
  the data.

### Conflicts, now resolved by Saiful's rulings

| Fork | kimi | antigravity | fable | Ruling |
|---|---|---|---|---|
| Fix mechanism | hand-fix + truth-checking guard | static "Dynamic Data Contract" block in all 13 personas | **generated** data-boundary block from the renderer | **R1: hand-fix + guard** |
| `primary_goal` | wire into overlays (D4) | wire as weighted guidance, no hard PM gates | (left open) | **R2: wire as weighted guidance** — the two "wire" votes agree on the shape |
| Class D | name + numbers rule (D1) | (not addressed) | acknowledge, don't restrict | **R3: name + numbers rule** |
| Data scope | all in CR219 (D6) | all in CR219 | one CR, free fields emphasised | **R4: all in CR219** — unanimous anyway |
| Thinking mode | (not addressed) | (not addressed) | measured experiment, PM only | **R5: in CR219, measured** |

### Fact conflicts — resolved in kimi's favour

1. **PM sampling default.** The CR doc's arms section and fable's `05` both say
   `pm_self_consistency_samples` "defaults to 1". It defaults to **5** since CR214
   (`config.py:751`, forwarded in `docker-compose.yml:407`). Kimi's correction is right.
   Consequence: production verdicts are already 5-way votes; the ~19.7% flip rate is a
   *harness* property (single-draw PM in `convene_gemini.py`), not a product property.
   The arms' "verdict column is not interpretable" conclusion stands; its stated cause
   should be corrected in the CR doc.
2. **The `trader_block_regex` hunk.** The CR doc says "uncommitted"; it landed in the
   CR210 commit `49380813`. Kimi reviewed against HEAD with the hunk present and got the
   substance right either way: the regex deliberately keeps Entry/Target/Stop out of the
   HOLD/WAIT branch, and the stale half is `trader.md`. The #12 fix belongs in the
   persona, not the regex.

### Where each package is weakest (and this review fixes)

- **kimi**: no target-state description — the plan says what to change, never what the
  prompt set should *look like* when done. `03_target_prompt_set.md` fills that.
- **antigravity**: the static contract block is hand-written, so it drifts exactly like
  the current `## Inputs` did — the very bug under investigation. Its per-finding
  rewrites are also careless in places (e.g. telling the social analyst it has a
  *sentiment* baseline it does not have — trading one false denial for one false claim).
- **fable**: the generated block is the architecturally superior idea that Saiful
  declined — but its **collision-marker** mechanism is worth stealing into the guard
  design (§4, item 2). Its `05` doc also still carries the stale "defaults to 1".

---

## 3. Assessment by finding class (post-ruling)

### Class A — 7 false denials to rewrite, one caution

Findings 1–7 are exact and verified. #8 (social media) is genuinely weaker, as the doc
says: the persona restricts *sentiment* elevation, the sheet supplies a *mention* trend.
The rewrite must name exactly what the mention trend does and does not baseline —
antigravity's proposed rewrite ("sentiment score, and mention trend over the available
baseline window") fails this and must not be used. The correct shape: "the sheet gives a
*mention* trend over 33d; you have no historical *sentiment* baseline — do not say
sentiment is elevated relative to normal."

The three true denials (no peer-basket P/E, no MACD/Bollinger, no Twitter/X) stay.

### Class B — #12 in the persona; #13/#14 is an overlay defect

- **#10 (Bull conviction)**: partially a false positive — `_build_stance_format` governs
  the stance line, the persona's "End with your CONVICTION" governs the prose. Fix by
  disambiguating vocabulary, not by deleting either instruction.
- **#11 (Bull date-pairing)**: bound the rule to the consensus-target line it was
  written about.
- **#12 (Trader WAIT vs mandatory stop)**: fix in `trader.md` — the output template gets
  a WAIT/HOLD branch (`Stop: N/A (no active order)`), and `## You DO NOT` gets the
  carve-out ("Skip the stop-loss on a BUY"). The landed CR210 regex and this persona fix
  are one logical change.
- **#13/#14 (Risk Officer drawdown)**: at HEAD the snapshot already computes the per-role
  line from `agent_size_pct` — the residual defect is the overlay's "Push for full
  mandate-allowed sizing" naming a size the snapshot didn't compute for. One diagnostic
  convene on the cached CAT profile (Phase 0) settles it before any rewrite. Do not
  rewrite both blind.

### Class C — back the demands, don't delete (R4)

Per R4 the earnings-revisions / surprise-history / guidance demands are backed with real
fetches (Phase 3). Until those fields land, the demand text must be **softened** in
Phase 1 — an unbacked demand in the interim is the live Class-C defect. This is the
sequencing rule from kimi's review, kept: contradiction fixes land first; adding fields
while personas still deny existing ones is how CR219 happened.

### Class D — name + numbers rule (R3)

The 8 downstream briefs get a sheet acknowledgment plus "quote the sheet's figures; do
not re-derive" — the DEF066/DEF241 history shows what happens when agents recompute
numbers in prose. Before/after measurement in Phase 2.

### Class E — lane-gate the 1-on-1 surface

`build_live_data_block()` hands the Fundamentals Analyst `Day move`, `Primary trend`,
`Beta`, `Short interest` and `Relative strength` while its persona says "You DO NOT
predict short-term price movements." Room lanes gate those away; on 1-on-1 nothing does.
Cheap fix, real confusion surface.

---

## 4. The guard design — hand-fix + guard (R1), with fable's collision markers stolen in

R1 keeps personas as the single written artifact and the guard as the drift-catcher.
Two additions to kimi's guard spec:

1. **Whole-file scan, truth-checked.** Every negative availability claim in every
   `content/agents/*.md` must resolve TRUE against the rendered sheet — scanning the
   whole persona, not `## Inputs` alone. Fixtures: a false denial planted in `## Voice`
   must go red; a deliberate field addition that contradicts a claim must go red.
2. **Collision markers on the absences.** For each "not available" claim the guard
   knows about, record the substrings that, if they ever appear in a fully-populated
   rendered sheet, prove the denial false. When a future CR ships a field (say,
   historical median multiples), the marker appears in the rendered sheet and the build
   fails until the persona line is updated. This is the forward-in-time guarantee — the
   exact inversion of today's bug, and the one piece of fable's generated-block design
   that R1 does not preclude.
3. **Overlay demands mapped to field_state keys.** #15/#16 are negative-truth failures
   in *code*, not personas. An authored mapping of overlay demands → field_state keys,
   same pattern as `_CLAIMED_REAL_INPUTS`, closes it.
4. **Accept and document the guard's own limit**: it is an authored phrase↔mechanism
   mapping, so a brand-new denial phrase no one mapped stays invisible. Say it in the
   test docstring so CR219's own "snapshot vs moving target" lesson isn't re-learned.

---

## 5. What the plan is missing beyond the reviews

1. **Correct the two stale lines in the CR doc itself** (arms section: "defaults to 1"
   → 5 via CR214; "uncommitted hunk" → landed via CR210 `49380813`). A reviewer who
   trusts the doc's arms section will mis-model production verdicts.
2. **The benchmark harness must mirror the production 5-way vote** (R5, and kimi's D3
   which R5 subsumes): reuse the production sampling/voting path rather than single
   draws, so pre/post comparisons measure real product behaviour. 4–5 cached profiles
   spanning archetypes (mega-cap cyclical = existing CAT, high-growth, dividend payer,
   distressed, one halal-screened name), rubric scored per turn.
3. **PM-only thinking experiment needs budget re-derivation before it runs** (R5).
   Reasoning tokens count inside `completion_tokens` — CR130's exact failure mode if
   unbudgeted — and CR210's `_CHARS_PER_TOKEN_WORST_CASE` test must be re-derived for
   the visible portion. The experiment is measured (corpus replay, thinking on vs off),
   never a flip-the-switch.
4. **Two dispositions now**: file a DEF for the PM breaking its JSON-only contract under
   instruction pressure (DEF067 lost ~13% of verdicts to parser fragility — an
   obedient-to-appendix gatekeeper is a real fragility); and sweep the 26 unswept
   prompts (concierge, Brief Your Agent) by extending `dump_sheets.py` +
   `assemble_room.py`, not by writing new scripts.
5. **Sequencing is the safety property**: Phase 1 (contradiction fixes + guard) must
   exist before Phase 3 adds a single field, and each new field ships with its persona
   line and guard entries in the same commit.

---

## 6. Limits of this review

- I did not re-run a convene; Class B is assessed from source + the stored transcripts.
  Phase 0 exists for exactly this.
- I verified the four analyst personas, `trader.md`, the guard, the overlay builder, the
  drawdown machinery, and the lane/sampling config firsthand; the 8 downstream personas I
  read only as embedded in `evidence/convene_CAT_long_wealth/convene.json`.
- The rubric in the benchmark is a proposal, not a validated instrument; its model-judged
  halves need a calibration pass against the banked corpus before pre/post numbers are
  trusted.
