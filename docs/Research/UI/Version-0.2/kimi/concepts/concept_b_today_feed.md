# Concept B — "Today Feed" ★ RECOMMENDED

**One-liner:** home is a 3-card daily feed — Today's Move / Portfolio Pulse /
One Lesson — and *everything else*, including the whole team, lives behind a
Menu drawer. Agents appear only as voices, never as a wall.

Mockups: [`../mockups/b_today_feed/`](../mockups/b_today_feed/)
(open `home.html`; screens are cross-linked).

## Principle

Maximum simplicity: the app behaves like a daily letter from your trading
desk. Three cards, read top to bottom, done in 30 seconds. Depth is one tap
behind every card. This is the Duolingo-path lesson (P3) + Robinhood
minimalism (P2) applied harder than Concept A dares.

Where Concept A reorganizes the existing app, Concept B **re-centers it on a
daily ritual**. It is the bolder bet with the bigger payoff for retention
(a reason to open every day) and the bigger IA change.

## Screens

### L0 — Today (`home.html`)
- Date header + streak.
- **Card 1 — Today's Move:** "Your team sees a setup on NVDA", one plain-
  English why, CTA → The Call. Signed "— Research desk": agents speak as
  *desks*, collapsing 12 identities into 3-4 human-scale voices.
- **Card 2 — Portfolio Pulse:** one number, sparkline, "Nothing needs your
  attention." (When something does: the card turns amber and says what.)
- **Card 3 — One Lesson:** 4-minute lesson, progress dots, "KEEP STREAK".
- Bottom nav reduced to **4**: TODAY / PORTFOLIO / LEARN / MENU.
  Journal, Team, League, Settings, Challenges live behind MENU ("desk drawer").

### L1 — The Call (`drilldown_room.html`)
- Plain-language summary first: "Why the desk likes NVDA" — 3 bullets.
- Disclosure: "HOW THE TEAM VOTED" — the 12 names appear *here, and only
  here*, compact, grouped by desk, agree/dissent dots.
- Actions: TAKE PAPER TRADE / SAVE TO JOURNAL.

## What happens to the 12 agents

They become **desks** at L0/L1 (Research desk, Risk desk) and individuals only
inside the vote disclosure and the Team page behind MENU. This is the most
aggressive abstraction of the four concepts.

## Why it's better

- The lowest possible cognitive load: nothing on the home screen requires
  knowing the app has agents at all.
- A daily-ritual shape that matches the monetization loop (streaks, lessons,
  league) without showing the machinery.
- Onboarding collapses to: read 3 cards, tap one thing.

## Why it might not be the one

- Bets against the "CEO of 12 analysts" fantasy — the team becomes backstage
  crew. If Saiful judges the team to be the brand, A is safer.
- Journal and League demotion to MENU could hurt the loops they drive.
- "Desks" is a new vocabulary layer that must be taught (though it *replaces*
  a harder one).

## Effort estimate

**M–L.** New Today feed + card models (needs a "daily briefing" aggregation —
server-side or concierge-prompt), desk-drawer menu, nav change, Call detail
screen. Touches more surfaces than A but still no new backend capabilities —
all data exists today.

## Risks / open questions

- Duolingo-backlash risk (P3): users who *want* the map must find it in one
  tap — MENU must be obviously "everything else", not a junk drawer.
- If the daily card has nothing meaningful to say (no setup, flat portfolio),
  L0 feels empty → needs a strong "quiet day" state.
