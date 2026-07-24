# DEF098 — Nothing ties a computed live-data field to the prompt that renders it, and two divergent renderers each drop what the other keeps

**Filed:** 2026-07-24 · **Source:** prompt-reported (Saiful, after DEF096: *"do it but register a
different def"* — run the set-vs-render sweep across every prompt surface and file the general guard
separately)
**Track:** AT:R59 (protect-the-Room lane — diagnosis + brief; the build team fixes)

---

## The class, not the instance

DEF074 (`support` computed, dropped, 52-week low shown instead) and DEF096 (three live Reddit fields
computed, dropped) are the same bug twice. This defect is the **class**: a field the data pipeline
computes must appear in the prompt block the consuming agent reads, and **nothing enforces that.**
CLAUDE.md's own rule — *second occurrence of anything ⇒ add an entry with a guard* — is triggered.
This is the guard.

## Root cause: two renderers, no parity, neither a superset

Live ticker data has **two independent rendering paths**, built at different times and never
reconciled:

| path | renderer | consumer |
|---|---|---|
| **Room** | `room_runner.py` sets `profile[...]`, `room_prompts.py::_format_profile()` renders it | all 12 Room agents |
| **1-on-1 chat** | `build_live_data_block` / `build_technicals_context_block` / `build_news_context_block` / `build_social_context_block` / `build_journal_context_block` | the single analyst in a 1-on-1 |

They have drifted, and the drift goes **both ways** — proof that neither is authoritative:

| live field | Room `_format_profile` | 1-on-1 blocks |
|---|:--:|:--:|
| Reddit mention volume + trend (`mention_trend`) | **dropped** ❌ | rendered ✅ |
| most-active communities (`influencer_take`) | **dropped** ❌ | rendered ✅ |
| buzz score + bull/bear split (`pattern`) | **dropped** ❌ | rendered ✅ |
| next earnings date + consensus EPS | rendered ✅ | **dropped** ❌ |
| fundamentals (P/S, EV/EBITDA, PEG, FCF, sector, dividend, analyst) | rendered ✅ | rendered ✅ |
| technicals (RSI, trend, volume, support, breakout) | rendered ✅ | rendered ✅ |

The Room drops the social trio (that is DEF096). The 1-on-1 path drops next-earnings — computed in
`room_runner.py` from `get_market_data_provider().earnings()`, but the 1-on-1 fundamentals block
never fetches or shows it (`agent_runner.py:187-216` injects live-data / news / social / technicals /
journal and no earnings). **Neither renderer is a superset of the other.** A field is safe only by
the accident of a developer remembering to hand-write it into two places.

## The precedent that already solved this shape for a different resource

`backend/tests/unit/test_config_compose_parity.py` exists because a config value defined in one place
(`settings`) was silently not forwarded in another (`docker-compose.yml`), and a feature shipped dark
twice (DEF038, DEF063). CLAUDE.md codifies it: *"Adding an env-driven setting? Forward it in
docker-compose … the parity test fails the build otherwise."* That is **exactly this bug for a
different resource** — a thing computed in one place, required in another, with no automatic link.
The fix here is the prompt-data analogue of that test.

## The sweep (all prompt surfaces, per Saiful's ask)

Proactive, not symptom-driven — every LLM-prompt-assembling surface in `backend/app/services/`:

- **Room** — social trio dropped (**DEF096**); Trader receives no derived R:R / drawdown for its own
  proposal (**DEF095**). Both already filed.
- **1-on-1 chat** — next-earnings date/EPS absent (above); every other block complete and, for
  social, *richer* than the Room. Worth a one-line follow-up, folded into the DEF096 fix rather than
  re-filed.
- **Concierge** (`build_concierge_messages`) — `_format_journal()` renders `entry_type + ticker +
  title` and drops `summary`, `user_note`, `tags`, `agents_involved`, `created_at`. **Judged
  intentional, not a defect:** the Concierge's job is to *route* to an entry ("open that one"), not
  to analyse it, so a compact index is correct. Flagged here only so the parity registry records it
  as a deliberate omission rather than an accidental one — which is the whole point of the guard.
- **Room researchers' journal** (`build_journal_context_block` → `format_journal_entry`) — renders
  `date + title + outcome`, drops `summary` and `user_note`. **Weaker, arguable:** DEF054/055 frame
  this as a decision-*lookback* so bull/bear can learn from past reasoning, and the reasoning lives
  in `summary`/`user_note`. Not filed as a defect — recorded as a question for the fix lane to
  decide deliberately, not by omission.
- **Technicals / news / fundamentals blocks** — every field the fetcher produces is rendered.
  Clean.
- **Coach, Daily Challenge** — content-retrieval services (`get_by_id` / `search`), not prompt
  assemblers. No computed field to drop. Out of class.

**Net: two real defects (DEF095, DEF096), one cross-path asymmetry (earnings), and two
by-design omissions that should be *declared* rather than *accidental*.** The instances are
containable; the absence of a guard is not.

## Proposed fix (build team owns it)

A **prompt-data parity test**, modelled on `test_config_compose_parity.py`:

1. For each live source (`fundamentals`, `technicals`, `news`, `social`, `earnings`, `journal`),
   enumerate the fields its fetcher/formatter produces.
2. Assert each field is either **present in the rendered block on every surface the consuming agent
   reads** (Room `_format_profile` *and* the matching 1-on-1 block), or **listed in an explicit
   `INTENTIONALLY_OMITTED` registry with a one-line reason** (e.g. "Concierge routes, does not
   analyse").
3. The test fails the build on a computed field that is neither rendered nor declared — turning
   DEF074/DEF096 from "spotted by luck months later" into "red on the commit that drops it."

Stronger structural option, if the build lane judges it worth the refactor: **collapse the two
renderers to one field registry** both paths derive from, so drift is impossible rather than merely
detected. The parity test is the minimum; the single source of truth is the cure.

**Guard-on-the-guard:** the registry must enumerate fields from the *fetcher's output*, not from a
hand-kept list, or it rots the same way — the check has to read what the pipeline actually produces.

## Governance

Relates to **DEF074** and **DEF096** (the two instances of this class), **DEF095** (the Room's other
data hole, found in the same audit), **CR040** (degrade-loudly — a silently-dropped field is the
quiet-failure this rule exists to forbid), and **CR038/failure_patterns** (add the guard on second
occurrence). Diagnosis + brief only from this lane; needs an architect lane, `coder.api` owns the
prompt-assembly files and the new test.
