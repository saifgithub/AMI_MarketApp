# R43 — DEF draft: the PM breaks its JSON-only contract under instruction pressure

**Status: DRAFT ONLY — not filed.** The ID below is deliberately left as `DEF###`.
Minting it is the Architect's job (single ID-minter rule, CLAUDE.md). This file is
WP08's R43 deliverable: the row-file body ready to paste into
`docs/defect/_registry/DEF###.row.md`, plus the evidence that justifies it.

The *fix* rides the minted DEF, not CR219. R43 closes when the DEF exists.

---

## Row file body (paste into `docs/defect/_registry/DEF###.row.md`)

| DEF### | 2026-09-02 | claude | room | **The Chief Investment Officer appends prose AFTER its closing `}` when the prompt carries any competing "also write X" instruction, and the production extractor then recovers nothing — the verdict is lost and the run fails safe to PASS.** `_PM_VERDICT_FORMAT` (`room_prompts.py:423-426`) states the contract twice over — *"Your ENTIRE reply must be one single JSON object — begin with '{' and end with '}'. Do not write any prose outside the JSON … anything outside it is discarded and your verdict is lost"* — and the model quotes that sentence back verbatim while violating it. **Measured, two independent corpora, both on `qwen3.8-flash-next` (`/models/qwen38-flash-next-nvfp4`):** (1) the CR219 six-arm mandate-variation run — **2 of 6 arms** (`h_short`, `g_learning`) emitted a well-formed leading object followed by 1278 / 1473 trailing characters of `DATA I LACKED:` + `PROMPT CONTRADICTIONS:` sections; `app.services.llm_json.extract_json_object` returns **None** on both, i.e. the production parser loses the verdict outright, while `json.JSONDecoder().raw_decode` recovers the object cleanly from the same bytes. (2) the CR219 harness smoke (`harness/results/CAT_long/run.json`, 2026-09-02, temperature 1.0, `pm_samples=5`) — **1 of 5 independent PM draws** unparseable (`samples_parsed: 4`, `samples_returned: 5`); the failing draw abandoned JSON from the first token and emitted a fabricated tool-use narration (*"Let me pull the latest intelligence on Caterpillar before convening the room."* followed by an invented price block), `finish_reason=stop`, so no truncation guard fires. **Why it matters beyond the parse:** with `pm_self_consistency_samples=5` (CR214 default) a lost draw silently shrinks the vote denominator — the smoke run's `agreement` reads `4/4`, a *unanimous* team, when one of five reads was in fact discarded; and at n=1 a lost draw is a lost verdict, landing on the DEF059 fail-safe PASS with `overridden_from_llm=True`. **Precedent — this is the DEF067 class, third occurrence:** DEF067 measured PM-shape parse loss at ~6.0% (9/150, arm A) after correcting for an invisible leak, against a <2% acceptance bar; DEF058 before it. Each prior fix hardened the *parser* (`_normalize_pm_action`, the one-shot reformatter, `repair_truncated`); none made the contract structural, so the failure recurs whenever a new instruction competes with it. **Candidate fix (for the DEF, not CR219):** CR210's `pm_verdict_schema()` grammar already makes this unrepresentable on vLLM — `room_json_constraints_enabled` gates it and is OFF pending the acceptance-3 re-run; that flag, not another prompt sentence, is the structural control (CR038: prompt instructions are not controls, ~70% ignored under pressure). Second, cheaper leg: `extract_json_object` should fall back to `raw_decode` on a leading object with trailing junk, which recovers both arm failures at zero model cost. Evidence: [CR219 arms](../../CR219_room_prompt_contradictions/evidence/arms/), [harness smoke](../../CR219_room_prompt_contradictions/harness/results/CAT_long/run.json), draft [R43_DEF_draft.md](../../CR219_room_prompt_contradictions/dev_instructions/R43_DEF_draft.md). | open | — | AT:R75 |

---

## Evidence note

### What was measured, and how

