<!--
history/ — the dispatch layer's durable memory + retention (keeps active files small). CR052.
-->

# Dispatch history (collective memory)

Where closed work goes so the active queue stays small and every agent can grep prior decisions.

```
history/
  lanes/<ITEM>.md        archived DONE lane pair — the full per-item record (what/why, every
                         Q/A round-trip, the auditor verdict). Written on DISPATCH: ACCEPTED.
  trail/<period>.md      rotated older ledger rows (e.g. trail-2026-Q3.md), moved out of the
                         active dispatch/trail.md when a period turns or the file gets large.
```

## Why (the "trail.md gets HUGE" fix)

A single unbounded ledger is expensive to read and noisy in diffs. So:

- **`dispatch/trail.md` stays bounded** — open lanes + the current period only. Older closed rows
  roll here into `trail/<period>.md`.
- **Per-item detail is here, not in the trail** — the trail is a terse index; the story of an item
  is its archived lane.
- **Query, never slurp** — `grep`/`tail` the trail and the archives for what you need.

## Who reads it

Any agent, for prior-decision context (e.g. a coder starting CR021 greps `history/lanes/CR020.md`
to see how the concierge context landed). The Architect distills durable cross-agent lessons from
here into the project `memory/` + `failure_patterns.md` — see DISPATCH_PROTOCOL.md §9.
