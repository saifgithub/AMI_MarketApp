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
| *external* — TradingAgents `47cbb32` → `4e7821d` | `get_verified_market_snapshot`: the market-analyst prompt ordered the call and the tool was never registered in the ToolNode, so the model reported it *"unavailable"* and skipped verification | 14 days | upstream, on the very feature meant to stop fabrication. Not ours to fix — recorded because it shows the class is structural, not an AMI-specific sloppiness, and their fix was an executor-registration regression guard of the same shape as `test_config_compose_parity.py`. See [CR167](../../forward_planning/CR167_tradingagents_upstream_drift/CR167_tradingagents_upstream_drift.md) §3.2. |

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
| **DEF135** | the background audit watcher process died | the audit queue stopped being served for ~10 h; every board still read healthy, because a dead watcher and an empty queue are byte-identical from outside — the checkpoint memo recorded "queue is EMPTY", true when written and wrong 2 h later, and every later report inherited it | none: no lane, no exit-3 timeout, no error, no non-zero status anyone saw |

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
- DEF135 → **`test_orchestration_watcher_contract.py`** (`backend/tests/unit/`). The watcher stamps
  a heartbeat each poll and clears it on either clean exit, so a stamp left behind means *stopped
  without saying so*; `watcher.sh state` says it and `dispatch.sh inbox` exits non-zero on it. The
  pin starts a real watcher, **SIGKILLs it**, and asserts the board says so — the only way to test a
  failure whose whole nature is producing nothing to assert on. Note the shape of the alarm: it
  fires on a *stale* stamp, never on an *absent* one, because a per-item spawned auditor never
  watches at all and alarming on that would be permanently red. **A loud signal that is always on
  is the same as no signal** — this pattern's own lesson applied to its own guard.
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

## P6b — A guard on deliberately-growing data pinned exact, not floored (blocks the next addition)

(Numbered P6b, not P7: it was added after P7–P9 were already cited across the
repo, and renumbering would have orphaned those references. New entries
continue at P10.)

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

## P9 — The verification procedure silently destroyed or hid its own evidence

Mutation testing is how this project proves a guard is real: break the code on purpose, watch the
test go red, restore. Both halves of that loop have now failed in a way that leaves a **green,
confident, meaningless result** — the tooling did not error, it just stopped measuring what the
operator thought it was measuring.

| | What the procedure did | Result |
|---|---|---|
| **DEF136** (2026-07-28) | ran the mutation matrix with `pytest -x` | pytest stopped at the first failure, so the operator never saw that only *one* of the two tests was firing. The loop-responsiveness test was **green against a real regression** and was reported as proven |
| **DEF127** (2026-07-28) | reverted each mutation with `git checkout -- <file>` while the fix was still **uncommitted** | `git checkout` cannot distinguish the mutation from the fix — both are uncommitted changes to the same file. It deleted the fix mid-matrix; every number after the first mutation was measured against partially-reverted code |
| **DEF130** (2026-07-28, same session) | the identical `git checkout` revert, ~20 minutes after writing "never do this" into DEF127's hand-off | the widened detector was wiped and had to be re-applied. **A written lesson did not survive one hour.** |

**Why the previous guard failed.** There was none, and the third row is the evidence that a prose
rule is not one — the operator who wrote the warning re-committed the error inside the same session.
This is the project's own *"prompt instructions are not controls"* rule (CR038) turned on its
verification tooling: the discipline lived in a hand-off document, which is exactly the place
CLAUDE.md says a control must not live.

**The invariant.** *A mutation run must not be able to lose the fix or hide a passing test. Concretely:
the fix is **committed before** any mutation is applied, so `git checkout` restores it rather than
deleting it; the matrix runs **without `-x`** so every test's result is observed, not just the first
failure; and the residual diff is **verified empty afterwards by reading `git status`**, not assumed
from the reverts having "worked".*

**Enforcing check.** `scripts/mutation_guard.sh` — refuses to apply a mutation while the target file
has uncommitted changes, refuses a pytest invocation containing `-x`, and diffs the tree afterwards
to prove the revert was total. Structural, so the rule survives the operator forgetting it.

---

## P10 — One expression, two obligations (and only malformed input can tell them apart)

A single expression is the **sole implementation of two independent duties**. When it fails it
fails both at once, silently — and because a *valid* input satisfies both duties simultaneously,
a test suite built from valid fixtures can never observe that they are coupled. The suite is
green, thorough-looking, and structurally incapable of seeing the bug.

| | The one expression | Duty A | Duty B | What the failure looked like |
|---|---|---|---|---|
| **DEF147** (2026-07-29) | `_STANCE_TAIL_RE`, end-anchored, both brackets required | *remove* the machine channel from the prose | *extract* stance / conviction / headline | a slightly-wrong tail was neither read nor removed, so "this agent stated no view" and raw `[STANCE: …` on the user's screen were **the same event**. 3 of 11 agents on live Alpha, 27% |
| **DEF149 (B)** (2026-07-29) | `proposed_value = (limit_price or 0.0) × qty` | *measure* the trade's size | *gate* whether the cap is evaluated at all | a MARKET order priced to 0, so the sector cap returned at its first guard. The cap never fired on a market buy for the life of CR026 |
| **DEF153** (2026-07-29) | the same expression, duplicated at the twin site | — | — | DEF149 fixed step 6b and left step 6 on the old formula. A 90% market buy passed a 50% single-name cap the same afternoon |

