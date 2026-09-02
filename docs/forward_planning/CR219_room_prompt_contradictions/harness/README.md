# CR219 harness — the outcome instrument

The measurement half of CR219 (register R29–R32, R46, R47, R48, R54). `../evidence/`
answers *"what is wrong with the prompts"*; this folder answers *"did fixing them change
anything"*, on a fixed golden set, with scorers a person can read.

Design ruled 2026-09-02 (`dev_instructions/DECISIONS_2026-09-02.md` §3): QWEN's
ticker × mandate frame with deterministic scorers, at Kimi/GLM's scale — 4–5 cached
profiles, three mandates each, PM verdicts mirroring the production 5-way vote.

---

## Run it

```bash
V="backend/.venv/bin/python"
H="docs/forward_planning/CR219_room_prompt_contradictions/harness"

$V $H/build_profile.py CAT                       # fetch + cache one profile (once)
$V $H/run_convene.py --ticker CAT --mandate long # one full 12-agent convene, scored
$V $H/score_only.py $H/results/CAT_long/run.json # re-score a banked run, no LLM calls
```

Every script runs from **any** working directory — paths derive from the script's own
location (`_paths.py`), the `../evidence/` convention. Use the repo venv: plain `pytest`
and plain `python` on PATH resolve to a `structlog`-less env.

Output lands in `results/<label>/`: `run.json` (prompts, answers, tokens, PM draws,
scores) plus one `.answer.txt` per agent. `--label` names the folder; the default is
`<TICKER>_<mandate>`, with `_thinking` appended for an R48 arm.

### Adding a ticker

1. `$V $H/build_profile.py <TICKER>` — it prints the LIVE-field count. A ticker whose
   count is far below the others has a data gap, and its scores are not comparable to
   the rest of the battery; note that rather than averaging it in.
2. Run it against all three mandates.

Adding a **mandate** is different: edit `BATTERY` in `mandates.py`, never the call site.
`path` is derived from `primary_goal` there, and that derivation is the guard against the
`h_short` artifact (below).

### Profiles are cached, and never committed

`profiles/*.pkl` is gitignored. A pickle cannot be reviewed in a diff and loading one
executes code, so it is a **local fixture** — `build_profile.py` rebuilds it. Caching is
not an optimisation: market data moves between fetches (R46), so if each arm refetched, a
difference between arms could not be attributed to the thing the arm varies. Every arm in
a comparison must load the same pickle.

---

## What the harness sends

`build_room_messages` is called exactly as `room_runner` calls it: same 12-agent order,
the four analysts sharing an empty transcript by design (`parallel_phase=True`), the
transcript growing turn by turn, `max_tokens_for(agent_id)` as each agent's decode budget.
**Nothing is appended to any prompt.**

