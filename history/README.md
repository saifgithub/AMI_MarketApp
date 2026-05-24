# History — track R (Development) — AMI Trade

Per-session wrap narratives. **Each file = one `/handover R` invocation.**

Filenames are `AT_R<NNNN>.md` (four-digit zero-padded session number) so
`ls history/` sorts chronologically.

Don't read these unless you need historical context — **current state
lives in [`../HANDOVER_R.md`](../HANDOVER_R.md)**. The "Recent sessions"
list at the bottom of HANDOVER_R.md links to the most recent few.

## File shape

```markdown
---
session: AT:R<N>
date: YYYY-MM-DD
prev: AT:R<N-1>     # omit on the first session
---

# AT:R<N>  (YYYY-MM-DD)

<the narrative — what shipped, what was learned, gotchas for the next session>
```

## Convention

- `/handover R` writes a new file per wrap. Never overwrites — if the
  same session is re-wrapped, the second file gets a `.1` suffix
  (`AT_R0040.1.md`, etc.).
- The "What just landed" section is no longer present in HANDOVER_R.md.
  It moved here from AT:R40 onward.
- Sessions AT:R19 through AT:R40 were split from the legacy
  `history_R.md` monolith on 2026-05-25.
