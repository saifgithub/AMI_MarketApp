# Failure patterns — recurring classes and the checks that enforce them

**Purpose:** `docs/defect/def_list.md` records *instances*. This file records *classes* — the
shapes of mistake this project makes more than once — and, for each, the executable check that
now prevents it.

**House rule: an entry without an enforcing check is not done.** Prose does not prevent
recurrence; this file exists because we proved that (see P1). If you add an entry, add its guard
in the same commit, or state explicitly why no guard is possible yet and what would make one
possible.

**When to add an entry:** the second time something bites. The first time is a defect; the second
time is a pattern, and by then the cost of the guard is already justified.

---

## P1 — Config that isn't forwarded to the container (feature silently dark)

**Symptom.** A feature ships, its key is provisioned, and it never runs in Alpha. No error, no
log line. Detection is accidental and can take months.

**Mechanism.** `docker-compose.yml` enumerates the `api-alpha` service's env vars explicitly.
`infra/alpha.env` → `melehost:~/ami_trade/.env` carries the value to the host, and compose reads
that file for `${VAR}` interpolation — but a var compose never *mentions* is never passed to the
container. There is no `.env` inside the container, so container env is the only channel. Most
integrations gate on "presence of the key turns it on" (`config.py`), so an absent key is
indistinguishable from a deliberate opt-out.

**Instances.**

| | What was dark | For how long | Found by |
|---|---|---|---|
| **DEF038** | `APPLE_AUDIENCES` / `GOOGLE_AUDIENCES` — OIDC tokens verified against an empty audience list | unknown | auth audit |
| **DEF063** | `ADANOS_API_KEY` (CR024 social feed), `ALPHA_VANTAGE_API_KEY` (CR023 news sentiment merge) | entire life of both CRs | CR035 benchmark, then Saiful challenging a wrong premise |

**Why the previous guard failed.** After DEF038 a comment was written *in the compose block
itself*:

> `# OIDC audiences (DEF038: these lived in .env but were never forwarded here…)`

DEF063's two keys should have been added roughly seven lines below it. The comment failed for two
structural reasons, both worth generalising:

1. **Descriptive, not imperative.** It explained a past bug about two specific keys. It never
   stated a rule binding on every future key.
2. **Nothing executed it.** A comment only fires if a human opens that file at that moment.
   CR024's work lived in `config.py` and `social_context.py` — compose was never opened.

**Enforcing check (CR040).**

- `backend/tests/unit/test_config_compose_parity.py` — every `Settings` field must be forwarded
  in compose's `api-alpha` env block or listed in `_NOT_FORWARDED` **with a reason**. Fails at
  commit time, on the Mac, in the normal suite. Verified red against the real DEF063 state before
  the fix landed; it names DEF063's two keys explicitly so that exact regression can't return
  quietly.
- `GET /v1/admin/config-check` — reports each gate's live state in-container (booleans only,
  never secret values). Turns "is Adanos on?" into one curl.
- `/promote-to-alpha` — calls config-check post-deploy and fails loudly on a key that is
  populated in `infra/alpha.env` but dark in the container.

**Rule for new code.** New env-driven setting ⇒ compose env block + the parity test passes. If
the container genuinely never needs it, say so in `_NOT_FORWARDED`.

---

## P2 — Silent, confident degradation

**Symptom.** When an input is missing or a dependency is down, the system does not fail — it
produces confident output built from fallback material, indistinguishable to the user from the
real thing. The less the system knows, the more assured it sounds.

**Instances (all surfaced in AT:R59, within a single day).**

| | Trigger | Degraded behaviour | Signal to anyone |
|---|---|---|---|
| **DEF063** | API key not forwarded | Social Analyst invents sentiment from `crc32(ticker)` scaffolding | none |
| **DEF059** | vLLM host down mid-batch | Room emits scripted **APPROVE** — "Synthesis defended; mandate checks pass" — in ~30 s | none; looked like a fast successful run |
| **DEF058** | PM verdict unparseable (22% of live runs) | silent PASS; the PM's real decision discarded | one log line |
| **CR037** | social feed unavailable | 23/32 messages assert invented sentiment with no hedge | none |
| **CR038** | no macro/Fed feed exists | 62/88 macro citations asserted as fact across all 12 agents | none |

**The invariant.** *Degrade loudly, never confidently.* A degraded path must be visible to
whoever depends on it — the user (honest copy), the operator (a distinct signal, not a log line
in a stream nobody tails), or the caller (an explicit status).

**Two lessons the instances share.**

1. **Prompt-level instruction is not a control.** The profile block tells agents, emphatically,
   *"never present them as real."* Compliance measures ~30% (CR038) and ~28% (CR037). DEF058 was
   the same model ignoring an equally emphatic *format* instruction ~22% of the time. If a
   property must hold for the user, it must be structural — remove the data at source, or render
   it outside agent prose. Anything else is a wish.
2. **Check the direction of your fallbacks.** DEF058 (unparseable → PASS) and DEF059 (LLM down →
   APPROVE) were built by the same reasoning and landed on opposite safety. Every fallback should
   be asked: *if this fires constantly and silently, what does the user end up believing?*

