# 01 — Current-State Audit: where the overwhelm lives

User feedback (Alpha): *"The UI is not very friendly, and a little bit too much.
It's like walking into a meeting with 12 staff waiting for you."*

This audit maps that feeling to concrete screens. Everything below exists today
in `mobile/lib/`.

## The core problem, stated precisely

The app presents **the machinery** (12 agents, phases, transcripts, overlays)
as **the interface**. The user's actual goals — *"what should I pay attention
to today, what did my team conclude, am I doing OK"* — are buried under the
org chart.

## Overwhelm inventory

### 1. The Floor (home) stacks five competing priorities
`mobile/lib/screens/floor/floor_screen.dart`

Top-to-bottom on one scroll: logo + streak chip → concierge centerpiece →
**"YOUR TEAM" + all 12 agent hexes at once** (88pt tiles, ~3 rows) → daily
challenge card → weekly league card → "CONVENE THE ROOM" CTA → footer links.
A first-run 5-target coach-mark tour is layered on top — an admission the
screen needs a guided explanation.

The 12-agent grid is the single loudest element on the most-seen screen, and
most of it is locked (35% opacity, lock icons) — visual noise that also
communicates "you can't use most of this yet."

### 2. The Room streams 12 long-form contributions live
`mobile/lib/screens/room/room_screen.dart` (1,656 lines)

All 12 agents speak in phases on one ticker-style feed, ~3,500–6,000 chars,
4–7 phone screens of prose. CR106's own docstring records the complaint; its
verdict **Board** view (summary first, transcript behind a toggle) was the
first mitigation — but the board only appears **after** the run settles, and
the live default is still the firehose.

### 3. Every agent exposes two chat surfaces, always
Every unlocked-agent tap → action sheet → `[1-ON-1]` or `[BRIEF]`, each a full
chat screen (`agent/one_on_one_screen.dart`, `agent/brief_screen.dart`), plus
brief history/rollback. That's 12 agents × 2 chat modes = 24 possible
conversations a new user must build a mental model for.

### 4. The vocabulary is pervasive
Agent names appear in journal entries, lesson quiz results, daily-challenge
explanations, league cards, locked-agent sheets. The 12-agent mental model is
not confined to one screen — you cannot use the app without learning the org
chart first.

### 5. The theme amplifies density
Dark "trading-desk console" aesthetic: uppercase mono labels with 1.8
letter-spacing ("CONVENE THE ROOM", "1-ON-1", "BRIEF"), glows, a permanent
scrolling ticker tape under the bottom nav on every tab, hex chrome
everywhere. It reads as *professional terminal*, not *friendly teacher*.

### 6. Navigation is fine but the destinations are heavy
5 tabs (Floor / Portfolio / Journal / Lessons / Settings) + 14+ modal sheets.
Tab count is acceptable; the problem is what each tab leads with.

## What already works (keep / build on)

- **CR106 Room Verdict Board** — summary-first, transcript behind a toggle.
  The single best in-app precedent for the redesign direction.
- **CR120 Portfolio segmentation** — one long list split into
  POSITIONS / WATCHLIST / HISTORY with a "SHOW ALL" escape hatch.
- **Sheets as the second layer** — convene picker, trade ticket, paywall keep
  base screens clean.
- **Locked-agent dimming + gateway lessons** — feature gating already exists;
  the redesign just needs to also collapse the *visual* presence.
- **The Concierge** — already exists as a character and an onboarding
  interviewer. Both recommended concepts simply promote it to the front door.

## Design tension to respect

The 12-agent team **is the product's differentiator** ("Your team of analysts.
Your call."). The redesign must not delete it — it must **demote it from the
home screen to a depth layer**, and let it surface as *evidence* ("9 of 12
agree", "Bear Researcher dissents") rather than as a wall of faces.
