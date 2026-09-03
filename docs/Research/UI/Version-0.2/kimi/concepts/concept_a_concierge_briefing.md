# Concept A — "Concierge Briefing" ★ RECOMMENDED

**One-liner:** the Concierge absorbs the org chart. Home is one calm briefing
with one action; the 12 agents live one tap down.

Mockups: [`../mockups/a_concierge_briefing/`](../mockups/a_concierge_briefing/)
(open `home.html` in a browser; screens are cross-linked).

## Principle

You don't walk into a meeting with 12 staff. Your chief of staff walks up to
*you* and says: "Here's the one thing today. Want the details?" The team is
still there — you feel their work in every line — but you meet them on demand,
not on arrival.

This is the smallest change that fixes the complaint, because it **reuses what
the app already has**: the Concierge character, the CR106 verdict board, and
the sheet/detail navigation idioms.

## Screens

### L0 — Floor → Concierge Briefing (`home.html`)
- Greeting + 2–3 sentence plain-language briefing: what the team flagged, how
  the portfolio did, one streak-keeping suggestion.
- **One** primary CTA: "SEE TODAY'S PLAY".
- Portfolio pulse strip: one number, one sparkline, one status line.
- "Your team" is a **single compact card** (overlapping avatars, "12 analysts ·
  5 unlocked", chevron) → Team screen. The 12-hex wall is gone from home.
- Daily challenge and league cards move off the home screen (one layer into
  their own tabs / drawer). Ticker tape no longer permanent.

### L1 — Room Verdict (`room_result.html`)
- Verdict card first: **BUY · MODERATE CONVICTION**, one-sentence rationale,
  confidence meter.
- Consensus strip: 12 tiny hexes, 9 filled / 3 hollow — the team expressed as
  *evidence*, not attendees.
- One dissent callout ("Bear Researcher dissents: …") — preserves intellectual
  honesty, which is the product's brand.
- "READ FULL DEBATE" → existing transcript. "ASK AN AGENT" → Team screen.
- Note: this is essentially CR106's board promoted from *post-run toggle* to
  *the default and only initial view*, including during streaming (phases
  collapse into a progress shimmer).

### L2 — Your Team (`team.html`)
- 12 agents grouped by **family** (Analysts / Research / Risk / Execution +
  Managers), collapsible sections, one-line plain-English role each ("Reads
  the filings so you don't have to").
- Locked agents stay but inside their family section — the unlock journey
  (gateway lessons) is unchanged.
- Tap → existing 1-on-1 / Brief action sheet. No backend change.

## What happens to the 12 agents

Demoted from home-screen residents to a depth layer. They surface at L0/L1
only as *consensus and named voices* ("your team flagged", "Bear Researcher
dissents"). Their individual personalities are fully intact at L2.

## Why it's better

- First screen answers the user's actual questions: *what today? how am I
  doing? what next?* — with one thumb-reachable action.
- Keeps the differentiator: "your team of analysts" is felt in every briefing
  line and proven in the consensus strip.
- Lowest engineering risk of the four concepts: mostly recomposition of
  existing widgets (Floor sections, CR106 board, existing agent screens).

## Effort estimate

**M.** Floor recompose (remove grid, add briefing + pulse + team card),
Room default-to-board (extend CR106), Team screen (new, but simple grouped
list). No backend changes. Roughly 1–1.5 weeks of Flutter work + content
strings for the briefing generator (Concierge engine already produces
mandate/readback prose; briefing template is a prompt change).

## Risks / open questions

- Briefing quality is now the product's first impression — the Concierge
  prompt needs to be genuinely good, not generic filler. Mitigation: template
  from real signals (portfolio delta, room results, streak) before any LLM
  prose.
- Daily challenge / league lose home-screen placement → possible engagement
  dip. Mitigation: surface them as briefing lines when relevant ("one lesson
  keeps your streak").
