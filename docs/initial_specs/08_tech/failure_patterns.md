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
| **DEF328** | `GOOGLE_API_KEY` — a real, paid Gemini key set under a name nothing reads (`google_ai_api_key` / `GOOGLE_AI_API_KEY` is what config, compose and the gateway all use) | hours; caught before the promotion that would have shipped it | asking what the key would actually do before assuming it worked |

**The third instance is a different link, not a failed guard — which is why it is a point fix and
not a Dilemma (CR185).** The chain from a value on the Mac to a feature running in Alpha has four
links, and `test_config_compose_parity.py` only ever guarded the second:

`infra/alpha.env` name → `${VAR}` compose interpolates → `Settings` field → running container

DEF038 and DEF063 both broke link 2. **DEF328 broke link 1**, which had never been guarded at all,
because `infra/alpha.env` is gitignored and therefore invisible to every check that reads the repo.
Nothing failed twice and no framing is suspect; a link was simply uncovered. It is covered now, and
all four links have an enforcing check — see below.

**Why the previous guard failed.** After DEF038 a comment was written *in the compose block
itself*:

> `# OIDC audiences (DEF038: these lived in .env but were never forwarded here…)`

DEF063's two keys should have been added roughly seven lines below it. The comment failed for two
structural reasons, both worth generalising:

1. **Descriptive, not imperative.** It explained a past bug about two specific keys. It never
   stated a rule binding on every future key.
2. **Nothing executed it.** A comment only fires if a human opens that file at that moment.
   CR024's work lived in `config.py` and `social_context.py` — compose was never opened.

**Enforcing check (CR040), one per link.**

- **Link 1 — the env file's names (DEF328).**
  `backend/tests/unit/test_def328_alpha_env_names_are_read_by_something.py` — every `NAME=` in
  `infra/alpha.env` must be either a `Settings` field or a `${VAR}` compose interpolates. Derived
  from both sources, never listed, per CR175 F3. Client-side keys (RevenueCat's Flutter SDK keys)
  are excused in `_CLIENT_SIDE` **with a reason that must name a real consumer** — "unused for now"
  is precisely the state the test exists to surface. Verified red against the real pre-fix file
  (`['ONESIGNAL_APP_ID_x', 'GOOGLE_API_KEY']` → `[]`); because the env file is gitignored the corpus
  half skips off the promoting machine, so the DEF328 name pair is *also* asserted on synthetic
  input against the real compose file, which runs everywhere.
- **Link 2 — compose forwarding.**
  `backend/tests/unit/test_config_compose_parity.py` — every `Settings` field must be forwarded
  in compose's `api-alpha` env block or listed in `_NOT_FORWARDED` **with a reason**. Fails at
  commit time, on the Mac, in the normal suite. Verified red against the real DEF063 state before
  the fix landed; it names DEF063's two keys explicitly so that exact regression can't return
  quietly.
- **Link 3 — Settings coverage.** `backend/tests/unit/test_cr175_config_coverage.py` — the
  config-check report is derived from `Settings.model_fields`, so a field added tomorrow is covered
  the day it is added rather than when someone remembers.
- **Link 4 — the running container.**
  `GET /v1/admin/config-check` — reports each gate's live state in-container (booleans only,
  never secret values). Turns "is Adanos on?" into one curl.
- `/promote-to-alpha` — calls config-check post-deploy and fails loudly on a key that is
  populated in `infra/alpha.env` but dark in the container.

**Rule for new code.** New env-driven setting ⇒ compose env block + the parity test passes. If
the container genuinely never needs it, say so in `_NOT_FORWARDED`. New *value* in
`infra/alpha.env` ⇒ spell the name exactly as `Settings`/compose spell it; the link-1 test tells
you the same thing in under a second if you don't.

**And the operator-side rule the whole pattern keeps re-teaching.** In all three instances the
evidence that the feature was live was that someone had provisioned the key. Provisioning is not
activation. A new integration is not on until a call has been made and a response read (P24) — for
DEF328 that was a `curl` returning HTTP 200 and a real stream through our own provider class,
neither of which takes longer than reading the config file you were about to trust.

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
| **DEF182** | `SECRET_KEY` rotated, or `ALPACA_ENCRYPTION_KEY` changed without a rollover | `decrypt_secret` returned the **ciphertext itself** on `InvalidToken` or a missing key, so the Alpaca client sent `gAAAAA…` as an API key; and with the dedicated key unset — the default, and the state Alpha ran in — the cipher key was silently derived from `SECRET_KEY`, so one secret both signed bearer tokens and protected broker secrets | a `warning` log line, and only at the moment of failure; the app then behaved as though the user's credential were simply wrong |

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
- DEF182 → **`backend/tests/unit/test_secret_crypto.py`** (19 tests). The fix is the direction of the
  fallback, exactly as lesson 2 says: `decrypt_secret` now **raises** rather than returning ciphertext,
  and `encrypt_secret` **raises** rather than reusing `SECRET_KEY` or storing plaintext. Both are
  mutation-proven — restoring `return stored` reds four tests, and neutering the strict-env branch reds
  the fifth. Note where the loudness stops: `EncryptedString.process_result_value` catches the raise and
  yields `None`, because these columns hang off `User`, which `get_current_user` loads on **every**
  authenticated request, so a raise reaching the caller would convert one unreadable credential into a
  total account lockout. `None` is the honest degradation (it is precisely "not linked", which every
  call site already handles) and the ERROR log carries the diagnosis. *Loud where an operator reads it,
  safe where a user lives* — the alternative, a 500 on every request, is this pattern's own "a loud
  signal that is always on is the same as no signal" from the other side.
  **Round 2 added the half that is easiest to re-break** (audit AT:U66): removing the *automatic*
  fallback to `SECRET_KEY` did not stop an operator setting `ALPACA_ENCRYPTION_KEY` **equal to** it
  by hand, and that state is worse than the original bug rather than the same — the row is stamped
  `enc::v2::`, whose documented meaning is "rotating `SECRET_KEY` no longer touches this ciphertext",
  and the `SECRET_KEY`-derived key opens it. The pre-fix state at least labelled such rows `v1`
  honestly. `_reuses_secret_key()` refuses it at the **write** site and drops it at the **read** site,
  covering `ALPACA_ENCRYPTION_KEY_PREVIOUS` too; `v1` is deliberately left alone, because its marker
  makes no false claim. **The mutation that matters here is the third one**: a refusal is the one fix
  shape where *over*-refusing passes every test written for it, so widening the check to "refuse
  whenever `SECRET_KEY` is set" is mutated toward on purpose and reds
  `test_a_dedicated_key_that_is_actually_dedicated_still_works`. If you are simplifying this check,
  that test is the one telling you not to.

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

## P18 — third, fourth and fifth instances, and the Dilemma they triggered (AT:R74, 2026-08-24)

The rule above is a **discipline**, and disciplines are what this class defeats. It happened three
more times **inside CR172 alone**, each found by a human reading code, each after the covering tests
were green:

| | Proven | Never exercised | What the user got |
|---|---|---|---|
| **`OptionProposalTicket`** | a fully defined, fully tested response model | a repo-wide search returned exactly one referencing file: its own test. No service ever called the options API | a live, green, unreachable surface |
| **DEF363** | the Dart model read `greeks_reason`; the server sends `greeks_not_evaluated` | **both** covering tests supplied the wrong key themselves, so both were correct about their own half and neither compared the halves | the reason a greek was unavailable never rendered |
| **DEF365** | `SimPortfolio.fromJson` read `options` and a whole portfolio card rendered from it | `PortfolioSnapshot` had **no `options` field at all**. 4 backend tests drove the builder; 13 Flutter tests built their own fixture maps; **17 tests, none consuming the other side's output** | a user could consent to an option structure and then not see it |