**Why the previous guard failed.** There were tests, and they were good tests — they were just all
*well-formed*. Every CR106 fixture was a correctly-bracketed envelope; every CR026 fixture was a
limit order. A well-formed input discharges both duties at once, so no assertion in either suite
could distinguish "it parsed" from "it was stripped", or "it was measured" from "it was checked".
Coverage was not the missing thing. **Adversarial input was.**

And DEF153 is the evidence that fixing one site is not fixing the class: DEF149's own repair
touched the three lines directly below the identical bug and did not see it, because each site
computed the shared value for itself.

**The invariant.** *Where one expression discharges two duties, at least one test must supply an
input that satisfies one duty and violates the other — and where the same value is needed at two
sites, compute it once and let both read it, so the sites cannot drift.*

**Enforcing checks.** Per instance, each an input that splits the two duties apart:

- `test_cr106_stance_envelope.py::test_an_envelope_that_parses_to_nothing_is_still_stripped` —
  parses to nothing, must still come off the prose (DEF147). Plus the leading/trailing/both-ends
  and malformed-tail fixtures alongside it.
- `test_def149_sector_cap_includes_cash.py::test_b_a_market_order_is_priced_and_therefore_checked` —
  an order the old gate valued at zero (DEF149).
- `test_def153_single_name_cap_market_order.py::test_the_two_order_types_agree_on_identical_economics`
  — the same economics routed two ways must get the same ruling (DEF153), backed by the pricing
  hoist that leaves only one site to change.

No static check can find the *next* coupling — the general control is a review question with a
concrete trigger: **when one expression is the only thing standing between two separate
guarantees, name the input that would satisfy one and break the other, and write it down as a
test. If no such input can exist, the duties are not actually coupled.** A structural version
would need a way to assert "these two obligations are discharged by different code", which the
language does not give us; hoisting the shared computation to one site is the closest available
approximation and is what DEF153 did.

---

## P11 — A rule fixed at the call site that reported it, in a codebase with forty call sites

A defect is filed, the fix is correct, and it is applied **where the bug was seen**. The class
survives untouched everywhere else, so the second report is not a regression — it is the same
defect arriving from one of the sites nobody edited. The tell is a fix whose diff touches one
file while the rule it enforces is a property of *every* file of that kind.

| | The rule | Where it was fixed | Where it still wasn't | What the second report looked like |
|---|---|---|---|---|
| **DEF073 → DEF148** (2026-07-23 → 07-29) | never show a user a raw exception | the Room convene's 5xx path got a typed exception + a friendly card | **39 other `catch (e) { error: '…: $e' }` sites** across 12 provider/screen files | a lesson load 404'd and printed `DioException [bad response] … RequestOptions.validateStatus … developer.mozilla.org` to the screen, under an app bar still reading "Loading…" |
| **DEF149 → DEF153** (2026-07-29) | price the proposal before gating on it | step 6b, the site the defect named | step 6, three lines above, computing the same value for itself | a 90% market buy passed a 50% single-name cap the same afternoon the sector cap was fixed |

**Why the previous guard failed.** There was no guard — there was a *fix*, and a fix is not a
guard. DEF073 produced good machinery (`ServerUnavailableException`, an interceptor, a friendly
card) and then relied on every future author noticing it existed. Thirty-nine authors did not,
including the one who wrote the interceptor. The rule was **enforced in one place and stated
nowhere**, which is indistinguishable from not existing.

The reason this is worth its own entry rather than folding into P10: P10 is about one expression
carrying two duties, and its remedy is adversarial input. This is about *N* expressions carrying
one duty, and no input finds it — the ninth site is not reachable from the first site's test at
all. What finds it is a **sweep**.

**The invariant.** *When a defect's rule is a property of a kind of code rather than of one
function, the fix is not complete until something enumerates every instance of that kind. Count
the sites before fixing one — if the count is greater than one, the deliverable is a sweep plus a
check that runs over all of them, not a patch.*

**Enforcing checks.**

- `mobile/test/friendly_error_test.dart::no caught object is interpolated into a user-facing string`
  — reads every `.dart` under `lib/state`, `lib/screens`, `lib/widgets`, `lib/features` and fails
  on `'…$e…'` in a string literal. It carries a **vacuity guard** (the sweep must still reach
  `lessons_providers.dart` and still see >40 files) and a **pin on its own regex** against the
  real DEF148 source lines, because a source-scanning guard that quietly stops matching is worse
  than none — it reads as proof.
- `test_def153_single_name_cap_market_order.py` plus the pricing hoist (see P10) — the structural
  half of the same lesson: leave one site to change, not two.

The general control is a counting question at file time, not at fix time: **"how many places
implement this rule?"** If the answer is not one, say so in the row, and make the fix a sweep.