**Enforcing checks.** Partial — this pattern is broader than one guard:

- DEF058 → `test_room_pm_prose_reply_recovered_by_reformat`,
  `test_room_pm_reformat_never_invents_an_approve_size` (`backend/tests/unit/test_room_runner.py`).
- DEF059 → `test_room_pm_llm_outage_fails_safe_to_pass` (same file) — asserts a dead LLM can
  never yield APPROVE.
- DEF063 → P1's parity test + config-check.
- CR037 / CR038 → **no guard yet; both undecided.** The measurement that would enforce them
  exists: the CR035 harness transcript audit (unhedged-assertion count over a ≥30-run batch).
  Whichever fix lands should wire that count into an acceptance check.

---

## P3 — Content validated by exemplar, never as a corpus

**Symptom.** Tests over a content-driven feature all pin to one hand-picked exemplar item.
The exemplar is, by construction, well-formed — it was chosen *because* its content is
controlled. So the suite is green while an arbitrary fraction of the real corpus is broken,
and the defect surfaces only when a user hits it.

**Instances (all surfaced in AT:R60).**

| | Defect | Scale | Signal to anyone |
|---|---|---|---|
| **DEF064** | 12 quizzes authored in a numeric free-response form the pipeline never implemented → zero options → lesson permanently un-completable, 2 of 12 agents unlockable | 12 / 571 questions | none |
| **DEF065** | 277 explanations cite an answer option by an index the reader never renders, under two contradictory conventions | 277 / 571 questions | none |
| **DEF068** | agent-unlock gateways derived by lexicographic id sort over `agent_callouts` — a set nobody chose, scattered so far through the corpus that a user 50 lessons deep held 1 of 12 agents | 12 / 12 agents | none |

DEF068 is the same shape one level up: the *relationship between* content items
was derived incidentally and never validated as a whole. `_gateway_lessons_for_agent`
sorted and sliced, so it always returned something plausible, for any corpus, in any
order — there was no state it could report as wrong. The tests that existed asserted
the slice worked, never that the resulting sets made sense.

**Why the existing guards could not see it.** `backend/tests/unit/test_lessons_service.py`
has 16 tests over lessons and every one pins to `283_market_order_vs_limit` — a lesson
selected for having *controlled* content. That is the structural reason, not an oversight:
an exemplar test answers "does the parser work?", never "is the content valid?" Nothing
iterated the other 269 lessons. `LessonsService._reload()` compounded it by swallowing
parse failures with a log line, so a malformed lesson would have vanished from the
catalogue rather than failing anything.

Both defects also had a P2 flavour — `attrs.get("answer", 0)` and `options=... or []` are
silent fallbacks that turned an unsupported authoring form into a dead end instead of an
error — but the reason they *survived for months* is P3: no test ever looked at the corpus.

**The invariant.** *If content ships, something iterates all of it.* An exemplar test and a
corpus test answer different questions; a feature backed by authored content needs both.
DEF068 adds a corollary: *a derivation over content is content too.* Anything that computes a
relationship across the corpus — which lessons gate an agent, what a code resolves to — needs
its whole output checked, not just the function that produces one element of it.

**Enforcing check.** `backend/tests/unit/test_lesson_corpus_integrity.py` — iterates all 270
lessons: ≥2 options per question, answer index in range, options distinct and non-empty,
question/explanation non-empty, no index citation in any user-visible surface
(explanation, question **and** option text), no `tolerance=` attribute anywhere in the
source, and lesson count exactly 270 so a silently-dropped lesson fails loudly. Verified red
against the real defect before the fix — 4 assertions failed, naming all 12 files.

DEF068 + CR044 extend the same file rather than starting a new one, since they are the same
class: every lesson has a `code` (present, unique, prefix matching its `track`, contiguous
`1..N` within the track), and the curated gateway map is checked whole — all 12 agents, exactly
`GATEWAY_SIZE` lessons each, every id resolving to a real lesson, every gateway lesson naming
its agent in its own `agent_callouts`, and `gates_agents` matching the inverse of the map so
the badge and the unlock check can't drift apart. Each was verified red against an injected
regression before being trusted.

Deliberately **not** asserted: the answer-position distribution CR042 corrected. A
uniformity assertion would go red on legitimate content edits and teach the next session to
weaken the file. One-off corrections belong in the authoring spec, not in a guard.

The sibling corpus (`content/daily_challenges/`, 183 questions) had only
`test_real_corpus_loads` asserting `len(items) >= 100`. It happened to be clean on both
counts — Pydantic validates each record on load, which is why. That is luck, not coverage.

---

## Adding an entry

1. Name the class, not the instance. Two instances minimum.
2. Record *why the previous guard failed* — that is the load-bearing part. "We forgot" is never
   the reason; find the structural one.
3. Name the executable check and where it runs. If none exists, say what would make one possible.
4. Link the instances in `docs/defect/def_list.md` / `docs/forward_planning/cr_list.md`.