`CLAUDE.md`'s third-occurrence rule fired. **Dilemma [`ISS002_WIRE_CONTRACT_UNPROVEN`](../../dilemmas/ISS002_WIRE_CONTRACT_UNPROVEN/)**
was convened on Saiful's ruling, three contributors answered blind, and the
[verdict](../../dilemmas/ISS002_WIRE_CONTRACT_UNPROVEN/VERDICT.md) is implemented as **CR208**.

**The deeper reading, from the Dilemma.** The suite cannot see across the wire because **every test
in this repository asserts against an input it authored itself** — a Python test builds a Python
object and checks the builder; a Dart test builds a map and checks the parser. Both are testing a
function against its own imagination. The wire is the only place one side's *output* is the other
side's *input*, so it is the only place this style of testing structurally cannot reach. Anything
that compares two *descriptions* of the contract (schemas, declared pairs, an IDL) is still two
imaginations and will drift the same way.

**Interim executable check.** `backend/tests/unit/test_wire_contract_parity.py` — asserts a
**declared pair** of one Dart class and one Pydantic model agree on key names. Proven to catch both
DEF363 and DEF365. Its measured limit is why it is interim: an undeclared sweep reported **~250
orphans, almost all false**, because this codebase serialises heavily through untyped `list[dict]`
that no schema-based check can see inside. Growing it requires a human to declare each pair — the
same manual act that failed three times.

**The check that replaces it — SHIPPED as CR208 (AT:R74, 2026-08-25).** This is P18's enforcing
check, and the house rule says an entry without one is not done.

`backend/scripts/wire_contract/` + the capture hook in `backend/tests/conftest.py`, run by
`scripts/promotion/preflight_suite.sh` immediately after the suite it reads from. It auto-discovers
(endpoint → Dart class) pairs by parsing `mobile/lib/services/api/api_client.dart` — the single file
every wire call passes through — captures every JSON response any test's `TestClient` receives via
one patch on `TestClient.request`, and diffs each class's read keys against the bodies actually
observed. **Nothing is declared by hand**, which is the whole point: manual declaration is the
mechanism that failed three times.

Measured on the shipped version: **85 surfaces, 1,311 responses captured across 5,303 tests,
45 PASS / 0 FAIL / 40 UNVERIFIED**.

Three things about it are worth knowing before trusting it:

- **A branch-conditional key is not a missing one.** Observation proves presence, never absence. The
  prototype's single reported FAIL (`SimSubmitResult` reading `order`) was a **false positive** —
  `sim.py` emits `order` on the `resting: True` branch only, and none of the 21 captured submissions
  rested. A key absent from every capture is a FAIL only when the server source shows no branch that
  could emit it; otherwise it is `UNVERIFIED`. Without this the guard's first output is a false
  alarm, and a guard that cries wolf gets ignored.
