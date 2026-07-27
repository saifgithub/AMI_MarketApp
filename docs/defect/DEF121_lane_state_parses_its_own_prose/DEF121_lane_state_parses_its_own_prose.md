# DEF121 — Lane state parses its own prose, and an impossible round freezes a lane silently

**Filed:** 2026-07-27 · **Source:** prompt (Architect, track R, escalated to Governance) · **Area:** infra / orchestration
**Status:** fixed · **Tag:** `AT:G2`

---

## What is broken

The Architect reported five findings (G-1…G-5) from running lanes against the CR052 handshake. All
five were re-derived against the code and the live board before anything was changed. Four are real
and fixed here; one was already fixed elsewhere.

### G-1 — an impossible round freezes a lane with no error

`668c640` (2026-07-23, DEF091) added `v_round` and the strict `SUBMITTED > VERDICT` test. Neither
watcher checks that the two numbers are a **possible pair**. A verdict stamped one round ahead of
the submission it answers makes `SUBMITTED == VERDICT`, which reads as "already answered": the board
shows `AUDIT_RETURNED` / `AWAITING_FIXES`, a perfectly ordinary state. The builder fixes, bumps,
resubmits — and the counters merely coincide again. Nothing errors, nothing logs, and the lane stops.

Confirmed on DEF116: the verdict file said `(round 2)` while the same commit's own message said
`AWAITING_FIXES round 1`.

### G-2 — prose is executable, and the last match wins

Lane files are prose and machine state in one document. Both tools take `grep … | tail -1`, so any
sentence *about* a token becomes the token. Worse, the anchoring was inconsistent between them:
`dispatch.sh` required `^STATUS:` at line start; `watcher.sh` did not anchor `SUBMITTED` at all.

**This was live, not theoretical.** Measured 2026-07-27 before the fix:

```
$ grep -Eon 'SUBMITTED: *round *[0-9]+' orchestration/audit/cr/DEF116.architect.md
8:SUBMITTED: round 3           <- the real submission
138:SUBMITTED: round 2          <- inside a blockquote, in the file's own write-up OF THIS BUG

$ sh orchestration/audit/watcher.sh state | grep DEF116
DEF116    COMPLETE    r2    r3(COMPLETE)      <- r2. The prose won.
```

The file documenting the round bug was being mis-parsed by the tool that has the round bug.

### G-3 — nothing cross-validates the two files

No check that a `VERDICT` round corresponds to a `SUBMITTED` round that exists, so G-1's typo was
unfalsifiable by the tooling.

### G-4 — `UNCOMMITTED` is advisory

The Architect read `CR098-ROOM.auditor.md` while the auditor was still writing it, reported its round
number, and dispatched a worker on an instruction derived from it. The number changed before the
auditor committed. The board said `UNCOMMITTED` at the time; nothing stood between the raw file and
the read.

### G-5 — budget was coupled to tier

Already fixed by the Architect at `5b3b6fc` (`DISPATCH_BUDGET_USD`, AT:R65 CR098). Verified present;
no further action. Recorded here so the finding set is closed, not silently dropped.

---

## Why the previous guard failed

DEF091's fix to this exact area was *more arithmetic* — add the round, compare strictly — with no
check that the pair was possible, so the next mistyped stamp had a new way to stall a lane in
silence. And the "tokens are line-anchored" rule existed in **one** tool and was never made a shared
rule, so the two boards could disagree about what a line meant with neither board able to show it.

Both halves are the same class: **a derived state trusting an input nobody validated** — the fourth
instance of which `668c640`'s own commit message had already named. Recorded as
[`failure_patterns.md` P8](../../initial_specs/08_tech/failure_patterns.md).

---

## The fix

**One rule for what carries state, byte-identical in both tools.** `TOK` / `emits()` /
`last_match()` in `orchestration/dispatch/dispatch.sh` and `orchestration/audit/watcher.sh`:

- A token counts only when it **opens a line**. Markdown emphasis and headings are formatting, so
  `**VERDICT: …**` and `## VERDICT: …` still count — the corpus uses all three forms (37 plain,
  38 heading, 30 bold) and the fix had to keep every one of them working.
- A backtick, a blockquote `>`, indentation, or any preceding word means the line is *talking about*
  the token. Ignored.
- Only the **line-opening occurrence** supplies the value, so a trailing comment on the same line
  cannot override it.

**`BAD_ROUND`** on both boards when `VERDICT round > SUBMITTED round` — a combination that cannot
exist, rendered as its own loud state rather than as a routine one. `dispatch.sh inbox` treats it as
hot, so it reaches the Architect at the next work-unit gate instead of waiting to be noticed.

**`dispatch.sh` compares the right counters.** It was testing the *instance* lane's `STATUS` round
against the *audit* lane's `VERDICT` round — two counters kept by two writers, which the corpus shows
drifting apart (CR026: instance r1, audit r3). It now reads the audit lane's own `SUBMITTED` round,
the same pair `watcher.sh` uses, so the two boards cannot disagree about whose turn it is.

**`dispatch.sh verdict <ITEM>`** prints a lane's verdict and **refuses** while it is undelivered.

---

## Scope limits, stated rather than omitted

- **`BAD_ROUND` catches the mis-stamp, not the freeze it causes.** It fires the instant the wrong
  verdict lands — which is when the Architect's `inbox` gate looks. Once the builder resubmits and
  the counters coincide, no tool can distinguish a mis-stamp from a legitimate answer. Proven by
  fixture T3, which correctly still reads `AWAITING_FIXES`.
- **G-4's fix is a safer path, not a control.** `verdict <ITEM>` cannot stop anyone opening the file;
  it makes the checked read the easy one and is the only read that can say no. Per CLAUDE.md's
  "prompt instructions are not controls", the residual is an acknowledged gap.
- **Observed, not fixed (reported to the Architect):** `DEF095` and `DEF096` carry `.auditor.md`
  verdicts with no `.architect.md` beside them. `watcher.sh` iterates `*.architect.md`, so those two
  verdicts have never appeared on the audit board at all. Both lanes are `DONE`, so nothing is live.

---

## Acceptance

| # | Check | Result |
|---|---|---|
| 1 | Prose immunity: backticked and blockquoted `STATUS:`/`VERDICT:` lines ignored | ✅ fixture T1 |
| 2 | Bold + heading token forms still parsed | ✅ fixture T1/T4 (`**SUBMITTED:**`, `## VERDICT:`) |
| 3 | Verdict ahead of submission ⇒ `BAD_ROUND` on **both** boards | ✅ fixture T2 |
| 4 | Healthy multi-round lane unaffected | ✅ fixture T4 |
| 5 | `verdict <ITEM>`: delivered ⇒ prints + exit 0; undelivered ⇒ refuses + exit 1 | ✅ both paths |
| 6 | **Full-corpus regression: 61 dispatch lanes + 60 audit lanes, board diffed before vs after** | ✅ exactly one change — `DEF116 SUBMITTED r2 → r3`, the bug being fixed. Dispatch board byte-identical |
| 7 | POSIX syntax check on both scripts | ✅ `sh -n` clean |

Check 6 also caught a regression **in this fix**: the first patch extracted every occurrence of a
token on an emitting line, so `GATE: independent  <!-- … a chunk may carry GATE: none … -->` in
`CR069.assign.md` flipped that lane's gate to `none`. The board diff surfaced it before it shipped;
`last_match()`'s `^` anchor is the correction.
