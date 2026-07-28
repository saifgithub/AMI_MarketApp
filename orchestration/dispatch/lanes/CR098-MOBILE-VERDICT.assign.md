<!-- dispatch assign lane — Architect-owned. CR052. -->
# CR098-MOBILE-VERDICT — assign (scope item 8, part 2 of 2: the verdict card)

KIND: code
INSTANCE: coder.mobile
GATE: independent    <!-- A new VerdictAction with every level field null is a crash surface, and the closing disclosure is paywall-adjacent. Same reason CR090-MOBILE took independent audit. -->
BUDGET: $15    <!-- Saiful, 2026-07-27. Export DISPATCH_BUDGET_USD=15 at launch — do NOT reach for `ultra` to get headroom. -->
ACCEPTANCE: this file (criteria below). Product context: `docs/forward_planning/CR098_room_analyst_pullback/CR098_room_analyst_pullback.md` — **read §"Amendment 2" and §"The message must read as professional discipline, not as a paywall" ONLY. That second section is the copy brief and it is the point of this lane.**
DEPENDS-ON: **CR098-ROOM audited COMPLETE and integrated**, AND **`CR098-MOBILE-LIVE` landed first**. Both touch the Room screen — they run **sequentially**. Rebase onto LIVE before you start.
HOT-FILES: the Room verdict card + `mobile/lib/services/api/api_client.dart` verdict parsing. **Overlaps `CR098-MOBILE-LIVE` — that lane goes first, you rebase.**

## Why this lane is split from the live lane

CR098-ROOM died on its budget **twice** as one 14-criteria lane. The sibling lane owns everything
that renders **while the run streams**; this one owns **the terminal verdict card**. This half is
the higher-risk of the two: it introduces an enum value that makes previously-non-null fields null.

## The contract — already on the backend, do not re-derive it

From `orchestration/dispatch/lanes/CR098-ROOM.coder.room.md` §"Event/field shapes for coder.mobile":

- **`Verdict.action` can now be `"NO_VERDICT"`** — a new member of the existing
  APPROVE/REJECT/MODIFY/PASS enum. `use_enum_values=True`, so it arrives as the bare string in JSON.
- **When `NO_VERDICT`, EVERY level field is `null`** — `size_pct`, `entry`, `target`, `stop`,
  `time_horizon_days`. **This is the crash risk.** Any non-null assumption in the verdict card —
  a `!`, a non-nullable field, a `.toStringAsFixed()` on a null double — throws at runtime on a real
  user's screen.
- **`Verdict.opinions_not_included: list[str]`** — `AgentId` *values* (e.g. `"social_media_analyst"`),
  **always present, empty list when nothing was withheld**, on **every** verdict regardless of action.

## Architect decisions — settled

**D1 — prove the null-safety by construction, not by inspection.** Do not read the card and conclude
it is fine. Feed a `NO_VERDICT` fixture with every level field null through the real parse-and-render
path and assert it renders. Then assert the level fields are **absent**, not rendered as `"null"`,
`"0"`, `"-"`, or an empty row that looks like a real zero-size position. A zero-size trade
recommendation shown to a user in a training simulator is worse than an error.

**D2 — `NO_VERDICT` must not read as a failure or an outage.** The spec's copy brief is explicit and
it is the acceptance, not decoration: (a) **the PM never sells** — no upgrade language, no plan
names, no pricing in anything attributed to an agent; (b) **credit the work that was done** — the
fundamentals case *was* argued in full by real agents; (c) **name the missing input factually, not
as a lack** — "this session ran without a market read", not "you are missing the Market analyst."
The upgrade CTA is app chrome, visually separate from the PM's voice.

**D3 — `opinions_not_included` renders on EVERY verdict, not only `NO_VERDICT`.** It is always
present and usually empty. An `APPROVE` with Social withheld must still disclose that Social was not
in the room — that is the honesty the whole CR exists for. Gating the disclosure on
`action == NO_VERDICT` silently drops it for the common case and is a DEF059-class inversion.

**D4 — empty list ⇒ render nothing.** No empty header, no "None", no stray divider. Today's verdict
card must be byte-identical when `opinions_not_included == []`, which is what every existing user
sees until a threshold is set. Prove it.

## Acceptance

1. `flutter test` green. **`flutter analyze` exits 1 legitimately** — 5 pre-existing issues
   (`main.dart:69` ×2, `floor_screen.dart:73,313`, `sign_in_email_disclosure_test.dart:27`).
   `--no-fatal-infos` exits 0.
2. **Current behaviour recorded first:** feed today's client a `NO_VERDICT` payload with null level
   fields and state what happens — renders, throws, or renders something wrong. Measure it, do not
   predict it. This is the single most useful number in your hand-off.
3. `NO_VERDICT` + all-null level fields renders without throwing, through the real parse path.
4. Level fields are **absent**, not `"null"` / `"0"` / `"-"` / an empty-looking zero-size row (D1).
5. `opinions_not_included` renders as a closing disclosure on **every** action, `NO_VERDICT` and
   `APPROVE` alike (D3). Assert on an `APPROVE` case specifically.
6. **Empty list ⇒ byte-identical to today's card** (D4).
7. Agent-attributed copy contains no upgrade language, plan names, or pricing (D2a). Assert on the
   rendered string. The backend lane had a real violation of exactly this caught in its round 2.
8. The upgrade CTA is visually distinct from the PM's voice — app chrome, not agent speech.
9. Unknown/future `action` values do not crash the card. CR090-MOBILE's SSE switches gained a logging
   `default:`; confirm the equivalent holds here, because `NO_VERDICT` proves this enum grows.

## Working rules

- **Create your own worktree** — `.claude/worktrees/coder.mobile-CR098-VERDICT`, branch
  `lane/CR098-MOBILE-VERDICT.coder.mobile`, **off `lane/CR098-MOBILE-LIVE.coder.mobile` once it has
  landed on `main`** (rebase onto `main` after it integrates).
- **Commit incrementally.** Prove the null-safety (criteria 2–4) and commit that *first* — it is the
  crash fix and is independently shippable. Copy work after. Four lane workers died mid-flight in
  27h; ordering by risk is what makes a death survivable.
- **Never background a command then emit your final message** (CR057 / failure_patterns P7).
- **Pathspec-commit only** — never `git add -A`, `-am`, or bare.
- Flutter: `/opt/homebrew/bin/flutter`, run from `mobile/`.
- Write your own hand-off ending with `STATUS: READY_FOR_AUDIT (round 1)` and your own row file.
  **Never hand-edit `cr_list.md`** (CR081); a healthy CR row is **6** raw cells.
- Report measurements, not expectations. List what you did **not** verify.

---

ASSIGNED: coder.mobile round 1
DISPATCH: ACCEPTED (round 1)

Auditor `VERDICT: COMPLETE (round 1)`, **BLOCKER 0 · MAJOR 0 · MINOR 0**, delivered at `18b81fd`;
audited SHA `89d3f95`. Merged to `main` at `fbc96da` and re-verified **on main after the merge**:
`flutter test` **143/143**, `flutter analyze --no-fatal-infos` exit **0**.

**This closes CR098** — `CR098-ROOM`, `CR098-MOBILE-LIVE` and `CR098-MOBILE-VERDICT` are all DONE.

Carried out of the lane, not fixed here: the 4 new `ar`/`ms` strings (folded into **DEF137**), the
duplicate `_resetDateStr` in `room_screen.dart`, and **CR106**'s overlap on this same surface.
