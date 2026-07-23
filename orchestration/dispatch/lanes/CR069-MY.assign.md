<!-- dispatch assign lane — Architect-owned. CR052. -->
# CR069-MY — assign (Phase 2: Malaysia via the SC Shariah Advisory Council list)

KIND: code
INSTANCE: coder.api
ACCEPTANCE: docs/forward_planning/CR069_sharia_compliance_indicator/CR069_sharia_compliance_indicator.md (§Phase 2, §Design constraints 1-3)
DEPENDS-ON: CR069-BE — reuses its three-state resolver and its staleness machinery.
GATE: independent    <!-- recorded upfront at decomposition. Same class as CR069-BE: a user-facing observance verdict, in a second jurisdiction, from an authority we cannot re-derive. -->
HOT-FILES: backend/app/agents/safety_floor.py · backend/app/core/config.py

**STATUS: BLOCKED — not assigned. Two things must resolve first, and neither is a coder's call.**

| Blocker | Who |
|---|---|
| **A PDF-parsing dependency.** The SC list is PDF-only — no CSV, no API, no machine-readable feed (verified: `https://www.sc.com.my/api/documentms/download.ashx?id=<doc-id>` → HTTP 200, 533 KB, `application/pdf`). The stack is intentionally lean; a new dependency gets flagged before it is added, not after. | Saiful |
| **Market scope.** Locked decision: **US equities at MVP**, GCC/Tadawul + Bursa later (`CLAUDE.md` § Decision pointers). Phase 2 ships a Malaysian screen into a product that does not trade Malaysian equities. Either the locked decision moves or this waits for it. | Saiful |

**Written now, deliberately, and left unassigned.** The protocol requires every chunk be written down
before any is dispatched — that is the only way to check the decomposition is complete, and it is
what the CR-level audit diffs against the CR document. A chunk nobody wrote down is a hole the
terminal audit cannot catch. This one is a real part of CR069's scope; it is blocked, not absent.

## When it unblocks

- Parse the SC PDF into a ticker set **versioned by its effective date**. Two-tier screen
  (business-activity benchmarks + financial-ratio benchmarks), updated **every May and November**;
  latest effective 28 Nov 2025.
- A twice-yearly snapshot needs an **explicit staleness guard** — past the rebalance window the
  Malaysian screen pauses loudly, exactly as SPUS does. A stale religious verdict presented as
  current is the failure this whole CR exists to stop.
- The standard is **SC/SAC**, not AAOIFI. It is a different authority with different thresholds, so
  it is a **separate** named standard in the copy and the verdict — never merged with the AAOIFI set
  into one "halal" universe. §3a's lesson applies across jurisdictions as much as within one.
- Do not compute or adjust any ratio yourself. Read the published list.

<!-- No ASSIGNED line — renders UNASSIGNED (Architect-actionable) by design, so the blocked state
stays visible on the board rather than living only in this file. -->
DISPATCH: OPEN