---

## P12 — An enforced limit with no settable twin (the user cannot change what binds them)

**Symptom.** A number the system enforces against a user — a cap, a floor, a ceiling — is derived
from something the user set once (an onboarding answer, a classification), but there is no write
path back to it. The user is bound by a rule they never had a chance to choose and cannot revisit.
Nobody notices because the number still shows up correctly everywhere it's *read* — Settings
simply never sends the key, and the derivation quietly re-runs the same default every time.

**Mechanism.** A mandate field gets **enforced** (a deterministic check reads it) and **disclosed**
(an agent overlay or a screen narrates it) early, because those are the steps that make the
feature visibly work. **Settable** is a fourth step — a Settings row, a PATCH path, a re-validation
— that ships later, or not at all, because the first three already look like "done". CR101: the
sector-concentration cap (`concentration_tolerance` → a preset table) and the single-name cap
(`risk_score` → a preset table) were both enforced and disclosed on `main`, and neither had a write
path — Settings sent exactly three keys (`risk_score`, `max_drawdown_pct`, `compliance`) of the
CR's promised set, and the sole write path for the sector cap's input was a keyword match on
onboarding free text that could never re-run. Saiful's own ruling: *"a risk setting that a user
cannot change violates the user's rights."*

**Instances.**

| | The field | Enforced at | Disclosed at | Missing leg |
|---|---|---|---|---|
| **CR101-BE1** (2026-07-30) | sector-concentration cap | `safety_floor.py` sector-breach check | the allocation donut | settable — no PATCH key existed |
| **CR101-BE1** (2026-07-30) | single-name cap | `safety_floor.py` position-size check | Trader/PM overlay narration | settable — no PATCH key existed |

**Why the previous guard failed.** There was no guard — enforced + disclosed is the state that
*looks* finished from the outside (the number is correct, the block fires), so nothing red ever
pointed at the missing fourth leg. A review that only asks "does this number get enforced?" or
"is this number shown correctly?" passes both fields long before either becomes settable, because
neither question is actually about the write path.

**The invariant.** *A field feeding an enforced limit is (a) enforced, (b) disclosed in its own
units, (c) disclosed wherever the system narrates the rule to an agent or the user, and (d)
settable — or it is deleted. No third state:* a field cannot sit at "enforced + disclosed,
not settable" indefinitely; that state is exactly the rights violation Saiful named. The migration
corollary, just as load-bearing: making a previously-implicit field explicit and settable must not
silently move any EXISTING user's enforced value — the preset table becomes the fallback for an
unset field, never a recomputation that fires again on every read.

**Enforcing checks.**

- `test_cr101_be1_settable_risk_caps.py::test_every_enforced_limit_field_is_enforced_disclosed_and_settable`
  — asserts all four legs concretely for every derived subject: a breaching trade is rejected, the
  resolved value round-trips through its own resolver in its own units, the agent overlay narrates
  the same number, and a PATCH sets it. **DEF191 (2026-07-30):** this test originally enumerated
  its subject fields **by hand**, and failed its own purpose the very next CR — CR101-BE2 added
  five new enforced limits and the hand-written list picked up none of them, staying green.
  The subject list is now **derived**, not enumerated: `Mandate.enforced_limit_field_names()`
  (`app/schemas/mandate.py`) walks `Mandate.model_fields` for the `Field(json_schema_extra=
  {"enforced_limit": True})` marker, and a second test,
  `test_no_unmarked_numeric_field_is_referenced_by_enforcement_code`, heuristically cross-checks
  for a numeric field that got wired into enforcement code but never marked — a disclosed partial
  fix, not a closed one; see that test's docstring for exactly what it does and doesn't catch. A
  future enforced field now fails review the moment it's marked without a probe, or — best-effort —
  the moment it's referenced by enforcement code without being marked at all.
