# DEF068 — Which lessons unlock an agent is invisible

**Status:** fixed · **Session:** AT:R60 · **Filed:** 2026-07-19
**Source:** `bug:d37cc9d0` — user-reported, `ui_glitch`, 2026-07-19 10:58 UTC
**Report:** *"why does it always say 0/3 gateway done"* — from the locked agent screen

## The report is not a UI glitch

It is a correct reading of a real number. Verified against the Alpha DB, the top alpha user
has **passed 50 lessons and unlocked 1 of 12 agents**:

| agent | gate | gateway lessons | why |
|---|---|---|---|
| `fundamentals_analyst` | **0/3** | 032, 033, 034 | user never reached the Fundamentals block |
| `aggressive_debator` | **0/3** | 052, 056, **225** | third gate is lesson 225 of 292 |
| `conservative_debator` | **0/3** | 047, 049, 050 | |
| `trader` | 1/3 | 014, 015, 016 | 014 + 016 were DEF064 dead quizzes until 2026-07-18 |
| `portfolio_manager` | 1/3 | 013, **014**, 017 | same |
| `neutral_debator` | 1/3 | 061, **236**, **238** | two of three gates are deep |
| `research_manager` | 1/3 | 057, 064, 077 | |
| `bull_researcher` | 1/3 | 036, 059, **155** | |
| `market_analyst` | 2/3 | 005, 006, 020 | |
| `news_analyst` | 2/3 | 005, 063, **151** | |
| `bear_researcher` | 2/3 | 046, 058, 060 | |
| `social_media_analyst` | **3/3 ✓** | 045, 046, 048 | the only unlock |

Both alpha users with meaningful progress — 50 and 28 lessons passed — hold exactly one
`agent_activations` row each, and it is `social_media_analyst` for both. That is the entire
earn-path economy in production.

## Mechanism

**Gateway selection is incidental, not designed.** `_gateway_lessons_for_agent`
([`lessons_service.py:424-434`](../../../backend/app/services/lessons_service.py)) takes *the
first `UNLOCK_REQUIRED_PER_AGENT` (3) lessons, sorted by lexicographic id, whose
`agent_callouts` names that agent*:

```python
all_lessons = sorted(
    (l.meta.id for l in self._lessons.values()
     if agent_id in l.meta.agent_callouts),
)
return all_lessons[:UNLOCK_REQUIRED_PER_AGENT]
```

Nobody chose 032/033/034. Nobody chose lesson 225. They are whatever sorted first. Three
consequences:

1. **`market_analyst` is named by 71 lessons; 3 count.** `lesson_tile.dart:28` renders every
   callout as an identical hex avatar, so a gateway lesson looks exactly like the other 68.
   There is no way to find the 3 by browsing.
2. **The gates are unreachable in learning order.** A user progressing through Foundations
   then Sentiment (which is what the top user did) hits three agents at literal 0/3 while
   having passed 50 lessons.
3. **A new lesson can silently steal a gate.** Authoring a low-numbered lesson with an
   `agent_callouts` entry reassigns that agent's gateway set with no signal to anyone.

### Three compounding faults

- **The copy is factually wrong.** `app_en.arb:84` — *"Earn this agent free by passing
  **every** lesson that involves them:"* The gate is 3. For `market_analyst` this instructs
  the user to pass 71 lessons while the checklist immediately below shows 3.
- **No API returns what remains.** `GET /v1/lessons/progress/{user_id}` returns
  `agents_unlocked` only; `activations` returns unlocked agents only; `QuizSubmitResponse`
  returns agents unlocked *by that submission*. Nothing anywhere says "you need these two
  more." So `floor_screen.dart:142-151` re-derives the gateway set client-side behind a
  hardcoded `const gatewaySize = 3` — a duplicate of the backend constant that will silently
  diverge the moment either moves. It is moving in this defect.