That last point is the deliberate difference from `../evidence/convene_gemini.py`, which
appends an evaluation addendum asking each agent to self-report. That addendum is an
excellent *elicitation* instrument and a bad *measurement* one — it manufactures a
contradiction of its own (the PM's JSON-only contract vs. two appended prose sections),
which is why `aggregate_arms.py` has to exclude the PM entirely. This harness measures the
shipped prompt, so it sends the shipped prompt.

**Mandates are production-coherent.** `mandates.py` derives `path` from `primary_goal`
using the production derivation in `concierge_engine.py:253-262`; it is not a parameter.
`convene_gemini.py:77` hardcoded `path=LONG_HORIZON` while `--horizon` varied, so the
`h_short` arm ran a mandate onboarding cannot produce, and four of that arm's twelve
contradiction reports are about *that* incoherence rather than production's. A harness
that manufactures its own contradictions cannot measure contradictions.

**The PM stage mirrors production** (R32). `settings.pm_self_consistency_samples`
(default 5, `backend/app/core/config.py:751`) independent draws, each parsed by the
production `_parse_pm_verdict`, voted by the production `_vote_pm_samples` — majority on
action, median size among winners, ties to PASS. Never a single draw: at n=1 the measured
flip rate is ~19.7%, so a one-draw verdict cannot be told from a coin toss, which is
exactly why the `../evidence/arms/` verdict column is uninterpretable.

**What it does not run:** `enforce_safety_floor`. The floor is a deterministic post-check
needing DB-backed trade history the Mac has no access to. The harness measures what the
Room produced; the floor's veto is production's separate guarantee, tested separately.

---

## The scorers

No judge model, anywhere. Every number is computable from the transcript plus the prompt
the agent was actually sent. A regex can be wrong — but it is wrong the *same way* on
every arm, which is what a before/after needs, and an LLM judge is a second unvalidated
model placed between the change and the number.

Each scorer carries its own `proves` string into `run.json`, so the caveat travels with
the figure.

| Scorer | What it proves | What it does **not** prove |
|---|---|---|
| `schema_validity` | The CIO produced a verdict the production parser accepts — legal action, non-empty reason — from N draws voted production's way. Reports `parse_rate` (how many of the N draws were readable at all) separately from `agreement`. | Nothing about whether the verdict is *right*. A confident PASS on a good name scores identically to a correct one. |
| `envelope_parse_rate` | The `[STANCE:…\|CONVICTION:…\|HEADLINE:…]` machine channel is emitting in a shape the **shipped** `parse_stance_envelope` reads. A miss is raw syntax on the user's screen *and* a null stance — the DEF147/DEF247 pair. | Nothing about whether the stance is correct, or whether it matches the prose above it. |
| `numbers_match_sheet` | How much of the arithmetic the Room states is traceable to bytes it was given (its own system prompt + user message: sheet *and* transcript). | **Not a fabrication count.** A ratio the agent legitimately computed and a number it recalled from training memory land in the same unmatched bucket — the scorer cannot separate them. Read it as a *movement between arms*. `unmatched_sample` is there so a human can look. |
| `mandate_echo` | The mandate the run claims is the mandate the agent was handed (the literal `Horizon:` / `Primary goal:` lines present in the prompt — a rendering regression is otherwise silent), and the turn does not assert a horizon the mandate rules out. | Nothing about whether the analysis *served* the mandate. Absence of a contradiction is not adherence. |
| `live_citation_rate` | Of the `(LIVE)`-labelled fields in the sheet an agent received, how many the turn actually names. This is the WP01 fixes' target: agents naming data they hold instead of denying it. | **R29 — a suppression proxy, not an outcome measure.** It shows agents stopped *refusing* data. It says nothing about whether the Room's answer got better, and a Room that cites every field and reaches a worse decision scores *better* here. Never report a citation delta as a quality result. |

### What the harness as a whole does NOT prove

- **Not decision quality.** Nothing here scores whether APPROVE or PASS was the right
  call. There is no ground truth in the run, and a forward-return label would need a
  holding period and a sample size this battery does not have.
- **Not a production A/B.** It is a fixed golden set on cached data, run off-Alpha. It
  detects *whether a prompt change moved the measured behaviours*, on this battery.
- **Not model-transferable.** Runs target the on-prem vLLM. Model identity is read from
  `/v1/models` `root` and banked in every `run.json` — never from the `id` alias, which
  was reused across the 2026-08-28 swap and now names a different model than it did
  before. Anything keyed to "ami-llm" before that date is unattributable. A second model
  is CR217's business.
- **Not a small-sample significance test.** One convene per cell. A cell-level difference
  smaller than the model's own run-to-run variance is noise; that variance is what R47's
  k-sweep is for.

---

## Banked results

`results/` holds the runs. R47 (residual PM flip rate at n=5) and R48 (thinking on/off
A/B) land here as dated notes when Saiful gives the go — those batches are **held**, not
run: this folder currently contains the build plus one smoke run.

| Path | What |
|---|---|
| `results/CAT_long/` | The smoke run, 2026-09-02: CAT × `long`, 12/12 turns, no errors, no truncation, 5 PM draws voted 4/4 PASS |
| `results/2026-09-02_R48_thinking_probe.md` | R48 step 1 — the raw finding that per-request thinking works, and the three things it changes for the A/B |

Smoke-run scores, for reference when a later run looks off:
`envelope_parse_rate` 0.909 (10/11) · `numbers_match_sheet` 0.922 (154/167) ·
`mandate_echo` 1.0 (12/12) · `live_citation_rate` 0.392 (71/181) ·
PM `parse_rate` 0.8 (4 of 5 draws readable). These are one run against pre-fix prompts —
a baseline to compare against, not a target.

### R48 probe — 2026-09-02, `192.168.20.74:8048`

Per-request thinking **is** honoured by this serve; no server-side config change is
needed. `chat_template_kwargs: {"enable_thinking": true}` moves
`usage.completion_tokens_details.reasoning_tokens` off zero (0 → 78 on a probe prompt) and
adds a thinking prefix to the rendered template (prompt_tokens 25 → 65). Two obvious
variants do **not** work — a top-level `enable_thinking` and
`chat_template_kwargs: {"thinking": true}` both returned `reasoning_tokens: 0`. The build
also accepts `reasoning_effort` with values `xhigh` (default), `medium`, `low`; any other
value is a 400. This build inlines the thinking into `content` rather than emitting a
separate `reasoning_content` field, so an A/B must budget for it: thinking tokens spend
from the same `max_tokens` as the answer, and `max_tokens_for(PORTFOLIO_MANAGER)` was
tuned with thinking off. Re-derive that budget before running the arm, or the thinking-on
side will truncate and fabricate a losing result.

`--thinking` on `run_convene.py` is the arm switch. `run.json` records
`reasoning_tokens_total`, so an arm claiming thinking-on can be checked rather than
believed.
