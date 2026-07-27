<!--
Auditor run report — run-70 (2026-07-27, session auditor.core/track U). Round-1
audit of DEF114. Audited SHA 2895970. Verdict COMPLETE, one MINOR (a new item,
not a round-2 fix). Also records an orchestration defect: the lane was
submitted to a directory the watcher does not scan. Owner: AUDITOR.
-->

# run-70 (round 1) — DEF114 SSE unescape corruption → COMPLETE

- **Auditor session:** auditor.core (track U), 2026-07-27.
- **Audited SHA:** `2895970`, off `main` @ `98c6a07`. Isolated worktree
  `.claude/worktrees/audit-DEF114/`.
- **The item:** every streamed text surface — Room `agent_token`, Brief Your Agent, 1-on-1 chat —
  decoded the backend's escape with two sequential `replaceAll`s that cannot invert it **in either
  order**, silently corrupting any text containing a backslash immediately followed by `n`.
- **Gate:** independent — corrupts text the user reads, on three shipped paths.
- **Provenance:** filed from the CR090-MOBILE auditor's mutation set as a *coverage gap*. Before
  laning, the Architect ran the round-trip in real Dart against the real backend encode and
  **upgraded it to live corruption**: both decode orders are wrong, so a test pinning the current
  order would have enshrined the bug — the obvious reading of the row, and the wrong one.

## Reproduced independently

| Check | Result |
|---|---|
| Scope | 6 files, **+402/−128**, exact match |
| **D2** — backend untouched | `git diff --name-only \| grep -c "^backend/"` → **0** |
| Mobile suite | `flutter test` → **114 passed, 0 failures** (worker claimed 97→114) |
| **D1** — one shared helper, every site | `unescapeSseText` defined at `api_client.dart:113`, used at `:171`, `:366`, `:480`; the only surviving `replaceAll` mention is the docstring at `:104` — **no live pair** |
| No streamed surface missed | checked every `yield` in `api_client.dart`: `:366`/`:480` call the helper, `:747` yields the parsed map whose `text` was unescaped at `:171`. **Nothing streams raw** |
| `flutter analyze` | **the Architect ran `flutter test` only.** I ran it: 5 issues, **zero in any DEF114-touched file** — all pre-existing infos in `main.dart`, `floor_screen.dart`, and an unrelated test |

## Correctness — a property test rather than another corpus

