<!-- CR109 architect brief — the front door to a ten-document package. Written for an
     Architect who has never seen CR109: what it is, what can be laned today, what is
     gated and on what, the non-negotiables, and the decisions that are Saiful's rather
     than anyone's to design around. Read this first; it tells you which of the other
     nine documents you actually need. Design stage; nothing here assigns work. -->

# CR109 — architect brief

**Read this first.** The package is ten documents and ~4,900 lines. This one is the front door:
it tells you what to read, what you can lane today, and what you must not.

`AT:Gamer`, 2026-07-30. **Status: `proposed`, design complete, not laned.**

---

## 1. What it is, in five lines

A **P&L competition played in AMI Cash**, separate from the training simulator. A player does not
own a game account — they **enter runs**: 10,000 AMI Cash fresh at entry, one open field per
cadence, scored on time-weighted return. No Room, no 12 agents, no mandate during play. *The Room
is the classroom, the game is the exam* — and also the lab, where going wild is sanctioned and its
cost is measured rather than prevented.

**Why it is large:** it is a new subsystem (schema, service, API, ~20 mobile surfaces) that also
crosses a standing product guardrail. **Why it is smaller than it looks:** at alpha field sizes the
entire contest layer is inert, so the expensive machinery is not on the critical path.

---

## 2. What you can lane today — and what you cannot

This is the only section that decides what you do this week.

| Slice | Ready? | Blocked on |
|---|---|---|
| **1 · the NAV spine** | **YES — lane now** | nothing |
| **2 · the run** | almost | **naming** (§4) |
| **3 · the close** | no | **the compliance work** (§5) |
| 3b/3c · duels, desks | no | slice 3 |
| 4+ | no | Gate 1 (§4), and slice 3 |

**Slice 1 is the right first assign for four independent reasons**, any one of which would justify
it alone:

1. **Zero compliance surface.** It ships the equity curve to the **training** portfolio. It touches
   nothing D-060 forbids, so the legal work in §5 does not gate it.
2. **No naming needed.** No game-facing strings, so the unresolved naming question (§4) does not
   bite.
3. **No CR133 dependency.** It lands in the existing `mobile/lib/screens/sim/portfolio_screen.dart`,
   not a new nav destination.
4. **Valuable even if CR109 is never built.** *The app cannot draw a portfolio's equity curve
   today.* Slice 1 fixes that on the training side regardless of what happens to the game.

Draft assigns are in [`lane_drafts/`](lane_drafts/) — written in the §3 format, ready to lift into
`orchestration/dispatch/lanes/` and rename. **They are drafts in my folder on purpose:** `lanes/` is
your write path, and the protocol's disjoint-path guarantee is worth more than my convenience.

---

## 3. What to read, and what you can skip

Ten documents. You do not need all of them to lane slice 1.

**To lane anything — read these two:**

| Document | Lines | Why |
|---|---|---|
| [`implementation_plan.md`](implementation_plan.md) | 752 | **The laning document.** Schema DDL, API contracts, slices with per-slice acceptance, the fences, the lane split, a 47-row test matrix. Written so an assign can say *"read this in full, do not re-derive."* |
| **This brief** | — | the boundaries |

**To review the design or answer a lane's question — read this:**

| [`CR109.md`](CR109.md) | 2,291 | The design. §3 is the spine and derives most of the rest; §12.2 answers the cross-product questions a lane hits at 2am; §20 records what the review series changed. |

**Only if you need the reasoning behind a specific decision:**

`playability_review.md` · `final_review.md` · `games_roadmap.md` (mine) and
`psychology_review.md` · `comparative_review.md` · `trade_execution_addendum.md` ·
`playability_addendum.md` · `review_synthesis.md` (an independent `AT:Fable` review series Saiful
commissioned before committing build cost). **Every item in that series has a disposition in
§20** — you do not need to read them to know what was accepted.

---

## 4. Decisions that are Saiful's, not yours

**Do not design around these. Ask.**

| Decision | Blocks | Why it can't be inferred |
|---|---|---|
| **Gate 1 / Gate 2 targets** — activation and close→re-entry rates | funding slice 4 | Must be set **before** the build, or the gate gets argued backwards from whatever the data turns out to be. That is the whole point of a gate. |
| **Naming** — the game, a run, the boards, the sixth title rung | **slice 2** | Every new string set carries `retranslate:[ar,ms]`. Naming after the strings exist means paying for translation twice. **AMI Cash is settled** as the money. |
| **The training-milestone gate** — must a player clear training before their first entry? | slice 3c routing | It delays the headline feature either way. Product call. |

**Eight tuning constants are open but block nothing** — first cuts exist for all of them, they all
live in one module (`games_scoring.py`), and §18 of the design is generated from it. Build against
the first cuts; retuning is one line and a failing test.

