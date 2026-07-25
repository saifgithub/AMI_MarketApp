<!--
Auditor run report — run-46 (2026-07-25, session auditor.core/track U). Round-1 audit of
CR056. Audited SHA 0b9d5b0 on lane/CR056.coder.api. Verdict COMPLETE. Owner: AUDITOR.
-->

# run-46 (round 1) — CR056 universal grounding directive → COMPLETE

- **Auditor session:** auditor.core (track U), 2026-07-25. First lane of the day, after ~9 quiet
  hours since CR087-BE.
- **Audited SHA:** `0b9d5b0c3c310cb30becb5ef2e3c49bc9313ad1e`, tip of `lane/CR056.coder.api`
  (branched from merge-base `e628cac` = main tip, zero divergence). Audited in a fresh isolated
  worktree `.claude/worktrees/audit-CR056/`.
- **The item:** prepend a single grounding directive ("use only explicitly-provided facts, never
  assume/infer/invent/recall absent data") to every LLM call, at the `LLMGateway.stream_chat`
  chokepoint — defence-in-depth for the SCHD phantom-holdings class, complementing CR055's
  structural fix.
- **Gate:** independent — blast radius is every LLM call in the system (12 agents + Concierge +
  PM reformatter + mock routing), so a wording or placement slip is system-wide.
- **Verdict:** COMPLETE (round 1) — zero BLOCKER/MAJOR/MINOR.

## Verification

### Reproduced independently

| Check | Result |
|---|---|
| Scope | 2 files, +292/−2. Zero touches to CR055's files (`agent_prompts.py`/`room_prompts.py`). |
| Full suite | 1130 passed (1116 baseline + 14 new). |
| Single chokepoint | Traced all 9 real `.stream_chat(` call sites in the codebase to confirm each resolves to a `LLMGateway`-typed variable — no path bypasses the patched method. |

### Five mutation-tested claims

Rather than read the 14 new tests and trust them, mutated the real source five separate times and
confirmed each targeted test (and often several cascading ones) failed for the exact claimed
reason, then reverted every time:

1. Disabled the injection entirely → all 4 flow types (agent/Concierge/reformatter/PM) went RED
   simultaneously, proving Concierge and reformatter genuinely depend on the gateway-level
   placement, not something inherited from `build_agent_prompt`.
2. Added an agent-id token ("trader") to the directive → both the static token-check and the live
   mock-routing test failed, and the routing failure **cascaded** to mis-route unrelated agents too
   — a concrete demonstration of the exact fragility the architect warned about.
3. Switched prepend to append → both PM-floor-last tests failed (plus 5 cascading failures),
   confirming an append-based implementation really would break the safety-floor-last invariant.
4. Removed the idempotency sentinel guard → both double-injection tests failed with a visibly
   doubled directive in the prompt.
5. Made the audit record diverge from what the provider actually saw → the
   `test_directive_reaches_provider_and_audit` equality assertion caught it, confirming that test
   verifies genuine parity, not just provider-side presence.

Final clean full-suite re-run after all reverts: 1130/1130.

### Honest-ceiling / no-regression check

Confirmed by scope diff alone (zero touches to `agent_prompts.py`/`room_prompts.py`) that CR055's
structural guard cannot have been weakened — not inferred from the coder's claim.

### Observation, not a finding

The CR056 spec's acceptance #4 (a "measured, not assumed" live SCHD-style repro reporting the
directive's practical effect) is absent from both hand-offs and the architect's adversarial-focus
list — consistent with the registry's `in_progress` status, since it needs a promoted Alpha
instance, not a worktree. Noted for the record so this lane's COMPLETE isn't mistaken for the full
CR056 spec being closed; not attempted myself (a model-behaviour research question, not a
code-verification task) and not a defect in this lane's own delivery.

## Findings

None.

## Verdict

**VERDICT: COMPLETE (round 1)**
