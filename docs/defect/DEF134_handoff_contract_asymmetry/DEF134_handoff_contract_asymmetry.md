# DEF134 — The architect hand-off and the auditor's expectations are not the same contract

**Filed:** 2026-07-27 · **Source:** prompt (Governance audit of the handshake) · **Area:** infra / orchestration
**Status:** fixed · **Tag:** `AT:G2`

---

## What is broken

`<ITEM>.architect.md` is one file with **two producers** — the audit-layer architect submitting its
own build ([`ARCHITECT_LOOP_PROMPT.md`](../../../orchestration/audit/ARCHITECT_LOOP_PROMPT.md) step
4) and a coder bridging up from the dispatch layer
([`CODER.md`](../../../orchestration/dispatch/loop_prompts/CODER.md) step 6) — and **one consumer**,
the auditor. Nothing kept the three in agreement. Six divergences, ranked by what each costs.

### H-1 — the auditor is never told the SHA is off the shared branch

`CODER.md` is explicit: source goes to `lane/<ITEM>.<your-id>`, **never** the shared branch, because
nothing reaches the shared branch except through the Architect's gate. The auditor's step 2 says only
*"Audit the COMMITTED SHA … check it out into a scratch worktree or use `git archive <sha>`."*

Measured: the strings `lane/`, `lane branch` and `git fetch` appear **nowhere** in
`AUDITOR_LOOP_PROMPT.md`, `PROTOCOL.md`, dispatch `AUDITOR.md`, or the audit bindings. The bindings
reinforce the wrong assumption — *"Shared branch: `main` — this repo works directly off main"*.

So a fetch is never prescribed, and when the SHA does not resolve the auditor has no instruction. The
available fallback is the shared branch, which by design does **not** contain the work — a `COMPLETE`
on it certifies code the auditor never read. Masked on this repo by topology (one shared clone, so
lane branches are already local — every recent audit used a bare `git worktree add --detach <sha>`
and no fetch), and unmasked the moment an auditor runs from its own clone, which is what
`AUDITOR.md` tells it to do.

### H-2 — the two producers give contradictory round-bump rules

| Source | Rule |
|---|---|
| `ARCHITECT_LOOP_PROMPT.md` step 4 | "Bump `round` by one on every resubmit." |
| `CODER.md` | "do not assume your resubmission is round 2 because it is your second try — read the auditor's latest verdict round first and submit at the next number above it" |
| `PROTOCOL.md` | "`N` is the round you AUDITED, never the round you are asking for" |

The architect's `+1` is precisely what produces `SUBMITTED == VERDICT` after an auditor self-reopen —
the DEF091 / DEF116 silent freeze. `BAD_ROUND` (DEF121) catches the verdict-ahead direction; the
submission-equal direction is the quiet one, and this rule walks straight into it.

### H-3 — the DoD rule keys on a fact the file never states

The auditor: *"CR-level submissions only: a chunk carries the shorter evidence list instead and must
not be bounced for a missing DoD."* Neither producer was told to declare which it is, so the auditor
inferred it — from an item id that does not reliably carry scope (`CR069-BE` is a chunk, `DEF116` is
a whole item).

### H-4 — the auditor must reproduce a measurement nobody records

Auditor step 3: *"Reproduce the item's real measurement where it has one."* The architect prompt tells
the builder to *reproduce it live before signalling* (step 3) but omits it from what the file carries
(step 4); the chunk evidence list omits it too. An unrecorded measurement cannot be reproduced.

### H-5 — the architect-actionable state set was stated four times, three of them wrong

| Source | States listed |
|---|---|
| `dispatch.sh` `needs_architect()` — the actual behaviour | 9 |
| `dispatch.sh` usage header | 5 |
| `DISPATCH_PROTOCOL.md` §4 | 6 |
| dispatch `ARCHITECT.md` step 1 | 5 |

The dispatch-layer `ARCHITECT.md` — the COO role prompt, the one an Architect instance actually
runs — contained **no mention of `inbox` at all**. DEF121 wrote the loop-entry gate into the
*audit-layer* architect prompt only, so the fix Saiful asked for was half-landed on the prompt that
matters most.

### H-6 — `ARCHITECT_LOOP_PROMPT.md` contradicted itself

Its new loop-entry gate says `watcher.sh architect` "wakes on `AWAITING_FIXES` but **never** on a
clean `COMPLETE`". Forty lines later, step 6 still said it "blocks until a verdict returns".

---

## The fix

- **H-1** — `AUDITOR_LOOP_PROMPT.md` step 2 and `PROTOCOL.md`'s lane description now state that an
  unmerged SHA is the *normal* case, prescribe `git fetch` before checkout, make an unresolvable SHA
  a bounce, and forbid falling back to the shared branch by name.
- **H-2** — the architect's `+1` rule is replaced with the lane-counter rule the other two already
  carry.
- **H-3** — a `SCOPE: cr | chunk` line, required by both producers, read by the auditor. **No script
  parses it.** Absent, the submission is audited as `cr` — fail toward demanding the DoD, since
  waiving one by accident is the expensive direction.
- **H-4** — the live/real measurement, *as run*, joins both carry-lists; "none applies, because …" is
  an acceptable disposition, silence is not.
- **H-5** — four copies collapsed to two. `needs_architect()` is the single list in code; the protocol
  table is the single list in prose (with the missing `UNCOMMITTED` / `UNPUSHED` rows added); both
  prompts now point instead of restating. `ARCHITECT.md` step 1 becomes the `inbox` entry gate, with
  the `verdict <ITEM>` rule.
- **H-6** — step 6 corrected.

Also fixed in passing, same lane: **five tier-A portability breaches introduced by DEF131 earlier
today** — `DEF131` cited four times and `melehost` once inside the two portable watcher scripts,
against `PORTABLE_MANIFEST.md` invariants #1 and #2. Rule and mechanism kept, archaeology removed.

---

## Acceptance

| # | Check | Result |
|---|---|---|
| 1 | Every element the auditor's loop consumes is produced by **both** writers of `<ITEM>.architect.md` | ✅ SCOPE / SHA / depends-on / what-why / test command + output / live measurement / revert-proof QA, in `ARCHITECT_LOOP_PROMPT` step 4, `CODER.md` step 6, and `PROTOCOL.md`'s lane description |
| 2 | Round rule identical across all three documents | ✅ |
| 3 | Architect-actionable state set stated in exactly two places, matching | ✅ `needs_architect()` (9) + the protocol table (9); both prompts point |
| 4 | Tier-A invariant scan clean over all 16 portable files | ✅ (was 5 hits) |
| 5 | Both scripts: syntax clean, **non-comment lines changed = zero** | ✅ verified by filtering the diff |
| 6 | Both boards byte-identical to HEAD across the full lane corpus | ✅ dispatch and audit, both |

Checks 5 and 6 are the point: this is a contract-alignment change, so any movement on either board
would have meant it changed behaviour it had no business changing.

## Not fixed — stated

`file:line` for changed source is still absent from both carry-lists. That is **by design**, not a
gap: the auditor is told *"do not audit the diff summary; audit the code"*, so it derives the diff
from the SHA itself. Handing it a curated file list would narrow what it looks at, which is the
opposite of independence.
