# WP08 — Verdict pipeline honesty (R43, R49–R52)

Fable's second-pass items ruled into CR219's umbrella (register: "RULED, Fable's
scoping") plus one DEF filing. These touch the run pipeline, not personas — model
routing: Opus or reviewed Sonnet.

## R43 — PM breaks its JSON-only contract under instruction pressure → file a DEF

The arms showed the PM emitting prose outside its mandatory JSON object when the
user message asks for extra sections (why `aggregate_arms.py` excludes it — 5 of 6
arms). That fragility class has precedent: DEF067 (~13% parser loss). Action: **ask
the Architect to mint a DEF** (single ID-minter rule — do not pick a number), write
the row file per governance (`docs/defect/_registry/DEF###.row.md`), evidence pointer
to `../evidence/arms/` and the aggregate exclusion. The *fix* rides that DEF, not
CR219 — this row closes when the DEF exists.

## R49 — PM is overridden by floor checks it never sees

`enforce_safety_floor` (`backend/app/agents/safety_floor.py`) deterministically
overrides verdicts on post-loss cooldown (~`:493`) and the over-trading brake
(~`:230` docstring), but the PM's prompt carries **no floor state** — so the PM
argues for trades the floor then vetoes, and the user sees an incoherent
deliberation→verdict pair. Fix: render a compact **floor-state preview** into the PM's
VERDICT-phase context (in cooldown until T? trades-this-window count? open-risk
headroom?) sourced from the same functions the floor calls — never a parallel
reimplementation (two implementations WILL drift; import and reuse). The floor stays
the enforcer (uncoachable, untouched); the PM just stops being blind. Acceptance:
unit test — profile in cooldown → PM prompt contains the cooldown line; floor
behavior byte-identical (`git diff` shows no `safety_floor.py` enforcement change).

## R50 — code-generated Room scoreboard

The stance envelopes are already parsed (`room_runner.py:2888–3005`) and then
under-used. Build a scoreboard table (agent | stance | conviction | headline number)
generated **in code** from the parsed envelopes, injected into the PM's context
(and optionally the transcript shown to users — that copy says **AMI**, not "the
LLM"). No model summarization — this is R20's philosophy at the Room level: AMI
mints the aggregate. Acceptance: unit test with a fixture transcript → deterministic
table; malformed envelope → the agent's row says `unparsed` (loudly), never dropped
silently.

## R51 — partial-outage honesty

When the provider fails mid-convene, scripted `_TEMPLATES` fallbacks fill agent turns
(`room_runner.py::_compute_agent_text`, ~L4906) — a Room can present N scripted turns
as deliberation. DEF059's lesson (LLM down → confident fake APPROVE) says this must
surface. Fix, three parts: (1) **count** scripted-fallback turns per convene (run-level
counter — verify none exists before adding; none was found 2026-09-01); (2)
**disclose** in the verdict payload + user-visible transcript ("N of 12 desks
responded; AMI filled the rest with standing guidance" — AMI naming rule); (3)
**cap**: at/above a threshold (proposal: >3 scripted turns of the 12) the verdict
must degrade to an abstain/incomplete state rather than a confident call — wire the
threshold as config, forwarded in `docker-compose.yml` (compose-parity test).
Acceptance: unit test at 0 / 2 / 4 scripted turns → disclosure text + degraded
verdict state appear exactly as specced.

## R52 — "what would change this call" (kill-criterion) on the verdict

Add one field to the PM verdict: the concrete observable that would flip the call
("a second quarter of margin compression", "close below the 64-day low"). Coordinate
with CR210's constrained-output work: the verdict JSON schema lives in
`backend/app/services/risk_officer.py` / `room_prompts.py` with tests in
`test_cr210_schemas.py` — extend schema + prompts + tests in one commit so the
grammar and the ask never diverge (that divergence class is exactly what CR210's
acceptance-3 note documents). Kill criteria must reference **sheet-observable**
quantities (WP02 R11 vocabulary), not unfetchable ones. Acceptance: schema tests
green; harness scorer (WP07) checks the field parses and references a sheet field.
