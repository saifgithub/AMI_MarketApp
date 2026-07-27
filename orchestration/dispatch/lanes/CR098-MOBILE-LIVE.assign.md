<!-- dispatch assign lane — Architect-owned. CR052. -->
# CR098-MOBILE-LIVE — assign (scope item 8, part 1 of 2: the in-run surface)

KIND: code
INSTANCE: coder.mobile
GATE: independent    <!-- Renders a paywall-adjacent disclosure. CR090-MOBILE's sibling lane took independent audit for the same reason: a disclosure that points at the wrong remedy is the DEF059 inversion class. -->
BUDGET: $15    <!-- Saiful, 2026-07-27. Export DISPATCH_BUDGET_USD=15 at launch — do NOT reach for `ultra` to get headroom; that switches on fan-out tooling this lane does not need. -->
ACCEPTANCE: this file (criteria below). Product context: `docs/forward_planning/CR098_room_analyst_pullback/CR098_room_analyst_pullback.md` scope item 8 — **read only §"Amendment 1", §"Amendment 2" and scope item 8; the other 270 lines are backend and cost you budget.**
DEPENDS-ON: **CR098-ROOM — SATISFIED.** Audited COMPLETE round 3 (zero findings) and integrated 2026-07-27. `WITHHELD_TENURE` **survived** the audit as a 4th `LiveDataState`, so this lane's contract stands as written. **CR104-ROOM has ALSO since landed** (COMPLETE r2, suite 1373) and changed the wire contract under you — see the section below.

## ⚠️ CR104 landed after this assign was written — new REQUIRED scope

CR104 deleted the synthetic numeric baseline from the Room path. Two consequences you must handle:

1. **Fields can now be genuinely ABSENT.** Before CR104, a provider gap was silently backfilled with
   a fabricated number, so the client always received a complete fact sheet. It no longer does — a
   Yahoo outage or a loss-making ticker now yields a Room that says what it does not know.
2. **Both auditors flagged the same gap, independently.** The client has **no "intentionally thin"
   rendering**, and cannot distinguish *genuinely absent* (nobody has this datum — no lever) from
   *withheld* (we chose not to fetch it — the user has a lever). CR090-MOBILE built exactly that
   distinction for news/social with **different CTAs**; fundamentals and technicals have no
   equivalent. Rendering both identically is the DEF059 inversion class: it either tells a user to
   upgrade for data nobody has, or tells them nothing is available when a plan change would fetch it.

**Required:** the in-run surface must render *absent* and *withheld* distinctly, and must not offer
an upgrade CTA for a field that is absent rather than withheld. If you judge the full thin-state
design to be a separate lane, **say so in the hand-off with a reason and render absent fields in a
visibly non-alarming way** — but do not ship a screen that shows a thin Room as an error or as a
paywall.

## Verification split — you run the FAST tests, the Architect runs the full suite

`cd mobile && flutter test test/services/ test/widgets/ -r compact` in the **foreground**. **Do NOT
run the full suite and do NOT background anything** — four workers died today by backgrounding a long
run then emitting a final message (CR057 / `failure_patterns.md` P7), one after being told not to.
The Architect runs `flutter test` in full.
HOT-FILES: `mobile/lib/services/api/api_client.dart`, `mobile/lib/state/room_providers.dart`, the Room console screen. **`CR098-MOBILE-VERDICT` touches the same Room screen — the two run SEQUENTIALLY, not concurrently.** Four CRs sharing one file is what forced CR091/092/094/096 into a single lane; do not repeat it by running these two in parallel.

## Why this lane is split from the verdict lane

CR098-ROOM died on its budget **twice** as a single 14-criteria lane. The fix is not only more money —
it is a seam. This lane is **everything that renders while the run is streaming**; its sibling is
**the terminal verdict card**. Different files, different failure modes, independently shippable.

## ⚠️ The contract is NOT on the wire yet — CR098-ROOM round 1 audit, MAJOR 1

Track U (2026-07-27) found that `agent_withheld` **is emitted by the runner but has no branch in
`room.py`'s SSE serialiser**, so it never reaches a client at all. CR098-ROOM round 2 fixes that.

This is why the DEPENDS-ON above is hard, not advisory: until that lands, there is nothing for this
lane to parse. **Confirm the event is actually on the wire before building against it** — and if it
is not, stop and say so rather than writing a parser for an event that never arrives.

## The contract — already on the backend, do not re-derive it

Lifted verbatim from `orchestration/dispatch/lanes/CR098-ROOM.coder.room.md` §"Event/field shapes
for coder.mobile". Read that section rather than the backend diff.