- **The counter can exceed its own maximum.** `_check_agent_unlocks` writes an `earn_path`
  activation row for `concierge` (26 callouts) even though the Concierge is never gated —
  `floor_screen.dart:300` renders `kAllAgents.sublist(0, 12)` and the Concierge separately. A
  user who passes 065/066/067 gets a 13th row, and both "/ 12" counters
  (`floor_screen.dart:362`, `lessons_screen.dart:194`) read **"13 of 12 unlocked"**.

The Concierge is also structurally unable to help: `concierge_prompts.py` gives it the full
lesson catalogue and the unlocked-agent set, but **no mapping between them**. Any specific
answer it gives to *"what do I read to unlock the Trader?"* is a guess.

## Fix

**Gate rises to 5 and is curated** (Saiful: *"Let's increase it to 5 and we will curate"*).

- `backend/app/services/agent_gateways.py` — `AGENT_GATEWAYS: dict[str, list[str]]`, 12 agents
  × 5 explicit lesson ids, plus `GATEWAY_SIZE = 5`. `_gateway_lessons_for_agent` reads the map;
  `UNLOCK_REQUIRED_PER_AGENT` is removed.
- **`agent_callouts` widened first.** Four agents have only 6 callouts total, so a 5-gate
  would leave essentially no curation freedom and force deep gates:

  | agent | callouts | at gate=5 without widening |
  |---|---|---|
  | `news_analyst` | 6 | must use 5 of 6; only early option is `005` |
  | `social_media_analyst` | 6 | must use 5 of 6; all L4 |
  | `aggressive_debator` | 6 | must use 5 of 6; four are L5 lessons 225–227 |
  | `neutral_debator` | 6 | must use 5 of 6; 236/238/241 all deep |

  Additional callouts are added to suitable early/mid lessons so each agent has a real pool
  with an early-track option before the 5 are picked.
- `LessonMeta.gates_agents` — derived from the curated map at load, so the lesson list can
  badge gateway lessons without a second call. This is the direct fix for "50 lessons, 0/3".
- **New** `GET /v1/lessons/requirements/{user_id}` — per agent: `agent_id`, `unlocked`,
  `required: [{lesson_id, code, title, passed}]`, `remaining_count`. Authoritative; the client
  deletes its local derivation and its hardcoded `gatewaySize`.
- No `earn_path` row for `concierge`.
- Copy corrected; gateway lessons listed by CR044 code + title.
- Concierge context gains the per-agent remaining-lesson map.

### No revocation

Activation rows persist and `_check_agent_unlocks` only ever runs on a fresh passing submit,
so the two existing `social_media_analyst` holders keep their agent even though the gate grew
from 3 to 5. This matters: a gate change that retroactively removed an earned agent would be
a takeaway, and users would be right to read it as one.

## Acceptance

- `AGENT_GATEWAYS` covers all 12 agents with exactly 5 entries each; every id exists; every
  gateway lesson declares that agent in its own `agent_callouts` (otherwise the tile's hex
  avatars lie about which agent a gate belongs to). All four enforced by the corpus test.
- Recomputing alpha user `054c4efe` (50 passed) under the curated map moves the three `0/x`
  agents off zero.
- Locked-agent sheet renders 5 lessons by code + title with real ticks and an `n / 5` counter,
  sourced from the endpoint — no client-side gateway derivation remains.
- Gateway lessons are visually distinguishable in the lesson list.
- The Concierge names the 5 curated lessons for a locked agent, and only those.
- `bug_reports.d37cc9d0` → `resolved` once verified on Alpha.

## Related

- **DEF064** — the 12 unanswerable quizzes; `014` and `016` are `trader`/`portfolio_manager`
  gateways, so that defect *also* held two agents shut. Fixed 2026-07-18; this defect is why
  nobody noticed for months.
- **CR044** — the lesson codes this defect's UI and prompts reference.
- **P3** in [`failure_patterns.md`](../../initial_specs/08_tech/failure_patterns.md).
