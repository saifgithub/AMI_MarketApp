# DEF127 round 1 — audit run report

- ITEM: DEF127 · ROUND AUDITED: 1 · VERDICT: COMPLETE
- Audited SHA: `f644b5c` (lane tip = fix `8199f63` + merge `bdbd110` + SUBMITTED docs), scratch worktree `.claude/worktrees/audit-DEF127/`, never the shared tree.
- Auditor: Kimi session, track U.

## What was verified, and how

| Claim | Auditor reproduction | Result |
|---|---|---|
| Full suite 1438 passed (~206s) | `backend/.venv/bin/python -m pytest tests/unit/ -q` from worktree `backend/` | **1438 passed in 207.00s** — exact match (baseline 1424 + 14 new) |
| All 20 emission sites route through framers | grep + read of `brief.py:118,123,125`, `one_on_one.py:116,119,145`, `room.py:218-281` (14 sites) | CONFIRMED — 20 sites counted; only remaining `data:` literals under `app/` are docstrings and `llm_gateway.py`'s upstream *parser* |
| Escape chain inverse of shipped client decoder | Python `unescape` in the guard test vs `mobile/lib/services/api/api_client.dart:113-135` | CONFIRMED line-by-line — same single-pass scanner, same 3 arms (`\\`, `\n`, other→keep both). Transcription is exact today; it remains a transcription (architect's own caveat), not a cross-language test |
| M2: brief.py error site → interpolation | applied, ran guard file | RED — **3 failed** (static + both behavioural), matches |
| M4: `escape_sse_text` neutered | applied, ran guard file | RED — **7 failed**, static layer green by design, matches |
| Register flips | `DEF127.row.md` → `\| fixed \|`, `DEF139.row.md` → open, `def_list.md` regenerated | CONFIRMED |
| Residual diff empty after mutations | `git status --porcelain` after each restore | EMPTY |

## Blind adversarial probe — M6 (the one the architect invited)

Attack surface #1: the static guard inspects `yield` expressions only. Built a
plausible sender in `room.py` — frame constructed into a local, yielded bare:

```python
frame = f"event: error\ndata: {ev.text or 'unknown'}\n\n"
yield frame
```

Ran `test_def127_sse_framing_invariant.py` + `test_room_runner.py`: **116
passed — fully green.** The bypass is real, not theoretical.

**Auditor pin shipped:** `orchestration/audit/regression/test_def127_sse_frame_literal_pin.py`
— flags any non-docstring string literal under `app/` holding a newline AND a
field marker (`data:`/`event:`), position-independent, with a non-vacuity
companion. Verified three ways:

- RED with M6 in place (1 failed, 1 passed)
- PASS at clean `f644b5c` (2 passed)
- RED at pre-fix `8199f63^` (the three original interpolated senders)

With the pin the invariant holds against every natural construction shape.
Graded MINOR (guard breadth, zero live violations — grep + AST both clean),
closed by the pin in this run rather than bounced, per auditor-pin precedent
(CR054-GUARD, CR077).

## Other invited attack surfaces

- **`sse_json` refusal (#2):** `json.dumps` and pydantic v2 `model_dump_json`
  both escape control characters; the raise is unreachable defensive code, loud
  per CR040. No finding.
- **M4 static-green (#4):** reproduced — design, not gap; layer 3 catches what
  layer 1 cannot.

## OUT-OF-SCOPE (recorded, not scored)

- `escape_sse_text` escapes `\n` but not `\r`; `sse_json` rejects both. A raw CR
  in a text payload reaches the wire and would split a spec-compliant parser
  (CR is a line terminator). Forced by the shipped `0.1.0+56` decoder, which
  has no `\r` arm — pre-existing wire-format limitation, not caused by this
  item. Architect may mint if it wants it tracked.
- Doc-numbering anomaly found earlier this session (not this lane):
  `docs/initial_specs/08_tech/failure_patterns.md` has **two sections headed
  P6**, throwing P7–P9 numbering off. Editorial; architect mints the ID.

## DoD

Table present, dispositions spot-checked: 20 sites (counted), 1438 (reproduced),
register flips (verified), commit tag `8199f63` (verified), the `cr_list.md`
regeneration excursion disclosed and docs-only (`4526440`). Waiver of 2026-07-28
not needed — table rendered.
