# Ad placement options — three slots, drawn to scale

Source: `/private/tmp/claude-501/-Volumes-Extreme-Pro-AMI-MarketApp/3b407fa5-.../scratchpad/ad-placements.html`
(claude.ai artifact + `/tmp` scratchpad, at risk of loss). Date: 2026-09-22.
**Internal research, not user-facing.** Backs [CR226](CR226_adaptive_banner_slot/CR226_adaptive_banner_slot.md)
(and its CR225 dependency). Converted to markdown and preserved here under
[CR231](CR231_stabilisation_programme.md). The original is a visual mock (three
iPhone-13-proportioned frames, 390×844dp, with real chrome heights from the shipped
code — header 64pt, bottom nav 64pt, ticker tape 28pt) comparing three candidate ad
placements; the verdicts and reasoning below are the substance.

## Option 1 — Header strip

**Not recommended.**

Sits in the `Spacer()` between title and actions. Easy to build — and the worst of
the three. Roughly 150–200pt wide, so no standard ad unit fits (smallest is
320×50): custom native render only, meaning house ads forever, no programmatic fill.

**Shared component.** Same header serves Settings and Mandate routes — both
ad-banned — so it needs a per-screen suppression list. Also displaces the screen's
accent identity.

## Option 2 — Inside the ticker tape

**Recommend against.**

~20 lines to build: inject a sponsored item every N positions in the 160pt-wide item
row. But it breaks a rule `ads.md` already states — "don't mimic native UI."

**Confusable by construction.** Paid placement in a stream of live quotes, same
font, same 10pt size, scrolling at 60px/s. An 8pt "AD" label can't fix that — and in
a financial app it invites store-review scrutiny. The tape is 28pt; no ad unit is
that short.

## Option 3 — Anchored banner

**Recommended.**

A 50pt adaptive banner between nav and tape — one new child in the shell's bottom
`Column`. A real ad unit that gets actual programmatic fill at the $2–5 eCPM the
spec projects.

**The bans enforce themselves.** Concierge, Room, 1-on-1, Mandate and the trade
ticket are pushed routes that cover this Scaffold — they hide the banner
structurally, not by a list that can rot. Cost: ~50pt of height on every screen.

## Why option 3 is the only one that's structurally safe

`home_shell.dart:125` already documents it: "the nav lives in THIS Scaffold, below
the pushed route." That was written for DEF190, about an orphaned screen covering
the nav — but it's the same mechanism that makes a banner mounted beside the nav
disappear on exactly the screens `ads.md` forbids ads on.

Options 1 and 2 both need an explicit "don't show here" list. Per CLAUDE.md, an
instruction is not a control — CR122 wrote a structural test precisely so a
forbidden context can't quietly gain an ad slot. Option 3 inherits that guarantee
from the navigation architecture instead of re-proving it.
