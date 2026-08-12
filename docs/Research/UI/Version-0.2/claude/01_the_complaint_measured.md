# 01 — The complaint, measured

> *"The UI is not very friendly, and a little bit too much. It's like walking into a meeting
> with 12 staff waiting for you."* — user feedback, relayed by Saiful, 2026-08-12.

The complaint names two surfaces. Both are measured below; the numbers come from the shipped
widget tree and from `prototype/concepts.html` frame `0-baseline` (method and limits in
`00_method_and_limits.md`).

## 1. The Floor at rest — the surface the user lands on

Post-onboarding, the app opens on the FLOOR tab (`home_shell.dart:30-36`, tab 0 of five).
`floor_screen.dart` stacks one scroll column:

| Order | Element | Source |
|---|---|---|
| 1 | Logo + streak chip | `floor_screen.dart:361-380` |
| 2 | **Concierge hex, 110pt**, pulsing `recentCall` status | `:383-392` |
| 3 | "AMI CONCIERGE" + pink tagline | `:394-399` |
| 4 | "YOUR TEAM" + "8 of 12 unlocked…" | `:403-408` |
| 5 | **Wrap of twelve 72pt agent hexes**, locked at 0.35 opacity + padlock | `:410-429`, `_AgentTile :509-565` |
| 6 | Daily Challenge card | `:434-437` |
| 7 | Weekly League card | `:441` |
| 8 | **CONVENE THE ROOM** CTA + caption | `:445-457` |
| 9 | restart-onboarding link, footer | `:462-496` |

Code-exact counts:

- **13 identity marks** render at rest — the Concierge plus all 12 trading agents
  (`kAllAgents`, `models/agent.dart:45-159`), each colour-coded by family and individually
  labelled. At 390pt the Wrap lays out 3 tiles per row → **4 rows of faces**.
- **The CTA is below everything.** The one action the core loop revolves around — Convene —
  stacks *after* the roster, the challenge and the league. In the baseline frame that puts
  its top edge at **1027px, 1.63 folds down** (fold = 632px); the user scrolls past the
  whole meeting to reach the meeting's purpose.
- **The first-run tour doubles down.** `floor_tour.dart` runs 5 coach-mark stops
  (`floor_screen.dart:49-53`): Concierge → agent #0 → agent #4 → challenge → convene. Three
  of five stops spotlight faces; the roster is presented as the product.
- Above the fold at rest: **10 of 13 identity marks, 16 of 23 tap targets** (baseline frame,
  DOM-read). The first screen is almost entirely *people*, no *task*.

The spec meant to do this: `docs/initial_specs/05_design/floor_home_honeycomb.md` wants the
user to read the Floor as *"a room with people in it, not a dashboard with options."* It
succeeded. The feedback is the cost of that success, paid by users who walked into the room
with no relationship to the people yet.

## 2. The Room live — the surface the user waits in

`room_screen.dart:382-405` (`_RoomLiveRoster`, CR112): the live phase pins **all 12 seats
from the first frame** — `kAllAgents.sublist(0, 12)`, one status row each, cycling
waiting / thinking / responded / interrupted (`:408-421`). A first-time user who asked one
question about one ticker watches a 12-row org chart animate for ~2 minutes.

The *settled* Room already solved its half of this: CR106 made the Verdict Board the
persisted default and collapsed the transcript behind a toggle, because — quoting the CR —
*"most users do not want to read too much."* The live phase never got that pass. CR106 fixed
the destination; the journey still seats the full firm
(`room_view_mode_provider.dart:1-14` documents the default's reasoning).

## 3. What the numbers say together

| Surface | Marks at rest | Task visibility |
|---|---|---|
| Floor (shipped) | 13 (10 above fold) | CTA 1.63 folds down |
| Room live (shipped) | 12 seats, frame one | verdict arrives after all 12 |
| Verdict Board (CR106, shipped) | 12 — *after* the verdict | verdict is the screen |

The pattern: identity-first while the user wants task-first, until the very last screen,
which got it right. Both recommended concepts (`05_recommendations.md`) are that last
screen's logic applied earlier.

## 4. Paper trail

No prior written record of this complaint exists: a sweep of `docs/` for
overwhelm/intimidate/cluttered/too-much language finds nothing about the Floor or the live
Room. Two structural reasons it took until now:

- The in-app feedback loop is open at both ends (CR043) — free-text UI gripes have no
  reliable capture path into `bug_reports`.
- CR004's `plan_b_playability_ux.md` audited navigation and found it fine (every key action
  ≤2 taps) — true, and orthogonal. `06_answering_cr004.md` takes that claim seriously.

This document is the complaint's first durable record.
