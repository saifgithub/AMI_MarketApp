# 06 — Answering CR004's plan_b

`docs/forward_planning/CR004_release_readiness/plan_b_playability_ux.md` states:

> Navigation is NOT the problem — every key action is ≤2 taps from the Floor. The problem
> is the reward economy.

This research **concedes the claim in full** — and shows it measures a different thing than
the complaint.

## The concession

Tap counts are fine. Neither recommendation adds, moves, or renames a tab; neither changes
the tap distance to any key action. Concept C — the one concept built purely on "make
actions closer" — is rejected in `04_concepts.md` largely *because* plan_b is right: its
task cards duplicate tabs that were never the problem.

## What tap counts cannot see

"≤2 taps from the Floor" measures the cost of *acting*. The complaint is about the cost of
*arriving*. Before the first tap, the shipped Floor bills the user:

- **13 identity marks** (10 above the fold), each colour-coded, labelled, and — per the
  design's own spec — meant to read as *people in a room*;
- **23 tap targets**, none marked as the recommended one (Hick's law's exact warning);
- a primary CTA whose top edge sits **1.63 folds down**, below the roster, the challenge
  and the league;
- a 5-stop tour, 3 of whose stops introduce more staff.

All numbers: `01_the_complaint_measured.md`; method and limits: `00_method_and_limits.md`.
A user can be 2 taps from everything and still feel they walked into a meeting — the meeting
*is* the greeting. That at-rest cognitive load is what "a little bit too much" names, and a
taps-from-Floor metric is structurally blind to it.

## Where plan_b's actual thesis wins

Plan_b's positive claim — the reward economy is what needs surfacing — is honoured, not
fought, by the recommendation:

| Reward surface | Shipped Floor | Concept A |
|---|---|---|
| Daily Challenge | below 4 rows of roster | card 2, above the fold, plus a chip in card 1 |
| Streak | chip, top right | chip, top right + in the Concierge's status line |
| League | below the challenge | card 3, ~one fold |
| Verdict delta ("your call is up 2.1%") | nowhere on the Floor | the Concierge's opening line |

The roster moved out of the way and the reward economy moved *up*. If plan_b is right about
what retains users, concept A is the layout that bets on it.

## Net position

CR004 measured navigation and found it healthy. This research measured the landing surface
and found it crowded. Both are true; they answer different questions. Nothing in the
recommendation contradicts a sentence of plan_b — it relocates its priorities to the top of
the screen.