---

## 5. The compliance gate — the real reason this isn't fully laned

**Four governing documents currently forbid what slice 3 ships**, and one of them is binding rather
than advisory:

| Where | Action needed |
|---|---|
| `roadmap.md:138` — "P&L-based leaderboards — encourages gambling psychology" | strike or amend |
| `decision_log.md:302` — **D-060**, which rejected exactly this | superseding decision |
| `daily_and_streaks.md` — "Sim P&L — 0, explicitly not counted" | amend |
| `legal/policies/competition_rules.md` v1.0 §1, §8 | re-version to **v2.0**, with the §8.5 eligibility clause |

Plus: **CR064 bound the zero-P&L rule as *a binding invariant, not a design note*** because the App
Store *"simulated gambling: No"* declaration depends on it. That declaration must be re-validated
before any scored surface ships.

**None of this is engineering, and it runs in parallel.** Slices 1–2 carry zero compliance surface,
so starting them buys the legal work weeks of runway. Slice 3 is the first user-visible scored
surface and cannot ship before it lands.

---

## 6. Non-negotiables — the fences that must survive laning

Full list in `implementation_plan.md` §7.2. These are the ones where a reasonable-looking shortcut
silently breaks something:

1. **`portfolio_nav_daily` must NOT foreign-key to `sim_portfolios`.** `reset_portfolio()`
   (`sim_engine.py:394`) hard-deletes the portfolio row and every trade; a FK cascades the game's
   entire history away on the first restart. Key on `user_id` + `run_id`. **A test must assert
   snapshots survive a reset**, or this regresses silently.
2. **Do not add a `skip_compliance` flag to `sim_engine.submit()`.** The game needs no mandate; the
   training path needs it always. Extract the shared mechanics and keep **two public entry
   points** — structural, per CR040. A boolean that disables the safety floor ends up `True` on the
   training path one day.
3. **The career ledger clamps at write time, not on read.** Clamping the display leaves the player
   carrying an invisible debt — they earn points and the screen does not move.
4. **The trading fee is burned.** No table, no counter, no field total. A pool of forfeited stakes
   is a wagered stake and the compliance position dies.
5. **The one-per-cadence guard is `kind='open'`-scoped, not cadence-scoped.** Writing it
   cadence-scoped is the natural mistake and it silently blocks duels and private fields.
6. **Boards rank % TWR only** — never absolute AMI Cash, and never another player's cash on any
   surface.
7. **Fills only during US market hours.** Out-of-hours orders queue. Not an arena rule — the engine
   fills at the current quote whenever called, so out-of-hours trading is a time machine.
8. **No paid feature may alter a run's inputs, scoring or ranking.** Post-close explanation is the
   entire permitted surface for plan tier.

---

## 7. Dependency: CR133

CR109 assumes the game has a home in the shell and **deliberately does not say where.** That is
**CR133** (`proposed`, spec + prototype), which has already chosen: **GAME takes nav slot 3**, `YOU`
takes slot 5, Settings comes off the bar. CR133 supersedes CR109's old §9.0.

They should be **developed together and may be shipped apart** — the game can live behind the Floor
card until CR133's destination exists. Slice 1 has no CR133 dependency at all.

---

## 8. Lane split

Disjoint write paths, per CR052.

| Lane | Owns | Fences |
|---|---|---|
| `coder.api` | `models.py` + alembic, `trading_math/twr.py`, `games_scoring.py`, `games_service.py`, `api/games.py`, the `main.py` tick, `merge_service.py` | do not touch `mobile/` |
| `coder.mobile` | `screens/games/`, the equity curve, the trade ticket, the Close, the Record, ARB strings | do not touch `backend/`; **no nav changes** (CR133) |
| CR133's lane | `home_shell.dart`, `hex_bottom_nav.dart`, the tab-index enum | do not implement game surfaces |

**Amendment D made the slice-2 mobile work larger than the original plan implied** — the 3-tap
ticket, the queue-first rhythm, the heat gauge and the one-screen entry fence. Worth its own assign
rather than riding along with the lobby.

---

## 9. State of the package

- **10 documents, ~4,900 lines.** Register row is `proposed`; flip it to `in progress` when you
  assign, and tell me — I own `_registry/CR109.row.md` and will regenerate.
- **Committed and clean.** ~17 `AT:Gamer` commits; `verify cr` OK at 129 rows.
- **`infra/PROMOTION_HOLD.md` — no active holds.**
- **Visual companion** (mockups, the pipeline, 20 screens):
  `https://claude.ai/code/artifact/b47a68ca-8a2c-4dc6-84af-c99f26867ed2`
- **Nothing is approved for build.** This brief describes readiness, not permission — Saiful decides
  when it starts.
