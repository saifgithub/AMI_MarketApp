# UI v0.2 — Alternative UI research (Kimi)

**TRACK: K · ROLE: Kimi · INSTANCE: -**

## Problem

Alpha user feedback: *"The UI is not very friendly, and a little bit too much —
like walking into a meeting with 12 staff waiting for you."*

Root cause ([audit](research/01_current_state_audit.md)): the app presents its
machinery — 12 agents, debate phases, transcripts — as the interface. The
user's real questions (*what today? how am I doing? what's next?*) are buried
under the org chart.

**Design constraint:** the 12-agent team is the product's differentiator and
must not be deleted — only demoted from the home screen to a depth layer,
surfacing as *evidence* (consensus, named dissent) rather than a wall of faces.

## Method

1. Audited the current Flutter UI screen-by-screen for overwhelm points.
2. Researched proven complexity-hiding patterns with sources
   ([pattern research](research/02_pattern_research.md)): progressive
   disclosure (Nielsen), fintech minimalism (Robinhood), guided paths
   (Duolingo — including its backlash), agent-UX control surfaces, Jakob's
   Law, single-character front doors.
3. Derived a 4-layer disclosure model both recommendations share:
   **L0 brief → L1 verdict → L2 debate → L3 machinery.**
4. Wrote up 4 concepts; built tappable HTML mockups for the 2 recommended.

## Concepts compared

| | Cognitive load | Depth access | Effort | Risk |
|---|---|---|---|---|
| **A — Concierge Briefing** ★ | Low (1 briefing, 1 action) | Team 1 tap, debate 2 taps | M (recomposes existing widgets) | Low — keeps current IA and engagement loops |
| **B — Today Feed** ★ | Lowest (3 cards) | All depth 1 tap via cards/MENU | M–L (new daily-aggregation surface) | Medium — demotes team/journal/league; needs strong "quiet day" state |
| C — Team Deck | Medium (grid folded, still present) | Unchanged | S | Low — but under-delivers on the feedback |
| D — Chat-first | Lowest visually | Poor (prompt-box discovery) | M | High — fails agent-UX evidence; rejected |

- ★ **A — [Concierge Briefing](concepts/concept_a_concierge_briefing.md)** —
  the Concierge narrates one briefing with one action; the 12 agents collapse
  into a single card → family-grouped team screen; Room defaults to the CR106
  verdict board.
- ★ **B — [Today Feed](concepts/concept_b_today_feed.md)** — a 3-card daily
  feed (Today's Move / Portfolio Pulse / One Lesson); agents speak as
  "desks"; everything else behind a Menu drawer.
- [C — Team Deck](concepts/concept_c_team_deck.md) — fold the grid into
  family sections. Interim patch only.
- [D — Chat-first Concierge](concepts/concept_d_chat_first.md) — rejected
  with evidence; salvage the voice, not the chat box.

## Recommendations

### 1. Concept A — Concierge Briefing (primary recommendation)

The smallest change that fixes the complaint. It promotes two things the app
already has — the Concierge and the CR106 verdict board — to the front door,
and removes exactly one thing from home: the 12-hex wall. No backend changes,
no engagement-loop risk, and it keeps the "CEO of a team" fantasy intact
because the team's *output* leads every screen even though the team itself is
one tap down. This is the right v0.2.

### 2. Concept B — Today Feed (the bolder alternative)

If the ambition is a daily-ritual app (Duolingo-shaped retention), B is the
better *end state*: lowest possible cognitive load and a home that is fresh
every day. It costs more (new aggregation surface, nav change) and bets
harder against the visible-team brand. A credible path: **ship A for v0.2,
evolve A's briefing card into B's feed for v0.3** — A's L0 is already 60% of
B's home.

What both share and any redesign must keep: plain language at L0, verdict
before transcript, the 12 agents visible as consensus/dissent before they are
visible as people, and a permanent one-tap route to full depth (Duolingo's
lesson: simplify the default, never hide the map).

## Sample looks

Static HTML mockups, AMI dark theme, cross-linked — open in any browser:

- `mockups/a_concierge_briefing/home.html` → `room_result.html` → `team.html`
- `mockups/b_today_feed/home.html` → `drilldown_room.html`

(Screenshots in `mockups/*/screens/` if rendered; otherwise the HTML files
are the sample look.)

## Suggested next step

Mint a CR for Concept A (Floor recompose + Room default-to-board + Team
screen). Decision needed from Saiful: A now, or A-now-B-later.