- `test_cr101_be1_settable_risk_caps.py::test_migration_no_existing_users_enforced_cap_changes` — the
  migration corollary, pinned against the actual pre-CR101 numbers (not this CR's own tables) for
  every `concentration_tolerance` × `risk_score` combination, so a regression in either preset
  table cannot mark itself green.

---

## P13 — Completion that lives only where nobody looks (silence means both "done" and "never started")

**Symptom.** A unit of work is finished, verified and pushed, and every board that is supposed to
show it reads as though it never began. Nobody notices, because the failure state is *silence* —
and silence is exactly what not-yet-started looks like. It surfaces only when a human re-reads a
board and thinks a number looks wrong, days later.

**Mechanism.** The producer and the reader are isolated from each other **by design**, and the
isolation is correct — it is the thing that makes parallel work safe. What is missing is a
*transport*, and because the producer's own view is complete and green, the producer has no signal
that anything is undelivered. CR052: a coder works in its own worktree on `lane/<ITEM>.<instance>`
and writes its hand-off and its §6 audit bridge **there**; `dispatch.sh` derives lane state from
files on `main`, and the auditor's watcher globs `orchestration/audit/cr/*.architect.md` on `main`.
Nothing moves the two files between them. So a complete, self-verified, pushed lane sits one branch
away reading as `ASSIGNED` with no status, and the independent gate never fires because the queue it
reads from is empty.

**Why the previous guard failed.** There was no guard — there was a *protocol line* telling workers
to land the hand-off on `main`, plus an Architect who hand-delivered it whenever it went missing.
Hand-delivery is the symptom, not the fix: it succeeds often enough to hide the defect, it depends
on the one person most likely to be busy, and recovering it badly costs real money (resuming a
worker to write a missing bridge re-pays for its whole accumulated context — a CR120 resume burned
a $3 cap that way). A rule that is enforced by someone remembering is not enforced.

**Instances.** CR120; DEF142 (`d5ac6614`); CR112 (`eab8470f`+). Three occurrences, each caught by
eye. Filed as DEF175.

**Enforcing check.**

- `dispatch.sh inbox` → `stranded_on_lane_branches()` scans local `lane/*` and `origin/lane/*` for a
  `STATUS: READY_FOR_*` hand-off or a `SUBMITTED: round N` audit bridge that this checkout does not
  have, and reports `STRANDED_HANDOFF` / `STRANDED_BRIDGE` with **exit 1**. It lands there because
  polling `inbox` after every work unit is already a standing rule, so the check runs where someone
  is already looking rather than where they would have to remember to look.
- Scoped to lanes not yet `DISPATCH: ACCEPTED`. The unscoped first version reported three lanes
  (CR087-BE, CR087-MOBILE, DEF114) that were all long since merged and closed — permanently red,
  never actionable, which would have trained the reader to skip the whole section. **The guard's
  usefulness and its noise floor are the same design decision.**

---

## P14 — A spec governed by a system that references it zero times

**Symptom.** A design or spec document reaches build-ready, is reviewed by several people, and
**never mentions the system it has to obey**. The work is careful and internally consistent, so
review finds nothing: reviewers check the artefact against its own goals, which it meets. The gap
is invisible until someone whose job *is* the system reads it, which happens after the design is
done, or after it has shipped.

**The inversion of P11.** P11 is a rule *enforced* in one place and *stated* nowhere, found by a
sweep. This is a rule *stated* in one place and *enforced* nowhere, and no sweep finds it — there
is nothing to sweep, because the offending document contains no instance of the thing.

| | The system | The spec that didn't cite it | What was actually wrong |
|---|---|---|---|
| **CR113 / CR106 §4.0** (2026-07-28) | *"hex is for marks and controls; large CTAs are rounded rects"* — recorded only in a decision log | `hex_button.dart` and the six CTA call sites | `HexButton` clipped unconditionally for months; Saiful found it from the outside — *"the larger buttons should all be normal rounded edge buttons"* |
| **CR109 → CR134** (2026-07-30) | `05_design/` — the hex rule, the family-colour rule, the honesty rules, the motion rule | the CR109 package: **13 documents, 5,297 lines, one reference**, in a lane draft | 20 screens drawn with **zero hexagons**, family hues spent on player titles and CTAs, derived values drawn as measured ones, mirrors rendered in warning colours |

**Why the previous guard failed.** CR113's remedy was to **move the rule to where its audience
reads** — out of the decision log and into `ami_hex_in_flutter.md`, beside the widget. That was
right and it was not enough. Relocating a rule improves the odds that someone consults it; it does
nothing when the author never asks the question at all. The CR109 package's failure is not that
its author looked in the wrong file — it is that **nothing in the pipeline made the design system
a thing you have to answer to.** §19 carried ~60 acceptance criteria, exhaustive on scoring,
integrity, restart, fees and feature cross-products, and **not one design criterion**. A CR's
acceptance list is its real specification; anything absent from it is optional in practice.

**The invariant.** *A spec that produces user-visible surfaces is not complete until its acceptance
criteria include the design system — as assertions, not as a reminder to read something. If the
acceptance list has no shape, colour, provenance or motion criterion, the design system did not
enter the room, regardless of how good the design is.*

**Enforcing checks.**

- **`mobile/test/widgets/cta_shape_test.dart`** is the existing bidirectional shape pin — CTAs have
  no clip, chips/avatars/track-button do. Every new surface family joins it. It is the right host
  because it already fails in *both* directions, so neither adding nor removing a clip is silent.
- **Design acceptance as assertions**, per-CR, in the CR's own §Acceptance: no colour literal
  outside `AmiColors`; no family hue on a non-agent concept; no agent mark changing hue; provenance
  by fill-vs-outline, never opacity and never amber; no numeric animation; every mono numeric run
  LTR-locked. CR134's `CR109_pnl_game_ami_cash/design_conformance_review.md` §3 is the first
  worked instance and the template for the next one.
- **The cheap upstream check, at CR-filing time:** `grep -rL "05_design" <cr-folder>/`. A CR that
  ships screens and never names the design system has not been reviewed against it. It costs one
  command and it is the only check that runs *before* the design exists.

---

## P15 — A check-then-INSERT with no `IntegrityError` handler (correct until there are two writers)

A function that SELECTs what exists and INSERTs the rest is correct in one process and raises in
two. The read-to-commit gap is the whole bug: two callers whose reads both land before either
commits will both INSERT, and one loses the unique constraint.

| | The write path | What happened / would happen |
|---|---|---|
| **`043995b0`** (first occurrence) | the earlier check-then-insert this repo already fixed | the same class, fixed at the site |
| **CR136 M03** | `portfolio_snapshot.py:192` | `except IntegrityError:` — *"a concurrent tick losing this race is a skip, not a failure"*. Written correctly the first time |
| **CR136 M01** (`DEF`-free, caught in audit) | `price_history.upsert_daily_bars` via `get_daily_series` | **no exception handling at all**. Proven by the auditor with two threads and a widened window: `sqlalchemy.exc.IntegrityError` propagates through `build_health_context` → `asyncio.to_thread` → the tiles route, whose own docstring commits to a 200 with an amber state rather than a 5xx |

**Why the previous guard failed.** There was none, and the reason it *looked* unnecessary is the
interesting part: an in-process throttle was holding the invariant by accident. The auditor measured
**0 races in 60 trials** on this stack, because `_last_fetch_attempt` is a per-process dict and one
uvicorn with no `--workers` means one fetcher. So the code reads as safe, tests green, and the
mechanism protecting it is not the one anybody wrote down. CLAUDE.md's stack decision for Beta is
**GCP Cloud Run** — instances share no dict — and on the day a second instance exists this stops
being a race and becomes the common case, since every single evaluation fetches SPY.

**The invariant.** *Any check-then-INSERT under a unique constraint handles `IntegrityError`
explicitly, and the handler says which outcome it chose (skip / retry / re-read). A throttle,
a lock, or "only one process runs this" is not a substitute — those are deployment facts, and
deployment facts change without the code changing.*

**Enforcing check (P15-GUARD).** `backend/tests/unit/test_p15_check_then_insert_guard.py`.
Source-read rather than runtime, for the same reason `test_cr136_dart_parity.py` is: the failure
only reproduces under concurrency a unit test cannot reliably stage, so the guard asserts the
*handler exists* rather than trying to lose the race on demand. Two rules:

1. **Call-site rule** — every `upsert_*` call inside a `get_session()` block sits inside a
   `try` with an `except IntegrityError`.
2. **Shape rule** — any function that reads a model AND `session.add`s that same model, where the
   model can actually collide (`UniqueConstraint`, unique `Index`, `unique=True` column, or a
   **primary key with no default** — the natural-key case). A uuid4-defaulted PK cannot collide and
   is excluded, which is what stops the rule flagging every append-only insert.

**The first version of this guard had only rule 1, and that was itself an instance of P11** — a rule
fixed at the shape that reported it. Matching `upsert_*` **by name** enforces a naming convention,
not this pattern: CR136-M01's round-2 auditor added an unguarded check-then-`session.add` that
simply was not called `upsert_*` and the guard passed (`AUD-M4`). Rule 2 is the fix, and on its
first run it surfaced **six** unguarded sites the name rule could not see — filed as **DEF220**,
pinned in `_UNREVIEWED` so a seventh fails the build, and deliberately not fixed blind: each needs
its own reachability answer, and wrapping all six in `except IntegrityError: pass` would satisfy
the guard while answering none of them.

**Corollary worth keeping:** *a guard that matches on a NAME tests that people followed a
convention. A guard that matches on the SHAPE tests the thing you actually care about.* When both
are cheap, write the shape one.

---

## P16 — A prose pattern validated only against the examples that motivated it

**Instances.** DEF147 (the stance envelope: one regex tuned to the shape the *prompt asked for*,
failing on the shapes the model actually produced — measured at 27% of agents on live Alpha the day
it shipped). DEF231 → its round-1 audit MAJOR and then DEF234 (a directional-instruction check
built from the 2 live verdicts that motivated it; it annotated a level in *"reclaim its margin
story before we'd pay $52.30"*, and once that was fixed, parsed `$1,073.46` as `$1.00` and told the
user the price was "107900.0% ABOVE" it).

**The class.** A pattern that reads a claim out of LLM prose is written from the handful of
examples that revealed the need for it, tested against those same examples, and shipped. The
positive cases are real; the *negative* cases are invented by the same person who wrote the pattern,
from the same mental model, so they probe the dimension the author was already thinking about and
no other. DEF231's negative cases all had the verb immediately followed by its own `$` level — they
tested the *direction* logic exhaustively and the *extraction* logic not at all, because extraction
felt like plumbing.

**Why the existing guards did not catch it.** Three layers ran, and all three shared one input set:

- *The build* — reasoning from the instances.
- *The tests* — written from the instances.
- *The revert-proof mutation pass* — nine mutations, all RED. **This is the load-bearing lesson.**
  Mutation testing proves a test suite is sensitive to changes in the code *as written*. It cannot
  detect a case nobody asserted on: a false-positive class produces no failing test under any
  mutant, because no test exercises it, so no mutant dies. A green mutation table is strong
  evidence the tests are not vacuous and **no evidence at all** that they are complete. It had
  been read here as the latter.

The independent auditor caught it — and the reason it could is that it generated **new inputs from
a different distribution** instead of re-checking the author's. That is the only step that added
information, and it is the property to reproduce mechanically rather than rely on.

**The guard.** Any pattern that extracts a claim or a number from LLM-authored prose must be swept
over the **real corpus** before it ships, not only over authored examples. The corpus exists and is
free: `room_runs.verdict->>'reason'` (946 real PM verdicts as of 2026-08-08), plus the `transcript`
JSONB for agent turns.

```bash
ssh melehost "docker exec ami_postgres psql -U postgres -d ami_trade -t -A -c \
  \"SELECT replace(verdict->>'reason', chr(10), ' ') FROM room_runs \
    WHERE jsonb_typeof(verdict)='object' \
      AND coalesce((verdict->>'overridden_from_llm')::boolean,false)=false\"" > reasons.txt
# then run the pattern over every line and READ every extraction.
# NOTE: no `length(...) > 40` filter — an earlier sweep carried one and
# undercounted the corpus 946 vs 949. Match this query exactly.
```

Read every extraction, not the count. On DEF231 the sweep took under a minute, returned 126
extractions, and both defects were visible on sight: one extraction whose `$` figure was not the
verb's object, and one truncated mid-number. Where a pattern's failure is *silent by design* (a
miss), also diff the extraction set against the previous pattern's — DEF234's markdown hole was a
coverage loss introduced by the fix for the MAJOR, and only the before/after diff showed it.

**The two methods are not interchangeable — this is the part that took three audit rounds to get
right.** A corpus sweep and adversarial construction fail on opposite classes:

| | corpus sweep | adversarial construction |
|---|---|---|
| **coverage** bug (real prose the pattern should match and doesn't, or mis-parses) | **finds it** — DEF234's `$1,073.46 → $1.00` and the markdown hole were both visible on sight | usually misses — you don't invent the shape you forgot |
| **false-positive** class (prose the pattern matches and shouldn't) | **cannot find it** unless the corpus happens to contain the shape | **finds it** — all three DEF231 MAJORs came this way |

The auditor's round-3 note is the precise statement: *nothing in the corpus asserts that an
extraction is wrong, so nothing about reading it looks wrong either, unless the reader already
knows to check.* DEF231's round-2 MAJOR — a sentence naming two levels, where the second level's
price was attributed to the first level's verb — **does not appear once in 949 real verdicts**. The
sweep read all 121 extractions and none of them exhibited it. Only a constructed sentence did.

So the guard is **both**, always, for any check that reads a claim out of prose:

1. **Sweep the corpus** and read every extraction — catches coverage bugs.
2. **Construct adversarial sentences** that satisfy the pattern's grammar while violating its
   intent — catches false-positive classes. Ask specifically: *what else could sit where my target
   sits?* For a level-reference pattern the answer was "a different level" and "a non-price noun".
3. **Diff the extraction set against the previous version** — a fix's own coverage loss is
   invisible in either set alone. DEF234's markdown hole showed up only as 126 → 119.
4. **Re-sweep after the fix and assert the count is unchanged** where it should be. DEF231's
   round-4 fix had to leave all 121 real extractions intact while killing three constructed ones;
   a tightening that silently zeroed the check would pass every negative test.

**Watch the harness too.** The round-4 sweep first reported **0 of 121** extractions — a generator
was passed where a tuple was needed and exhausted after the first line. The number was implausible
enough to catch, which is the only reason it was caught. A measurement that would have "confirmed"
a wrong conclusion is the same failure as the defect being measured.

**Corollary.** *A mutation table answers "would my tests notice if I broke this?". It never answers
"did I think of this?". A corpus answers "what does the world actually send?". It never answers
"what else would my pattern accept?". Three different questions, three different instruments — and
the third one only an adversary asks.*

**Amendment 1 (AT:R66) — the generality law, and why it is the root cause here.** DEF231's row had
specified the correct design in the sentence that justified filing it: the level is *"already a
structured number the verdict carries… so a comparison is available without parsing free text"*. A
general prose parser was built instead, and every defect that followed came from the gap:

| finding | captured figure | a structured level of that run? |
|---|---|---|
| r1 MAJOR | `we'd pay $52.30` | no |
| r2 MAJOR | a second sentence's level | yes — but not the verb's |
| **DEF234 — reached live Alpha** | `$1.00` truncated out of `$1,073.46` | no |
| r4 MINOR | `break above near the recent low of $X` | no |

*A prose pattern's false-positive surface is proportional to how much wider than the structured
answer it is.* Three of the four become unreachable once the figure must match a level the run
holds; the fourth genuinely needs grammar, which is the point — **both halves are usually needed,
and the prose half must cover only what the structured half cannot.** Building the prose half first
means it covers everything. **DEF235** is the same shape one function over (`\bsize\b` + a number
matched *"a MEDIUM size entry at $188.62"* and published a 63×-overstated drawdown contribution),
and **CR106 B1** is this lesson learned once already and not generalised. Now a convention rule:
[`coding_conventions.md` § "Reading a claim out of agent prose"](coding_conventions.md) (CR144).

Measured, so the trade is not theoretical: narrowing DEF231's check to the run's own levels and then
spending the safety it bought on recall (an offline LLM sweep that found three whole verb families)
took the corpus from **121 figures extracted** to **365 extracted, 246–277 of them matched to a
structured level and actually checked**. Narrowing did not cost coverage; it is what made tripling
coverage affordable, because adding three verb families to the general check would have tripled its
false-positive surface too.

**Amendment 2 (AT:R66) — never select the guard's corpus with the thing it guards.** The P16 fixture
originally selected verdicts carrying a `$` **and a directional verb stem**. That made the guard's
own population a function of the pattern under test: broadening the verb set moved the count for two
reasons at once, so the diff was unreadable — and far worse, a **narrowing** would have shrunk the
population in lockstep and **hidden its own coverage loss**, which is the single failure the fixture
exists to prevent. Selection must depend only on the raw property that makes a row *capable* of
exercising the pattern (here: it contains a `$`). Fixed at 811 rows.

**Amendment 3 (AT:R66) — two more harness bugs, and how they were caught.** Measuring the narrowing's
coverage cost needed each run's own levels reconstructed from history. Two errors, both of which
would have produced a confident wrong number:

1. `auto_adjust=False` against an app that calls `.history()` with yfinance's default (`True`).
   Every dividend payer's reconstructed low sat above the level the run held, which read as coverage
   loss.
2. The 52-week range omitted from the reconstruction entirely — **understated retention by 26
   points**, and it is the level the PM quotes most.

Neither was caught by a number looking wrong. Both were caught by the **shape of the unmatched
list** — the misses clustered just under the reconstructed support, and a systematic offset is a
harness signature, not a finding. Read the rejects, not just the count; that is where the harness
confesses.

**Amendment 4 (AT:R66, DEF244/DEF245) — when the guard is over prose *we* author, stop matching and
enumerate.** Three audit rounds, each defeated by ordinary synonyms: a **vocabulary list** (verbs,
then nouns) fell in round 1; **structural rules** (quoted-`%`, the lexical root `siz`) fell in round
2 to an unquoted percentage and to sizing bullets containing no `siz` substring. The round-3 fix was
not a better pattern — it was **abandoning matching**. The 12 agent prompts contain *zero* literal
percentages after the fix, so the invariant became "stays zero": no anchor, nothing to walk around.
The two researcher prompts are additionally pinned by a whole-file SHA-256, so an edit is a review
prompt rather than something silently accepted. 21 of 21 auditor constructions caught.

The distinction that makes this a rule rather than a mood: **enumerating a closed class is complete;
enumerating an open one never is.** English number words (one…twenty, the tens, hundred) are closed,
so adding them was not a return to the lists that failed twice. Synonyms for "decline" are open, so
listing them can only ever be theatre. And a MINOR from the same round: the first pin covered one
`## Output style` section, and the auditor simply moved the offending line to `## Role`. **The set is
the file.**

**Amendment 5 (AT:R66, DEF247) — a test that encodes an unmeasured hypothesis becomes a lock on the
fix.** P16's root cause is negative cases invented by the pattern's author from their own mental
model. DEF147 did exactly that in a *test*: `test_a_stance_line_mid_argument_is_prose_not_the_machine_channel`
asserted that a whole line opening with `STANCE:` mid-turn is "an agent quoting the format", so the
strip stayed bounded to the first and last non-blank lines. Measured three weeks later across all
**11,057** stored agent turns: 15 such lines exist mid-turn and **all 15 are the machine channel,
zero are a quote** — each preceded by one conversational opener the model writes despite the prompt.
The invented negative case had never occurred; the shape it excluded had been leaking raw machine
syntax to users since 2026-07-29, and fixing it required *reversing an existing green test*, which is
the shape of a bad change and cost an extra round of scrutiny to justify.

So: an assertion about **what a model will or will not emit** is a measurement, not a premise. Either
cite the corpus in the test's docstring, or write the test against the mechanism (here: the regex
anchor that actually excluded mid-sentence asides at every position) rather than against the
behaviour you are guessing at.

---

## P17 — A read-sounding command that writes tracked files

**Instances.** (1) `scripts/i18n_coverage_report.py` — a command named `..._report.py` rewrote 8
tracked content files on every run, stripping `ar`/`ms` from 7 lessons' `locale_versions`. Run as a
throwaway diagnostic during an unrelated CR (AT:R66, 2026-08-09), it dirtied another track's domain
on the shared checkout and **blocked `/promote-to-alpha`**, whose preflight requires a clean tree —
correctly, because the rsync ships the whole worktree, so the stray edits would have deployed.
(2) `scripts/i18n_verify_lesson_translation.py` — same shape, writes the tracked
`content/i18n/lesson_confidence_log.json`. Lower blast radius only because it makes LLM calls, so
nobody runs it casually.

**Why the previous guard failed.** There *was* one, and it was prose. The module docstring opened
with *"Read-only reporting except for one deliberate side effect."* The footgun was accurately
documented and completely unenforced — the reader has to notice the caveat *before* running the
thing, which is precisely backwards. This is CR040's rule applied to tooling rather than to agents:
**prose is not a control.** The name is what an operator acts on, and the name said `report`.

The shared-checkout era makes the cost asymmetric. A stray write is no longer just noise in your own
diff — it lands in a lane you do not own, under a tag that is not yours, and the promotion gate that
catches it fires far from the cause.

**The guard.** Any script whose name reads as observational (`*_report`, `*_check`, `*_verify`,
`*_status`, `*_coverage`) must be **read-only by default** and mutate only behind an explicit
`--write` / `--apply` flag, printing what *would* change otherwise. Fixed for instance 1: bare
`python scripts/i18n_coverage_report.py` now writes nothing and ends with
`[read-only] … Nothing was modified.`; `--write` restores the old behaviour for the i18n lane.

**Executable check.** No repo-wide test yet — the honest statement is what would make one possible:
a test that, for each script matching those name patterns, runs it bare in a temp clone and asserts
`git status --porcelain` is unchanged. That is cheap for the pure-Python ones and impossible for the
LLM-calling ones without a stub, which is why instance 2 is flagged rather than fixed here.

**Corollary for agents.** Do not run another lane's tooling to "just check" something. Read the file
instead — a script may write, and the name will not tell you.

---

## P18 — A feature proven on the builder, never on the caller that must feed it

**Symptom.** A function takes the datum as a parameter and does the right thing with it. Its tests
call that function directly and pass the parameter themselves. Every one is green, and the feature
has never worked in production, because the one call site that matters never passes the argument —
or passes it only on some of the paths that need it. The test suite proves the *builder*, and says
nothing about the *call graph*.

**Instances (both AT:R66, 2026-08-08/09, both surfaced by reading real assembled prompts).**

| | Proven | Never exercised | What the user got |
|---|---|---|---|
| **DEF238** | `build_room_messages(sector_weights=…)` renders CR026's PM-only sector-allocation line correctly; tested that way for its whole life | `_stream_pm_response` never passed `sector_weights` | **18 of 18** epoch PM prompts read *"sector allocation: no open positions yet (0% in every sector)"* while **8 of 18** listed real holdings in the same prompt. The feature was dark from the day it shipped |
| **DEF241** | the per-debator computed drawdown figure, tested against `build_room_messages` with `agent_size_pct` passed by hand | `build_room_messages` gates the whole reference-position block on `phase in ("RISK", "VERDICT")` | shipped `fixed` while reaching **3 of the 5 agents named in its own evidence table** — Bull Researcher (RESEARCHERS) and Research Manager (SYNTHESIS) were byte-identical before and after. Caught by the independent auditor, not by the suite; the remainder became DEF244 |

**Why the previous guard failed.** Not "we forgot a test" — there were tests, and they were the
*right* tests for the unit. The structural reason is that a keyword argument with a default is a
**silent contract**. `sector_weights=None` and `agent_size_pct=None` are legal, produce sane-looking
output, and are indistinguishable from "this user genuinely has no positions". So the failure mode of
a caller that forgets is not an exception, a log line, or a red test — it is a **plausible sentence
in a prompt**, which is exactly the shape nothing downstream can catch. This is P2's silent-confident-
degradation applied to an internal call boundary rather than to a provider.

DEF241 shows the second half of the class, which is worse: the caller *was* updated, so the naive
"does the runner pass it?" check would have passed. What was never surveyed was **which callers
exist** — the phase gate meant two of the five target agents could not receive the datum on any code
path. Proving one caller is not proving the call graph.

**The guard.** Any change that adds a datum to an assembled prompt (or to any string a model reads)
owes **one test that drives the real entry point** — `RoomRunner.run()`, not `build_room_messages` —
captures the prompt the gateway actually received, and asserts the datum is in it **for every agent
that is supposed to have it**. Enumerate the intended recipients explicitly and assert the count; a
test that checks "the PM got it" cannot notice that four others were supposed to.

Corollary, from DEF241: when a fix names N agents in its own evidence, the acceptance test asserts N,
not "at least one".

**Executable check.** `backend/tests/unit/test_def241_def243_debator_arithmetic_and_stance.py::
test_def241_the_runner_actually_hands_each_debator_its_own_size` — stands up a capturing gateway,
drives the real `RoomRunner.run()`, and asserts the three debators receive three *different* figures.
Its docstring names DEF238 as the reason it exists. Verified RED without the runner change (no
debator prompt contains *"the size YOUR role argues for"* at all).

**Rule for new code.** A default-valued kwarg on a prompt builder is a place a feature can go dark
without anything turning red. Adding one ⇒ add the end-to-end test in the same commit, or give the
parameter no default so the compiler finds the callers for you.

---

## Adding an entry

1. Name the class, not the instance. Two instances minimum.
2. Record *why the previous guard failed* — that is the load-bearing part. "We forgot" is never
   the reason; find the structural one.
3. Name the executable check and where it runs. If none exists, say what would make one possible.
4. Link the instances in `docs/defect/def_list.md` / `docs/forward_planning/cr_list.md`.
