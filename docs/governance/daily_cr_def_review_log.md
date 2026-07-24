# Daily CR/Defect open-items review log

Append-only ledger written by `/daily-cr-def-review` (CR085). One writer only — the
daily routine — so this is a plain running file, not one-per-item like the CR/Defect
registers (that split exists to avoid concurrent-write sweeps; a single writer has no
sweep risk, see CR081).

One `## YYYY-MM-DD` section per day. Within a section, one line per item asked:

```
- **CR014** (proposed since 2026-07-10) — asked: "Start now / keep deferring / drop it?"
  → Saiful: "start it, assign to coder.mobile"
```

Follow-up context (checked at the *start* of the next run, before re-asking) is appended
to that day's section as a second line under the same item, not as an edit to history:

```
- **CR014** — follow-up: still `proposed`, no commit tagged CR014 since 07-25 → re-asked
```

Nothing here changes a CR/Defect's actual status — that only happens through the normal
governance flow (a domain owner's row-file edit + `gen_registers.py`). This log records
what Saiful said and whether it happened; it is not itself a source of truth for status.

---
