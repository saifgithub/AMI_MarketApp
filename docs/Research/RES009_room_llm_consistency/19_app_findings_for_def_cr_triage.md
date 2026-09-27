# 19 — Production-app findings surfaced by the CR240 language investigation, for DEF/CR triage

**Status: findings compiled, checked against the actual production code —
nothing here is filed as a DEF/CR yet.** Saiful, 2026-09-27: "It seems we
have found a lot of error conditions that the app itself would benefit.
Ensure we document this in RES009 for minting into a DEF/CR later." This
doc separates what's genuinely a production gap from what turned out to
already be handled, so a future minting pass isn't re-discovering things
the codebase already defends against.

## Method

Every anomaly hit across docs 15/16/18 (scripted-fallback rate, JSON
truncation, JSON format abandonment) was checked against the ACTUAL
production parsing/fallback code in `room_runner.py`/`llm_json.py` before
being listed here — not assumed to be new just because this investigation's
own replay tooling (`room_agent_replay.py`, a standalone `httpx` probe, not
routed through the app's real parsing path) hit it. Two of the three
turned out to already be defended; one is a real, undefended gap.

## Finding 1 — REAL GAP: scripted-fallback template is context-blind, and this coincided with the one verdict that flipped

**What was found (doc 15):** DeepInfra+Malay hit the Room's own
scripted-fallback path on 2/5 draws (40%) — zero on every other
combo/language tested. One of those two (`SO`, `research_manager` scripted)
coincided with the ONLY draw across all 20 in doc 15 whose verdict differed
from that ticker's otherwise-consistent pattern.

**Checked against the code:** `_scripted_for()`
(`backend/app/services/room_runner.py:8298`) renders `_TEMPLATES[agent_id][0]`
— a FIXED, generic legacy template, filled only with `formatter`'s shared
keys (ticker, price, etc.), never conditioned on what the actual live
upstream transcript (the bull/bear debate this convene actually produced)
concluded. This is a real, structural gap: `research_manager`'s job is to
synthesize the bull/bear debate into a stance; when it falls back to the
generic template, the fallback text is disconnected from that specific
convene's real argument, and downstream agents (`trader`, `portfolio_manager`)
read it as if it were real synthesis.

**Not proven causal yet** — the failed agent's would-be real output was
never diffed against what the scripted template said, so "the fallback
caused the flip" is a hypothesis, not a demonstrated fact. But the
mechanism is real and undefended regardless of whether it explains this
specific flip: **any live-call failure on `research_manager` (network
error, malformed response, timeout — not just a language-prompting
artifact) substitutes a context-blind stance into a pipeline whose whole
job is synthesizing that specific convene's context.**

**Candidate DEF, not filed:** research_manager's (and plausibly other
synthesis-role agents') scripted fallback should either (a) derive its
stance from the upstream bull/bear transcript directly (even a crude
majority-of-keywords heuristic beats a fixed template) rather than a
canned response, or (b) the Room should surface a strong, visible
disclosure when a SYNTHESIS-stage agent (not an independent-opinion agent)
falls back, since the failure mode here is qualitatively different from an
analyst dropping out — everyone downstream is now reasoning over a
synthesis that never actually looked at the debate.

## Finding 2 — ALREADY HANDLED: mid-JSON truncation

**What was found (doc 18):** several replay draws truncated mid-JSON
(unbalanced braces) well below the token ceiling, for reasons not
understood, not always reproducible on retry.

**Checked against the code:** `_parse_pm_verdict()`
(`room_runner.py:2625`) already has a dedicated, documented repair path for
exactly this (DEF258): a strict parse failure triggers
`extract_json_object(text, repair_truncated=True)`, and a successful repair
is disclosed to the user via `_PM_TRUNCATED_NARRATION` rather than silently
presented as complete. DEF258's own comment states this was measured live
(2 of 14 verdicts in a real batch) and that raising the token budget was
considered and rejected (the clipped samples weren't near the ceiling
there either — matching what this investigation independently observed).
**Not a new finding — this investigation rediscovered an already-fixed,
already-disclosed defect.** The only real gap is that
`room_agent_replay.py` (this toolkit's own standalone probe) has no
equivalent repair logic, so a truncated draw there just reads as "extraction
failed" — worth a note in the toolkit's own docs, not a production DEF.

## Finding 3 — ALREADY HANDLED: PM abandoning JSON for free text

**What was found (doc 18):** one draw answered in a labeled free-text
format instead of the required JSON schema — fluent, correct content,
wrong shape.

**Checked against the code:** `extract_json_object()`
(`llm_json.py:153`) already returns `None` cleanly when no `{` is found at
all, and `_parse_pm_verdict` already fails safe to PASS in that case
(DEF059's documented behavior — "the caller fails safe to PASS... rather
than fabricating APPROVE"). **Not a new finding either** — this is the
designed, already-shipped fail-safe working exactly as intended. Restated
here only so nobody re-discovers "PM sometimes doesn't return JSON" as if
it were new; the app's answer to that is already correct (PASS, not a
fabricated decision).

## Net: one real candidate, two already covered

Of the three anomalies this session's language investigation surfaced,
**only Finding 1 (context-blind scripted-fallback on synthesis-role
agents) is an actual, undefended production gap** worth a DEF/CR when
minted. Findings 2 and 3 are restated here explicitly so a future triage
pass doesn't waste time re-discovering fixes that already shipped
(DEF258, DEF059) — the value of documenting them is negative-confirmation,
not a new action item.

## Not filed as a DEF/CR by this doc

Per standing process, Claude does not auto-file a DEF/CR from a research
doc — Saiful mints via the Architect once he's seen this and decided it's
worth acting on now vs. later. This doc is written so that step is a quick
read-and-decide, not a re-investigation.
