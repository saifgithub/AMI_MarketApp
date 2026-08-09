# CR159 — "Your Firm": desk structure on the Floor (View A)

**Status:** proposed · **Filed:** 2026-08-09 · **Category:** quality

> **This may or may not be built.** Filed as a design of record so the thinking is not lost.
> Saiful, 2026-08-09: *"The new screen design will be a different CR. It may or may not be built."*

## Context

The Room's agent graph is inherited from TradingAgents and is not defensible on its own
(Apache-2.0, ★96k). Differentiation has to live in persistence and accountability — things a
repo structurally cannot have. The first step is making the team look like a *firm the user
manages* rather than a flat grid of twelve icons.

**This is not a new screen.** [`mobile/lib/screens/floor/floor_screen.dart`](../../../mobile/lib/screens/floor/floor_screen.dart)
(541 lines, tab 0) already renders all 12 agents as tappable hexes in a centred `Wrap`
(line 409), plus the Concierge, lock states, the earn-path sheet, and a coach-mark tour.
CR159 replaces the flat `Wrap` with desk-banded tiers. Everything else on the Floor stays.

## The display

Hierarchy comes from **vertical order and band labels**. No connector lines — at 390pt wide
they are noise, and a drawn tree forces horizontal scroll or pinch-zoom, both bad on a phone.

```
┌──────────────────────────────────┐
│  YOUR FIRM                       │
│                                  │
│              ⬢  YOU              │   CEO marker — not an agent
│              ⬢  CIO              │   (was Portfolio Manager)
│  ──────────────────────────────  │
│  ANALYST DESK              4/4   │
│    ⬢     ⬢     ⬢     ⬢           │
│   FUND  TECH  MACRO  FLOW        │
│  ──────────────────────────────  │
│  RESEARCH                  2/3   │
│    ⬢     ⬢     ⬡                 │   ⬡ = unfilled seat
│   BULL  BEAR  RES-M              │
│  ──────────────────────────────  │
│  EXECUTION  1/1   RISK     0/3   │
│    ⬢              ⬡  ⬡  ⬡        │
│  ──────────────────────────────  │
│    ⬢  CONCIERGE — reports to you │
└──────────────────────────────────┘
```

Four decisions worth stating:

1. **No connector lines.** Vertical position carries the hierarchy; band labels carry the
   grouping; colour (already on `Agent.color`) carries the family. Lines add nothing.
2. **Locked renders as an unfilled seat, not a locked feature.** Same earn-path data, framed
   as hiring. A firm with three empty risk seats reads as *your firm, incomplete* — which is
   the CEO metaphor doing work instead of being asserted.
3. **Band header carries a count today, a standing metric later.** `4/4` now; hit-rate or
   override-rate when the accountability CR lands. The slot is designed in from the start so
   that CR is additive.
4. **Execution and Risk share a band.** Execution is one agent; giving it a full-width band
   wastes a third of the fold.

Tap behaviour is unchanged — the existing `agent_action_sheet` still opens. Selection
highlight is deliberately left free: it is the hook View B (the pipeline) will use to trace
handoffs across the same hexes.

## Dependencies and traps

**T-TOUR — the coach marks will break.** `FloorTour` anchors `GlobalKey`s `_agentKey0` and
`_agentKey4` to *positions* in the flat `Wrap`
([floor_screen.dart:47-52](../../../mobile/lib/screens/floor/floor_screen.dart#L47-L52)).
Re-banding moves both. The keys must be re-anchored to named agents, not indices, and the
tour re-run on device before this ships.

**T-SLICE — positional roster slicing.** Lines 342–343 do
`concierge = kAllAgents.last` and `tradingAgents = kAllAgents.sublist(0, 12)`. Grouping must
be derived from a field, never from list position, or the next roster edit silently
mis-assigns a desk.

**T-TWICE — DEF098's failure class.** `HexAvatar` is rendered in **10 files**, and CR106
already fought this exact fight: two renderers of the same data, neither a superset, is what
produced DEF143. The Verdict Board's consensus comb (`kCombVoices`) and the Floor would
become two independent arrangements of the same roster. Mitigation: the band/cluster is one
shared widget consuming `kAllAgents` plus the grouping field, and a parity test in the shape
of `test_cr106_board_parity` asserts Floor and comb agree on membership.

**T-SEQUENCE — do the rename first.** CR158 edits `displayName`/`abbreviation` in
`mobile/lib/models/agent.dart` and its backend mirror `backend/app/schemas/agents.py`. CR159
edits the same file to add the grouping field. Landing CR159 first means redoing the band
labels.

## Data change

Add a `desk` field to `Agent` in `mobile/lib/models/agent.dart`, mirrored in
`backend/app/schemas/agents.py`:

| desk | members |
|---|---|
| `officeOfCio` | Chief Investment Officer |
| `analyst` | Fundamentals · Technical Strategist · Macro & Events · Flow & Positioning |
| `research` | Bull · Bear · Research Manager |
| `execution` | Execution Desk |
| `risk` | Risk Officer ×3 |
| `concierge` | AMI Concierge |

**Do not overload `AgentFamily`.** It exists, but it lumps Research Manager and the PM
together as `manager`, which is wrong for hierarchy — Research Manager sits *inside*
Research, the CIO sits *above everything*. A sweep shows `AgentFamily` is only read in three
places, all `== AgentFamily.concierge` checks
([one_on_one_screen.dart:134](../../../mobile/lib/screens/agent/one_on_one_screen.dart#L134),
[floor_screen.dart:134](../../../mobile/lib/screens/floor/floor_screen.dart#L134),
[agent_action_sheet.dart:34](../../../mobile/lib/widgets/agent_action_sheet.dart#L34)), so
changing it is *safe* — but there is no reason to make one field mean two things.

## Steps

1. Add `AgentDesk` enum + `desk` field to `agent.dart`; mirror in `app/schemas/agents.py`.
   Assert in a test that every agent has a desk and every desk is non-empty.
2. Extract the desk band as a shared widget (label + count + hex row + unfilled-seat state).
3. Replace the flat `Wrap` in `floor_screen.dart` with the banded tiers; add the YOU/CIO
   topper. Derive every group from `desk`, delete the `sublist(0, 12)` slicing.
4. Re-anchor `FloorTour` keys to named agents; re-run the tour on device.
5. Parity test: Floor bands and `kCombVoices` agree on roster membership.

## Out of scope

- Per-agent standing / track record — separate CR, this one only reserves the slot.
- View B (the pipeline) — separate CR; `kAgentPhase` already holds the data.
- Any change to `agent_id`, which is a DB key across five tables.
- The rename itself — that is **CR158**, which must land first.

## Verification

- `flutter test` in `mobile/`, including the new desk-coverage and parity tests.
- Release build to the iPhone (`flutter build ios --release` + `flutter install`) — the tour
  and the unfilled-seat state both need a real device, not a simulator screenshot.
- Visual check at 390pt portrait that no band scrolls horizontally and the YOU/CIO topper
  plus at least two bands are above the fold.
