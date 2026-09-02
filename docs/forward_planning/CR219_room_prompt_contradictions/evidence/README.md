# CR219 evidence — what is here and how to regenerate it

Everything the finding rests on. Nothing here is a summary: the raw prompts sent and the
raw replies received are stored in full, so any claim in the CR doc can be checked against
the bytes rather than against my reading of them.

## The record

| Path | What |
|---|---|
| `convene_CAT_long_wealth/` | The first full 12-agent Gemini convene (live profile, `long`/`long_term_wealth`) |
| `arms/<arm>/` | Six mandate-variation convenes against **one shared cached profile** |
| `arms/<arm>.log` | Per-turn timing and token counts as each arm ran |
| `rendered/*.txt` | The 12 **complete** assembled Room prompts at HEAD — persona + overlay + sheet + tail |
| `rendered/sheets/*.txt` | The fact sheet each of the 15 agent ids receives, all-live, lane-gated |
| `origin/` | Where this started: the real `fundamentals_analyst` prompt from the CAT@2025-08-08 `llm_audit` row, and GLM-5.3's reasoning + answer on it during CR217 |

**84 turns are stored, and every one carries all four of:** the exact `system_prompt` sent,
the `user_message`, the model's full `thought` trace, and its `answer` — plus `finish`,
`elapsed_s` and the three token counts. Verify with:

```bash
python3 - <<'PY'
import json, glob
for r in sorted(glob.glob("*/convene.json") + glob.glob("arms/*/convene.json")):
    t = json.load(open(r))["turns"]
    bad = [x["agent"] for x in t
           if not all(x.get(k) for k in ("system_prompt", "user_message", "thought", "answer"))]
    print(f"{r:34s} {len(t):2d} turns  {'complete' if not bad else 'MISSING: ' + str(bad)}")
PY
```

Totals: **1.96M chars of prompts sent, 226k chars of reasoning, 190k chars of answers.**

## The scripts

**Every script runs from any working directory** — paths are derived from the script's own
location, never hardcoded. Verified by running each one from `/tmp`. Use the repo's venv:

```bash
V=backend/.venv/bin/python
D=docs/forward_planning/CR219_room_prompt_contradictions/evidence

$V $D/analysis/verify_citations.py          # start here: do the doc's citations hold?
$V $D/analysis/citation_rates.py            # the suppression measurement
$V $D/analysis/aggregate_arms.py            # verdicts, contradictions, data gaps
$V $D/analysis/extract_reports.py $D/arms/h_short/convene.json contradictions
$V $D/dump_sheets.py    /tmp/sheets         # optional out-dir; defaults beside the script
$V $D/assemble_room.py  /tmp/assembled
```

`gem.py` finds `infra/alpha.env` by walking up from itself; override with `AMI_ALPHA_ENV`.
It never prints or stores the key — no credential appears anywhere in this folder.

| Script | What it does |
|---|---|
| `dump_sheets.py` | Renders the real per-agent fact sheet through `_format_profile`, reusing `test_prompt_data_parity`'s sentinel injection so it comes out of the production renderers rather than a hand-built approximation |
| `assemble_room.py` | Assembles all 12 **complete** Room prompts at HEAD. The persona file is only 10–18% of a prompt; a contradiction exists only in the concatenation, which is why the persona-only reviews could not see these |
| `convene_gemini.py` | Runs one full 12-agent sequential convene. Production prompts byte-identical — same phase order, analysts sharing an empty transcript by design, transcript growing turn by turn |
| `gem.py` | Gemini client. Reads the key from `infra/alpha.env` at call time and **never prints or stores it** — no key appears anywhere in this folder |
| `analysis/citation_rates.py` | The suppression measurement over the banked `llm_audit` corpus |
| `analysis/extract_reports.py` | Pulls each agent's two self-report sections out of any convene |
| `analysis/aggregate_arms.py` | Cross-arm rollup: verdicts, contradiction reproduction, clustered data gaps |
| `analysis/verify_citations.py` | Checks every `file:line` the CR doc cites still points at the text it claims. **Exit 0 = all resolve.** Run it after anyone edits a persona — line numbers rot, and a citation that lands on the wrong line costs the reader their trust in the rest of the document |

### Reproducing a convene

```bash
# One profile, shared by every arm, so the mandate is the only variable.
# Pickle, not JSON: the profile carries Pydantic news/social objects and a JSON
# round-trip degrades them to dicts, which `format_headline` then crashes on.
backend/.venv/bin/python - <<'PY'
import sys, os, pickle
sys.path.insert(0, "backend"); os.chdir("backend")
from app.core.config import settings
settings.use_real_market_data = True; settings.suppress_analyst_consensus = False
from app.services import room_runner
pickle.dump(room_runner._profile_for_ticker("CAT"), open("../<evidence>/profile_CAT.pkl", "wb"))
PY

backend/.venv/bin/python <evidence>/convene_gemini.py \
  --label h_short --horizon short --goal long_term_wealth \
  --out-root <evidence>/arms --profile-cache <evidence>/profile_CAT.pkl
```

`profile_CAT.pkl` is **deliberately not committed** (`.gitignore`): a pickle cannot be
reviewed in a diff and loading one executes code. It is a local fixture; the snippet above
rebuilds it. The market data behind it moves anyway, which is exactly why every arm in a
comparison must share one.

## What the convene does that production does not

One addendum, appended to the **user** message only — never the system prompt, which stays
byte-identical to what Alpha sends. It asks each agent, after its normal turn, for:

- `DATA I LACKED:` — the datum, what its answer would have changed to, and whether it
  believes the datum was ABSENT, WITHHELD, or FORBIDDEN;
- `PROMPT CONTRADICTIONS:` — any instruction that fights another instruction or the fact
  sheet, **quoting both sides**, and which one it obeyed.

That second section is the instrument. GLM-5.3 surfaced the margin-trend contradiction by
accident inside its reasoning during CR217; this asks for it deliberately. The incumbent
emits zero reasoning tokens and has been resolving these silently on every convene since
2026-08-13.

## Three things the record does NOT support

Stated here so a later reader does not over-read the files.

1. **Verdict differences between arms are not attributable to the mandate.**
   The arms ran single PM draws (production has defaulted to 5 since CR214); at n=1
   the measured flip rate is ~19.7% (`risk_officer.py`), so one draw per arm cannot separate a mandate effect from a coin
   toss — and the observed pattern is non-monotonic in horizon, which a real horizon effect
   would not be. The verdicts are a record, not a result.

2. **The Portfolio Manager's contradiction reports are mostly our own artifact.** Its prompt
   requires the entire reply to be one JSON object; the addendum asks for two appended
   sections. That collision is this harness's, not production's, and `aggregate_arms.py`
   excludes it — which drops the PM from 6/6 arms to 1/6. Counting it would have inflated
   the headline finding by a whole agent.

3. **Four of `h_short`'s twelve contradiction reports are our own artifact too.**
   `convene_gemini.py:77` hardcodes `path=Path.LONG_HORIZON` while `--horizon` varies, so
   the short arm ran an internally incoherent mandate (`Horizon: short (<1 year)` alongside
   `Path: long_horizon` / `Primary goal: long_term_wealth`), and four agents (market,
   social, bull, trader) dutifully reported that incoherence. Those reports are about the
   harness's mandate, not production's — production mandates come from onboarding and
   cannot combine these values this way. Unlike the PM exclusion, `aggregate_arms.py` does
   NOT filter these; discount them when reading `h_short/`. (Added 2026-09-02 by the
   fable review track — see `../fable/01_review_of_findings.md`.)
