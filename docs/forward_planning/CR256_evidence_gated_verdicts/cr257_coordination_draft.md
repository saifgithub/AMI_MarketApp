# CR257 coordination draft — objections question set (for Saiful to send)

**Purpose:** agree the Jev question set CR256's card pilot needs, without
freezing anything CR257 depends on.

## Context (one paragraph)

CR256 (evidence-gated verdicts) is at Step 0 done / M7 done. The card pilot
(desk CLAIMS cards + OBJECTIONS blocks, spec Layer 1) needs Jev to audit two
new artifacts that today's V1 four questions don't cover: (1) per-card support
(a CLAIM card's `support_grade` vs the payload evidence), and (2) objections
(severity vs the target claim's actual grounding). The V1 questions were
built for prose stance turns; cards/objections are structured.

## Asks (minimal, freeze-compatible)

1. **Add two questions to the shared set** (wording to CR257's taste, this is
   the shape):
   - `card_support_justified`: given the card's `claim`, its `key_numbers`,
     and the payload — is the desk's self-`support_grade` (well/partial/
     unsupported) justified?
   - `objection_severity_fair`: given the objection's `target_claim` and
     `severity`, does the payload actually support an objection of that
     severity against that claim?
2. **Reuse verbatim:** card self-grades reuse the Jev rubric wording from
   `jev_score_runs.py` (spec Layer 1 already requires this) — so
   `card_support_justified` is a self-grade-vs-Judge comparison on one scale.
3. **No change to existing questions** — the V1 four stay frozen for prose
   turns; the two additions apply to card/objection records only (records
   carry `flow`/`artifact_type` so scoring routes by shape).
4. **Harness:** scoring lives in `jev_score_runs.py` (--agents flag already
   landed for targeted passes); the pilot adds a card parser + question
   routing, harness-side only.

## What CR256 brings CR257 in return

- M7 fix (committed `bbd525d1`): the consolidated risk_officer turn is now
  Jev-visible — a new auditable surface for CR257's label work.
- The shared evaluation harness decision (Saiful 2026-10-13) — CR256's
  evidence_bar.py + the arms' Jev outputs are shaped for cross-CR reuse.