Two corpora, both against the live on-prem serve (`root` =
`/models/qwen38-flash-next-nvfp4`, read from `/v1/models`, not the `ami-llm` alias
— CLAUDE.md's model-identity rule).

**Corpus 1 — the six mandate-variation arms** (`evidence/arms/*/convene.json`).
Each arm ran one full convene with a harness addendum asking every agent for two
extra sections (`DATA I LACKED:`, `PROMPT CONTRADICTIONS:`). For the PM that
addendum directly contradicts its JSON-only contract. Replayed through the
production extractor:

| Arm | Leading object | `extract_json_object` | Trailing chars |
|---|---|---|---|
| `h_short` | parses via `raw_decode` | **None** | 1278 |
| `h_medium` | — | OK (`PASS`) | 0 |
| `h_long` | — | OK (`APPROVE`) | 0 |
| `h_very_long` | — | OK (`PASS`) | 0 |
| `g_income_now` | — | OK (`PASS`) | 0 |
| `g_learning` | parses via `raw_decode` | **None** | 1473 |

2 of 6 arms lost. `aggregate_arms.py:10-13` excludes the PM from its contradiction
tally for exactly this reason, and is right to: the *collision* is the harness's,
not production's. What is **not** the harness's is the PM's *response* to a
collision — it chose to break the JSON contract rather than fold the extra sections
into `narration`, and four of the six arms show it knew that was the choice (each
of the four passing arms explicitly narrates the tradeoff inside the JSON, e.g.
*"…placed these sections inside the JSON's narration string to ensure the verdict
remains a perfectly parsable JSON object"*). Two arms reasoned their way to the
opposite conclusion, one of them stating that the backend *"likely extracts the JSON
via regex before reading this section"* — a guess about our parser that is wrong.

**Corpus 2 — the harness smoke** (`harness/results/CAT_long/run.json`, CAT,
`mandate_label=long`, temperature 1.0, thinking off, `pm_samples=5`). No addendum,
plain production prompt. `pm.samples_parsed = 4` against `samples_returned = 5`;
replaying each draw through `extract_json_object` reproduces exactly one failure
(draw index 1, `finish=stop`, `tok_out=152`). That draw did not overflow a JSON
object — it never opened one, emitting instead a fabricated retrieval narration and
an invented price block. So the class is broader than "trailing sections": under
sampling the PM sometimes abandons the output contract entirely, on an unmodified
prompt.

### Why the existing guards do not catch it

- `finish_reason` is `stop` in every failing case, so `_mark_if_truncated`,
  `room_pm_truncated` and DEF258's `repair_truncated` branch are all inapplicable —
  nothing was cut off.
- `_normalize_pm_action` (DEF067's fix) operates on an already-extracted dict; here
  extraction itself returns `None`, so it never runs.
- The DEF058 reformatter fires, but DEF067 restricted it to *recovering an APPROVE*
  — a reformatter PASS is deliberately discarded. Both arm failures were shaped as
  APPROVE/PASS mixes, so recovery is a coin toss at best and costs a second call.
- With `pm_self_consistency_samples > 1` the loss is worse than invisible, it is
  *mislabelled*: `_cands` simply omits the unparseable draw, and the agreement
  string is computed over the survivors. The smoke run reports `4/4` — read by
  `_vote_pm_samples`'s own caller as a unanimous team — when the true denominator
  was 5. The split-team disclosure at `room_runner.py:4602-4613` therefore stays
  silent on a run where one voice was dropped.

### Rate, stated honestly

Two small samples: 2/6 (arms, under deliberate instruction pressure) and 1/5
(smoke, no pressure). Neither sizes a production rate — the arms are adversarial by
construction and the smoke is a single ticker. What they establish is that the
failure is **reachable on the current serve without any prompt pressure at all**,
which the DEF067 fix was assumed to have closed. A production rate should be read
off `room_pm_verdict_parse_failed` and `room_pm_reformat` counts on Alpha rather
than extrapolated from either number here.

### Relationship to other open items

- **DEF067** (fixed AT:R59) — same class, parser-side fix, measured 6.0% pre-fix.
- **DEF397** (open, filed 2026-09-02) — the sibling at the Room level: a partial
  Room banked as COMPLETE. The dropped-draw arithmetic above is one of its listed
  mechanisms (`room_runner.py:4540`, `) if r`), noted there and not re-litigated
  here.
- **CR210** — `pm_verdict_schema()` already exists and makes the whole class
  unrepresentable where the provider enforces grammars.
  `room_json_constraints_enabled` is OFF pending the acceptance-3 re-run
  (`docs/forward_planning/CR210_grammar_constrained_room_output/results/acceptance3_wrong_constraint_regressions.md`).
  That re-run is the gating dependency for the structural fix.

### Reproduce

```bash
cd backend && ./.venv/bin/python - <<'PY'
import json, sys; sys.path.insert(0, '.')
from app.services.llm_json import extract_json_object
base = "../docs/forward_planning/CR219_room_prompt_contradictions"
for a in ["h_short","h_medium","h_long","h_very_long","g_income_now","g_learning"]:
    d = json.load(open(f"{base}/evidence/arms/{a}/convene.json"))
    s = [t for t in d["turns"] if t["agent"] == "portfolio_manager"][0]["answer"]
    print(a, extract_json_object(s) is not None)
d = json.load(open(f"{base}/harness/results/CAT_long/run.json"))
print([extract_json_object(x["answer"]) is not None for x in d["pm"]["draws"]])
PY
```