The Architect verified 18 hand-picked cases (the assign's 13 plus 5 adversarial). Rather than add a
19th case, I did something independent and stronger: transcribed the backend escape
(`chunk.replace("\\","\\\\").replace("\n","\\n")` — identical at `room.py:214`/`:237`,
`one_on_one.py:115`, `brief.py:115`) into Dart and **exhaustively enumerated every string up to
length 5 over the alphabet that can actually break this codec** (`\`, `n`, newline, `a`, tab), plus a
20,000-case randomised sweep over a wider alphabet including `"`, `'`, `é` and an emoji.

```
cases checked            : 23906
SHIPPED helper failures  : 0
old order A failures     : 3772   (non-vacuity check)
old order B failures     : 3772   (non-vacuity check)
   e.g. both break on [92, 92, 92, 92, 110]   ->  \\\\n
```

`unescape(encode(s)) == s` holds for **all 23,906 cases**. The sweep is provably non-vacuous — both
previously-shipped orders fail 3,772 each — which independently confirms the Architect's "both
orders are wrong" re-grade exhaustively rather than on three examples. That re-grade is the most
valuable thing in this lane: it converted a "pin today's behaviour" coverage fix into a real
correctness fix.

It also subsumes the divergence the Architect flagged between the shipped helper and their reference
implementation (shipped writes both chars and advances 2 on an unrecognised escape; theirs advances
1). The two cannot diverge: the only character that can *start* an escape is `\`, and `\\` is handled
explicitly, so the character at `i+1` can never itself begin one. Reasoned, then covered empirically
by the sweep.

## Both mutations re-proved with my own runs

| Mutation | Result |
|---|---|
| **M1** — helper body reverted to the shipped `.replaceAll(r'\n','\n').replaceAll(r'\\',r'\')` pair | **111 passed, 3 failed** — matches the claim |
| **M2** — `parsed['kind'] == 'done'` removed from the terminating condition at `:748` | **113 passed, 1 failed** — matches the claim |

Each reverted individually, tree confirmed clean (`git status --short` → 0) after each.

## D3 — the judgement call the Architect asked for, answered

They offered it rather than asserting it: *"is an untested cross-file invariant acceptable here, or
does it want a guard on the backend side?"*

I verified the invariant myself rather than accept the conclusion. All four sender sites apply the
escape to a **complete value**, not to a stream: `room.py:214` (`msg.content`), `:237` (`ev.text`),
`one_on_one.py:115` and `brief.py:115` (`chunk`). No escape sequence can span a chunk boundary, by
construction, at every site as it stands.

**Judgement: acceptable, but worth a new item — MINOR, not blocking.** It is not fail-open in the
current code; it is a correct invariant that no test pins, so a future switch to a streaming escape
would silently reinstate the corruption on all three surfaces at once. The cheap guard belongs on the
backend (assert each SSE sender escapes a complete value), and D2 deliberately scoped the backend
out — so I agree this is a **new item, not a round-2 fix**, and it does not hold up the verdict.

## ORCHESTRATION DEFECT — this lane was structurally invisible to the auditor

`DEF114.architect.md` was submitted to **`orchestration/audit/def/`**. That directory does not exist
in the protocol:

- `AMI_TRADE_BINDINGS.md:24` — `<AUDIT_LANE_DIR>` = `orchestration/audit/cr` **"(holds CR and DEF
  lanes alike)"**
- `PROTOCOL.md:42` — *"Per item, two files under `<AUDIT_LANE_DIR>/` (**one directory holds CR and
  DEF lanes alike**)"*
- `watcher.sh:21` — `CR_DIR=${HANDSHAKE_CR_DIR:-"$SCRIPT_DIR/cr"}`, the only directory scanned

DEF114 was therefore `SUBMITTED: round 1` and **absent from the watcher and the state table
entirely**. It would have sat unaudited indefinitely. Every other DEF lane (DEF039…DEF116, DEF123)
lives in `cr/`. I found it only because the CR104 submit commit named DEF114 in its message while the
state table did not — i.e. by the `git log` cross-check, not by the tooling.

This is the **third** silent-queue-loss mechanism surfaced today, after DEF121 (a lane file's own
prose shadowing its `SUBMITTED` token) and the missing-notification watcher gap. Same failure class
each time: work is submitted, the tooling reports nothing, and silence is indistinguishable from an
empty queue.

I placed my auditor file at the canonical `orchestration/audit/cr/DEF114.auditor.md` so that a
**single** move — `def/DEF114.architect.md` → `cr/` — reconciles the pair and lets the state derive
correctly. The lane file is architect-owned; I have not moved it. Minting an ID is the Architect's
call.

## Not verified — as the lane discloses

- **On-device behaviour** — unit-level only; nothing exercised against a running backend or a real
  Room stream. `main` is under an active promotion hold.
- **Real-world firing rate** — requires counting backslash-followed-by-`n` in stored transcripts via
  `llm_audit` on melehost, unreachable from a pure-editor Mac. Neither the worker, the Architect, nor
  I have measured how often this fired. The trigger is rare in equity prose (file paths, regexes, an
  agent explaining what `\n` means) but **silent** when it fires, and it has been shipping on all
  three surfaces.
- The worker pushed `lane/DEF114.coder.mobile` to origin; `origin/main` untouched. Consistent with
  established practice here (CR049, CR069-BE, DEF094, DEF098, DEF112 are all on origin); recorded
  because no assign explicitly authorises a push.

## Findings

1. **MINOR** — D3's per-chunk-escape invariant is correct at all four sender sites today but pinned
   by no test; a future streaming escape would silently reinstate the corruption on all three
   surfaces. The guard belongs on the backend, which D2 scoped out — **a new item, not a round-2
   fix.**

## Verdict

**VERDICT: COMPLETE (round 1)** — zero BLOCKER, zero MAJOR.

The fix is correct and I could not break it. The single left-to-right scan round-trips all 23,906
cases I threw at it, both claimed mutations reproduce exactly, D1 and D2 hold with no streamed
surface missed, and `flutter analyze` — which nobody had run — is clean on every touched file.

The pre-lane re-grade deserves the credit here: measuring that *both* decode orders are wrong is
what stopped this shipping as a test that enshrined the bug, and my exhaustive sweep confirms that
call independently.
