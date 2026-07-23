<!--
backlog/README.md — the parked audit queue. RUNTIME STATE, never copied to another repo
(PORTABLE_MANIFEST.md tier C). Lane files live here instead of ../ so watcher.sh's
`*.architect.md` glob does not surface them to a working auditor. Parking is a scheduling
decision and nothing else: it changes no verdict, satisfies no gate, and leaves every one of
these items UNGATED on the dispatch board. CR073.
-->

# Deferred audit backlog

Six lanes shipped to Alpha without ever being audited. CR070 gave that state a name —
`UNGATED` — and the dispatch board has shown all six ever since. They are still owed a real
audit; none of them is closed, waived, or downgraded.

They are parked here for one reason: a fresh auditor starting on a live item would otherwise
open onto a queue of seven `AWAITING_AUDIT` rows, six of which are months-old shipped work
with no owner in the current session. That is the batch-and-skim pressure the concurrency cap
exists to prevent, arriving through the front door instead.

**What parking does and does not do**

| | |
|---|---|
| Auditor's queue (`sh ../watcher.sh state`) | these six disappear — they no longer glob |
| Dispatch board (`sh ../../dispatch/dispatch.sh state`) | **unchanged — all six still read `UNGATED`** |
| The lane's `GATE:` | untouched, still `independent` on every one |
| Verdicts | none exist; none was created here |

The two derivations read different files, which is what makes this honest rather than quiet:
`watcher.sh` globs `*.architect.md` (moved), `dispatch.sh` reads `<ITEM>.auditor.md` (never
existed for these, and still doesn't). The alarm stays lit where the Architect has to look at
it; only the auditor's inbox is cleared.

## Parked lanes

| Item | Builder | SHA | Why it is owed an audit |
|---|---|---|---|
| `CR038` | `coder.room` | `c0d6c87` | synthetic macro/Fed scaffolding asserted as fact by all 12 agents; removed at source, never independently re-verified |
| `CR058-MATH` | `coder.math` | `21fb8b6` | CR046 screening module — the Sharia ratio screens + purification math. **Direct ancestor of CR069's subject matter** |
| `DEF062` | `coder.api` | `4a87312` | `PATCH /v1/mandate/{user_id}` accepted unvalidated `dict[str, Any]`; `max_drawdown_pct` feeds the deterministic safety-floor compliance check |
| `DEF084-BE` | `coder.api` | `44759a9` (`bd5c74d`) | the `halal` flag was a 7-ticker allowlist, not a screen — 4th occurrence of the "degrade loudly" class |
| `DEF084-MOBILE` | `coder.mobile` | `e344b27` | the Settings toggle claiming a Sharia screen; **this is the lane that pushed straight to the shared branch and had its gate waived at hand-off** — the incident behind three portable rules |
| `DEF084-ROOM` | `coder.room` | `cef212f` | agent-narration layer still asserted a Sharia screen at three sites after DEF084-BE fixed the deterministic path |

## Restoring one

```sh
# from orchestration/audit/cr/
git mv backlog/<ITEM>.architect.md .
sh ../watcher.sh state          # <ITEM> reappears as AWAITING_AUDIT
```

Nothing else is needed — the file is unmodified, its `SUBMITTED: round 1` intact, so the
handshake resumes exactly where it stopped.

## Reading order when these are picked up

`DEF084-BE` → `DEF084-MOBILE` → `DEF084-ROOM` is one defect across three surfaces and should
be audited as one pass; `CR058-MATH` belongs with them, since CR069 is the fix-forward for the
same claim. `CR038` and `DEF062` are independent.
