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
| **DEF123** | yfinance lacks a field (loss-making name, no `trailingPE`) | `_profile_for_ticker` pre-filled an rng-seeded value BEFORE the live fetch; a partial `dict.update` overlay left it in place while `data_source` flipped to `"yfinance_live"` for the whole profile — 178/842 (21.1%, 36 tickers) live-declared Room prompts carried a fabricated P/E, four agents rationalised it as real | the disclosure header itself, which said LIVE |

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
- DEF123 → **`test_no_protected_numeric_field_in_the_unconditional_baseline_dict` +
  `test_no_rng_derived_value_assigned_to_a_protected_numeric_field`**
  (`backend/tests/unit/test_cr104_no_fabricated_numeric_reaches_room_prompt.py`, CR104). DEF123 is
  the instance that proves *labelling* the fabrication doesn't work — it was the sixth attempt at
  this sub-mechanism (DEF052, DEF063, CR037, CR038 all shipped a better disclosure string around
  the same rng scaffolding; DEF123's own header said "LIVE" over an rng P/E). CR104 is the first
  fix that removes the data instead of describing it, and the guard above tests that removal
  structurally (walks `_profile_for_ticker`'s AST) rather than pinning today's field names — a
  future field added the same fabricated-but-labelled way turns it red on sight. Re-runnable
  corpus acceptance check: `backend/scripts/def123_corpus_check.py` (reproduces DEF123's 178/842
  measurement against melehost's `llm_audit` table; goes to 0 only for prompts generated after the
  fix reaches Alpha via `/promote-to-alpha`).
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

## P4 — Contradictory instruction sets across prompt layers

**Symptom.** An LLM prompt is assembled from several layers (a base profile, an overlay, a
per-turn format block). Two layers give conflicting instructions about the *same* thing — the
allowed output vocabulary, the required shape. The model follows one layer; the parser expects
the other; the mismatch is dropped to a silent fail-safe. Green tests, because no test builds the
*assembled* prompt and checks it against the parser that consumes its output.

**Instances (both surfaced by the CR035 benchmark, AT:R59).**

| | The two layers that disagreed | What the model did | What was lost |
|---|---|---|---|
| **DEF058** | base PM profile said *"Output format: prose"*; `_PM_VERDICT_FORMAT` said *"one JSON object"* | mixed — mostly JSON, sometimes prose | prose verdicts hit a fragile reformatter; ~22% lost at first measure |
| **DEF067** | base PM profile advertised `MODIFY-AND-APPROVE` as an action; `_PM_ACTION_SYNONYMS` knew only `APPROVE`/`PASS` | **90%** of live verdicts used `MODIFY-AND-APPROVE` — every one a complete, sized approval | parser returned `None` → reformatter → **~13% refused and lost** (5/150 arm A, 8/150 arm B), all scored as genuine Room conservatism |

**Why the previous guard failed.** DEF058's fix added `test_room_pm_prose_reply_recovered_by_reformat`
— but it tested the *recovery mechanism* (feed prose, assert the reformatter rescues it), never
the *contradiction* (does any layer of the real prompt offer a token the parser can't read?). So
when the very next batch showed the model wasn't writing prose at all but valid JSON with an
out-of-enum action, the existing test stayed green: it was exercising a path the model had already
stopped taking. An exemplar/mechanism test answers "does the rescue work?"; it never answers "is
the prompt internally consistent with its parser?"

**The invariant.** *A prompt and the parser that reads its output are one contract; test them
together against the assembled prompt, not the fragments.* Every action/shape token any layer
offers the model must be understood by the code that parses the reply — or it is a silent loss.

**Enforcing check (DEF067).** `backend/tests/unit/test_room_prompt_parity.py` — assembles the real
Portfolio-Manager system prompt via `build_room_messages(...)`, extracts every action token the
prompt enumerates as a verdict option, and asserts each normalises to a known action through
`_normalize_pm_action`. Verified **red** against the pre-DEF067 parser (`MODIFY-AND-APPROVE` →
None) before the fix. A companion test asserts the extractor actually finds the vocabulary, so a
green result can never mean "found nothing".

**Rule for new code.** Adding or changing an action/shape a prompt layer offers ⇒ the parity test
must still pass (extend the parser, or don't offer the token). Contradiction between layers is not
resolved by prompt wording — the CR035 data shows recency wins on shape but the older layer's
*vocabulary* still leaks through ~90% of the time. Make the parser tolerant of everything any
layer offers.

---

## P5 — LLM asked to compute a number it presents as fact

**Symptom.** An agent states a specific figure — a technical indicator, a risk percentage, a
position cap — that it derived itself from data in the prompt. The number is wrong, or drifts from
what the system actually enforces, and the user (or the PM's binding verdict) treats it as measured
truth.

**Mechanism.** LLMs are unreliable at arithmetic. A prompt hands the model raw inputs and asks it,
explicitly or implicitly, to do the sum. Sometimes there is no data at all and the model invents
one. Either way the output is fluent and confident, so nothing downstream can tell a computed number
from a fabricated one.

**Instances.**

| | What the LLM was left to compute | What went wrong | Scale |
|---|---|---|---|
| **DEF052** | RSI / trend / volume / support for the Market Analyst | 100% fabricated (a coin flip or `rng.randint`); the prompt also claimed MACD/MAs/Bollinger never computed anywhere | every ticker, every run |
| **DEF066** | a position's contribution to portfolio drawdown | compared a raw stop *distance* to the portfolio cap, ignoring size — ~20× overstatement | 16 of 64 benchmark Buys refused |
| **CR046 M03** | (latent) what position size is "allowed" | the Trader was *told* 40% per name while the PM *clamped* to 4.5% — shown ≠ enforced, ~9× gap | every risk-5 convene |
| **DEF077** | the Bear Researcher's P/E-compression downside | inline `int(pe/(pe+10)*100−50)` — unrelated to a de-rating; ~3× understated at P/E 20, ~2× overstated at P/E 55 | every scripted / LLM-timeout Bear turn |
| **CR046 audit (AT:R62)** | a systematic sweep of all 7 prompt surfaces for the class | D-b (profit margin mislabelled "FCF margin"), C-a (a bare "50%" in the PM safety-floor prose that could drift from the enforced cap), M06/M08 (R:R & asymmetry the LLM invented, incl. a fixed "28% vs 18%" for every ticker) | Room + 1-on-1 |

**Why prose could not fix it.** The task framing already hard-instructs *"use ONLY numbers from the
data block… do not cite figures from training memory."* Compliance with that class of instruction
measures ~30% (P2). An emphatic "compute this carefully" is a wish; the model still does the sum, or
invents it. The fix is always the same shape: **compute it in Python, inject the finished figure,
and make the number the agent is shown equal to the number the system enforces.**

**The invariant.** *If an agent presents a number as fact and it can be computed deterministically,
Python computes it and the agent is handed the result — never asked to derive it.* This is the
standing charter of **CR046** (`docs/forward_planning/CR046_agent_math_ledger/`): every such number
is a ledger entry with a formula, a source, and a guard test, computed in the portable
`app/trading_math/` library.

**Enforcing check.**

- Per-calc guard tests pin each computation (`test_trading_math.py`, `test_technicals.py`,
  `test_room_prompts.py`, `test_fundamentals.py`).
- **Coherence tests** for any agent-facing figure the system also enforces:
  `test_position_sizing.py` asserts the cap the Trader is *shown* equals the cap the PM *clamps to*,
  for every risk tier — verified red against the pre-fix 40-vs-4.5 state.
  `test_safety_floor.py::test_safety_floor_prose_cap_equals_the_enforced_constant` (C-a) asserts the
  single-name cap the PM is *shown* in `SAFETY_FLOOR_BLOCK` equals the `SINGLE_NAME_CAP_PCT` the
  deterministic check *enforces* — the prose interpolates the constant instead of a bare literal.
- The CR046 ledger discipline: a new number that reaches an agent gets a ledger entry + a test, or
  it does not ship (the house rule, applied to numbers).

**Rule for new code.** Before a prompt hands an agent inputs to reason over numerically, ask: *is
there a figure here the model will state as fact?* If yes and it's derivable, compute it in
`trading_math/`, inject it, add its ledger entry + guard test. If it's genuinely unmeasurable, mark
it illustrative in the value string itself (the CR034/sentiment convention), not in a separate
prompt line the LLM can drop.

---

## P6 — ARB copy authored for the wrong escaping mode (renders literally)

**Symptom.** A localized string ships with a visible escaping artifact — a doubled
apostrophe `''` where one belongs. It looks correct in the ARB to anyone who "knows"
ICU MessageFormat needs apostrophes escaped, and there is no lint for it, so it reaches
the user's screen unchanged.

**Mechanism.** Flutter gen-l10n's `use-escaping` is **off** (unset in `mobile/l10n.yaml`
→ default `false`). Under that mode the ICU quote character is not processed: a literal
`''` in an ARB value is copied verbatim into the generated Dart and renders as two
apostrophes. The correct authoring is a single `'`. The mistake is a *plausible-but-wrong
belief* — "ARB is ICU, so escape apostrophes" — which is true only with `use-escaping:
true`, the mode this project does not use.

**Instances (all surfaced by DEF069, on one on-device report).** 9 occurrences across 8
keys in `app_en.arb`: `roomWinzipBody`, `roomPaywallBody` (CR047), and **6 pre-dating
CR047** — `onboardingErrorTitle` ("CAN''T REACH THE BACKEND"), `portfolioStartSimTradingBody`
("PM''s"), `journalNoteHint`, `lessonReaderQuizOnlyBannerOne`, `mergeSheetMandate`,
`roomTradeTicketCaption`. Every one had **no signal to anyone** — `flutter analyze` does
not inspect ARB content, and no test iterated the string values.

**Why nothing caught it.** The one automated gate over Dart (`flutter analyze`) lints code,
not ARB copy. The correct-looking strings (`settingsSignedOut: "You've…"`, single `'`) and
the wrong ones coexisted for months because nothing ever compared them.

**The invariant.** *ARB values are authored for the configured escaping mode.* With
`use-escaping` off, apostrophes are single; `''` is always a rendering bug.

**Enforcing check (DEF069).** `backend/tests/unit/test_arb_apostrophe_escaping.py` — fails
if any `''` appears in `mobile/lib/l10n/app_*.arb`. Runs in the `pytest` promote-preflight
(the one gate that executes; `flutter analyze` can't see this), skips cleanly when the mobile
tree is absent.

**Rule for new code.** New ARB string with an apostrophe ⇒ single `'`, never `''`, unless
`use-escaping` is turned on in `l10n.yaml` (a deliberate, whole-file decision). The guard
enforces it.

---

## P6 — A guard on deliberately-growing data pinned exact, not floored (blocks the next addition)

A count/emptiness guard written as an exact equality against today's size turns red the instant the
data grows as designed — and when the guard lives in a tree a different role owns, it deadlocks that
role's lane.

| | The pin | What it blocked | Who was deadlocked |
|---|---|---|---|
| **CR054 (count)** | `EXPECTED_LESSON_COUNT == 270` in `test_lesson_corpus_integrity.py` | every Wave-1+ content lane (each adds lessons) | `noncoder.edu` — a maintainer may not edit `backend/` |
| **CR054 (emptiness)** | `test_cr054_new_tracks_are_empty_at_wave_0` | the same lanes (tracks fill by design in Wave 1) | same |

**Why the previous guard failed.** The guard's real job — catch a *silent shrink* (a lesson that
vanishes because the loader swallows a parse error) — is served equally by a floor; the exact upper
pin added nothing but a tripwire on intended growth. "Strict = safe" read as correct.

**The invariant.** *A guard on data designed to grow is a FLOOR (`>=`), never an exact pin. Before
shipping any count/emptiness guard, ask: does this go red on the next planned addition?*

**Enforcing check (CR054-GUARD).** `LESSON_COUNT_FLOOR` (`>=`) + the auditor pin
`orchestration/audit/regression/test_cr054_guard_capstone_floor_pin.py`. The floor is bumped at each
wave's integration (a code-side micro-step) so shrink-detection stays tight without blocking growth.

---

## P7 — A headless one-shot agent backgrounds a command and dies before it returns

A `claude -p` worker ends the instant it stops calling tools. Backgrounding a long command and
"waiting" ends the turn first — the worker dies mid-lane, and in a detached launch nothing notices.

| | What was backgrounded | Result |
|---|---|---|
| **CR054-GUARD builder** | `uv run pytest &` (to dodge `-q` output buffering) + a "waiting…" message | session ended before the suite returned; lane stuck at `STATUS: CLAIMED`, work uncommitted; a full re-run billed on top |
| **CR054-GUARD launch** | `claude -p … & echo` (the Architect's own launch) | the `&` detached the worker from the Bash task-tracker → no completion callback, stdout to nowhere |

**Why the previous guard failed.** There was none — the discipline lived only in the DeliveryOS
heritage (MABP §8: foreground + redirect-to-log, never `| tail`) and had not been ported into the
CR052 loop prompts. Both instances are the same class: *backgrounding in a headless one-shot context
breaks the coordination it was meant to help.*

**The invariant.** *In a headless one-shot session, run every command in the FOREGROUND; for long
output redirect to a log and read it after the command returns — never `| tail`, never `&`, never an
"I'll check back" message; don't stop until the work is committed + pushed.*

**Enforcing check (CR057).** The "Headless one-shot mode" section in
`orchestration/dispatch/loop_prompts/{CODER,AUDITOR,NONCODER}.md`; the launch footguns are removed
structurally by `orchestration/dispatch/dispatch_launch.sh` (no `&`, task-tracked) + the liveness
relaunch rule.

---

## P8 — A derived state trusts an input nobody validated

The orchestration lane files are prose and machine state in one document, and the two watchers
derive whose turn it is from regex + `tail -1`. Both halves of that have now failed the same way:
the parser accepted a line that was *describing* state, and the arithmetic accepted a round number
that could not exist. Neither errors; both render as a state that looks routine.

| | What was read as state | Result |
|---|---|---|
| **DEF091** (2026-07-23) | an auditor's self-reopen consumed round 2 | the coder's `SUBMITTED: round 2` read as already-answered; lane quiet with nobody's turn |
| **DEF116** (2026-07-27) | a verdict stamped `(round 2)` against `SUBMITTED: round 1` | lane deadlocked on `AUDIT_RETURNED` across a full fix-and-resubmit cycle; nothing logged |
| **DEF116's own lane file** (measured 2026-07-27) | `SUBMITTED: round 2` quoted inside the file's write-up **of this bug** | `watcher.sh` reported the lane at r2 while its live submission line said r3 |

**Why the previous guard failed.** DEF091's fix was *more arithmetic* — add `v_round`, compare
strictly — with no check that the two numbers were a possible pair, so the next mistyped stamp had a
new way to freeze a lane silently. And the anchoring rule existed in exactly one tool: `dispatch.sh`
required `^STATUS:` while `watcher.sh` left `SUBMITTED` unanchored, so the two boards disagreed about
what a line even meant, and neither disagreement was visible from either board.

**The invariant.** *A document that is both prose and machine state must define which lines EMIT
state, in one rule shared by every reader of it. And a derived state must reject input combinations
that cannot exist — loudly, as their own state — instead of rendering them as a normal one.*

**Enforcing check (DEF121).** The shared `TOK` / `emits()` / `last_match()` rule, byte-identical in
`orchestration/dispatch/dispatch.sh` and `orchestration/audit/watcher.sh`: a token counts only when
it opens a line, and only its line-opening occurrence supplies the value. Plus `BAD_ROUND` on both
boards when `VERDICT round > SUBMITTED round`, surfaced as hot by `dispatch.sh inbox` so it reaches
the Architect at the next work unit rather than waiting to be noticed.

---

## Adding an entry

1. Name the class, not the instance. Two instances minimum.
2. Record *why the previous guard failed* — that is the load-bearing part. "We forgot" is never
   the reason; find the structural one.
3. Name the executable check and where it runs. If none exists, say what would make one possible.
4. Link the instances in `docs/defect/def_list.md` / `docs/forward_planning/cr_list.md`.