- **`UNVERIFIED` is ratcheted, not failed outright.** 40 of 85 surfaces are unverified today
  (DEF367). Failing on all of them would ship a gate that is red on day one, and a gate whose
  failing state is its normal state teaches the operator that firing does not mean stop — paid for
  three times already (DEF277, the tree gate, DEF200's own vacuity guard). So today's set is
  enumerated by name in `unverified_baseline.json`, a **new** unverified surface fails, and the
  baseline may only shrink. Nothing passes silently; the debt has names attached. A **FAIL is never
  ratcheted** — that is a live disagreement, not coverage debt.
- **Layer 3 finds nothing today, and that is recorded rather than hidden.** All 132 Dart classes
  with a `fromJson` have a caller. The verdict claims this layer catches `OptionProposalTicket` "by
  construction"; it cannot — that is a Flutter *Widget* with no `fromJson`, so no wire-model scan
  could reach it. The layer is still cheap and covers a real class, but not for the stated reason.

The 40 unverified are [DEF367](../../defect/def_list.md) — **47% of wire surfaces have no
route-level test**, which is the precondition for every instance above.

**Rule for new code, amended.** A key read on one side of the wire and written on the other is a
silent contract with no home in either suite. `UNVERIFIED` — *no test exercises this route* — must
be a hard failure, never a silent pass (DEF169/DEF190). And observation proves presence, never
absence: a key missing from every captured response is a `FAIL` only when the server source shows no
branch that emits it. The winning prototype's single reported failure was exactly this mistake —
`SimSubmitResult` reads `order`, and `sim.py:726` does send it, on the `resting: True` branch only.

---

## Adding an entry

1. Name the class, not the instance. Two instances minimum.
2. Record *why the previous guard failed* — that is the load-bearing part. "We forgot" is never
   the reason; find the structural one.
3. Name the executable check and where it runs. If none exists, say what would make one possible.
4. Link the instances in `docs/defect/def_list.md` / `docs/forward_planning/cr_list.md`.

---

## P19 — A new measurement contradicts a control already shipped, and the measurement is believed

**Symptom.** A metric is built to check something, and it fires. The number is alarming, plausible,
and precisely wrong, because the metric's *own* assumption is broken — not the corpus. The tell was
available at the time and nothing consulted it: **something this codebase already ships had computed
the same quantity and disagreed.** The new instrument wins the argument purely because it is the one
being read.

**Instances (three, two of them in a single session).**

| | The metric said | The truth | The control that already disagreed |
|---|---|---|---|
| **DEF279** (AT:R6x) | M7 date accuracy: **13.4%** mismatch | **0%** — all eleven hand-read, none a model error | the fact sheet's own as-of anchor, which the pattern was matching against incorrectly |
| **DEF302 v1** (CR179 Leg 5) | derived-% inconsistency **26.5%**, then 12.5% after one correction | **7.5%** (3/40) | `_annotate_rr_against_levels` had printed *"entry $173.40 / stop $164.70 … 23.9% upside vs **5.0% downside**"* **in the same prompt the checker was reading**, confirming the −5% the checker called wrong |
| **CR179 Leg 5 social** | fabricated community attribution **20.5%** | **0%** — every hit describes the supplied Reddit aggregate | the fact sheet's own disclosure line, *"Reddit only — no Twitter/X, StockTwits, Google Trends, or Discord data exists"* |

**Why the previous guard failed.** P16 ("a count nobody read is not a measurement") already required
hand-reading samples, and in all three cases samples *were* printed. Hand-reading is necessary and it
is **not sufficient**: it catches a metric that matches obvious nonsense, but not one whose hits are
individually plausible. Every flagged claim above looked like a real error in isolation — `$164.70` is
genuinely not 5% below `$203.62`. What distinguishes error from artefact is not the sample, it is the
**referent**, and a reader checking samples one at a time has no reason to question the reference the
metric silently chose. DEF302 v1 was filed in the same document that had, two sections earlier, written
*"a metric's first number is a hypothesis about the metric"* — so awareness of the class does not
prevent it either. The structural reason is that a new metric and an existing control are never
compared: they live in different files, run at different times, and nothing joins them.

**The check.** Before any new measurement is published or filed as a defect:

1. **Ask what already computes this.** Search for a shipped control over the same quantity —
   `_annotate_rr_against_levels`, `_verify_and_annotate_geometry`, `drawdown_contribution`,
   `_asymmetry_line`, the fact sheet's own tagged fields. If one exists, **run the new metric against
   the control's output on the same rows.** Disagreement means the new metric is the suspect until
   proven otherwise — it is the one without a production track record.
2. **Pin every referent explicitly.** A percentage is meaningless without the pair it was measured
   from. Where the metric assumes a reference (close, entry, cap, supplied aggregate), assert that
   assumption against the row rather than defaulting it — `entry` is not `last close` whenever a limit
   order exists, which is most of the time.
3. **Publish the excluded count beside the scored count.** All three instances were found by asking
   what the metric *dropped*, not what it caught.

**Executable form.** `backend/scripts/cr179_leg5_pct_check.py` carries the corrected shape: it prints
`scored / inconsistent / excluded`, names why each exclusion happened, and its docstring records the
26.5% → 7.5% correction rather than presenting the final number as if it were the first. Any future
prose-measurement script belongs beside it and should be read before writing a new one.

---

## P20 — A test asserts a string the app stopped rendering, and only a device run can tell

**Symptom.** A UI test hard-asserts visible copy. The key it copied that copy from still exists in
every ARB and still generates into `app_localizations*.dart`, so every static check agrees the string
is real. No screen references it. The assertion is unsatisfiable, and it fails on the device as
*"the app is not showing X"* — a sentence that sends the reader to the app.

| | The string | What it actually was | How long |
|---|---|---|---|
| **DEF250** | `tabFloor`, `tabPortfolio` | live ARB keys referenced by no screen; the nav renders `floorTabUpper`/… | ~2 weeks |
| **DEF307's run** | `floorConciergeHeading` = "AMI CONCIERGE" | same; the Floor redesign moved the Concierge access point into `floorOmniboxHint` | unknown — found by the first Android run of CR162 |

**Why the previous guard failed.** DEF250's guard was written to catch DEF250: it compares the four
tab labels against the four ARB keys the nav renders, and separately pins `tabFloor`/`tabPortfolio` by
name as known-dead. Both are assertions about *two specific keys*. The class is "any asserted string
whose key no screen renders", and a check that enumerates yesterday's instances cannot see tomorrow's.
The second instance was a different key on a different screen, so it walked straight past.

The deeper reason the class is invisible: **existence in the ARB is not the property that matters, and
it is the only property anything checked.** Flutter's generated localizations define every key by
construction, so a dead key has a definition, a getter, and three translations — it looks more alive
than a live one. Grepping "is this string real?" returns yes.

**The invariant.** *A test may only assert copy whose ARB key is referenced by a non-generated file
under `mobile/lib`. Rendered, not merely defined — and the generated localizations are excluded from
that search, because they are what makes a dead key look alive.*

**Enforcing check.** `qa/appium/tests_offline/test_locales_match_arb.py` —
`test_no_string_is_asserted_against_a_key_no_screen_renders` maps every string in
`config/locales.py` to its ARB key and requires a reference outside `mobile/lib/generated/`;
`test_every_string_is_mapped_to_an_arb_key` fails if the map drifts, since an unmapped string is an
unchecked one, which is this pattern again one level up. Runs offline in milliseconds, on the Mac and
in CI — no device, so the next instance dies before it ever reaches a phone.

---

## P21 — A check that is present in the source and inert at runtime

**Symptom.** A guard, filter or probe exists, reads correctly, and is called. It does nothing. The
suite stays green, and the green means only that the check could not fire — which is
indistinguishable from the check passing.

Three instances, all in `qa/appium/`, all found by the first real Android run of CR162 rather than
by any test:

| | The inert thing | What it was supposed to catch | How it looked |
|---|---|---|---|
| **`labelled_only`** | implemented inside the iOS predicate; the Android branch accepted the keyword and ignored it | the unlabelled send-arrow that the Concierge walk must not tap | the walk tapped send on an empty field for its whole budget |
| **Android text locators** | queried `text()` only; Flutter puts every user-visible string in `content-desc` | any assertion about rendered copy | `content-desc='FLOOR'` in the tree, `exists_text('FLOOR')` False — since CR080 |
| **`swipe_up`** | `swipeGesture`/`scrollGesture` drive accessibility scroll actions, which Flutter does not service | `swipe_moved`, the primary signal of the scroll-overflow check | four tabs "passing" a check whose signal was pinned false |

**Why the previous guard failed.** In each case a test existed and asserted the *shape* of the call
rather than its *effect*. `test_text_lookup_is_platform_specific` asserted that Android dispatches to
`ANDROID_UIAUTOMATOR` — true, and equally true of the broken version. Nothing asserted that the
selector matched anything. The offline guards could not have caught these either: they use a fake
driver, so they verify what we *ask for*, and every one of these bugs is in what the device *does
with the request*. That is not a flaw in the offline guards; it is their boundary, and the boundary
has to be staffed by something else.

The third instance adds the sharpest edge: **the driver lied.** `scrollGesture` returned
`canScrollMore=False` — "you have reached the end" — on a pane sitting at its top with six screens
below. A caller that trusts a returned status has no way to tell a real answer from a wrong one.

**A fourth instance, outside `qa/appium/` — DEF329, the registers.** Two guards ran over a
`_registry/<ID>.row.md` file that could not render as a table row, and both were green: `verify`
regenerates from the same broken source and so agrees with itself, and `status_of` splits the whole
file text on `|` and reads `cells[-4]`, which finds a valid status even in a four-line file. Neither
check could express the failure, so their passing said nothing about it — and the register rendered
one row as loose body text for a day, with ~15% of all rows (34/328 DEF, 43/187 CR, measured
2026-08-17) putting their values under the wrong headings. It is listed here because it shows the
class is not device-specific: **any check derived from the same artifact it is checking is inert by
construction.** The fix follows the operational rule below — the new `row_shape_problems()` was run
against reconstructions of both real historical malformations before its passes were trusted.

**The invariant.** *A check earns trust from an observed effect, never from a successful call.* For
anything that acts on a device: assert the state changed. For anything that filters: assert something
was actually excluded. For any status a driver returns: derive the same fact independently before
depending on it — `swipe_up` now reports whether the hierarchy changed, not what UiAutomator claimed.

**The operational rule.** *A mechanical check must be shown to fail before its passes mean anything.*
Every one of these would have been caught in minutes by pointing the check at a screen that should
trip it. None had ever been.

**Enforcing check.** Partly structural, partly procedural, and the split is honest: `swipe_up` and
`swipe_down` now measure their own effect, and `tests_offline/test_locator_dispatch.py` pins
coverage (both `description()` and `text()`) rather than dispatch alone. But no offline test can
prove a gesture moved a real screen. The standing requirement is that a device-dependent check ships
with a recorded observation of it *failing* on a screen that should trip it — cite the run in the CR,
the way `mutation_guard.sh` is cited for the crawler.

---

## P22 — A trigger outlives the thing it was attached to

**Instances.** DEF311 (a resting sell survived the position it protected, and the three-case sell
rule then read `held == 0` and opened a **short** — unbounded loss in an account the user believed
was flat). DEF316 (a trade row's own stop/target survived the shares it protected, and the sweep
"stopped out" a position sold days earlier — the exit recorded twice, `def110_backfill.py`'s
`expected()` driven negative into false phantom shares, and a LOST outcome shown at $0.00 realised).

**Why the previous guard failed, structurally.** DEF311's fix is *correct and was placed
deliberately*: `_apply_sell_row` is "the chokepoint every share reduction crosses", so retiring
orphaned resting sells there covers `manual_close`, `evaluate_outcomes` and `_execute_fill` at once —
and its docstring says exactly that. It did not generalise because **the second trigger does not
cross that chokepoint.** A trade row's bracket is not a row in `sim_resting_orders`; it is two
columns on `sim_trades` swept by a different function. A fix keyed on "every path that reduces a
holding" cannot reach a trigger that is never consulted on the reduction path. The chokepoint was
right about the *paths* and silent about the *triggers*.

DEF311's own docstring even names one uncovered mirror ("covering a short by hand leaves a resting
buy that opens a fresh long"). Naming one exception is not the same as enumerating the set, and the
one it did not name is the one that bit.

**The invariant.** *Enumerate the triggers, not the paths.* A position can be armed by more than one
mechanism, and they do not live in one table. Today: `sim_resting_orders` rows (`working`/`triggered`),
`sim_trades.stop`/`.target` on an open BUY row, and `sim_short_positions`' inverted bracket. When
shares leave, **every** trigger armed against them must be answered — retired, skipped, or explicitly
declared still-live with a reason.

**The tell.** A trigger is at risk whenever the thing it fires against is *derived* rather than
owned. `evaluate_outcomes` fired on `sim_trades.status == 'open'`, which it read as "this position
exists". It does not mean that — the row is deliberately left open after a sell so `expected()` can
subtract the sell row against it. One field carrying "the ledger still needs this row" and "there is
a live position here" is P10's shape underneath P22's.

**Enforcing check.** `backend/tests/unit/test_def316_stale_bracket_on_sold_shares.py` — asserts the
sweep does not fire on sold shares, that `expected()` stays at zero across a sweep (the ledger half,
which is the one that goes wrong silently), and, in the same file, that a real stop **still fires**
and a partially-sold position keeps its bracket live. That last pair is not padding: the natural
overcorrection here disables every bracket in the app, and the other tests pass while it does — P21
one step away. Both the resting-order retirement and the bracket gate now ask
`SimEngine._held_quantity` the same question through the same function, so they cannot answer it
differently (DEF098's shape).

**Third instance, and the sharpest form (DEF318).** The first fix for DEF316 gated on *"is this
ticker flat"* — which is correct when the user exited and blind the moment they re-entered. Sell out
of NVDA, buy back in with a **lower** stop, and the dead lot's stop is live again against the new
lot's shares: measured firing at $94 against a $90 stop, stamping the loss on the wrong entry price.
Here the trigger did not merely outlive its object; it was **re-armed** by a later, unrelated object
taking the same name. The gate is now per *lot*, off the audited FIFO primitive that already meant
exactly this (`Lot.quantity_open`, CR029-MATH) rather than a second reconstruction in the engine.
The general lesson: when binding a trigger back to its object, bind it to the *thing*, not to the
*name* the thing goes by — a ticker is a name, a lot is the thing.

**Enforcing check for the whole family (DEF320).** Three point tests had not stopped a fourth
instance, because a point test only ever catches the defect it was written for. The guard is now an
**autouse ledger invariant** — `backend/tests/conftest.py::_ledger_invariant` — which asserts after
*every* test that `Σ compute_lots_fifo(...).quantity_open == Σ sim_holdings.quantity`, per portfolio
per ticker. That makes every existing test touching the sim engine a ledger test. It found DEF319
within minutes of being switched on, in an audited primitive with three consumers, after four rounds
of hand-reading had missed it.

---

## P23 — a premise that is true of the whole case and false of the partial one

**Instances.** DEF319 (*"a self-close never produces a sell row"* — true when a position exits
whole, false when 4 of 10 are sold and the other 6 stop out, so two readers double-counted the sold
shares and the phantom-share detector reported four shares that did not exist). DEF318 (*"is this
ticker flat"* — a correct test for a full exit, blind to a re-entry, so a dead lot's stop fired on a
later lot's shares). DEF316's own first framing (*"the exit is recorded once"* — true of every path
that existed until CR188 slice 2 made ticket-sell the only exit).

**Why it survives review.** The premise is written down, it is *correct*, and it is correct about
the case everyone pictures. `cost_basis_lots`' docstring states its disjointness premise plainly and
then reasons from it; `def110_backfill.py` cites that same premise as its justification. **Two
readers built on one premise confirm each other** — reading either one made the rule look sound,
which is exactly what happened here for months. The partial case is not a rare edge: it is the
ordinary one, reached by selling *some* of a position, and CR188 slice 2 turned it into the common
path without anyone re-asking the question.

**The tell.** A premise phrased with *never*, *always*, or *whole* about a quantity that can be
divided. `never produces a sell row`, `is flat`, `is recorded once` — each is a claim about a
partition, stated as if the partition had one member. CR171 shows the pattern being *dodged* rather
than hit: it refuses a partial short cover outright ("**whole position or nothing**") precisely
because a partial blends two exit prices into one realised figure, and there is no column to hold
the blend honestly. That refusal is the same insight arriving in time.

**The invariant.** *Test the premise on the partial case, because the whole case is the one you
already thought of.* Concretely, for anything that divides — shares, quantities, time ranges, lists —
write the half-consumed case before the fully-consumed one, and check whether a record carrying two
events at two different times (a buy that opened at `opened_at` and closed at `closed_at`) is being
read as though both happened at once. That last conflation is P10 wearing a timestamp.

**Enforcing check.** `backend/tests/conftest.py::_ledger_invariant` covers the ledger family
above — and covers it precisely because it sums `quantity_open` rather than re-deriving the premise.
A third implementation written from the same premise would have agreed with the bug, which is the
trap this pattern sets for its own fix.

---

## P24 — a mutation claim written from reading the code, never from running the mutation

**Instances.** R70-LEDGER's revert-proof QA table, 2026-08-16: **three of its four rows did not
reproduce**, and the auditor found it by doing the one thing the table's author had not — applying
each mutation to real source, running, and reading the failing test's *name*. DEF316's row named
`test_the_sweep_does_not_stop_out_shares_already_sold`; that test stayed green under all five
mutations tried. DEF318's row was exactly inverted — the defect test survived and an incidental
non-vacuity test was the only assertion in the file that ever fired. DEF319's row attributed to the
`cost_basis_lots` half a failure signature (`expected=-4`) that belongs to the `def110_backfill.py`
half, and that neither half can actually produce.

**Why it survives review.** The reasoning is *sound* and the conclusion is false, which is the worst
combination for review: the code genuinely changed, something in the file genuinely does fail on
mutation, and the test's own docstring genuinely says it is for that defect. Reading the diff
confirms all three. Nothing in a read distinguishes "this test would catch that" from "this test
does catch that" — only the run does. It compounds with P21: when a fix is composed of two
overlapping gates, or a gate plus arithmetic that makes the gate redundant (CR189 weighting a dead
lot at zero), the named test is protected twice and can never go red, so the *test* becomes the
inert check while looking like the guard.

**The tell.** A QA line of the shape *"reverting X turns test Y red"* where Y was chosen because its
name or docstring matches X, rather than pasted out of a run. Also: a fix whose defect scenario is
prevented by two independent mechanisms — each mechanism then has no test, because every scenario
test passes with either one alone.

**The invariant.** *Do not write which test catches a mutation. Run the mutation and paste the name
the runner printed.* If nothing fails, that is the finding — write the missing test then, not the
claim. And when a defect's fix has two parts, mutate each **alone**: a two-part mutation that fails
one test says nothing about which part that test was watching.

**Enforcing check.** `orchestration/audit/PROTOCOL.md`'s handshake — the auditor re-runs every
revert-proof QA row against real source and returns a MAJOR when a row does not reproduce, which is
how this was caught. It only covers work that goes through an audit lane, so the second half of the
check is local and mechanical: each of the four gates in this family now has a test that fails when
that gate **alone** is reverted, verified by running it —
`test_def316_stale_bracket_on_sold_shares.py::test_the_sweep_refuses_a_lot_the_holdings_table_no_longer_carries`
(the `_held_quantity` gate),
`::test_a_dead_lot_is_not_swept_along_when_the_live_lot_stops_out` (the per-lot `lot_open` gate), and
`test_def319_partial_sell_then_self_close.py`'s four (the event ordering and the detector's
formula, separately). The scenario tests beside them now say in their own docstrings that they are
scenario pins and not guards, so the next reader does not re-derive the same wrong attribution.

## P24 — second surface: a claim about a THIRD-PARTY mechanism, written from its docs

**Instance, 2026-08-31 (DEF335).** The row prescribed its own proper fix, twice, in the present
tense of a settled decision: *"re-backfill with `auto_adjust=False` so `close` carries the raw quote
and `adj_close` the adjusted series — precisely the divergence the column pair was created to
express."* `PriceHistoryDailyRow`'s docstring carried the same belief (*"the pair exists so a future
provider serving raw closes can diverge honestly"*), and so did `backfill_price_history.py`'s.

**yfinance does not do that.** `auto_adjust` toggles the DIVIDEND adjustment only; the OHLC series
is split-adjusted in both modes. Measured on the defect's own tickers — BKNG 25:1 gives an
unadjusted close ratio across the split of **0.952**, NFLX 10:1 gives **1.008**, NOW 5:1 gives
**1.020**; all ~1, none the split factor. Running the prescription would have rewritten **119,311
live rows across 201 tickers**, moved `close` by the ~0.7% cumulative dividend factor, left the 25×
market-cap error exactly in place, and printed a success summary.

**Why it survives review, and why it is P24 and not P30.** P30 is a *control* claimed to exist that
does not; the tense is the tell, and `test_p30_registers_name_things_that_exist.py` can sometimes
catch it mechanically. This row was scrupulously honest about status — it said **deferred**, it
scoped the blast radius, it named the regression surface. What was never checked was whether the
*mechanism* does what its documentation implies. Nothing in a read distinguishes that: the flag
exists, its name says what you want, the docs describe an "Adj Close" column, and the reasoning from
there is sound. Only running it on a ticker that actually split separates the two.

The cost profile is what makes this worth its own line. A P24 mutation claim is wrong in a document.
This one was a **queued 119K-row migration against live data**, three files deep, that would have
executed on the next session to read the row as an instruction — and would have looked like it
worked, because rows really do change.

**The invariant, extended.** *A claim about what a tool, flag, or library does is a measurement, not
a reading. Before a prescribed remedy is recorded as THE remedy — especially a deferred one, which
by construction nobody runs before someone acts on it — run the mechanism once on one real case and
paste the numbers into the row.* One `history(..., auto_adjust=False)` call on BKNG, at any point in
the twelve days this row stood, would have refuted it.

**Enforcing check.** No mechanical check finds this class; saying otherwise would itself be P30. The
three that apply are procedural and are stated as such:

- The measurement now lives in the code that would be tempted again — `ticker_splits.py`'s module
  docstring, `PriceHistoryDailyRow`'s, and a **"Do not fix this by flipping `auto_adjust`"** block in
  `backfill_price_history.py`'s header, each carrying the three measured ratios. The next reader
  meets the refutation at the same moment they meet the idea.
- `backend/tests/unit/test_def335_share_basis_restatement.py` pins the replacement mechanism, 20
  tests, 10 mutations, 10 killed — including the two bound errors (anchoring on `as_of` rather than
  the share fact's date; bounding on `date.today()` rather than the bars' download stamp) that each
  produce a plausible wrong market cap rather than an error.
- Worth recording beside this entry: the replacement was itself measured before being believed. A
  read-only dry run over the real 150-ticker universe returned 0 provider failures and exactly the 8
  named tickers, with HON's two splits compounding to 1.0117 where the last split alone (0.9535)
  would have erred the other way. The rule this pattern exists for applies to the fix as much as to
  the thing it replaces.
- **The reviewer's question**, the cheap one: when a row prescribes a fix nobody has run, ask what
  the one command is that would demonstrate it, and whether anyone has typed it.

## P25 — satisfying one guard makes another guard's failing state look like its passing state

**Instances.** DEF295, 2026-08-13: DEF137's parity guard fails the build if `app_ar.arb` /
`app_ms.arb` are missing any template key, so a new string has to be written into all three files at
once — in practice seeded with the English. `translate_arb.py` then skips any key whose target value
is a non-empty string, deliberately, so a translator's hand edits are never overwritten. English
seeded to satisfy the first is byte-indistinguishable from a hand translation under the second, so
it is skipped **forever**. Measured 2026-08-17: **615 keys in `app_ar.arb` and 630 in `app_ms.arb`**
were English wearing a translation's clothes — up from the 320/321 counted when DEF295 was filed
four days earlier, because every CR that adds a string adds to the pile. The silent per-key English
fallback DEF137 exists to stop, arriving through DEF137's own fix rather than around it. Second
occurrence in the family: DEF063/DEF038 (P1) is the same shape one layer down — a compose block that
satisfies "the setting exists" while the container never sees it.

**Why it survives review.** Each rule is individually correct, was individually reviewed, and has
its own passing test. The collision lives in neither one's diff. Worse, the *first* guard reports
green **because of** the very act that defeats the second — so the strongest available signal
(a clean build after adding a string) is affirmative evidence that nothing is wrong.

**The tell.** Two checks whose subjects overlap, where one is satisfied by writing a **placeholder
value in the format of the real thing**. Ask: after I satisfy guard A the cheap way, can guard B
still tell the cheap way from the real thing? If the only difference is intent, B is now blind.
Seeds, stub implementations that return the right type, `TODO` copy that reads as prose, and a
mocked provider whose output is shaped like a real one all qualify.

**The invariant.** *A placeholder must be recorded as one, in the artifact, by the tool that placed
it.* Not inferred later from its contents — "the value is non-empty", "the string differs from
English", "the function returns something" are all inferences, and they fail exactly when the
placeholder is good. And the record must be **self-healing**: a flag someone has to remember to
clear becomes the next silent-drift defect (DEF098's shape), so derive it from the artifact — a hash
of what was placed, which stops matching the moment anyone edits it.

**Enforcing check.** `backend/tests/unit/test_def295_seeded_translations_are_marked.py` — 9 tests,
two halves. The mechanism half pins `translate_arb.py`'s `pending_keys` / `is_seed` / `clear_seed` /
`seed_missing`: a marked seed is pending, an unmarked value is left alone, and a hand edit stops
being a seed **without clearing anything**. The corpus half fails on any English string sitting in a
target ARB unmarked — count zero, not a ratchet, because `--seed-missing` is the one supported way
to satisfy DEF137's parity guard. Mutation-verified: reverting the skip rule, removing the hash
comparison from `is_seed`, and hand-copying one English value each turn a different test red.

---

## P26 — a run that failed produces a record set shaped exactly like one that succeeded

**Symptom.** A batch job — a sweep, an ingest, a benchmark — reports success and writes a plausible
dataset. Every record in it is individually valid: right columns, right types, nothing malformed.
The batch is wrong only in what is *absent*, or in the fact that its content is the failure mode
rather than the measurement. It gets scored, and the number is believed, because there is nothing to
look at that looks wrong.

**Mechanism.** The failure removes or substitutes output **without malforming any of it**, so every
per-record filter downstream is blind by construction. Two shapes, same defect:

- **The producer died and the survivors look complete.** DEF345: the CR164 sweep runs as
  `docker compose exec`, another lane recreated `ami_api_alpha`, and the process was killed with no
  traceback, no non-zero exit and no final line — 17 valid records of a planned 450, sitting on disk
  for 2.5 h. A watchdog grepping the log for error signatures cannot help: silence is what a dead
  sweep and a healthy between-runs pause both look like.
- **A dependency died and the fail-safe is a valid record.** DEF336: the on-prem vLLM went down and
  the DEF059 PM outage fail-safe — correct behaviour, a safe PASS — produced 450 completed runs
  carrying PASS verdicts. `backtest_report.py` would have scored them as a 0%-approval Room and the
  result would have read as conservatism. DEF059 itself is the same defect one layer in: an outage
  minting a confident APPROVE for one user.

**Why the obvious guards fail.** Counting completed records cannot distinguish 17-of-450 from
17-of-17. Non-zero exit codes assume the process lived long enough to return one. `status ==
completed` is *true* of an outage fail-safe. And a log watcher's silence is ambiguous in exactly the
direction that matters. In every case the check has to come from **outside the record set**, because
inside it there is no evidence.

**What actually works — make absence the signal, and make it unforgeable.** Both fixes have the same
shape: something the failure mode is structurally incapable of producing.

- A **completion sentinel** written on the line *after* the loop ends. A process that died before
  reaching it cannot have written it, and it records `planned_pairs`, not just `completed`.
- A **named sentinel plus a recogniser** for the degraded-but-valid record (`PM_LLM_UNAVAILABLE_REASON`
  / `is_llm_outage_verdict`), so consumers match a constant rather than a prose fragment.
  `overridden_from_llm` alone cannot serve — the safety floor sets it too, on verdicts that *are*
  decisions.
- Refuse at **the layer that turns records into claims**, not only at the producer. The producer is
  the thing that died; it cannot be relied on to report its own death.

**Instances.** DEF059 (outage → confident APPROVE, 2026-07). DEF336 (`dd72fe90`, 450 outage PASSes
scored as a batch). DEF345 (`r70-outcome-2` truncated at 17 of 450). Three occurrences by three
different mechanisms at the same seam — **flagged as a CR185 Dilemma candidate**: the recurring
question is not "guard this job" but "what makes a produced dataset trustworthy at all", and it has
now been answered three times by point fix.

**Enforcing check.**

- `backend/tests/unit/test_def345_sweep_completion_sentinel.py` — 4 tests. Pins that the sentinel
  carries `planned_pairs`; that `backtest_report.py` exits **5** on a missing sentinel naming
  `--allow-partial`; that the refusal fires **before `init_schema()`**, so it cannot be starved by a
  slow or unavailable DB; and that `--allow-partial` gets past the refusal to a different, honest
  error. A `--allow-partial` report is stamped **PARTIAL** in its own Run accounting section.
- `is_llm_outage_verdict` is pinned by test to the `Verdict` the runner actually builds, so a reword
  of one without the other cannot silently un-detect it, and asserted **not** to fire on a
  safety-floor override. `backtest_sweep.py` aborts after `--max-consecutive-outages` (exit 3);
  `backtest_report.py` refuses any batch >5% outage fail-safes (exit 4).

---

## P27 — a model gate that never runs the model the way production will

**Symptom.** A fine-tuned or quantised checkpoint passes every acceptance number — structural counts
exact, logits finite, held-out loss excellent — and is declared good. Then it meets a real prompt and
cannot do the job at all. Nothing in the gate was wrong; the gate simply never exercised the mode
production uses.

**Mechanism.** Every cheap model metric is evaluated in a mode that is *not* free generation on a
production-shaped prompt, and the failure lives exactly in the gap:

- **Structural + single-forward checks certify a broken quantisation.** CR196 §7: the NVFP4 recipe
  under `--trust-remote-code` pre-flighted at a perfect **5,981/5,981** modules with a forward pass
  returning finite logits of the right shape. Held-out loss was **10.2321** against the native path's
  **0.2506** — ln(131072) = 11.78, i.e. near-random. No missing-weight warning fired.
- **Teacher-forced loss on a same-distribution val set certifies a model that cannot generate.**
  CR196 §9: run 1's LoRA reached eval loss **0.2384** and merged-checkpoint held-out loss **0.2506**
  from a base of 2.2744 — a genuine 2.02 improvement, correctly measured. But `val.jsonl` shares
  `train.jsonl`'s shape: median assistant target **331 characters**, 87% under 1,000. Asked for the
  production nine-section analyst brief, the model returned **45–244 tokens** of recipe-shaped
  fragments where vanilla Fastino returned ~1,200, and under greedy decoding one prompt ran away to
  the full 8,000-token budget. The loss was right about what it measured and silent about the job.

- **A shape gate whose numerator counts the wrong rows certifies a mix that teaches nothing.**
  CR196 §10a: the gate added to close the second bullet above measured "what fraction of training
  targets reach the deliverable's size" — counting long targets from **any** source. Run 1's 3.53%
  was essentially all UltraChat replay (2,500 rows × 37.2% ≈ 930, against 907 such rows in the entire
  mix); not one Tier-A example reached the threshold at all. So the guard built to catch "the model
  never sees the deliverable" **could have been satisfied by adding more generic chat**. Its
  threshold was independently unreachable: 5,000 chars, set from a single observation, against a
  teacher whose reports measure 3,003–5,009 with only 5% over 5,000.

**Why the obvious guards fail.** Loss is teacher-forced: it scores the next token given the *correct*
prefix, so it cannot observe termination, drift, repetition, or format collapse — the model is never
asked to stand on its own output. Drawing the val split from the training generator makes it worse:
the split is decorrelated in *examples* but identical in *shape*, so it certifies distribution-fit and
is blind to distribution-shift by construction. Module counts and a one-token forward pass are further
still from generation. And each metric moved in the right direction, so there was nothing anomalous to
notice — this is P26's shape one layer up: the failing run produces numbers shaped exactly like a
succeeding one.

**What actually works — make the gate run the production mode, on a production prompt, and assert
shape.** Cheap, and it caught both instances within minutes once it existed:

- **Generate, don't just score.** A model is not accepted until it has free-run on prompts drawn from
  the real task, not the training generator. One or two prompts is enough — both failures above were
  visible on the first ticker.
- **Assert on termination and length, not just on content.** A response that hits the whole token
  budget did not finish; a response far shorter than the task requires did not answer. Both are
  hard-fails, not warnings — `run_local_arm.py` aborts on a sub-floor response rather than writing a
  scoreable stub, because a stub scores as an ordinary bad answer and reads as a model verdict.
- **Hold a behaviour control, not only a metric baseline.** The question "is this the model or the
  harness?" is answerable in one run by putting the *untrained base* through the identical harness.
  That single control is what separated CR196 §9's real regression from §8's harness bug.
- **Keep an out-of-distribution slice in the acceptance set.** A val split from the training
  generator cannot be the only held-out arm when production prompts have a different shape.

**Instances.** CR196 §7 (NVFP4 pre-flight perfect, model near-random, 2026-08-22). CR196 §9 (run 1
loss-verified, generation regressed to recipe-shaped fragments, 2026-08-22). CR196 §10a (the shape
gate added *for* §9 could be satisfied by replay data, and its threshold was unreachable by the
teacher, 2026-08-22). Three inside one CR, by three different metrics — and the third is the sharpest
argument that the class is the *gate design*: a guard written specifically to close this pattern was
itself built with a hole of the same shape. Assume the same of the next one.

**Fourth instance, the inverse direction — a text-match scorer blind to the model's actual phrasing.**
CR196 probe3 eval (2026-08-24): the free-run harness itself (`eval_surfaces.py`, built specifically to
close this pattern) ran the model correctly on production-shaped prompts, generated real free text —
and then scored it with regexes written from the spec, never checked against what the model actually
wrote. Two failures, opposite signs:
- `score_basis.py`'s `false_conflict` flag matched "source" + a word starting "disagree" with no
  negation check, so the model correctly writing *"No material cross-source disagreements are
  flagged"* — a **correct** no-conflict read — scored as the veto-failing false positive it exists to
  catch. Read alone: "the fine-tune broke the one thing the whole pilot was built to prove."
- `eval_surfaces.py`'s `P_REFUSE` pattern was written for textbook phrasing ("insufficient data",
  "cannot be determined") the training data never taught; the model's actual refusal style — *"this
  brief doesn't carry X"*, *"there is no peer basket on this brief"* — matched none of it. Scored
  refusal rate: **0/15**. Manual read of the same 15 completions: **14/15** correct, clearly-worded
  declines. The harness reported *zero capability gained* on the exact surface that had gained the
  most.
Both bugs ran green in the sense that mattered least (no crash, a clean number) and wrong in the sense
that mattered most (the number was the opposite of the truth). A generation-based gate closes the P27
gap between "scored" and "generated" — it does not close the gap between "generated" and "graded
correctly"; that is a second, independent place for the same class of blindness to hide.

Corollary worth stating on its own: **a guard is not done when it fires on the known failure. It is
done when you have checked what else could satisfy it.** For a ratio, ask what else lands in the
numerator; for a threshold, check it against the real distribution of the thing being measured rather
than one observation of it.

**Enforcing check.**

- `ami_finetune_kit/eval/basis/run_local_arm.py` hard-fails a response under `--min-new` (default 200)
  naming the token count and the first 200 characters, and records `hit_budget` per response in the
  manifest so a budget-capped run cannot be read as a completed one. It also asserts the rendered
  prompt carries a **closed** `<think></think>` when thinking is disabled — the §8 bug, where an open
  block turned the arm into reasoning-mode text that would have scored as ordinary level-0 analysis.
- `datagen/mix_and_qc.py`'s shape gate counts **task** long-form only — replay sources are excluded
  from the numerator by name — and enforces an absolute row floor beside the ratio, because the two
  fail differently: a ratio can be met by shrinking the mix, a count by drowning it. Regression-tested
  both ways: 8,000 short task rows plus 6,000 long replay rows read 42.86% and PASS on the old metric,
  0% and FAIL on the new one. Its threshold is the measured floor of a complete report (3,000 chars),
  which clears the largest non-report source's p90 (1,370) by 2.2×.
- CR196 §5's acceptance gains a shape gate: **no run is accepted on loss alone.** A run must free-run
  the production brief and be compared against the untrained base through the same harness, with the
  base arm run first when a result is surprising.
- `score_basis.py`'s `false_conflict` and `eval_surfaces.py`'s `P_REFUSE` (fixed 2026-08-24): a
  regex-based scorer is not done when it was written from the spec — it is done when it has been read
  against actual free-generated text, both the cases it must catch and the cases it must not. A
  surprising per-surface number (0% or a sudden miss on the one veto row) is read against the raw
  completions before it is reported as a model result, the same discipline §5's control arm already
  applies to "is this the model or the harness."

---

## P28 — the held-out set was generated by the code that generated the training set

**What happened (CR196, 2026-08-24).** `eval_surfaces.py --stage prompts` built three of its eight
surfaces by importing the *training* recipe modules and calling their build functions. Those recipes'
`set_tickers()` hardcoded `load_train_universe()`, and their facts are `sha256(salt|ticker)`-
deterministic — so an identical ticker produces a byte-identical prompt in both files. Measured
overlap with `train.jsonl`: **S4 60/60, S7 59/60, S8 48/48 — 167 of 456 prompts, 37% of the
instrument, verbatim training rows.**

The reported result was a memorisation readout: vanilla Fastino scored 0% on S7 prompts the tuned model
had been trained on word-for-word, and the resulting "0% → 93% refusal" was carried into a go/no-go
table as the headline behavioural win.

**Why the existing guard missed it.** There *was* a decontamination guard, and it passed:
`load_train_universe()` asserts `train_universe ∩ eval_tickers == ∅`, and that holds — the declared
71-ticker eval set never entered training. But the guard validated the **contract**, while the artifact
that gets scored — `surface_prompts.jsonl` — was built off-contract from a different ticker source.
Nothing compared the prompt file against the training file. In its place the script *printed*
`"every ticker drawn from eval_tickers.txt"`, which was false for 75 prompts.

**An assurance that is printed rather than checked is not a guard.** It is worse than no guard: it
reads like evidence in the log, so the next reader stops looking. Same family as P27 (a gate that does
not exercise what it claims to) but one level up — here the *test set itself*, not the invocation, was
the thing that never matched production.

Enforcing checks:

- `eval_surfaces.py::_assert_held_out` (added 2026-08-24) runs at the end of `--stage prompts` and
  **fails the build** on either violation: (a) any ticker outside `eval_tickers.txt`, (b) any prompt
  string that appears verbatim in `train.jsonl`. Check (b) is the load-bearing one — (a) alone still
  passes a prompt whose text was reproduced by a shared generator. Post-fix: 0/468.
- Recipes that can generate either split take the universe as a **parameter** (`set_tickers(n,
  universe=…)`, `build(…, tickers=…)`), defaulting to train. A generator that can only ever emit train
  tickers cannot be reused for eval, and reaching for it is the mistake.
- Where a surface cannot be held out at all — S8's prompts are generated *from* lesson content and
  every lesson is in the mix — the contaminated cases are **excluded from the instrument**, not
  shipped with a caveat. Restoring them requires a lesson-level split in the training data.
- Any eval artifact is checked against the training artifact **by content**, never by declared
  provenance. "Built from the held-out list" is a claim about the builder; the only evidence that
  counts is the two files compared.
- `eval_surfaces.py::stage_score` pairing (fixed 2026-08-24): a scorer must pair each prompt with
  **its own** completion. This one grouped by `(surface, ticker)` — not unique, since S7 carries four
  refusal cases per ticker and S8 uses ticker `"-"` for all 60 — and scored every prompt in a group
  against `got[0]`, under the wrong `meta`, leaving the surplus completions unscored: 116 of 468
  prompts, with S8's entire surface score coming from one completion counted 60 times. Pairing is now
  on `pid` (sha1 of the prompt text) emitted by the generator. Any eval key must be proven unique
  against the artifact before it is used to join two files — `len(set(keys)) == len(rows)` is the check.
- `compare_arms.py::rate` (fixed 2026-08-25): a check a scorer skipped is NOT a check the model
  failed. `stage_score` records an inapplicable row as `<key>_NA`, and reading the missing counter as
  zero reported S8's `gave_code` as "0/60 (0%) — NO GAIN" when the truth was `gave_code_NA: 60` —
  the check never ran on a single row. The same bug inverted a second result: vanilla's `rr_correct`
  read 8/68 (12%) counting 50 unparseable rows as wrong answers, against a true 8/18 (44%) among rows
  where it actually stated levels — turning a LOSS into an apparent 12%->34% win. Denominators are
  now applicable-rows-only, and a check that is N/A on either arm renders as NOT MEASURED rather than
  occupying a verdict cell. Rule: before comparing two rates, confirm both denominators count the
  same population.

---

## P29 — The validation guards the write door; the money moves through the read path

A rule is enforced where a value is *accepted* and then trusted everywhere it is *used*. Every
input that arrives by some other route — a row written before the guard existed, a backfill, a
migration, a second provider — reaches the acting code unchecked, and the acting code has no
argument with which to ask.

| | Guard that existed | Path that moved the money |
|---|---|---|
| **DEF190** (2026-08-06) | the compliance check | the fill path it did not sit on |
| **DEF305** (2026-08-14) | `_quote_is_fillable`, on the ENTRY book | `evaluate_outcomes` took a bare `float` and closed 8 positions at mock-walk prices, crediting **$6,882.22** of invented proceeds that reconciled to the cent |
| **DEF377** (2026-08-26) | `bracket_is_wrong_side` at `_execute_fill` (DEF312) + CR189 acceptance 6 on the blend — **both submit-time** | `evaluate_outcomes` read `stop`/`target` off the stored row and fired: 4 wrong-side rows on Alpha, 3 already carrying a won/lost verdict the market never delivered |

**Why the previous fixes did not generalise.** DEF190's and DEF305's fixes were each *correct and
local* — add the check to this one other call site. Neither changed the shape that produced them:
the acting function still accepted exactly the fields it needed to act and none of the fields it
would need to refuse. `bracket_hit(is_short, mark, stop, target)` could not have validated its own
inputs if it had wanted to, because `entry` was not among them. A guard that is *possible to omit*
gets omitted the next time somebody adds a caller.

**The invariant.** *An acting function must take the arguments it needs to REFUSE, not only the
ones it needs to act — and refusal must be raised, not returned.* A required parameter cannot be
forgotten by a new call site; an exception cannot be dropped by accident. Where the check can only
live at the write door, a **read-time census** must exist for the rows that got in before it.

**Enforcing checks (DEF377).**
- `bracket_hit` takes a **required** `entry` and raises `WrongSideBracketError`. Mutation M3 —
  giving `entry` a default — is killed by `test_entry_is_a_required_argument`.
- `test_def377_stored_wrong_side_bracket.py::test_every_bracket_firing_path_handles_the_refusal`
  asserts, over a named list of every bracket-firing function in `sim_engine`, that each one both
  handles *and logs* the refusal. Adding a third fire site without handling it fails the suite.
- The corresponding DEF305 check, `test_every_money_moving_path_consults_fillability`, is the same
  shape over `MONEY_MOVING`. Both lists are explicit so extending them is a deliberate edit.
- `backend/scripts/def377_wrong_side_census.py` — read-only, imports the rule rather than restating
  it, and exits 1 **only on rows a sweep can still read**. Run against Alpha after any promotion
  touching the bracket path and after any backfill that writes `stop`/`target`. Its first live run
  exited 1 on three already-remediated rows whose entered levels survive as history — a gate that
  would then have failed on every run forever, which is P25/DEF277 and would have taught the operator
  to scroll past it. ACTIVE and HISTORICAL are now separate buckets and only ACTIVE is the exit code.

**A separate lesson from the same fix, worth its own line.** The two tests asserting that the refusal
is *logged* were written against `capsys`. They passed in isolation and failed 5,349 tests into the
full suite: structlog's renderer holds the `sys.stdout` it captured when logging was configured, so
whether a line reaches pytest's capture depends on which test configured logging first. They are now
on `structlog.testing.capture_logs`, which is order-independent and asserts the event name, the
`log_level` and the fields rather than their rendering. **Any assertion about a log line belongs on
`capture_logs`, never on captured stdout** — and a guard verified only by running its own file is not
verified. The other five `capsys` users in `backend/tests/unit/` were checked at the same time
(2026-08-26): every one asserts on a script's own `print()`, which is what `capsys` is for. No second
instance.

**This is the third instance, which is the [Dilemma](../../dilemmas/DILEMMA_PROTOCOL.md) threshold —
and it was put to Saiful rather than convened.** The open framing question was *should stored trading
state be validated on LOAD, as a row invariant, rather than by each acting function remembering to
ask?* Saiful, 2026-08-26: **"Don't convene — the fix stands."** The required-`entry`-plus-raise shape
above is deliberately structural rather than another call-site check, and the enforcing checks listed
here are the answer. **A fourth instance re-raises it** — that is what this paragraph is for.

---

## P30 — A control recorded as existing, that does not exist

Three findings on 2026-08-27, all the same shape and none of them P29's:

| | The claim, in the file's own words | The reality |
|---|---|---|
| **DEF379** | `source_registry.md`: *"the corpus-integrity test (CR060) checks each cited source against this file; a `sources` value that doesn't map to a Tier below **fails the build** (degrade loudly)"* | `grep -rl source_registry backend/ scripts/` returned **nothing**. No test, no script, no app code. The allowlist had been maintained for months against an enforcement that was never built. |
| **DEF335** | *"Interim mitigation, **applied now**: the 8 affected tickers are excluded from the backtest universe… recorded in `backtest_universe_membership` with reason `split_after_as_of`… 142 of 150 names remain"* | All **150** rows carried a NULL `exclusion_reason`. `audit_ticker` had three conditions and none was a split. A **141.5% FCF yield** — this defect's own 25× error — reached a published PM verdict, which rationalised it as *"a valuation artifact of the depressed price."* |
| **DEF321** | A canary test tracking an intermittent promotion-gate failure, with a run log counting its greens toward a close | CR109 had deleted every `award()` call site, making the canary's assertion `_events(…) == []` unfailable. It would have gone green forever while the log tallied evidence. |

**Why this is worse than an unguarded gap, which is the whole point.** An absent
control is merely missing, and the next person to look finds nothing and builds
it. A control *documented as present* stops them looking. Every reader after the
sentence is written inherits a false belief, and because the sentence is cheap
to write and expensive to falsify, it survives longer than the code would have.
DEF379's row called it *"P21 written in prose"*; three instances in one day
earns it an entry.

Note the direction of the error is always the same: the document is more
confident than the repository. Nobody writes *"this is guarded"* about something
they know is not — these were written by someone who intended to build it, or
who had built something adjacent, and the tense was never corrected.

**The invariant.** *A document may describe the past freely, but any claim in
the PRESENT tense — "is enforced", "is excluded", "fails the build" — must name
something a reader can open. If it names nothing openable, it is a plan, and it
must be written in the future tense.*

**Enforcing checks.**

- `backend/tests/unit/test_p30_registers_name_things_that_exist.py` — every file
  a register row claims in its **FILES column** must exist (368 claims today; 6
  were broken link paths and are fixed), and every backticked snake_case
  identifier cited anywhere in a row must appear somewhere in the non-`docs/`
  tree. That second check is DEF335's shape exactly: `split_after_as_of` existed
  in no file and was mechanically detectable for months. A ratchet — 14
  identifiers are legitimately absent (gitignored infra names, a memory
  filename, symbols in the read-only TradingAgents upstream) and are frozen with
  the rows that owe them; a NEW one fails, and the baseline only shrinks.
  `docs/` is excluded from the haystack deliberately: a row citing a symbol that
  appears only in another row is the circular evidence this refuses.
- **What that guard does NOT catch, stated rather than implied.** It cannot see
  DEF379 (the claim named no symbol at all) or DEF321 (a real test whose
  assertion had gone hollow). Those are the existing house rules doing their
  job: *an entry without an enforcing check is not done*, and *every guard must
  be mutation-proved*. The mechanical half is not the whole pattern, and
  presenting it as such would itself be P30.
- **The reviewer's question**, which is the cheapest of the three: when a row
  says a thing *is* guarded, open the guard. All three of these were found that
  way inside a day, by someone who happened to be working nearby.

**The guard's own self-reference, found by the guard**, and worth the line: the
baseline file lists the absent identifiers by name and lives under
`backend/tests/unit/`, so once committed it entered the haystack it is checked
against and every baselined entry read as present. It passed while the file was
untracked and failed on the first run after the commit. Left in, it would have
hollowed the ratchet entirely — any identifier added to the baseline would
justify its own presence there. The baseline is now excluded from its own
haystack, and that exclusion is itself mutation-proved.

**A related trap met while building this guard**, recorded because it is P24
inverted: a mutation was reported as SURVIVING when its anchor string did not
exist in the target file, so nothing was ever mutated. A survival claim needs
the same proof as a kill — confirm the mutation actually landed before reading
the result.

---

## P31 — an advisory signal parked where the gate can parse it

**Class:** a second opinion written into a namespace the enforcement layer reads,
so an opinion nobody meant to be binding becomes binding by regex.

**How it arises.** CR215 added a foreign, non-Claude auditor as *advisory*
insurance under the existing Claude gate. The obvious implementation — have it
write findings into the audit lane like any other reviewer — would have put a
model we neither control nor trained one string away from ruling the board.
`dispatch.sh:62` derives lane state from the last line matching
`TOK='^(#{1,6} )?\*{0,2}'` + `VERDICT: *(COMPLETE|AWAITING_FIXES)`. Any writer
into that namespace votes, whether or not anyone intended it to.

The tempting mitigation is to instruct the model not to emit the token. That is
exactly the mitigation CLAUDE.md rules out: **prompt instructions are not
controls** — CR038 measured ~70% non-compliance on emphatic instructions, and
this one is a token the model has every reason to reach for, since it is
producing something verdict-shaped.

**What generalises.** When adding an advisory producer alongside an enforcing
one, separation has to be structural and layered, not asserted:

- a **different token** the parser does not recognise;
- a **different file** the parser does not read;
- a **different branch** that never reaches the shared one;
- and a **post-hoc check** that the produced artifact does not carry the
  enforcing token anyway, run by the launcher rather than requested in a prompt.

Any one of these can be undone by a later refactor; together they fail safe.

**Enforcing check:**
`backend/tests/unit/test_cr215_foreign_harness_guard.py`. Beyond scanning
produced artifacts, it **pins the launcher's quarantine regex to `dispatch.sh`'s
own `TOK` verbatim** — so widening the board's token without widening the guard
fails the build, rather than silently leaving the guard covering a pattern the
board no longer uses. Same shape as `test_config_compose_parity.py`: two places
that must agree, made to prove they still do.