- `RoomEvent(kind="agent_withheld", agent_id: AgentId, reason: "upgrade", next_step_agent: AgentId | None, next_step_days: int | None)`
  — emitted **once per withheld analyst, all at the start of the ANALYSTS phase**, before any
  analyst speaks.
  **`next_step_agent`/`next_step_days` carry the SAME value on every event in a run.** It is the
  roster's single nearest upcoming pull-back step — **not** "when does *this* analyst come back."
  Pull-back is monotonic; an analyst never un-withholds without an upgrade. Both are `None` once
  nothing further is scheduled to go dark. **Rendering it as a per-agent countdown is a lie** — it
  would tell the user their Social analyst returns in 4 days when what actually happens in 4 days is
  that News *also* goes dark.
- `live_data_notice`'s `live_data.{news,social}` can now be `"withheld_tenure"` — same event shape,
  new possible value, distinct from CR090's `"withheld_paid"`.

## Architect decisions — settled

**D1 — `withheld_tenure` must NOT reuse the credits CTA.** CR090-MOBILE renders `withheld_paid` with
a **credits** CTA and `unavailable` with **no CTA**. A tenure withhold is a third thing: the data
exists, the user could pay, but the analyst is off their roster on account age. Buying credits will
**not** bring them back. Routing it to `withheld_paid` is a DEF059-class inversion — a truthful
disclosure pointing at the wrong remedy. It needs its own copy and its own CTA target.

**D2 — this is a shipped-but-dark fix, and that is the whole point.** `withheld_tenure` is
**already live on the backend contract** the moment CR098-ROOM promotes. CR090-MOBILE's switch has a
logging `default:`, so today the app **does not crash — it renders nothing at all.** Silent. That is
the DEF038 / DEF063 / CR100 class exactly. Verify the current behaviour first and say what you saw.

**D3 — add the `agent_withheld` case to BOTH switches.** `api_client.dart` (~`:655-690`) and
`room_providers.dart` (~`:111`) each switch on the event kind. CR090-MOBILE added a logging
`default:` to them; an unhandled new kind is therefore silently dropped **twice over**. Both need the
new case or the event never reaches the widget tree.

**D4 — the locked chair renders in the analyst's real seat, at the top of the phase.** The events
arrive before any analyst speaks, so the chair must be present from the start of the ANALYSTS phase,
not appear late. A withheld analyst that pops in after three others have spoken reads as a bug.

## Acceptance

1. `flutter test` green. **Note `flutter analyze` exits 1 legitimately** — 5 pre-existing issues
   (`main.dart:69` ×2, `floor_screen.dart:73,313`, `sign_in_email_disclosure_test.dart:27`).
   Clean-on-touched ≠ globally clean; `--no-fatal-infos` exits 0.
2. **Current behaviour recorded first:** with a `withheld_tenure` value and an `agent_withheld`
   event on the wire today, state what the app does. Expected: silently nothing. Say what you
   actually observed.
3. `agent_withheld` parses in **both** switches; a test proves the parsed event reaches state.
4. Locked chair renders in the withheld analyst's seat from the **start** of the ANALYSTS phase.
5. Countdown copy is **roster-level, not per-agent** — it must not claim the withheld analyst
   returns. Assert on the rendered string.
6. `next_step_agent`/`next_step_days` **both null** ⇒ chair still renders, countdown omitted, no
   "null days" artifact.
7. `withheld_tenure` renders distinctly from `withheld_paid` and from `unavailable`, with a CTA that
   points at the tenure/plan remedy — **not** the credits CTA (D1). Mutation-check it: swap the
   handling to the credits CTA and prove a test goes red.
8. **No agent voice sells.** The CTA is app chrome. The backend lane already had to strip
   `"(upgrade to include the X Analyst)"` out of the rendered *prompt* — that was a real violation
   caught in its round 2. Do not reintroduce selling copy into anything attributed to an agent.

## Working rules

- **Create your own worktree** — `.claude/worktrees/coder.mobile-CR098-LIVE`, branch
  `lane/CR098-MOBILE-LIVE.coder.mobile`, off `main`. A worker branched inside the shared `main`
  checkout and put another track's commit onto its lane branch.
- **Commit incrementally.** Build + prove the parse (criteria 2–3), commit; then the chair; then the
  CTA. Four lane workers died mid-flight in 27h; the two that survived usefully did so purely
  because they had committed as they went.
- **Never background a command then emit your final message** (CR057 / failure_patterns P7).
- **Pathspec-commit only** — never `git add -A`, `-am`, or bare.
- Flutter: `/opt/homebrew/bin/flutter`, run from `mobile/`.
- Write your own hand-off ending with the byte-exact token `STATUS: READY_FOR_AUDIT (round 1)`, and
  your own row file. **Never hand-edit `cr_list.md`** (CR081); a healthy CR row is **6** raw cells.
- Report measurements, not expectations. List what you did **not** verify — an honest gap costs far
  less than a claim that will not reproduce.

---

ASSIGNED: coder.mobile round 1
DISPATCH: OPEN
