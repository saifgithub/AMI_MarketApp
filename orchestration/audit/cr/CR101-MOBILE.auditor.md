<!-- auditor lane — track U (Kimi). CR052 / orchestration/audit/PROTOCOL.md. -->
# CR101-MOBILE — auditor

VERDICT: COMPLETE (round 1)

Audited `lane/CR101-MOBILE.coder.mobile` @ `34faaab1` in scratch worktree
`.claude/worktrees/audit-CR101-MOBILE` (never `main`, never the builder's
tree). SCOPE: `chunk` — shorter evidence list, no DoD bounce (DoD present
anyway). Tiered audit policy: targeted tests + registers + blind mutation up
front, full flutter suite + analyze backgrounded during the read — both
completed green before this verdict was written.

---

## Round 1

### The three judgment calls — weighed, all upheld

**JC1 (unset BE1 caps render "Following your risk profile", not "OFF" —
deviating from the assign's literal "None means OFF for all seven").** The
deviation is correct and I verified its premise independently: CR101-BE1's
own audit (mine, `9608d56d`, round 1) upheld exactly that measurement — unset
`sector_cap_pct`/`single_name_cap_pct` fall back to a binding server-side
preset (`risk_tier_cap`/`resolved_sector_cap_pct`), and no endpoint exposes
the resolved number. Rendering "OFF" there would be the CR046 lie. The
screen names the mechanism and fabricates no number; the backend
resolved-value addition is named for the architect to mint rather than
scope-creeped into a mobile lane. **My blind mutation** — forcing the
off-chip to render "OFF" for preset-linked fields too — went exactly 1 RED
(`risk_limits_section_test.dart::acceptance 1: unset renders OFF /
following-profile`), so the honest split is pinned behaviourally, not just
asserted in comments. Reverted, `git status` clean, re-green.

**JC2 (retro-tightening disclosure fires immediately after save, not
before).** Premise verified against the shipped backend: BL12's audit
endpoint (`backend/app/api/mandate.py:270-299` on current `main`) reads the
*persisted* mandate via `store.get_or_default` — no candidate-mandate
preview endpoint exists, and a client-side reimplementation would be the
client-enforcement defect. Post-save audit + dialog is the honest achievable
reading. Implementation checked: `_save()` fires the audit only when the
touched fields include `max_open_positions`/`max_open_risk_pct` (the only two
with a portfolio-state dimension — consistent with CR101-BE2's own judgment
call 3), and the dialog renders flag-and-block language with no liquidation
text (acceptance-5 test asserts `liquidat*` absent).

**JC3 (L1 writes only the two BE1 caps).** Correct read of the backend:
no preset relationship exists for the five BE2 fields anywhere server-side,
so inventing client-side presets would be the CR046 defect. Verified in
code: `_onRiskScoreChanged` sets `risk_score` and nulls exactly the two BE1
pending keys (`settings_screen.dart:79-88`); the five BE2 fields are
untouched by L1.

### Source read — the rest of the diff

- `risk_limits_section.dart` (new, 465 lines): all seven fields keyed off
  `mandate.<field>` or pending PATCH values; no numeric cap literal anywhere
  (the `100` in `classifyLimitEdit` is the mathematical percent ceiling, a
  unit boundary, not a preset — commented as such). Directionality table
  (`higherIsLooser`) is config, not constants. Cooldown's inverted direction
  (shorter = looser) is correct and test-pinned.
- `mandate.dart`: `HoldingsAuditResult.fromJson` matches the backend's
  `HoldingsAuditResult` shape (verified against `safety_floor.py`'s pydantic
  model — snake_case keys, violations carry `ticker`); the seven new
  `UserMandate` fields parse nullable-correctly.
- `api_client.dart`: `auditMandateHoldings` hits `GET /v1/mandate/{id}/audit`
  — the endpoint exists on current `main` (BE2 r2 integrated, confirmed via
  `git branch -r --contains 095948ed` → `origin/main`).
- `settings_screen.dart`: pending-map semantics (containsKey = touched, value
  possibly null → explicit-null PATCH to unset — matches the server's
  `"key" in updates` contract BE2 shipped); pending cleared after save so the
  next build reads the server value (acceptance 2's round-trip, tested with a
  server that returns a *different* value than sent).

### Measured (all reproduced by me, worktree @ `34faaab1`)

| Check | Builder claimed | Auditor reproduced |
|---|---|---|
| `flutter test -r compact` | 330 passed (baseline 309) | **330 passed**, "All tests passed!", background during read |
| `flutter analyze --no-fatal-infos` | exit 0, 5 pre-existing infos | **exit 0, 5 issues**, 4.8s |
| Targeted: the 2 new test files | acceptance matrix ✅ | **21 passed** |
| `gen_registers.py verify all` | untouched | DEF 192 / CR 124 rows, both OK |
| Mutation: off-label lie (auditor's own) | n/a | exactly **1 RED** (acceptance 1), reverted clean |

Builder's own two-mutation matrix (both RED) accepted on the strength of my
independent mutation hitting the riskiest dimension (the CR046 rendering
split) plus the acceptance-6 source-literal guard being itself present and
green.

### MINORs (recorded, not blocking)

- m1. The retro-tightening audit call is wrapped in a bare `catch (_)` — a
  failed audit read after a tightening save goes undisclosed silently
  (`settings_screen.dart:126-132`). Comment calls it best-effort, which is
  the right priority (never misrepresent a succeeded save), but a quiet
  "couldn't check — verify in Portfolio" snackbar would close the gap.
  Architect's call; not a MAJOR because the save itself is honestly
  confirmed and the breach flags surface on the next audit read.
- m2. NEEDS-DEVICE-CHECK: number-pad keyboard, `Wrap` layout at real device
  widths, and AR/MS at real translated string lengths (current AR/MS are the
  flagged EN placeholders) are untested beyond the 390×2000 widget surface —
  builder disclosed; recorded per protocol.

### OUT-OF-SCOPE (architect mints, per protocol)

- No backend endpoint exposes the resolved BE1 preset value when unset —
  the builder's "Found, NOT fixed". Concur: mint a follow-up so this screen
  can eventually show the enforced number instead of naming the mechanism.
